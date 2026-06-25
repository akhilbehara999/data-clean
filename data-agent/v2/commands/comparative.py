"""Command [5] — Comparative Analysis: time periods, segments, files."""

from __future__ import annotations
from typing import TYPE_CHECKING

import pandas as pd
import numpy as np
from rich.table import Table
from rich import box

from ..utils import safe_input, fmt_num, fmt_pct_delta, suggest_next

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


def run_comparative(agent: DataAnalystAgentV2) -> dict | None:
    """Comparative analysis menu and execution."""
    con = agent.console
    df = agent.df
    ct = agent.col_types

    con.print()
    con.print("[bold bright_white]  What would you like to compare?[/bold bright_white]")
    con.print("    [1] Two time periods     (e.g. Q3 vs Q4, Jan vs Feb)")
    con.print("    [2] Two column segments   (e.g. Premium vs Regular)")
    if hasattr(agent, "batch_files") and agent.batch_files:
        con.print("    [3] Two uploaded files    (batch mode)")

    pick = safe_input(con, "[bold bright_cyan]  Choice: [/bold bright_cyan]")

    if pick == "1":
        return _compare_time_periods(agent)
    elif pick == "2":
        return _compare_segments(agent)
    elif pick == "3" and hasattr(agent, "batch_files") and agent.batch_files:
        return _compare_files(agent)
    else:
        con.print("[dim]Invalid choice.[/dim]")
        return None


def _build_diff_table(con, label_a: str, label_b: str,
                      metrics: list[dict]) -> list[dict]:
    """Build and print a comparison diff table."""
    con.print()
    con.print(f"  ─────────────────────────────────────────────────────────")
    con.print(f"  ⚖️  COMPARISON — {label_a}  vs  {label_b}")
    con.print(f"  ─────────────────────────────────────────────────────────")

    tbl = Table(box=box.SIMPLE, header_style="bold bright_white")
    tbl.add_column("Metric", style="bold")
    tbl.add_column(label_a, justify="right")
    tbl.add_column(label_b, justify="right")
    tbl.add_column("Change", justify="right")
    tbl.add_column("%Δ", justify="right")

    for m in metrics:
        val_a = m["val_a"]
        val_b = m["val_b"]
        change = val_b - val_a if pd.notna(val_a) and pd.notna(val_b) else float("nan")
        pct_change = (change / val_a * 100) if pd.notna(val_a) and val_a != 0 else float("nan")

        change_str = f"{'+' if change > 0 else ''}{fmt_num(change)}" if pd.notna(change) else "—"
        if pd.notna(change):
            change_str += " ↑" if change > 0 else (" ↓" if change < 0 else "")

        pct_str = fmt_pct_delta(pct_change) if pd.notna(pct_change) else "—"

        m["change"] = change
        m["pct_change"] = pct_change

        tbl.add_row(
            m["name"],
            fmt_num(val_a),
            fmt_num(val_b),
            change_str,
            pct_str,
        )

    con.print(tbl)
    con.print(f"  ─────────────────────────────────────────────────────────")
    con.print(f"  ↑ improved   ↓ declined   pp = percentage points")
    con.print()

    # Summary sentences
    significant = sorted(
        [m for m in metrics if pd.notna(m.get("pct_change"))],
        key=lambda x: abs(x["pct_change"]),
        reverse=True,
    )[:3]

    if significant:
        for m in significant[:2]:
            direction = "increased" if m["pct_change"] > 0 else "decreased"
            con.print(
                f"  {m['name']} {direction} by {abs(m['pct_change']):.1f}% "
                f"from {label_a} to {label_b}."
            )
        if len(significant) >= 3:
            m = significant[2]
            direction = "grew" if m["pct_change"] > 0 else "declined"
            con.print(
                f"  {m['name']} {direction} by {abs(m['pct_change']):.1f}%."
            )

    return metrics


