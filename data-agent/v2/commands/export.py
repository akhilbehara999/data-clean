"""Command [9] + Export Rules — format selection, save, size warnings."""

from __future__ import annotations
from typing import TYPE_CHECKING
import os

import pandas as pd

from ..utils import safe_input, ensure_output_dir, fmt_size, get_clean_path_base

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2

_FORMATS = {
    "1": ("csv", "CSV — universal, lightweight"),
    "2": ("xlsx", "XLSX — formatted workbook"),
    "3": ("parquet", "Parquet — compressed, fast (best for >100k rows)"),
    "4": ("json", "JSON — records format, API-ready"),
    "5": ("md", "Markdown (.md) — plain text, shareable"),
    "6": ("html", "HTML — styled, opens in any browser"),
    "7": ("all", "All formats — export everything at once"),
}


def run_export(agent: DataAnalystAgentV2) -> str | None:
    """Export the active working dataset."""
    base = get_clean_path_base(agent.original_filepath)
    return run_export_df(agent, agent.df, default_name=f"{base}_export")


def run_export_df(agent: DataAnalystAgentV2, df: pd.DataFrame,
                  default_name: str = "export") -> str | None:
    """Core export workflow — used by multiple commands."""
    con = agent.console

    con.print()
    con.print("[bold bright_white]  Export as:[/bold bright_white]")
    for k, (_, desc) in _FORMATS.items():
        con.print(f"    [{k}] {desc}")

    while True:
        pick = safe_input(con, "[bold bright_cyan]  Format: [/bold bright_cyan]")
        if pick in _FORMATS:
            break
        con.print("[dim]Enter 1–7.[/dim]")

    fmt_key = _FORMATS[pick][0]
    suggested = default_name
    name = safe_input(
        con,
        f"[bold bright_cyan]  Filename (Enter for '{suggested}'): [/bold bright_cyan]"
    )
    if not name:
        name = suggested

    out_dir = ensure_output_dir()

    if fmt_key == "all":
        paths = []
        for ext in ["csv", "xlsx", "parquet", "json", "md", "html"]:
            p = _save_single(df, out_dir, name, ext, con)
            if p:
                paths.append(p)
        return ", ".join(paths) if paths else None
    else:
        return _save_single(df, out_dir, name, fmt_key, con)


def _save_single(df: pd.DataFrame, out_dir: str, name: str,
                 ext: str, con) -> str | None:
    """Save a single file in the given format."""
    filepath = os.path.join(out_dir, f"{name}.{ext}")

    try:
        if ext == "csv":
            df.to_csv(filepath, index=False)
        elif ext == "xlsx":
            df.to_excel(filepath, index=False, engine="openpyxl")
        elif ext == "parquet":
            df.to_parquet(filepath, index=False)
        elif ext == "json":
            df.to_json(filepath, orient="records", indent=2, force_ascii=False)
        elif ext == "md":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(df.to_markdown(index=False))
        elif ext == "html":
            html = _styled_html_table(df)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
        else:
            con.print(f"[red]Unknown format: {ext}[/red]")
            return None

        size = os.path.getsize(filepath)
        con.print(f"  [green]✓ Saved → {filepath}  |  Size: {fmt_size(size)}[/green]")

        if size > 10_485_760:  # 10 MB
            con.print(
                f"  [yellow]⚠ File is {fmt_size(size)} — may be too large to email. "
                f"Consider Parquet for sharing large datasets.[/yellow]"
            )

        return filepath

    except ImportError as e:
        lib = "openpyxl" if ext == "xlsx" else "pyarrow"
        con.print(f"[red]Export failed — run: pip install {lib}[/red]")
        return None
    except Exception as e:
        con.print("[red]Export failed. Please check that the file is not corrupted and try again.[/red]")
        return None


def _styled_html_table(df: pd.DataFrame) -> str:
    """Generate a styled HTML page from a DataFrame."""
    rows_html = df.to_html(index=False, classes="data-table", border=0)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Data Export</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0;
         padding: 2rem; }}
  h1 {{ color: #00d4ff; }}
  .data-table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  .data-table th {{ background: #16213e; color: #00d4ff; padding: 10px 14px;
                    text-align: left; border-bottom: 2px solid #0f3460; }}
  .data-table td {{ padding: 8px 14px; border-bottom: 1px solid #2a2a4a; }}
  .data-table tr:nth-child(even) {{ background: #16213e; }}
  .data-table tr:hover {{ background: #0f3460; }}
</style>
</head>
<body>
<h1>📊 Data Export</h1>
<p>Rows: {len(df):,} | Columns: {len(df.columns)}</p>
{rows_html}
</body>
</html>"""
