# -*- coding: utf-8 -*-
"""DataAnalystAgent v3 — conversational AI analyst with LLM integration."""

from __future__ import annotations

import os
import sys

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

from .llm import detect_provider, get_model_label, call_llm, MODEL_REGISTRY, get_api_key_for_provider, is_key_configured, fetch_available_models
from .memory import Memory
from .intent_parser import parse_intent, Intent
from .narrator import (
    narrate_eda, narrate_relationships, narrate_insights,
    narrate_column_detail, narrate_geographic,
    narrate_general_greeting, narrate_ambiguous,
)
from .code_exporter import get_code_for_operation
from .session_bridge import save_and_switch_to_v2, autosave

console = Console(force_terminal=True)


# ── System prompt builder ────────────────────────────────────────────────────

def _build_system_prompt(session: dict, df: pd.DataFrame) -> str:
    from v1 import session_manager
    active_ds = session_manager.get_active_dataset(session)
    if not active_ds:
        active_ds = session
    file_info = active_ds.get("file", {})
    col_types = active_ds.get("column_types", {})
    v1 = active_ds.get("v1_summary", {})
    v2 = active_ds.get("v2_summary", {})

    cols = file_info.get("columns", [])
    if len(cols) > 15:
        cols_str = f"{cols[:15]} ... (+{len(cols) - 15} more)"
    else:
        cols_str = str(cols)

    actions_log = v1.get("actions_log", [])
    issues_resolved = v1.get("issues_resolved", 0)
    v1_summary_line = f"V1 actions applied: {len(actions_log)} actions resolved {issues_resolved} issues."

    v2_available = []
    for key in ["eda_results", "relationships_results", "insights_triggered",
                 "pivot_results", "comparison_results", "geo_results"]:
        if v2.get(key) is not None:
            v2_available.append(key.replace("_results", "").replace("_triggered", ""))

    v2_str = ", ".join(v2_available) if v2_available else "none yet"

    return f"""You are DataAnalystAgent v3, an AI analyst in a terminal tool.

DATASET CONTEXT:
  File: {file_info.get('cleaned', 'unknown')}
  Shape: {file_info.get('cleaned_shape', [0,0])}
  Columns: {cols_str}
  Column types: {col_types}

V1 CLEANING SUMMARY:
  {v1_summary_line}

V2 ANALYSES AVAILABLE: {v2_str}

RULES:
- Only reference data that exists in the context above.
- Never fabricate values, columns, or statistics.
- For data questions where a [LOCAL ANALYSIS RESULT] is NOT yet provided in the prompt, respond with a JSON function call like:
  {{"function": "eda"}} or {{"function": "insights"}}
  The system will execute it and return results for you to narrate.
- If a [LOCAL ANALYSIS RESULT] IS already provided in the prompt, DO NOT output a JSON function call (e.g. {{"function": "eda"}}). Instead, explain the results directly in plain English markdown.
- For explanation/report/code requests, respond directly.
- Keep responses under 8 lines unless "full"/"detailed" requested.
- End data-query responses with one suggested follow-up.
- Be concise, direct, and helpful. Use markdown formatting."""


# ─────────────────────────────────────────────────────────────────────────────
#  Agent class
# ─────────────────────────────────────────────────────────────────────────────

