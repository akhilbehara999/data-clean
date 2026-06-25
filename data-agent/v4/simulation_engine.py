# -*- coding: utf-8 -*-
"""
Feature 5 — What-If Simulation Engine.

Available in V3 chat mode ("what if...") and as /simulate in V2.
All results are explicitly labelled as ESTIMATES.
"""

from __future__ import annotations

import re
import datetime
from typing import Optional

import pandas as pd
import numpy as np
from rich.console import Console
from rich.markdown import Markdown

console = Console(force_terminal=True)

# ── Intent detection ──────────────────────────────────────────────────────────

TRIGGER_PHRASES = [
    "what if", "suppose", "if we changed", "projected impact of",
    "if we increased", "if we decreased", "if we removed", "if we stopped",
    "if we only kept", "if we filtered", "impact of",
]

INCREASE_WORDS = {"increase","raise","hike","grow","boost","add"}
DECREASE_WORDS = {"decrease","reduce","drop","cut","lower","shrink","remove"}


def is_simulation_query(query: str) -> bool:
    q = query.lower()
    return any(phrase in q for phrase in TRIGGER_PHRASES)


# ── Column detection helpers ──────────────────────────────────────────────────

def _find_col(query: str, df: pd.DataFrame, col_types: dict) -> Optional[str]:
    """Find the most likely column referenced in a simulation query."""
    q = query.lower()
    # Try exact match against column names
    for col in sorted(df.columns, key=len, reverse=True):
        if col.lower() in q:
            return col
    # Try numeric cols for price/value simulations
    for col in col_types.get("numeric", []):
        keywords = ["price", "revenue", "value", "cost", "amount", "sales", "profit"]
        if any(kw in col.lower() for kw in keywords) and any(kw in q for kw in keywords):
            return col
    return None


