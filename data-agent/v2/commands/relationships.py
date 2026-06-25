"""Command [2] — Relationship Detection: correlations, redundancy, join keys."""

from __future__ import annotations
from typing import TYPE_CHECKING

import pandas as pd
import numpy as np
from ..utils import suggest_next

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


def run_relationships(agent: DataAnalystAgentV2) -> dict:
    """Run three relationship scans and print results."""
    con = agent.console
    df = agent.df
    ct = agent.col_types

    results: dict = {
        "correlations": [],
        "redundant": [],
        "join_keys": [],
    }

    con.print()
    con.print("[bold bright_white]  GROUP A — STATISTICAL CORRELATIONS[/bold bright_white]")
    con.print()

    # ── Group A — Pearson correlations ───────────────────────────────────
    num_cols = ct["numeric"]
    if len(num_cols) >= 2:
        corr = df[num_cols].corr()
        seen: set[tuple] = set()
        for i, c1 in enumerate(num_cols):
            for j, c2 in enumerate(num_cols):
                if i >= j:
                    continue
                r = corr.loc[c1, c2]
                if pd.notna(r) and abs(r) > 0.30:
                    pair = (min(c1, c2), max(c1, c2))
                    if pair not in seen:
                        seen.add(pair)
                        direction = "increase" if r > 0 else "decrease"
                        note = (
                            f"When {c1} goes up, {c2} tends to {direction}. "
                            f"This {'strong' if abs(r) > 0.7 else 'moderate'} "
                            f"relationship may indicate a shared driver."
                        )
                        entry = {"col_a": c1, "col_b": c2, "r": round(r, 2), "note": note}
                        results["correlations"].append(entry)
                        con.print(f"  {c1} ↔ {c2}  r = {r:.2f}")
                        con.print(f"  [dim]{note}[/dim]")
                        con.print()

        if not results["correlations"]:
            con.print("  No correlations above |r| = 0.30 found.")
            con.print()
    else:
        con.print("  Fewer than 2 numeric columns — correlation analysis skipped.")
        con.print()

    # ── Group B — Redundant columns ──────────────────────────────────────
    con.print("[bold bright_white]  GROUP B — REDUNDANT COLUMNS[/bold bright_white]")
    con.print()

    sample = df[num_cols].head(500) if len(num_cols) >= 2 else pd.DataFrame()
    found_redundant = False

    if len(num_cols) >= 2:
        for i, c1 in enumerate(num_cols):
            for j, c2 in enumerate(num_cols):
                if i >= j:
                    continue
                # Check if c2 ≈ k * c1 (linear relationship)
                s1 = sample[c1].dropna()
                s2 = sample[c2].dropna()
                common = s1.index.intersection(s2.index)
                if len(common) < 10:
                    continue
                s1c, s2c = s1.loc[common], s2.loc[common]
                if (s1c == 0).all():
                    continue
                ratio = s2c / s1c.replace(0, np.nan)
                ratio = ratio.dropna()
                if len(ratio) < 10:
                    continue
                if ratio.std() < 0.01 * abs(ratio.mean()) and ratio.mean() != 0:
                    factor = ratio.mean()
                    entry = {
                        "derived": c2, "source": c1,
                        "factor": round(factor, 4),
                    }
                    results["redundant"].append(entry)
                    found_redundant = True
                    con.print(
                        f"  ⚠ [{c2}] appears derivable from [{c1}] "
                        f"(factor ≈ {factor:.2f})."
                    )
                    con.print(f"  [dim]Check if both columns are needed.[/dim]")
                    con.print()

        # Also check product relationships (a = b * c)
        if len(num_cols) >= 3:
            for i, ca in enumerate(num_cols):
                for j, cb in enumerate(num_cols):
                    for k, cc in enumerate(num_cols):
                        if i == j or i == k or j >= k:
                            continue
                        sa = sample[ca].dropna()
                        sb = sample[cb].dropna()
                        sc = sample[cc].dropna()
                        common = sa.index.intersection(sb.index).intersection(sc.index)
                        if len(common) < 10:
                            continue
                        product = sb.loc[common] * sc.loc[common]
                        diff = (sa.loc[common] - product).abs()
                        if diff.mean() < 0.01 * sa.loc[common].abs().mean():
                            entry = {
                                "derived": ca,
                                "source": f"{cb} × {cc}",
                                "factor": None,
                            }
                            if entry not in results["redundant"]:
                                results["redundant"].append(entry)
                                found_redundant = True
                                con.print(
                                    f"  ⚠ [{ca}] appears derivable from "
                                    f"[{cb} × {cc}]."
                                )
                                con.print(
                                    f"  [dim]Check if both columns are needed.[/dim]"
                                )
                                con.print()

    if not found_redundant:
        con.print("  No redundant column relationships detected.")
        con.print()

    # ── Group C — Join key candidates ────────────────────────────────────
    if hasattr(agent, "batch_files") and agent.batch_files:
        con.print("[bold bright_white]  GROUP C — JOIN KEY CANDIDATES[/bold bright_white]")
        con.print()
        found_keys = False
        primary_cols = set(df.columns)
        for bf in agent.batch_files:
            other_df = bf["df"]
            other_name = bf["filename"]
            shared_cols = primary_cols.intersection(set(other_df.columns))
            for col in shared_cols:
                vals_a = set(df[col].dropna().unique())
                vals_b = set(other_df[col].dropna().unique())
                if not vals_a or not vals_b:
                    continue
                overlap = len(vals_a & vals_b) / max(len(vals_a), len(vals_b))
                if overlap > 0.60:
                    entry = {
                        "column": col,
                        "file_b": other_name,
                        "overlap_pct": round(overlap * 100),
                    }
                    results["join_keys"].append(entry)
                    found_keys = True
                    con.print(
                        f"  ✓ [{col}] exists in both files with "
                        f"{entry['overlap_pct']}% value overlap."
                    )
                    con.print("  [dim]Recommended merge key.[/dim]")
                    con.print()

        if not found_keys:
            con.print("  No join key candidates found across loaded files.")
            con.print()
    # If not in batch mode, skip Group C entirely (per spec)

    con.print("[green]Relationship scan complete. Results queued for report builder.[/green]")
    con.print(suggest_next(results, "relationships"))

    return results
