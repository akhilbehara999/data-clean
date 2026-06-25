"""Shared utilities for the v2 analyst agent."""

import os
import re
import pandas as pd


# ── Column type detection ────────────────────────────────────────────────────

def detect_column_types(df: pd.DataFrame) -> dict[str, list[str]]:
    """Classify every column as numeric, categorical, or datetime."""
    numeric: list[str] = []
    categorical: list[str] = []
    datetime_cols: list[str] = []

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric.append(col)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            datetime_cols.append(col)
        else:
            # Attempt datetime parse on object columns
            try:
                sample = df[col].dropna().head(50)
                if len(sample) > 0:
                    pd.to_datetime(sample, format="mixed")
                    datetime_cols.append(col)
                else:
                    categorical.append(col)
            except Exception:
                categorical.append(col)

    return {"numeric": numeric, "categorical": categorical, "datetime": datetime_cols}


# ── Geographic column detection ──────────────────────────────────────────────

GEO_KEYWORDS = [
    "city", "state", "region", "country", "pincode", "zip",
    "postal", "location", "address", "area", "district",
    "province", "territory", "town", "village",
]


def detect_geo_columns(df: pd.DataFrame) -> list[str]:
    """Return columns whose names suggest geographic data."""
    found: list[str] = []
    for col in df.columns:
        if any(kw in col.lower() for kw in GEO_KEYWORDS):
            found.append(col)
    return found


# ── Number & size formatting ─────────────────────────────────────────────────

def fmt_num(n, decimals: int = 2) -> str:
    """Format a number with commas."""
    if pd.isna(n):
        return "N/A"
    if isinstance(n, float):
        return f"{n:,.{decimals}f}"
    return f"{n:,}"


def fmt_pct(n) -> str:
    """Format as percentage."""
    if pd.isna(n):
        return "N/A"
    return f"{n:.1f}%"


def fmt_size(byte_count: int) -> str:
    """Human-readable file size."""
    if byte_count >= 1_048_576:
        return f"{byte_count / 1_048_576:.1f} MB"
    if byte_count >= 1_024:
        return f"{byte_count / 1_024:.1f} KB"
    return f"{byte_count} bytes"


def fmt_delta(val) -> str:
    """Format a delta value with +/- prefix and arrow."""
    if pd.isna(val):
        return "—"
    sign = "+" if val > 0 else ""
    arrow = "↑" if val > 0 else ("↓" if val < 0 else "—")
    return f"{sign}{fmt_num(val)} {arrow}"


def fmt_pct_delta(val) -> str:
    """Format a percentage delta with arrow."""
    if pd.isna(val) or val == 0:
        return "—"
    sign = "+" if val > 0 else ""
    arrow = "↑" if val > 0 else "↓"
    return f"{sign}{val:.1f}% {arrow}"


# ── Safe input helpers ───────────────────────────────────────────────────────

try:
    from prompt_toolkit.completion import Completer, Completion

    class CommandCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            # Canonical commands only — aliases omitted to avoid duplicate clutter
            commands = {
                "eda":           "Run Exploratory Data Analysis & profiling",
                "relationships": "Analyze correlation & potential join keys",
                "geographic":    "Break down city, state, or region fields",
                "pivot":         "Build custom group-by & aggregation tables",
                "comparative":   "Compare segments, files, or time periods",
                "insights":      "Detect statistical patterns & anomalies",
                "simulate":      "What-if simulation engine",
                "specialist":    "Domain-specific analysis (fraud/marketing/inventory)",
                "explain":       "Show methodology trace for a calculation",
                "rules":         "List or remove custom self-healing rules",
                "templates":     "List or delete saved report templates",
                "files":         "Return to the browser file ingestion interface",
                "report":        "Export comprehensive HTML/MD reports",
                "export":        "Save current cleaned dataset to disk",
                "reclean":       "Return to the interactive clean phase",
                "settings":      "Configure API keys, provider, and model",
                "menu":          "Show full grouped command menu",
                "help":          "Get detailed command documentation",
                "exit":          "Exit from the DataSanitizer environment",
            }
            if not text:
                for cmd, desc in commands.items():
                    yield Completion(f"/{cmd}", start_position=0, display_meta=desc)
                return

            if text.startswith("/"):
                query = text[1:].lower()
                for cmd, desc in commands.items():
                    if cmd.startswith(query):
                        yield Completion(f"/{cmd}", start_position=-len(text), display_meta=desc)
            else:
                query = text.lower()
                for cmd, desc in commands.items():
                    if cmd.startswith(query):
                        yield Completion(cmd, start_position=-len(text), display_meta=desc)
                        yield Completion(f"/{cmd}", start_position=-len(text), display_meta=desc)

    command_completer = CommandCompleter()
