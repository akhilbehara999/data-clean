"""Command [1] — Auto EDA: full dataset profile in five sections."""

from __future__ import annotations
from typing import TYPE_CHECKING

import pandas as pd
import numpy as np
from datetime import datetime
from rich.panel import Panel
from rich import box

from ..utils import fmt_num, fmt_pct, suggest_next

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_eda(agent: DataAnalystAgentV2, silent: bool = False) -> dict:
    """Run full EDA. If *silent*, collect results without printing."""
    con = agent.console
    df = agent.df
    ct = agent.col_types
    date = datetime.now().strftime("%Y-%m-%d")

    results: dict = {
        "overview": {},
        "numeric": [],
        "categorical": [],
        "datetime": [],
        "correlations": [],
    }

    # ── Section A — Overview ─────────────────────────────────────────────
    mem = df.memory_usage(deep=True).sum() / 1_048_576
    ov = {
        "filename": agent.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "memory_mb": round(mem, 2),
        "date": date,
    }
    results["overview"] = ov

    if not silent:
        con.print()
        con.print(Panel(
            f"[bold bright_white]📊 EDA REPORT — {ov['filename']}[/bold bright_white]\n"
            f"Rows: {ov['rows']:,} | Columns: {ov['columns']} | "
            f"Memory: {ov['memory_mb']:.1f} MB | Date: {ov['date']}",
            border_style="bright_blue",
        ))
        con.print()

    # ── Section B — Numeric columns ──────────────────────────────────────
    if ct["numeric"] and not silent:
        con.print("[bold bright_white]  NUMERIC COLUMNS[/bold bright_white]")
        con.print()

    for col in ct["numeric"]:
        s = df[col].dropna()
        skew_val = s.skew() if len(s) > 2 else float("nan")
        if pd.notna(skew_val):
            if skew_val > 1.0:
                skew_lbl = "highly right-skewed"
            elif skew_val >= 0.5:
                skew_lbl = "moderately right-skewed"
            elif skew_val >= -0.5:
                skew_lbl = "normal"
            elif skew_val >= -1.0:
                skew_lbl = "moderately left-skewed"
            else:
                skew_lbl = "highly left-skewed"
        else:
            skew_lbl = "N/A"

        nulls = int(df[col].isna().sum())
        null_pct = nulls / len(df) * 100

        notes: list[str] = []
        if pd.notna(skew_val) and abs(skew_val) > 1.0:
            notes.append(
                f"Distribution is significantly {skew_lbl} — "
                "median may be more reliable than mean."
            )
        if null_pct > 10:
            notes.append(
                f"{null_pct:.0f}% of values are missing — "
                "results may be skewed by incomplete data."
            )

        profile = {
            "column": col,
            "mean": s.mean() if len(s) else float("nan"),
            "median": s.median() if len(s) else float("nan"),
            "std": s.std() if len(s) > 1 else float("nan"),
            "min": s.min() if len(s) else float("nan"),
            "max": s.max() if len(s) else float("nan"),
            "nulls": nulls,
            "null_pct": null_pct,
            "skew": skew_val,
            "skew_label": skew_lbl,
            "note": " ".join(notes),
        }
        results["numeric"].append(profile)

        if not silent:
            con.print(f"  [bold cyan]{col}[/bold cyan]")
            con.print(
                f"    Mean: {fmt_num(profile['mean'])} | "
                f"Median: {fmt_num(profile['median'])} | "
                f"Std Dev: {fmt_num(profile['std'])} | "
                f"Min: {fmt_num(profile['min'])} | "
                f"Max: {fmt_num(profile['max'])}"
            )
            con.print(
                f"    Nulls: {profile['nulls']} ({fmt_pct(profile['null_pct'])}) | "
                f"Skew: {profile['skew_label']}"
            )
            if profile["note"]:
                con.print(f"    [dim]Note: {profile['note']}[/dim]")
            con.print()

    # ── Section C — Categorical columns ──────────────────────────────────
    if ct["categorical"] and not silent:
        con.print("[bold bright_white]  CATEGORICAL COLUMNS[/bold bright_white]")
        con.print()

    for col in ct["categorical"]:
        s = df[col]
        unique = s.nunique()
        nulls = int(s.isna().sum())
        null_pct = nulls / len(df) * 100
        top5 = (
            s.value_counts(normalize=True)
            .head(5)
            .items()
        )
        top5_list = [
            {"value": str(v), "pct": round(p * 100, 1)} for v, p in top5
        ]

        profile = {
            "column": col,
            "unique": unique,
            "nulls": nulls,
            "null_pct": null_pct,
            "top5": top5_list,
        }
        results["categorical"].append(profile)

        if not silent:
            top_str = ", ".join(
                f'"{t["value"]}" ({t["pct"]}%)' for t in top5_list
            )
            con.print(f"  [bold cyan]{col}[/bold cyan]")
            con.print(f"    Unique values: {unique} | Nulls: {nulls} ({fmt_pct(null_pct)})")
            con.print(f"    Top 5: {top_str}")
            con.print()

    # ── Section D — Datetime columns ─────────────────────────────────────
    dt_cols = ct["datetime"]
    if dt_cols and not silent:
        con.print("[bold bright_white]  DATETIME COLUMNS[/bold bright_white]")
        con.print()

    for col in dt_cols:
        try:
            ds = pd.to_datetime(df[col], errors="coerce", format="mixed")
        except Exception:
            ds = pd.to_datetime(df[col], errors="coerce")
        valid = ds.dropna().sort_values()

        if len(valid) == 0:
            results["datetime"].append({"column": col, "empty": True})
            continue

        earliest = valid.iloc[0]
        latest = valid.iloc[-1]

        # Peak period
        month_counts = valid.dt.to_period("M").value_counts()
        peak_period = str(month_counts.idxmax()) if len(month_counts) else "N/A"

        # Day pattern
        day_counts = valid.dt.day_name().value_counts()
        if len(day_counts):
            busiest_day = day_counts.index[0]
            busiest_pct = day_counts.iloc[0] / len(valid) * 100
        else:
            busiest_day, busiest_pct = "N/A", 0

        # Gaps
        diffs = valid.diff().dropna()
        max_gap = diffs.max() if len(diffs) else pd.Timedelta(0)
        gap_days = max_gap.days if hasattr(max_gap, "days") else 0

        if gap_days > 1:
            gap_idx = diffs.idxmax()
            gap_start = valid.loc[:gap_idx].iloc[-2] if gap_idx in valid.index else earliest
            gap_end = valid.loc[gap_idx]
            gap_str = (
                f"largest gap: {gap_days} days between "
                f"{gap_start.strftime('%Y-%m-%d')}–{gap_end.strftime('%Y-%m-%d')}"
            )
        else:
            gap_str = "none detected"

        profile = {
            "column": col,
            "earliest": earliest.strftime("%Y-%m-%d"),
            "latest": latest.strftime("%Y-%m-%d"),
            "peak_period": peak_period,
            "busiest_day": busiest_day,
            "busiest_day_pct": busiest_pct,
            "gap_days": gap_days,
            "gap_str": gap_str,
        }
        results["datetime"].append(profile)

        if not silent:
            con.print(f"  [bold cyan]{col}[/bold cyan]")
            con.print(f"    Range      : {profile['earliest']} → {profile['latest']}")
            con.print(f"    Peak period: {profile['peak_period']}")
            con.print(f"    Day pattern: {busiest_day} ({busiest_pct:.0f}% of total)")
            con.print(f"    Gaps       : {gap_str}")
            con.print()

    # ── Section E — Correlation summary ──────────────────────────────────
    num_cols = ct["numeric"]
    corr_pairs: list[dict] = []
    if len(num_cols) >= 2:
        corr_matrix = df[num_cols].corr()
        seen: set[tuple] = set()
        for i, c1 in enumerate(num_cols):
            for j, c2 in enumerate(num_cols):
                if i >= j:
                    continue
                r = corr_matrix.loc[c1, c2]
                if pd.notna(r) and abs(r) > 0.30:
                    pair = (min(c1, c2), max(c1, c2))
                    if pair not in seen:
                        seen.add(pair)
                        direction = "positive" if r > 0 else "negative"
                        note = (
                            f"As {c1} increases, {c2} tends to "
                            f"{'increase' if r > 0 else 'decrease'}."
                        )
                        corr_pairs.append({
                            "col_a": c1, "col_b": c2,
                            "r": round(r, 2), "direction": direction,
                            "note": note,
                        })

    # Sort by absolute r descending
    corr_pairs.sort(key=lambda x: abs(x["r"]), reverse=True)
    results["correlations"] = corr_pairs

    if not silent:
        con.print("[bold bright_white]  CORRELATION SUMMARY[/bold bright_white]")
        con.print()
        if corr_pairs:
            pos = [p for p in corr_pairs if p["direction"] == "positive"]
            neg = [p for p in corr_pairs if p["direction"] == "negative"]
            if pos:
                con.print("  [bold]Top positive pairs:[/bold]")
                for p in pos[:5]:
                    con.print(
                        f"    {p['col_a']} ↔ {p['col_b']}  "
                        f"(r = {p['r']}) — {p['note']}"
                    )
            if neg:
                con.print("  [bold]Top negative pairs:[/bold]")
                for p in neg[:5]:
                    con.print(
                        f"    {p['col_a']} ↔ {p['col_b']}  "
                        f"(r = {p['r']}) — {p['note']}"
                    )
        else:
            con.print("  No strong correlations detected (all |r| < 0.30).")
        con.print()

    if not silent:
        con.print("[green]EDA complete. Results queued for report builder.[/green]")
        con.print(suggest_next(results, "eda"))

    return results