def _compare_time_periods(agent: DataAnalystAgentV2) -> dict | None:
    """Compare two time periods within a datetime column."""
    con = agent.console
    df = agent.df
    ct = agent.col_types

    dt_cols = ct["datetime"]
    if not dt_cols:
        con.print("[yellow]No datetime columns detected for time comparison.[/yellow]")
        return None

    # Pick date column
    if len(dt_cols) == 1:
        date_col = dt_cols[0]
    else:
        con.print("  Choose date column:")
        for i, c in enumerate(dt_cols, 1):
            con.print(f"    [{i}] {c}")
        pick = safe_input(con, "[bold bright_cyan]  Column: [/bold bright_cyan]")
        idx = int(pick) - 1 if pick.isdigit() and 1 <= int(pick) <= len(dt_cols) else 0
        date_col = dt_cols[idx]

    try:
        dates = pd.to_datetime(df[date_col], errors="coerce", format="mixed")
    except Exception:
        dates = pd.to_datetime(df[date_col], errors="coerce")

    df_work = df.copy()
    df_work["_parsed_date"] = dates
    df_work = df_work.dropna(subset=["_parsed_date"])

    if len(df_work) == 0:
        con.print("[yellow]No valid dates found in this column.[/yellow]")
        return None

    # Auto-split into two halves by date
    median_date = df_work["_parsed_date"].median()
    group_a = df_work[df_work["_parsed_date"] <= median_date]
    group_b = df_work[df_work["_parsed_date"] > median_date]

    label_a = f"Before {median_date.strftime('%Y-%m-%d')}"
    label_b = f"After {median_date.strftime('%Y-%m-%d')}"

    # Build metrics from numeric columns
    metrics: list[dict] = [
        {"name": "Row count", "val_a": len(group_a), "val_b": len(group_b)}
    ]
    for col in ct["numeric"]:
        metrics.append({
            "name": f"{col} (mean)",
            "val_a": group_a[col].mean(),
            "val_b": group_b[col].mean(),
        })
        metrics.append({
            "name": f"{col} (sum)",
            "val_a": group_a[col].sum(),
            "val_b": group_b[col].sum(),
        })

    result_metrics = _build_diff_table(con, label_a, label_b, metrics)

    con.print()
    con.print("[green]Comparison complete. Results queued for report builder.[/green]")
    result = {
        "type": "time_period",
        "label_a": label_a, "label_b": label_b,
        "metrics": result_metrics,
    }
    con.print(suggest_next(result, "comparative"))
    return result