except ImportError:
    command_completer = None


def safe_input(console, prompt: str, completer=None) -> str:
    """Get input, returning empty string on interrupt, with optional dropdown autocompletion."""
    try:
        if completer is not None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.styles import Style
                
                # Strip Rich bracket markup for prompt_toolkit prompt compatibility
                clean_prompt = re.sub(r'\[\/?[a-zA-Z0-9 _#]+\]', '', prompt)
                
                style = Style.from_dict({
                    "completion-menu.completion": "bg:#2c2c3e #a0a5c0",
                    "completion-menu.completion.current": "bg:#9d4edd #f8f9fa bold",
                    "completion-menu.meta.completion": "bg:#2c2c3e #606080",
                    "completion-menu.meta.completion.current": "bg:#9d4edd #f8f9fa",
                    "prompt": "#80deea bold",
                    "bottom-toolbar": "bg:#1e1e2f #a0a5c0",
                    "bottom-toolbar.badge": "bg:#00fa9a #1e1e2f bold",
                })
                
                def get_toolbar():
                    return [
                        ("", "  /help for command details · /exit to exit                             "),
                        ("class:badge", " ● active "),
                        ("", " · /reclean"),
                    ]
                
                try:
                    session = PromptSession()
                    return session.prompt(
                        clean_prompt,
                        completer=completer,
                        complete_while_typing=True,
                        style=style,
                        bottom_toolbar=get_toolbar,
                    ).strip()
                except Exception:
                    pass
            except ImportError:
                pass
        return console.input(prompt).strip()

    except (KeyboardInterrupt, EOFError):
        return ""




def numbered_choice(console, prompt: str, options: list[str],
                    allow_skip: bool = False) -> int | None:
    """Show numbered list, return 0-based index or None if skipped."""
    for i, opt in enumerate(options, 1):
        console.print(f"    [{i}] {opt}")
    if allow_skip:
        console.print("    [Enter] Skip")

    while True:
        val = safe_input(console, prompt)
        if allow_skip and val == "":
            return None
        if val.isdigit() and 1 <= int(val) <= len(options):
            return int(val) - 1
        console.print(f"[dim]Please enter a number between 1 and {len(options)}.[/dim]")


# ── Output path helper ───────────────────────────────────────────────────────

def ensure_output_dir() -> str:
    """Ensure the output directory exists and return its path."""
    out = os.path.join(os.getcwd(), "output")
    os.makedirs(out, exist_ok=True)
    return out


def get_clean_path_base(filepath: str) -> str:
    """Get a clean base name preserving subdirectory structures and formats."""
    if not filepath:
        return "export"
    try:
        rel = os.path.relpath(filepath)
        if rel.startswith(".."):
            # Outside CWD, use parent folder + filename
            parent = os.path.basename(os.path.dirname(os.path.abspath(filepath)))
            base = os.path.basename(filepath)
            if parent:
                rel = os.path.join(parent, base)
            else:
                rel = base
    except Exception:
        rel = os.path.basename(filepath)

    # Split the extension so we can include it in the base name
    # e.g., data/sample_data.csv -> data_sample_data_csv
    name, ext = os.path.splitext(rel)
    ext_clean = ext.strip('.').lower()
    
    # Replace non-alphanumeric characters with underscores
    name_clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    
    if ext_clean:
        name_clean = f"{name_clean}_{ext_clean}"
        
    # Collapse multiple underscores
    name_clean = re.sub(r'_{2,}', '_', name_clean)
    name_clean = name_clean.strip('_')
    return name_clean


# ── Result-aware next-step suggestion (Phase 4) ──────────────────────────────

