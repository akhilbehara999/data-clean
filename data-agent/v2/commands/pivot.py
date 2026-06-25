"""Command [4] — Pivot Table Builder: interactive step-by-step."""

from __future__ import annotations
from typing import TYPE_CHECKING

import pandas as pd
from rich.table import Table
from rich import box

from ..utils import safe_input, fmt_num, suggest_next

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2

_AGG_MAP = {
    "1": ("sum", "Sum"),
    "2": ("mean", "Mean"),
    "3": ("count", "Count"),
    "4": ("max", "Max"),
    "5": ("min", "Min"),
    "6": ("nunique", "Count Unique"),
}


def run_pivot(agent: DataAnalystAgentV2) -> dict | None:
    """Interactive pivot table builder — one prompt at a time."""
    con = agent.console
    df = agent.df
    ct = agent.col_types

    row_options = ct["categorical"] + ct["datetime"]
    if not row_options:
        con.print("[yellow]No categorical or date columns available for pivot rows.[/yellow]")
        return None
    if not ct["numeric"]:
        con.print("[yellow]No numeric columns available for aggregation.[/yellow]")
        return None

    # Step 1 — Row grouping
    con.print()
    con.print("[bold bright_white]  PIVOT TABLE BUILDER[/bold bright_white]")
    con.print()
    con.print("  [bold]Step 1:[/bold] Choose row grouping column:")
    for i, c in enumerate(row_options, 1):
        con.print(f"    [{i}] {c}")

    while True:
        pick = safe_input(con, "[bold bright_cyan]  Row column: [/bold bright_cyan]")
        if pick.isdigit() and 1 <= int(pick) <= len(row_options):
            row_col = row_options[int(pick) - 1]
            break
        con.print(f"[dim]Enter 1–{len(row_options)}.[/dim]")

    # Step 2 — Column grouping (optional)
    con.print()
    con.print("  [bold]Step 2:[/bold] Choose column grouping (Enter to skip):")
    col_options = [c for c in ct["categorical"] if c != row_col]
    for i, c in enumerate(col_options, 1):
        con.print(f"    [{i}] {c}")
    con.print("    [Enter] Skip")

    col_col = None
    pick = safe_input(con, "[bold bright_cyan]  Column grouping: [/bold bright_cyan]")
    if pick.isdigit() and 1 <= int(pick) <= len(col_options):
        col_col = col_options[int(pick) - 1]

    # Step 3 — Value columns
    con.print()
    from ..utils import multi_select
    selected_indices = multi_select(
        con,
        prompt="Step 3: Choose value column(s) to aggregate",
        options=ct["numeric"],
        preselected=[0]
    )
    val_cols = [ct["numeric"][idx] for idx in selected_indices]
    if not val_cols:
        val_cols = [ct["numeric"][0]]

    # Step 4 — Aggregation
    con.print()
    con.print("  [bold]Step 4:[/bold] Choose aggregation:")
    con.print("    [1] Sum  [2] Mean  [3] Count  [4] Max  [5] Min  [6] Count Unique")

    while True:
        pick = safe_input(con, "[bold bright_cyan]  Aggregation: [/bold bright_cyan]")
        if pick in _AGG_MAP:
            agg_func, agg_label = _AGG_MAP[pick]
            break
        con.print("[dim]Enter 1–6.[/dim]")

    # Build pivot
    try:
        if col_col:
            pivot = pd.pivot_table(
                df, values=val_cols, index=row_col,
                columns=col_col, aggfunc=agg_func, fill_value=0,
            )
        else:
            pivot = df.groupby(row_col)[val_cols].agg(agg_func)
            pivot.columns = [f"{c} ({agg_label})" for c in val_cols]
    except Exception as e:
        con.print("[red]Pivot failed. Please check your column selections and try again.[/red]")
        return None

    # Display preview (max 8 rows × 6 cols)
    preview = pivot.head(8)
    display_cols = list(preview.columns[:6])

    con.print()
    col_label = f" × {col_col}" if col_col else ""
    con.print(f"  ─────────────────────────────────────────────────────────")
    val_label = ", ".join(val_cols)
    con.print(
        f"  PIVOT — {row_col}{col_label} → {val_label} ({agg_label})"
    )
    con.print(f"  ─────────────────────────────────────────────────────────")

    tbl = Table(box=box.SIMPLE, header_style="bold magenta")
    tbl.add_column(row_col, style="bold")
    for c in display_cols:
        tbl.add_column(str(c), justify="right")

    for idx, row in preview[display_cols].iterrows():
        tbl.add_row(str(idx), *[fmt_num(v) for v in row])

    con.print(tbl)
    con.print(
        f"  Total: {pivot.shape[0]} rows × {pivot.shape[1]} columns in full pivot"
    )
    con.print(f"  ─────────────────────────────────────────────────────────")

    # Save prompt
    save = safe_input(con, "[bold bright_cyan]  Save this pivot? (y/n): [/bold bright_cyan]")
    export_path = None
    if save.lower() in ("y", "yes"):
        from .export import run_export_df
        export_path = run_export_df(
            agent, pivot.reset_index(),
            default_name=f"{agent.filename.rsplit('.', 1)[0]}_pivot",
        )

    con.print()
    con.print("[green]Pivot complete. Results queued for report builder.[/green]")
    result = {
        "pivot_df": pivot,
        "row_col": row_col,
        "col_col": col_col,
        "val_col": ", ".join(val_cols),
        "agg_label": agg_label,
        "shape": pivot.shape,
        "export_path": export_path,
    }
    con.print(suggest_next(result, "pivot"))
    return result
