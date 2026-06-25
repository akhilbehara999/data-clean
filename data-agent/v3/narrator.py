# -*- coding: utf-8 -*-
"""Narrator — converts raw V2 result dicts into plain-English markdown."""

from __future__ import annotations
import pandas as pd
from v2.utils import fmt_num


def narrate_eda(results: dict, col_types: dict) -> str:
    overview = results.get("overview", {})
    rows, cols = overview.get("rows", 0), overview.get("columns", 0)
    lines = [
        "### 📊 Dataset Profile", "",
        f"**{rows:,} rows × {cols} columns** — "
        f"{len(col_types.get('numeric',[]))} numeric, "
        f"{len(col_types.get('categorical',[]))} categorical, "
        f"{len(col_types.get('datetime',[]))} datetime.",
    ]
    for p in results.get("numeric", [])[:3]:
        lines.append(f"- **{p['column']}**: mean {fmt_num(p['mean'])}, range {fmt_num(p['min'])}–{fmt_num(p['max'])}")
    for p in results.get("categorical", [])[:3]:
        top = p["top5"][0]["value"] if p.get("top5") else "—"
        lines.append(f"- **{p['column']}**: {p['unique']} unique, top: \"{top}\"")
    for c in results.get("correlations", [])[:2]:
        lines.append(f"- Correlation: {c['col_a']} ↔ {c['col_b']} (r={c['r']})")
    lines += ["", "*What would you like to dig into?*"]
    return "\n".join(lines)


def narrate_relationships(results: dict) -> str:
    lines = ["### 🔗 Relationship Analysis", ""]
    corrs = results.get("correlations", [])
    if corrs:
        for c in corrs:
            s = "strong" if abs(c["r"]) > 0.7 else "moderate"
            lines.append(f"- **{c['col_a']}** ↔ **{c['col_b']}** (r={c['r']}) — {s}")
    else:
        lines.append("No strong correlations detected.")
    for r in results.get("redundant", []):
        lines.append(f"- ⚠ **{r['derived']}** may be derivable from **{r['source']}**")
    lines += ["", "*Compare two columns, or run insights?*"]
    return "\n".join(lines)


def narrate_insights(results: dict) -> str:
    count = results.get("count", 0)
    insights = results.get("insights", [])
    lines = [f"### 💡 {count} Insight(s) Found", ""]
    if not insights:
        lines.append("No significant patterns detected.")
    else:
        for i, ins in enumerate(insights[:5], 1):
            lines.append(f"**{i}. {ins['title']}** — {ins['detail']}")
            lines.append("")
    lines.append("*Which insight to explore further?*")
    return "\n".join(lines)


def narrate_column_detail(col: str, df: pd.DataFrame, col_types: dict) -> str:
    s = df[col].dropna()
    total = len(df)
    lines = [f"### 📋 Column: **{col}**", ""]
    col_type = next((t for t, cs in col_types.items() if col in cs), "unknown")
    lines.append(f"- **Type**: {col_type}  |  **Non-null**: {len(s):,}/{total:,}  |  **Unique**: {s.nunique():,}")
    if pd.api.types.is_numeric_dtype(df[col]):
        lines.append(f"- Mean: {fmt_num(s.mean())} | Median: {fmt_num(s.median())} | Std: {fmt_num(s.std())} | Range: {fmt_num(s.min())}–{fmt_num(s.max())}")
    else:
        for val, cnt in s.value_counts().head(5).items():
            lines.append(f"- `\"{val}\"`: {cnt:,} ({cnt/total*100:.1f}%)")
    lines += ["", "*Pivot on this column, or compare segments?*"]
    return "\n".join(lines)


def narrate_geographic(results: dict) -> str:
    lines = ["### 🌍 Geographic Breakdown", ""]
    for row in results.get("breakdown", [])[:8]:
        lines.append(f"- **{row['region']}**: {row['rows']:,} rows ({row['pct']}%)")
    lines += ["", "*Compare two regions?*"]
    return "\n".join(lines)


def narrate_general_greeting() -> str:
    return ("I'm your AI data analyst with full context of your dataset.\n\n"
            "Try: *\"summarize the data\"*, *\"show price by city\"*, "
            "*\"compare A vs B\"*, or *\"write a summary for my manager\"*")


def narrate_ambiguous(query: str, columns: list[str]) -> str:
    sample = ", ".join(f"**{c}**" for c in columns[:3])
    return (f"I'm not sure what you mean. Try:\n"
            f"1. *\"run eda\"* — profile the dataset\n"
            f"2. Mention a column: {sample}\n"
            f"3. *\"find insights\"* — scan for patterns\n"
            f"4. *\"compare X vs Y\"* — segment comparison")