def suggest_next(results: dict, command: str) -> str:
    """Return a context-aware suggestion based on the results of a command."""
    GENERIC = "[bold bright_cyan]What would you like to do next?[/bold bright_cyan]"

    if command == "eda":
        for p in (results or {}).get("numeric", []):
            if p.get("skew_label") in ("right-skewed", "left-skewed"):
                col = p["column"]
                return (
                    f"[bold bright_cyan]Try [bold purple]/insights[/bold purple] "
                    f"to see if the skew in '[italic]{col}[/italic]' is meaningful.[/bold bright_cyan]"
                )
        corrs = (results or {}).get("correlations", [])
        if corrs:
            return (
                "[bold bright_cyan]Correlations found — try "
                "[bold purple]/relationships[/bold purple] for a deeper scan.[/bold bright_cyan]"
            )
        return GENERIC

    if command == "geographic":
        breakdown = (results or {}).get("breakdown", [])
        if len(breakdown) >= 2:
            r1 = breakdown[0]["region"]
            r2 = breakdown[1]["region"]
            return (
                f"[bold bright_cyan]Try [bold purple]/comparative[/bold purple] "
                f"to compare [italic]{r1}[/italic] vs [italic]{r2}[/italic] directly.[/bold bright_cyan]"
            )
        return GENERIC

    if command == "relationships":
        corrs = (results or {}).get("correlations", [])
        if corrs:
            pair = corrs[0]
            return (
                f"[bold bright_cyan]Try [bold purple]/pivot[/bold purple] "
                f"on '[italic]{pair['col_a']}[/italic]' × '[italic]{pair['col_b']}[/italic]' "
                f"to explore the correlation.[/bold bright_cyan]"
            )
        return GENERIC

    if command == "insights":
        insights = (results or {}).get("insights", [])
        if insights:
            title = insights[0]["title"]
            return (
                f"[bold bright_cyan]Ask about '[italic]{title}[/italic]' "
                f"to get more detail, or run [bold purple]/comparative[/bold purple] "
                f"on the segments mentioned.[/bold bright_cyan]"
            )
        return GENERIC

    if command == "pivot":
        return (
            "[bold bright_cyan]Try [bold purple]/comparative[/bold purple] "
            "to compare segments of the pivot result.[/bold bright_cyan]"
        )

    if command == "comparative":
        return (
            "[bold bright_cyan]Run [bold purple]/insights[/bold purple] "
            "to check if these differences are statistically meaningful.[/bold bright_cyan]"
        )

    return GENERIC


# ── Checkbox-style multi-select (Phase 6) ────────────────────────────────────

def multi_select(console, prompt: str, options: list[str],
                 preselected: list[int] = None) -> list[int]:
    """
    Show a checkbox-style selection dialog. Returns list of selected 0-based indices.
    Falls back to comma-separated numeric input if prompt_toolkit unavailable.
    If user presses Enter with no input, returns all indices (select all).
    """
    try:
        from prompt_toolkit.shortcuts import checkboxlist_dialog
        from prompt_toolkit.styles import Style

        style = Style.from_dict({
            "dialog":              "bg:#18182c",
            "dialog.body":         "bg:#18182c #f8f9fa",
            "dialog frame.label":  "bg:#9d4edd #f8f9fa bold",
            "checkbox-list":       "bg:#18182c",
            "checkbox":            "#9d4edd",
            "checkbox-selected":   "bg:#9d4edd #f8f9fa bold",
            "button":              "bg:#2c2c3e #a0a5c0",
            "button.focused":      "bg:#9d4edd #f8f9fa bold",
        })

        values = [(i, opt) for i, opt in enumerate(options)]
        default_values = preselected if preselected is not None else list(range(len(options)))

        result = checkboxlist_dialog(
            title=prompt,
            text="Space to toggle, Enter to confirm, Tab to move focus:",
            values=values,
            default_values=default_values,
            style=style,
        ).run()

        if result is None:
            # User cancelled — return all
            return list(range(len(options)))
        return list(result)

    except Exception:
        # Fallback: comma-separated numeric input
        console.print()
        console.print(f"  [bold]{prompt}[/bold]")
        for i, opt in enumerate(options, 1):
            console.print(f"    [{i}] {opt}")
        console.print("    [Enter] Select all")
        raw = safe_input(console, "  [bold bright_cyan]Enter numbers (comma-separated): [/bold bright_cyan]")
        if not raw.strip():
            return list(range(len(options)))
        selected = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(options):
                selected.append(int(part) - 1)
        return selected if selected else list(range(len(options)))