def _parse_pct(query: str) -> Optional[float]:
    """Extract percentage from a query like 'increased by 10%'."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", query)
    if m:
        return float(m.group(1))
    m = re.search(r"by\s+(\d+(?:\.\d+)?)", query)
    if m:
        return float(m.group(1))
    return None


def _parse_threshold(query: str) -> Optional[float]:
    """Extract threshold value like '> 3 orders', '> 500'."""
    m = re.search(r"[>>=<]{1,2}\s*(\d+(?:\.\d+)?)", query)
    if m:
        return float(m.group(1))
    m = re.search(r"more than\s+(\d+)", query, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _parse_segment(query: str, df: pd.DataFrame, col_types: dict) -> Optional[tuple[str, str]]:
    """Return (column, value) for a segment-removal/filter query."""
    q = query.lower()
    for col in col_types.get("categorical", []):
        vals = df[col].dropna().unique()
        for val in vals:
            if str(val).lower() in q:
                return col, str(val)
    return None


# ── Simulation types ──────────────────────────────────────────────────────────

def _simulate_price_change(
    df: pd.DataFrame,
    col: str,
    pct: float,
    col_types: dict,
    session_dict: dict,
) -> str:
    """Simulate revenue impact of a price/value change by pct%."""
    if col not in df.columns:
        return f"⚠ Column '{col}' not found in dataset."

    s = df[col].dropna()
    # Handle case where all values are NaN
    if len(s) == 0:
        return f"⚠ Column '{col}' contains no valid numeric data for simulation."

    original_sum = s.sum()
    original_mean = s.mean()
    multiplier = 1 + pct / 100

    new_sum = original_sum * multiplier
    new_mean = original_mean * multiplier
    currency = "₹" if any(c in col.lower() for c in ["revenue", "sales", "amount", "price", "profit"]) else ""

    # Try to estimate elasticity from historical price variation
    price_std = s.std()
    # Avoid division by zero - if mean is 0, variation percentage is 0
    price_variation_pct = price_std / original_mean * 100 if original_mean != 0 else 0
    has_elasticity = price_variation_pct > 10  # only meaningful if >10% variation

    direction = "increase" if pct > 0 else "decrease"
    abs_pct = abs(pct)

    lines = [
        f"**What-if: {direction} '{col}' by {abs_pct}%** *(estimate)*",
        "",
        f"| Metric | Current | Projected |",
        f"|--------|---------|-----------|",
        f"| Total '{col}' | {currency}{original_sum:,.0f} | {currency}{new_sum:,.0f} |",
        f"| Mean '{col}' | {currency}{original_mean:,.2f} | {currency}{new_mean:,.2f} |",
        f"| Change | — | {'+' if pct > 0 else ''}{pct:.1f}% |",
    ]

    if has_elasticity:
        # Very rough linear elasticity estimate
        # (If price varied by price_variation_pct and volume is the row count,
        #  we can't actually estimate demand elasticity from mean alone — say so)
        lines += [
            "",
            f"**Note on volume effect:** Your data shows {price_variation_pct:.1f}% price variation "
            f"historically. Estimating demand elasticity from a single column mean is unreliable "
            f"without paired volume-over-time data. The numbers above assume **volume stays constant**.",
        ]
    else:
        lines += [
            "",
            f"⚠ Your price data doesn't show enough historical variation to estimate "
            f"how volume would respond. The projection above **assumes volume stays constant**.",
        ]

    lines += [
        "",
        "> ⚠ **This is a simple estimate**, not a forecast. Real-world response may differ "
        "due to competition, seasonality, or other factors not in this data.",
    ]

    result_text = "\n".join(lines)

    # Log to session
    _log_simulation(session_dict, {
        "type": "price_change",
        "column": col,
        "pct": pct,
        "original_total": float(original_sum),
        "projected_total": float(new_sum),
        "assumption": "volume constant",
    })

    return result_text


def _simulate_segment_removal(
    df: pd.DataFrame,
    col: str,
    value: str,
    col_types: dict,
    session_dict: dict,
) -> str:
    """Simulate removing a segment from the dataset."""
    if col not in df.columns:
        return f"⚠ Column '{col}' not found."

    total_rows = len(df)
    segment_df = df[df[col].astype(str).str.lower() == value.lower()]
    seg_rows = len(segment_df)
    seg_pct = seg_rows / total_rows * 100 if total_rows > 0 else 0

    lines = [
        f"**What-if: Remove segment '{value}' from '{col}'** *(estimate)*",
        "",
        f"| Metric | Current | After Removal |",
        f"|--------|---------|---------------|",
        f"| Row count | {total_rows:,} | {total_rows - seg_rows:,} |",
        f"| '{value}' rows | {seg_rows:,} ({seg_pct:.1f}%) | 0 |",
    ]

    # Revenue / numeric contribution
    for num_col in col_types.get("numeric", [])[:3]:
        if num_col in df.columns:
            total_val = df[num_col].sum()
            seg_val = segment_df[num_col].sum()
            pct = seg_val / total_val * 100 if total_val != 0 else 0
            lines.append(
                f"| '{num_col}' | {total_val:,.0f} | {total_val - seg_val:,.0f} "
                f"(-{pct:.1f}%) |"
            )

    lines += [
        "",
        "> ⚠ This is a **direct subtraction**, not accounting for any knock-on effects "
        "on other segments (e.g. cross-selling, referral revenue).",
        "",
        "> ⚠ **Estimate only** — not a business forecast.",
    ]

    result_text = "\n".join(lines)
    _log_simulation(session_dict, {
        "type": "segment_removal",
        "column": col,
        "value": value,
        "seg_rows": int(seg_rows),
        "seg_pct": float(seg_pct),
    })
    return result_text


def _simulate_threshold_filter(
    df: pd.DataFrame,
    col: str,
    threshold: float,
    col_types: dict,
    session_dict: dict,
) -> str:
    """Simulate focusing on rows where col > threshold."""
    if col not in df.columns:
        return f"⚠ Column '{col}' not found."

    filtered_df = df[df[col] > threshold]
    orig_rows = len(df)
    filt_rows = len(filtered_df)
    pct_rows = filt_rows / orig_rows * 100 if orig_rows > 0 else 0

    lines = [
        f"**What-if: Focus on rows where '{col}' > {threshold}** *(estimate)*",
        "",
        f"| Metric | Full Dataset | Filtered |",
        f"|--------|-------------|---------|",
        f"| Row count | {orig_rows:,} | {filt_rows:,} ({pct_rows:.0f}%) |",
    ]

    for num_col in col_types.get("numeric", [])[:4]:
        if num_col in df.columns and num_col != col:
            orig_val = df[num_col].sum()
            filt_val = filtered_df[num_col].sum()
            pct = filt_val / orig_val * 100 if orig_val != 0 else 0
            lines.append(
                f"| '{num_col}' total | {orig_val:,.0f} | {filt_val:,.0f} ({pct:.0f}%) |"
            )
        elif num_col in df.columns:
            orig_mean = df[num_col].mean()
            filt_mean = filtered_df[num_col].mean() if len(filtered_df) > 0 else 0
            lines.append(
                f"| '{num_col}' avg | {orig_mean:,.2f} | {filt_mean:,.2f} |"
            )

    lines += [
        "",
        "> ⚠ **Estimate** — based on direct data filter, no behavioral assumptions.",
    ]

    result_text = "\n".join(lines)
    _log_simulation(session_dict, {
        "type": "threshold_filter",
        "column": col,
        "threshold": threshold,
        "filtered_rows": int(filt_rows),
        "pct": float(pct_rows),
    })
    return result_text


# ── Session logging ───────────────────────────────────────────────────────────

def _log_simulation(session_dict: dict, entry: dict) -> None:
    """Log simulation entry to session.simulation_log."""
    sim_log = session_dict.setdefault("simulation_log", [])
    entry["timestamp"] = datetime.datetime.now().isoformat()
    sim_log.append(entry)


# ── Main dispatch ─────────────────────────────────────────────────────────────

def run_simulation(query: str, df: pd.DataFrame, col_types: dict, session_dict: dict) -> str:
    """
    Parse a natural language simulation query and return a Markdown result string.
    """
    q = query.lower()

    # Detect type
    # A) Price/value change
    pct = _parse_pct(query)
    if pct is not None and any(w in q for w in INCREASE_WORDS.union(DECREASE_WORDS)):
        col = _find_col(query, df, col_types)
        if col:
            signed_pct = pct if any(w in q for w in INCREASE_WORDS) else -pct
            return _simulate_price_change(df, col, signed_pct, col_types, session_dict)
        # Try any numeric column
        num_cols = col_types.get("numeric", [])
        if num_cols:
            return _simulate_price_change(df, num_cols[0], pct, col_types, session_dict)

    # B) Segment removal / stopping selling to
    seg = _parse_segment(query, df, col_types)
    if seg and any(kw in q for kw in ["remove", "stop", "without", "exclude", "drop"]):
        col, value = seg
        return _simulate_segment_removal(df, col, value, col_types, session_dict)

    # C) Threshold filter
    threshold = _parse_threshold(query)
    if threshold is not None and any(kw in q for kw in ["kept", "keep", "only", "filter", "orders", "customers"]):
        col = _find_col(query, df, col_types)
        if col is None:
            # Guess an order/count column
            for c in df.columns:
                if any(kw in c.lower() for kw in ["order", "count", "quantity", "freq"]):
                    col = c
                    break
        if col:
            return _simulate_threshold_filter(df, col, threshold, col_types, session_dict)

    # Fallback
    return (
        "**Simulation:** I wasn't able to determine the specific what-if scenario from your query.\n\n"
        "Try phrasing like:\n"
        "- *'what if we increased [column] by 10%'*\n"
        "- *'what if we stopped selling to [segment value]'*\n"
        "- *'what if we only kept customers with > 3 orders'*\n\n"
        "> ⚠ All simulation results are estimates only."
    )