def _compare_segments(agent: DataAnalystAgentV2) -> dict | None:
    """Compare two segments within a categorical column."""
    con = agent.console
    df = agent.df
    ct = agent.col_types

    if not ct["categorical"]:
        con.print("[yellow]No categorical columns for segment comparison.[/yellow]")
        return None

    # Pick segment column
    con.print("  Choose segment column:")
    for i, c in enumerate(ct["categorical"], 1):
        con.print(f"    [{i}] {c}")
    
    seg_col = None
    while True:
        pick = safe_input(con, "[bold bright_cyan]  Column (or 'q' to cancel): [/bold bright_cyan]").strip()
        if pick.lower() in ("q", "quit", "exit", "cancel"):
            return None
        if pick.isdigit() and 1 <= int(pick) <= len(ct["categorical"]):
            seg_col = ct["categorical"][int(pick) - 1]
            break
        con.print(f"  [bold red]Error: Please select a valid number from 1 to {len(ct['categorical'])}.[/bold red]")

    # Show top values and let user pick two
    top_vals = df[seg_col].value_counts().head(10)
    val_list = list(top_vals.index)
    if len(val_list) < 2:
        con.print(f"  [yellow]Not enough unique values in '{seg_col}' to perform a comparison.[/yellow]")
        return None

    con.print(f"  Top values in column '{seg_col}':")
    for i, v in enumerate(val_list, 1):
        con.print(f"    [{i}] {v} ({top_vals.iloc[i-1]:,} rows)")

    # Pick first segment
    while True:
        pick_a = safe_input(con, "[bold bright_cyan]  First segment (number, or 'q' to cancel): [/bold bright_cyan]").strip()
        if pick_a.lower() in ("q", "quit", "exit", "cancel"):
            return None
        if pick_a.isdigit() and 1 <= int(pick_a) <= len(val_list):
            idx_a = int(pick_a) - 1
            break
        con.print(f"  [bold red]Error: Please select a valid number from 1 to {len(val_list)}.[/bold red]")

    # Pick second segment
    while True:
        pick_b = safe_input(con, "[bold bright_cyan]  Second segment (number, or 'q' to cancel): [/bold bright_cyan]").strip()
        if pick_b.lower() in ("q", "quit", "exit", "cancel"):
            return None
        if pick_b.isdigit() and 1 <= int(pick_b) <= len(val_list):
            idx_b = int(pick_b) - 1
            if idx_b != idx_a:
                break
            con.print("  [bold red]Error: The second segment must be different from the first segment.[/bold red]")
        else:
            con.print(f"  [bold red]Error: Please select a valid number from 1 to {len(val_list)}.[/bold red]")

    val_a, val_b = str(val_list[idx_a]), str(val_list[idx_b])
    group_a = df[df[seg_col] == val_list[idx_a]]
    group_b = df[df[seg_col] == val_list[idx_b]]

    metrics: list[dict] = [
        {"name": "Row count", "val_a": len(group_a), "val_b": len(group_b)}
    ]
    for col in ct["numeric"]:
        metrics.append({
            "name": f"{col} (mean)",
            "val_a": group_a[col].mean(),
            "val_b": group_b[col].mean(),
        })

    result_metrics = _build_diff_table(con, val_a, val_b, metrics)

    con.print()
    con.print("[green]Comparison complete. Results queued for report builder.[/green]")
    result = {
        "type": "segment",
        "label_a": val_a, "label_b": val_b,
        "metrics": result_metrics,
    }
    con.print(suggest_next(result, "comparative"))
    return result


def _compare_files(agent: DataAnalystAgentV2) -> dict | None:
    """Compare two files in batch mode."""
    con = agent.console
    if not agent.batch_files:
        return None

    con.print("  Choose files to compare:")
    con.print(f"    [1] {agent.filename} (primary)")
    for i, bf in enumerate(agent.batch_files, 2):
        con.print(f"    [{i}] {bf['filename']}")

    pick_a = safe_input(con, "[bold bright_cyan]  First file: [/bold bright_cyan]")
    pick_b = safe_input(con, "[bold bright_cyan]  Second file: [/bold bright_cyan]")

    # Build comparison between two files' numeric summaries
    all_dfs = [{"filename": agent.filename, "df": agent.df}] + agent.batch_files
    idx_a = int(pick_a) - 1 if pick_a.isdigit() else 0
    idx_b = int(pick_b) - 1 if pick_b.isdigit() else min(1, len(all_dfs) - 1)

    df_a, df_b = all_dfs[idx_a]["df"], all_dfs[idx_b]["df"]
    label_a, label_b = all_dfs[idx_a]["filename"], all_dfs[idx_b]["filename"]

    metrics: list[dict] = [
        {"name": "Row count", "val_a": len(df_a), "val_b": len(df_b)},
        {"name": "Column count", "val_a": len(df_a.columns), "val_b": len(df_b.columns)},
    ]

    common_numeric = [
        c for c in df_a.select_dtypes(include="number").columns
        if c in df_b.columns and pd.api.types.is_numeric_dtype(df_b[c])
    ]
    for col in common_numeric:
        metrics.append({
            "name": f"{col} (mean)",
            "val_a": df_a[col].mean(),
            "val_b": df_b[col].mean(),
        })

    result_metrics = _build_diff_table(con, label_a, label_b, metrics)

    con.print()
    con.print("[green]Comparison complete. Results queued for report builder.[/green]")
    result = {"type": "file", "label_a": label_a, "label_b": label_b, "metrics": result_metrics}
    con.print(suggest_next(result, "comparative"))
    return result