class DataAnalystAgentV3:
    """Conversational AI data analyst backed by LLM + V2 analysis engines."""

    def __init__(self, session_dict: dict):
        self.console = console

        from v1 import session_manager
        active_ds = session_manager.get_active_dataset(session_dict)
        if not active_ds:
            active_ds = session_dict
            
        file_info = active_ds.get("file", {})
        self.session_dict = session_dict

        # Load dataframe
        if "df" in session_dict:
            self.df = session_dict["df"]
        else:
            pkl_path = file_info.get("dataframe_pickle")
            if pkl_path and os.path.exists(pkl_path):
                self.df = pd.read_pickle(pkl_path)
            elif file_info.get("cleaned") and os.path.exists(file_info.get("cleaned")):
                cleaned_path = file_info.get("cleaned")
                if cleaned_path.endswith((".xlsx", ".xls")):
                    self.df = pd.read_excel(cleaned_path, engine="openpyxl")
                elif cleaned_path.endswith(".tsv"):
                    self.df = pd.read_csv(cleaned_path, sep="\t")
                else:
                    self.df = pd.read_csv(cleaned_path)
            else:
                self.df = pd.DataFrame()
            session_dict["df"] = self.df


        # File metadata
        self.filename = os.path.basename(file_info.get("original", ""))
        self.cleaned_path = file_info.get("cleaned", "")
        self.original_shape = tuple(file_info.get("original_shape", (0, 0)))
        self.cleaned_shape = tuple(file_info.get("cleaned_shape", (0, 0)))
        self.columns = list(file_info.get("columns", []))

        # Column types
        ct = active_ds.get("column_types", {})
        self.col_types = {
            "numeric": ct.get("numeric", []),
            "categorical": ct.get("categorical", []),
            "datetime": ct.get("datetime", []),
            "identifier": ct.get("identifier", []),
            "text": ct.get("text", []),
        }

        # V1 / V2 summaries
        self.v1_summary = active_ds.get("v1_summary", {})
        self.v2_summary = active_ds.get("v2_summary", {})

        # V2 results store — mirrors v2/agent.py's results dict
        self.results = {
            "eda": self.v2_summary.get("eda_results"),
            "relationships": self.v2_summary.get("relationships_results"),
            "geographic": self.v2_summary.get("geo_results"),
            "pivot": self.v2_summary.get("pivot_results"),
            "comparative": self.v2_summary.get("comparison_results"),
            "insights": self.v2_summary.get("insights_triggered"),
        }

        # Memory
        self.memory = Memory(session_dict)

        # LLM provider & model selection
        self.provider = session_dict.get("active_provider")
        self.model_id = session_dict.get("active_model_id")

        # Fall back to defaults if not set/detected
        default_prov, default_key = detect_provider()
        if not self.provider or not get_api_key_for_provider(self.provider):
            self.provider = default_prov
            if self.provider:
                self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")
        
        if self.provider and not self.model_id:
            self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")

        self.api_key = get_api_key_for_provider(self.provider) if self.provider else None
        self.model_label = get_model_label(self.provider, self.model_id)

        # Track last operation for /export code
        self.last_operation: str | None = session_dict.get("last_operation")

        # Whether this is a /switch entry (skip suggestions)
        self._is_switch = session_dict.get("_switch_entry", False)
        if "_switch_entry" in session_dict:
            del session_dict["_switch_entry"]

    # ── Startup ──────────────────────────────────────────────────────────

    def start(self):
        """Entry point — print header, enter REPL."""
        self._print_startup()
        self._repl()

    def _no_api_key_fallback(self):
        c = self.console
        c.print()
        c.print("[bold yellow]⚠ No LLM API key found.[/bold yellow] "
                "V3 requires an API key to run.")
        c.print("  Set [bold]ANTHROPIC_API_KEY[/bold], "
                "[bold]OPENAI_API_KEY[/bold], or "
                "[bold]GEMINI_API_KEY[/bold]")
        c.print("  as an environment variable, or add it to config.json.")
        c.print()
        c.print("[dim]Returning to V2 command mode...[/dim]")
        c.print()
        save_and_switch_to_v2(self.session_dict, self.df)

    def _print_startup(self):
        c = self.console
        c.print()

        # Build analyses list
        analyses_run = self.v2_summary.get("analyses_run", [])
        analyses_str = ", ".join(analyses_run) if analyses_run else "none yet"

        issues = self.v1_summary.get("issues_resolved", 0)

        # Header box
        from rich.table import Table

        header_table = Table.grid(expand=True)
        header_table.add_column(ratio=6, justify="left")
        header_table.add_column(width=3, justify="center")
        header_table.add_column(ratio=7, justify="left")

        # Left Column content: logo, active session details (V3 style)
        left_lines = [
            " [bold white]Welcome to DataSanitizer V3![/bold white]",
            "",
            "          [bold cyan]  ▟██▙  [/bold cyan]",
            "          [bold cyan] ▟█▛▜█▙ [/bold cyan]  [bold yellow]✦[/bold yellow]",
            "          [bold cyan]▐█▛  ▜█▌[/bold cyan]",
            "          [bold cyan] ▜█▙▟█▛ [/bold cyan]",
            "          [bold cyan]  ▜██▛  [/bold cyan]",
            "",
            f" [bold dim]File:[/bold dim] [bold cyan]{self.filename}[/bold cyan]",
            f" [bold dim]Model:[/bold dim] [bold purple]{self.model_label}[/bold purple]"
        ]

        # Right Column content: tips & metrics (V3 style)
        right_lines = [
            " [bold white]Tips for getting started[/bold white]",
            " • Ask questions in plain English",
            " • Type [bold purple]/switch[/bold purple] to return to V2",
            " ────────────────────────────────────────────────",
            " [bold white]Dataset Statistics[/bold white]",
            f" • Shape: [bold dim]{self.original_shape[0]}x{self.original_shape[1]}[/bold dim] → [bold green]{self.df.shape[0]}x{self.df.shape[1]}[/bold green]",
            f" • Issues Resolved: [bold green]{issues}[/bold green]",
            f" • Analyses run in V2: [bold green]{analyses_str}[/bold green]"
        ]
        # Token budget warning
        total_chars = sum(len(m.get("content", "")) for m in self.memory._history)
        if total_chars > 60000:
            right_lines.append(
                f" [bold yellow]⚠ Token budget high: {total_chars:,} chars (>{60_000:,}) — older messages will be trimmed.[/bold yellow]"
            )

        # Combine lines
        max_len = max(len(left_lines), len(right_lines))
        for i in range(max_len):
            l_val = left_lines[i] if i < len(left_lines) else ""
            r_val = right_lines[i] if i < len(right_lines) else ""
            header_table.add_row(l_val, "│", r_val)

        panel = Panel(
            header_table,
            box=box.ROUNDED,
            border_style="dim",
            title="[bold cyan] DataSanitizer v3.0.0 [/bold cyan]",
            title_align="left"
        )
        c.print(panel)

        # Print session banner alert and inline command list
        c.print()
        c.print("  [bold cyan]▎[/bold cyan] [bold]AI Chat Mode Active[/bold] · Ask a question in plain English or type a slash command")

        # V2 reuse notice
        if analyses_run:
            run_str = ", ".join(f"[bold purple]{a}[/bold purple]" for a in analyses_run)
            c.print(f"  [bold dim]Note:[/bold dim] I can see you already ran {run_str} in V2 — I'll use those results instead of recomputing.")
            c.print()

        c.print("  [bold dim]Commands:[/bold dim] "
                "[bold purple]/switch[/bold purple] · "
                "[bold purple]/model[/bold purple] · "
                "[bold purple]/provider[/bold purple] · "
                "[bold purple]/config[/bold purple] · "
                "[bold purple]/export[/bold purple] · "
                "[bold purple]/code[/bold purple] · "
                "[bold purple]/help[/bold purple] · "
                "[bold purple]/exit[/bold purple]")
        c.print("  [dim]" + "─" * 85 + "[/dim]")

        if self.memory.history:
            c.print()
            c.print("  [bold dim]── Conversation History ───────────────────────────────────────────────────[/bold dim]")
            c.print()
            for msg in self.memory.history:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    c.print(f"[bold bright_cyan]AI Chat ❯ [/bold bright_cyan]{content}")
                elif role == "assistant":
                    c.print()
                    c.print(Markdown(content))
                    c.print()
            c.print("  [bold dim]──────────────────────────────────────────────────────────────────────────[/bold dim]")
            c.print()

        if self._is_switch:
            c.print()
            c.print("  [bold bright_cyan]Welcome back. Picking up where you left off —[/bold bright_cyan]")
            c.print("  [bold bright_cyan]what would you like to explore?[/bold bright_cyan]")
            c.print()
        c.print()

    # ── REPL ─────────────────────────────────────────────────────────────

    def _repl(self):
        from v2.utils import safe_input
        from prompt_toolkit.completion import WordCompleter

        completer = WordCompleter(
            ["/switch", "/model", "/provider", "/config", "/export", "/exit", "/quit", "/help", "/code"],
            sentence=True,
        )

        while True:
            user_input = safe_input(
                self.console,
                "[bold bright_cyan]AI Chat ❯ [/bold bright_cyan]",
                completer=completer,
            )
            if not user_input:
                continue

            cmd_cleaned = user_input.strip()
            cmd_lower = cmd_cleaned.lower()

            # Step 1 — slash commands
            if cmd_lower in ("/switch", "switch", "switch to v2", "go to v2"):
                self._do_switch()
                break
            if cmd_lower in ("/exit", "/quit", "quit", "done", "bye", "exit"):
                self._do_exit()
                break
            if cmd_lower.startswith("/model"):
                self._do_model(cmd_cleaned)
                self.console.print()
                continue
            if cmd_lower.startswith("/provider"):
                self._do_provider(cmd_cleaned)
                self.console.print()
                continue
            if cmd_lower.startswith("/config"):
                self._do_config()
                self.console.print()
                continue
            if cmd_lower in ("/export", "/code"):
                self._do_code()
                self.console.print()
                continue
            if cmd_lower in ("/help",):
                self._do_help()
                self.console.print()
                continue

            # Step 2-6 — process natural language
            self._process_query(user_input)
            self.console.print()

    # ── Command handlers ─────────────────────────────────────────────────

    def _do_switch(self):
        c = self.console
        c.print()
        c.print("[bold purple]Saving session... switching to V2 Command Mode.[/bold purple]")
        c.print()
        self.session_dict["active_version"] = "v2"
        self._sync_results_to_session()
        save_and_switch_to_v2(self.session_dict, self.df)

    def _do_exit(self):
        c = self.console
        self._sync_results_to_session()
        autosave(self.session_dict, self.df)
        c.print()
        c.print("[yellow]Session saved. Goodbye![/yellow]")
        c.print()

    def _do_code(self):
        if not self.last_operation:
            self.console.print()
            self.console.print("  ⚠️ [yellow]No analysis operation has been run in this session yet.[/yellow]")
            self.console.print("     Please ask a question or run a command first.")
            return
        code = get_code_for_operation(self.last_operation, self.filename)
        self.console.print()
        self.console.print(Markdown(code))

    def _do_help(self):
        c = self.console
        c.print()
        c.print("  [bold]V3 Commands:[/bold]")
        c.print("    [bold purple]/switch[/bold purple]    — Return to V2 command mode")
        c.print("    [bold purple]/model[/bold purple]     — Show or switch AI models (e.g. `/model 2`)")
        c.print("    [bold purple]/provider[/bold purple]  — Show or switch AI providers (e.g. `/provider gemini`)")
        c.print("    [bold purple]/config[/bold purple]    — Configure/add API keys interactively")
        c.print("    [bold purple]/export[/bold purple]    — Show pandas code for the last operation")
        c.print("    [bold purple]/exit[/bold purple]      — Save session and quit")
        c.print("    [bold purple]/help[/bold purple]      — Show this help message")
        c.print()
        c.print("  Or just ask a question in plain English!")

    def _do_model(self, user_input: str):
        c = self.console
        from rich.table import Table

        # Parse potential args
        args = user_input.strip().split()
        target = args[1] if len(args) > 1 else ""

        # Build list of all models in parallel
        models_list = []
        providers = ["gemini", "openai", "anthropic"]
        from concurrent.futures import ThreadPoolExecutor

        def fetch_models_for_provider(prov_name):
            has_key = get_api_key_for_provider(prov_name) is not None
            try:
                prov_models = fetch_available_models(prov_name)
            except Exception:
                prov_models = {}
            return prov_name, has_key, prov_models

        with c.status("  [bold dim]Querying providers for active models in parallel...[/bold dim]"):
            with ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(fetch_models_for_provider, providers))

        for prov_name, has_key, prov_models in results:
            for m_key, m_info in prov_models.items():
                is_active = (self.provider == prov_name and self.model_id == m_key)
                models_list.append({
                    "key": m_key,
                    "name": m_info["name"],
                    "provider": prov_name,
                    "has_key": has_key,
                    "is_active": is_active
                })

        # If user provided a model name/index as arg, attempt immediate switch
        if target:
            selected = None
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(models_list):
                    selected = models_list[idx]
            else:
                for m in models_list:
                    if target.lower() in m["key"].lower() or target.lower() in m["name"].lower():
                        selected = m
                        break
            
            if selected:
                if not selected["has_key"]:
                    c.print(f"  [bold red]⚠ Cannot switch to {selected['name']} because no API key is configured for {selected['provider'].capitalize()}.[/bold red]")
                    c.print(f"  [dim]Type [bold]/config[/bold] to add a key, or switch to a provider that has a key.[/dim]")
                    return
                self.provider = selected["provider"]
                self.model_id = selected["key"]
                self.api_key = get_api_key_for_provider(self.provider)
                self.model_label = get_model_label(self.provider, self.model_id)
                self.session_dict["active_provider"] = self.provider
                self.session_dict["active_model_id"] = self.model_id
                self._sync_results_to_session()
                autosave(self.session_dict, self.df)
                c.print(f"  [bold green]✓ Switched model to {selected['name']} ({selected['provider'].capitalize()})[/bold green]")
                return
            else:
                c.print(f"  [bold red]⚠ Model not found matching '{target}'.[/bold red]")
                return

        # Otherwise, display beautiful Rich selection table
        table = Table(title="[bold cyan]Supported Models[/bold cyan]", box=box.ROUNDED)
        table.add_column("#", justify="center", style="dim")
        table.add_column("Model Name", style="bold")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", justify="left")

        for idx, m in enumerate(models_list, 1):
            if m["is_active"]:
                status = "[bold green]✓ Active[/bold green]"
            elif m["has_key"]:
                status = "[bold yellow]✓ Key Configured[/bold yellow]"
            else:
                status = "[dim red]✗ Key Missing[/dim red]"
            table.add_row(str(idx), m["name"], m["provider"].capitalize(), status)

        c.print()
        c.print(table)
        c.print()

        from v2.utils import safe_input
        choice = safe_input(c, "  [bold bright_cyan]Enter model number or name to switch (or press Enter to cancel): [/bold bright_cyan]")
        if not choice or not choice.strip():
            c.print("  [dim]Cancelled model selection.[/dim]")
            return

        choice = choice.strip()
        selected = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(models_list):
                selected = models_list[idx]
        else:
            for m in models_list:
                if choice.lower() in m["key"].lower() or choice.lower() in m["name"].lower():
                    selected = m
                    break

        if not selected:
            c.print("  [bold red]Invalid selection.[/bold red]")
            return

        if not selected["has_key"]:
            c.print(f"  [bold red]⚠ Cannot switch to {selected['name']} because no API key is configured for {selected['provider'].capitalize()}.[/bold red]")
            c.print(f"  [dim]Type [bold]/config[/bold] to add a key, or switch to a provider that has a key.[/dim]")
            return

        self.provider = selected["provider"]
        self.model_id = selected["key"]
        self.api_key = get_api_key_for_provider(self.provider)
        self.model_label = get_model_label(self.provider, self.model_id)
        self.session_dict["active_provider"] = self.provider
        self.session_dict["active_model_id"] = self.model_id
        self._sync_results_to_session()
        autosave(self.session_dict, self.df)
        c.print(f"  [bold green]✓ Switched model to {selected['name']} ({selected['provider'].capitalize()})[/bold green]")

    def _do_provider(self, user_input: str):
        c = self.console
        from rich.table import Table
        from .llm import SUPPORTED_PROVIDERS

        # Parse potential args
        args = user_input.strip().split()
        target = args[1] if len(args) > 1 else ""

        if target:
            target = target.lower()
            if target in SUPPORTED_PROVIDERS:
                has_key = get_api_key_for_provider(target) is not None
                if not has_key:
                    c.print(f"  [bold red]⚠ No API key configured for {target.capitalize()}.[/bold red]")
                    c.print(f"  [dim]Please type [bold]/config[/bold] to set the API key for {target.capitalize()} first.[/dim]")
                    return
                self.provider = target
                self.model_id = MODEL_REGISTRY[target]["default"]
                self.api_key = get_api_key_for_provider(self.provider)
                self.model_label = get_model_label(self.provider, self.model_id)
                self.session_dict["active_provider"] = self.provider
                self.session_dict["active_model_id"] = self.model_id
                self._sync_results_to_session()
                autosave(self.session_dict, self.df)
                c.print(f"  [bold green]✓ Switched provider to {target.capitalize()} (Default model: {self.model_label})[/bold green]")
                return
            else:
                c.print(f"  [bold red]⚠ Unsupported provider '{target}'. Supported: gemini, openai, anthropic.[/bold red]")
                return

        # Render list of providers
        table = Table(title="[bold cyan]Supported Providers[/bold cyan]", box=box.ROUNDED)
        table.add_column("#", justify="center", style="dim")
        table.add_column("Provider Name", style="bold")
        table.add_column("Status", justify="left")

        for idx, p in enumerate(SUPPORTED_PROVIDERS, 1):
            has_key = get_api_key_for_provider(p) is not None
            is_active = (self.provider == p)
            if is_active:
                status = "[bold green]✓ Active[/bold green]"
            elif has_key:
                status = "[bold yellow]✓ Key Configured[/bold yellow]"
            else:
                status = "[dim red]✗ Key Missing[/dim red]"
            table.add_row(str(idx), p.capitalize(), status)

        c.print()
        c.print(table)
        c.print()

        from v2.utils import safe_input
        choice = safe_input(c, "  [bold bright_cyan]Enter provider name or number to switch (or press Enter to cancel): [/bold bright_cyan]")
        if not choice or not choice.strip():
            c.print("  [dim]Cancelled provider selection.[/dim]")
            return

        choice = choice.strip().lower()
        selected_prov = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(SUPPORTED_PROVIDERS):
                selected_prov = SUPPORTED_PROVIDERS[idx]
        else:
            if choice in SUPPORTED_PROVIDERS:
                selected_prov = choice

        if not selected_prov:
            c.print("  [bold red]Invalid selection.[/bold red]")
            return

        has_key = get_api_key_for_provider(selected_prov) is not None
        if not has_key:
            c.print(f"  [bold red]⚠ No API key configured for {selected_prov.capitalize()}.[/bold red]")
            c.print(f"  [dim]Please type [bold]/config[/bold] to set the API key for {selected_prov.capitalize()} first.[/dim]")
            return

        self.provider = selected_prov
        self.model_id = MODEL_REGISTRY[selected_prov]["default"]
        self.api_key = get_api_key_for_provider(self.provider)
        self.model_label = get_model_label(self.provider, self.model_id)
        self.session_dict["active_provider"] = self.provider
        self.session_dict["active_model_id"] = self.model_id
        self._sync_results_to_session()
        autosave(self.session_dict, self.df)
        c.print(f"  [bold green]✓ Switched provider to {selected_prov.capitalize()} (Default model: {self.model_label})[/bold green]")

    def _do_config(self):
        c = self.console
        from rich.table import Table
        from .llm import SUPPORTED_PROVIDERS

        c.print()
        c.print("  [bold cyan]⚙ API Key Configuration[/bold cyan]")
        c.print("  Set or update API keys for your AI models.")
        c.print()

        table = Table(box=box.ROUNDED)
        table.add_column("#", justify="center", style="dim")
        table.add_column("Provider", style="bold")
        table.add_column("Env Variable", style="cyan")
        table.add_column("Status", justify="left")

        key_vars = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

        for idx, p in enumerate(SUPPORTED_PROVIDERS, 1):
            key = get_api_key_for_provider(p)
            var_name = key_vars[p]
            if key:
                masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
                status = f"[bold green]✓ Configured[/bold green] [dim]({masked})[/dim]"
            else:
                status = "[dim red]✗ Not Configured[/dim red]"
            table.add_row(str(idx), p.capitalize(), var_name, status)

        c.print(table)
        c.print()

        from v2.utils import safe_input
        choice = safe_input(c, "  [bold bright_cyan]Select provider number or name to configure (or press Enter to cancel): [/bold bright_cyan]")
        if not choice or not choice.strip():
            c.print("  [dim]Cancelled config.[/dim]")
            return

        choice = choice.strip().lower()
        selected_prov = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(SUPPORTED_PROVIDERS):
                selected_prov = SUPPORTED_PROVIDERS[idx]
        else:
            if choice in SUPPORTED_PROVIDERS:
                selected_prov = choice

        if not selected_prov:
            c.print("  [bold red]Invalid selection.[/bold red]")
            return

        var_name = key_vars[selected_prov]
        new_key = safe_input(c, f"  [bold bright_cyan]Enter new API key for {selected_prov.capitalize()} ({var_name}): [/bold bright_cyan]")
        if not new_key or not new_key.strip():
            c.print("  [dim]Cancelled update. No changes made.[/dim]")
            return

        new_key = new_key.strip()

        # Verify key
        c.print()
        with c.status(f"  [bold dim]Verifying API key for {selected_prov.capitalize()}...[/bold dim]"):
            from .llm import verify_api_key
            success, err_msg = verify_api_key(selected_prov, new_key)
        
        if not success:
            c.print(f"  [bold red]⚠ API Key verification failed: {err_msg}[/bold red]")
            bypass = safe_input(c, "  [bold yellow]Would you like to save this key anyway? (y/N): [/bold yellow]")
            if not bypass or bypass.strip().lower() != "y":
                c.print("  [dim]Cancelled config. No changes made.[/dim]")
                return
        else:
            c.print(f"  [bold green]✓ API Key successfully verified for {selected_prov.capitalize()}![/bold green]")

        # Update environment variable in memory
        os.environ[var_name] = new_key


        # Save to .env file
        env_path = os.path.join(os.getcwd(), ".env")
        lines = []
        updated = False

        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith(f"{var_name}="):
                            lines.append(f"{var_name}={new_key}\n")
                            updated = True
                        else:
                            lines.append(line)
            except Exception:
                pass

        if not updated:
            lines.append(f"{var_name}={new_key}\n")

        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            c.print(f"  [bold green]✓ Successfully saved key to .env file![/bold green]")
        except Exception as e:
            c.print("  [bold red]⚠ Failed to save key to .env file.[/bold red]")
            c.print("  [yellow]Key updated in current session memory only.[/yellow]")

        # Update active credentials if they apply to current provider
        if self.provider == selected_prov or not self.provider:
            self.provider = selected_prov
            self.model_id = MODEL_REGISTRY[self.provider]["default"]
            self.api_key = new_key
            self.model_label = get_model_label(self.provider, self.model_id)
            self.session_dict["active_provider"] = self.provider
            self.session_dict["active_model_id"] = self.model_id
            self._sync_results_to_session()
            autosave(self.session_dict, self.df)
            c.print(f"  [bold green]✓ Switched active model to default for {selected_prov.capitalize()}: {self.model_label}[/bold green]")

    # ── Core query processing ────────────────────────────────────────────

    def _process_query(self, query: str):
        """Steps 2-6 of the core loop."""
        c = self.console

        # Step 2 — Intent parsing
        intent = parse_intent(query, self.columns)

        # Step 5 — Add user message to memory
        self.memory.add_user(query)

        # Step 3 — Execute
        response = ""
        func_called = None

        if intent.category == Intent.DATA_QUERY:
            response, func_called = self._handle_data_query(intent)

        elif intent.category == Intent.EXPLANATION:
            response = self._handle_explanation(intent)

        elif intent.category == Intent.REPORT:
            response, func_called = self._handle_report()

        elif intent.category == Intent.CODE:
            if not self.last_operation:
                response = "⚠️ **No analysis operation has been run in this session yet.** Please ask a question or run an analysis command first."
            else:
                response = get_code_for_operation(self.last_operation, self.filename)

        elif intent.category == Intent.GENERAL:
            response = self._handle_with_llm(query, narrate_general_greeting())

        elif intent.category == Intent.AMBIGUOUS:
            response = self._handle_with_llm(
                query, narrate_ambiguous(query, self.columns))

        # Step 4 — Render response
        c.print()
        c.print(Markdown(response))

        # Step 5 cont — save assistant response
        self.memory.add_assistant(response, func_called)

        # Step 6 — Autosave
        self._sync_results_to_session()
        autosave(self.session_dict)

    # ── Data query handler ───────────────────────────────────────────────

    def _handle_data_query(self, intent) -> tuple[str, str | None]:
        func = intent.v2_function

        if func == "eda":
            return self._run_eda(), "eda"

        elif func == "relationships":
            return self._run_relationships(), "relationships"

        elif func == "insights":
            return self._run_insights(), "insights"

        elif func == "geographic":
            return self._run_geographic(), "geographic"

        elif func == "column_detail":
            col = intent.column_ref
            if col:
                self.last_operation = "column_detail"
                raw = narrate_column_detail(col, self.df, self.col_types)
                return self._handle_with_llm(intent.raw_query, raw), f"column_detail({col})"
            return narrate_ambiguous(intent.raw_query, self.columns), None

        elif func == "pivot":
            # Pivot is interactive in V2, so we narrate what's needed
            return self._handle_with_llm(
                intent.raw_query,
                "Pivot tables require interactive column selection. "
                "Use `/switch` to go to V2 and run `/pivot` there, "
                "or tell me which column to group by and which metric to aggregate."
            ), None

        elif func == "comparative":
            return self._handle_with_llm(
                intent.raw_query,
                "Comparisons require segment selection. "
                "Use `/switch` to go to V2 and run `/comparative`, "
                "or tell me which two groups you want to compare."
            ), None

        return narrate_ambiguous(intent.raw_query, self.columns), None

    # ── V2 function runners (silent, capture results) ────────────────────

    def _run_eda(self) -> str:
        if self.results.get("eda"):
            raw = narrate_eda(self.results["eda"], self.col_types)
            return self._handle_with_llm("run eda", raw)

        # Run V2 EDA silently
        self.console.print("  [dim]⏳ Running EDA analysis...[/dim]")
        from v2.commands.eda import run_eda
        self.results["eda"] = run_eda(self._as_v2_agent(), silent=True)
        self.last_operation = "eda"

        raw = narrate_eda(self.results["eda"], self.col_types)
        return self._handle_with_llm("run eda", raw)

    def _run_relationships(self) -> str:
        if self.results.get("relationships"):
            raw = narrate_relationships(self.results["relationships"])
            return self._handle_with_llm("check relationships", raw)

        self.console.print("  [dim]⏳ Running relationship scan...[/dim]")
        from v2.commands.relationships import run_relationships
        self.results["relationships"] = run_relationships(self._as_v2_agent())
        self.last_operation = "relationships"

        raw = narrate_relationships(self.results["relationships"])
        return self._handle_with_llm("check relationships", raw)

    def _run_insights(self) -> str:
        if self.results.get("insights"):
            raw = narrate_insights(self.results["insights"])
            return self._handle_with_llm("find insights", raw)

        self.console.print("  [dim]⏳ Running insight engine...[/dim]")
        # Insights needs EDA first
        if not self.results.get("eda"):
            from v2.commands.eda import run_eda
            self.results["eda"] = run_eda(self._as_v2_agent(), silent=True)

        from v2.commands.insights import run_insights
        self.results["insights"] = run_insights(self._as_v2_agent())
        self.last_operation = "insights"

        raw = narrate_insights(self.results["insights"])
        return self._handle_with_llm("find insights", raw)

    def _run_geographic(self) -> str:
        if self.results.get("geographic"):
            raw = narrate_geographic(self.results["geographic"])
            return self._handle_with_llm("geographic breakdown", raw)

        return self._handle_with_llm(
            "geographic analysis",
            "Geographic analysis requires interactive column confirmation. "
            "Use `/switch` to go to V2 and run `/geographic` there."
        )

    # ── Report handler ───────────────────────────────────────────────────

    def _handle_report(self) -> tuple[str, str | None]:
        return self._handle_with_llm(
            "generate report",
            "Report generation is interactive (section selection, format choice). "
            "Use `/switch` to go to V2 and run `/report` for the full builder.\n\n"
            "Or I can give you a quick text summary right now — just say "
            "\"write a quick summary\" instead."
        ), None

    # ── Explanation handler ──────────────────────────────────────────────

    def _handle_explanation(self, intent) -> str:
        col = intent.column_ref
        context_parts = []

        if col:
            raw = narrate_column_detail(col, self.df, self.col_types)
            context_parts.append(raw)

        if self.results.get("eda"):
            context_parts.append("EDA results are available.")
        if self.results.get("insights"):
            ins = self.results["insights"]
            titles = [i["title"] for i in ins.get("insights", [])[:5]]
            context_parts.append(f"Insights found: {', '.join(titles)}")

        context = "\n".join(context_parts) if context_parts else "No prior analysis available."
        return self._handle_with_llm(intent.raw_query, context)

    # ── LLM integration ──────────────────────────────────────────────────

    def _format_api_error(self, e: Exception) -> str:
        import json
        import re
        msg = str(e)
        if "LLM request failed:" in msg:
            inner = msg.replace("LLM request failed:", "").strip()
            if "getaddrinfo failed" in inner or "timed out" in inner or "connection" in inner.lower():
                return "Connection Error: Failed to reach the AI server. Please verify your internet connection."
            return f"Request Failed: {inner}"

        if "LLM API HTTP" not in msg:
            return msg

        try:
            parts = msg.split(":", 1)
            if len(parts) < 2:
                return msg

            header = parts[0].strip()
            code_str = header.replace("LLM API HTTP", "").strip()
            code = int(code_str) if code_str.isdigit() else 0
            body_str = parts[1].strip()

            try:
                body = json.loads(body_str)
            except Exception:
                body = {}

            details = ""
            if isinstance(body, dict):
                if "error" in body and isinstance(body["error"], dict):
                    details = body["error"].get("message", "")
                elif "error" in body and isinstance(body["error"], str):
                    details = body["error"]
                elif "message" in body:
                    details = body["message"]

            if code == 429:
                clean_details = "You exceeded your current quota. Please check your plan and billing details."
                m = re.search(r"Please retry in ([\d\.]+)s", details)
                if m:
                    seconds = int(float(m.group(1)))
                    clean_details += f" Please try again in {seconds} seconds."
                else:
                    clean_details += " Please wait a moment and try again."
                return f"Quota Exceeded (HTTP 429): {clean_details}"

            if code == 401:
                return "Invalid API Key (HTTP 401): The provided API key is invalid or unauthorized. Please check your `.env` configuration."

            if code == 403:
                return f"Access Forbidden (HTTP 403): The request was forbidden by the AI provider. Details: {details if details else 'Permission denied.'}"

            if code == 404:
                msg_404 = f"Not Found (HTTP 404): The requested model endpoint was not found or is not supported. Details: {details if details else 'Endpoint not found.'}"
                if getattr(self, "provider", None) == "nvidia":
                    msg_404 += " Try switching to a different model using /model."
                return msg_404

            if details:
                return f"HTTP {code}: {details}"
        except Exception:
            pass

        return msg

    def _handle_with_llm(self, query: str, local_context: str) -> str:
        """Try LLM enrichment; display friendly error inline on failure or missing API key."""
        from .llm import get_api_key_for_provider
        c = self.console
        
        # Always check/refresh current key
        if self.provider:
            self.api_key = get_api_key_for_provider(self.provider)

        if not self.provider or not self.api_key:
            self.provider, self.api_key = detect_provider()
            if self.provider:
                self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")
            self.model_label = get_model_label(self.provider, self.model_id)

        if not self.provider or not self.api_key:
            return (
                "⚠️ **No LLM API Key Found**\n\n"
                "V3 Chat Mode requires an API key to communicate with the model. Please check the following:\n"
                "- Ensure one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY` is set in your environment variables.\n"
                "- Or verify your `.env` file in the project root.\n\n"
                "*(Tip: You can switch back to offline V2 Command Mode at any time by typing `/switch`)*"
            )

        try:
            system = _build_system_prompt(self.session_dict, self.df)
            enriched_query = f"{query}\n\n[LOCAL ANALYSIS RESULT]:\n{local_context}"
            
            with c.status(f"  [bold dim]Thinking ({self.model_label})...[/bold dim]"):
                response = call_llm(
                    system, enriched_query,
                    self.memory.limited_recent(4),
                    self.provider, self.api_key,
                    self.model_id,
                )
            return response
        except Exception as e:
            friendly_err = self._format_api_error(e)
            return (
                "⚠️ **AI Call Failed**\n\n"
                f"I encountered an error trying to request a response:\n"
                f"**{friendly_err}**\n\n"
                "Please verify your network connection, API key configuration, or model limits. "
                "You can switch to offline V2 Command Mode by typing `/switch`."
            )

    # ── V2 agent adapter ─────────────────────────────────────────────────

    def _as_v2_agent(self):
        """Create a lightweight adapter that V2 command functions can use."""
        return _V2Adapter(self)

    # ── Session sync ─────────────────────────────────────────────────────

    def _sync_results_to_session(self):
        from v1 import session_manager
        active_ds = session_manager.get_active_dataset(self.session_dict)
        if not active_ds:
            active_ds = self.session_dict
        v2 = active_ds.setdefault("v2_summary", {})
        v2["eda_results"] = self.results["eda"]
        v2["relationships_results"] = self.results["relationships"]
        v2["geo_results"] = self.results["geographic"]
        v2["pivot_results"] = self.results["pivot"]
        v2["comparison_results"] = self.results["comparative"]
        v2["insights_triggered"] = self.results["insights"]

        ar = v2.setdefault("analyses_run", [])
        for key, val in self.results.items():
            if val is not None and key not in ar:
                ar.append(key)
        self.session_dict["last_operation"] = self.last_operation


# ── V2 adapter — makes V3 look like a V2 agent for command functions ─────────

class _V2Adapter:
    """Minimal adapter so V2 command functions (run_eda, run_insights, etc.)
    can call agent.df, agent.console, agent.col_types, etc."""

    def __init__(self, v3: DataAnalystAgentV3):
        self.df = v3.df
        self.console = v3.console
        self.col_types = v3.col_types
        self.results = v3.results
        self.filename = v3.filename
        from v1 import session_manager
        active_ds = session_manager.get_active_dataset(v3.session_dict)
        if not active_ds:
            active_ds = v3.session_dict
        self.original_filepath = active_ds.get("file", {}).get("original", "")
        self.original_shape = v3.original_shape
        self.cleaned_shape = v3.cleaned_shape
        self.issues_resolved = v3.v1_summary.get("issues_resolved", 0)
        self.applied_actions = v3.v1_summary.get("actions_log", [])
        self.geo_cols = []
        self.batch_files = []

        # Session log stub
        from v2.session import SessionLog
        self.session = SessionLog()

        # Detect geo columns
        from v2.utils import detect_geo_columns
        self.geo_cols = detect_geo_columns(self.df)
