"""Command [6] — Insight Suggestions Engine: 10 rule-based checks."""

from __future__ import annotations
from typing import TYPE_CHECKING

import pandas as pd
import numpy as np

from ..utils import fmt_num, suggest_next

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


def run_insights(agent: DataAnalystAgentV2) -> dict:
    """Pure rule-based insight engine. Zero LLM reasoning."""
    con = agent.console
    df = agent.df
    ct = agent.col_types

    # If EDA hasn't run, run it silently first
    if agent.results.get("eda") is None:
        from .eda import run_eda
        agent.results["eda"] = run_eda(agent, silent=True)
        agent.session.log("[6] Insights", "", "Silent EDA run for insight rules")

    insights: list[dict] = []
    num = 0

    # ── RULE 01 — SEASONALITY ────────────────────────────────────────────
    for col in ct["datetime"]:
        try:
            dates = pd.to_datetime(df[col], errors="coerce", format="mixed")
        except Exception:
            dates = pd.to_datetime(df[col], errors="coerce")
        valid = dates.dropna()
        if len(valid) < 10:
            continue
        q_counts = valid.dt.quarter.value_counts(normalize=True)
        for q, pct in q_counts.items():
            if pct > 0.40:
                num += 1
                insights.append({
                    "rule": 1,
                    "title": "Seasonality detected",
                    "detail": (
                        f"Q{q} accounts for {pct*100:.0f}% of records in '{col}'. "
                        f"Strong seasonal concentration — other quarters may see a significant dip."
                    ),
                })
                break  # One per column

    # ── RULE 02 — HIGH-VALUE LOW-VOLUME SEGMENT ──────────────────────────
    # Needs a category col + a revenue-like numeric col
    rev_candidates = [c for c in ct["numeric"] if any(k in c.lower() for k in
                      ["revenue", "amount", "sales", "price", "total", "value", "salary", "income", "compensation", "pay", "wage", "earnings"])]
    for cat_col in ct["categorical"]:
        for rev_col in rev_candidates:
            cat_rev = df.groupby(cat_col)[rev_col].sum()
            cat_count = df[cat_col].value_counts()
            if len(cat_rev) < 2:
                continue
            rev_share = cat_rev / cat_rev.sum()
            count_share = cat_count / cat_count.sum()
            for cat_val in rev_share.index:
                if cat_val in count_share.index:
                    rs = rev_share[cat_val]
                    cs = count_share[cat_val]
                    if rs > 2 * cs and rs > 0.15:
                        num += 1
                        insights.append({
                            "rule": 2,
                            "title": "High-value low-volume segment",
                            "detail": (
                                f'"{cat_val}" drives {rs*100:.0f}% of {rev_col} '
                                f'but only {cs*100:.0f}% of orders. '
                                f'High-value, low-frequency — treat as a premium segment.'
                            ),
                        })
                        break
            if insights and insights[-1]["rule"] == 2:
                break
        if insights and insights[-1]["rule"] == 2:
            break

    # ── RULE 03 — SINGLE-PURCHASE CUSTOMERS ──────────────────────────────
    id_candidates = [c for c in df.columns if any(k in c.lower() for k in
                     ["customer", "user", "client", "buyer"])]
    for id_col in id_candidates:
        order_counts = df[id_col].value_counts()
        single = (order_counts == 1).sum()
        total_cust = len(order_counts)
        if total_cust > 0 and single / total_cust > 0.20:
            num += 1
            pct = single / total_cust * 100
            insights.append({
                "rule": 3,
                "title": "Single-purchase customers",
                "detail": (
                    f"{pct:.0f}% of customers in '{id_col}' made only one purchase. "
                    f"High churn risk — a retention campaign could significantly lift LTV."
                ),
            })
            break

    # ── RULE 04 — CUSTOMER CONCENTRATION ─────────────────────────────────
    for id_col in id_candidates:
        for rev_col in rev_candidates:
            cust_rev = df.groupby(id_col)[rev_col].sum().sort_values(ascending=False)
            if len(cust_rev) < 10:
                continue
            top10_share = cust_rev.head(10).sum() / cust_rev.sum()
            if top10_share > 0.30:
                num += 1
                insights.append({
                    "rule": 4,
                    "title": "Customer concentration risk",
                    "detail": (
                        f"Top 10 customers represent {top10_share*100:.0f}% of total {rev_col}. "
                        f"High dependency — losing one key account would hurt significantly."
                    ),
                })
                break
        if insights and insights[-1]["rule"] == 4:
            break

    # ── RULE 05 — DISCOUNT-REVENUE CORRELATION ──────────────────────────
    disc_cols = [c for c in ct["numeric"] if "discount" in c.lower()]
    for dc in disc_cols:
        for rc in rev_candidates:
            valid = df[[dc, rc]].dropna()
            if len(valid) < 10:
                continue
            r = valid[dc].corr(valid[rc])
            if pd.notna(r) and r < -0.50:
                num += 1
                insights.append({
                    "rule": 5,
                    "title": "Discount-revenue negative correlation",
                    "detail": (
                        f"Higher discounts correlate with lower {rc} (r = {r:.2f}). "
                        f"Discounting may not be driving enough volume to compensate."
                    ),
                })
                break

    # ── RULE 06 — WEEKEND/WEEKDAY SKEW ───────────────────────────────────
    for col in ct["datetime"]:
        try:
            dates = pd.to_datetime(df[col], errors="coerce", format="mixed")
        except Exception:
            dates = pd.to_datetime(df[col], errors="coerce")
        valid = dates.dropna()
        if len(valid) < 10:
            continue
        weekday = valid.dt.dayofweek < 5  # Mon-Fri
        wd_pct = weekday.sum() / len(valid) * 100
        if wd_pct > 70:
            num += 1
            insights.append({
                "rule": 6,
                "title": "Weekday-heavy transaction pattern",
                "detail": (
                    f"{wd_pct:.0f}% of transactions in '{col}' occur on weekdays. "
                    f"Weekend activity is negligible — weekend campaigns may not be cost-effective."
                ),
            })
        elif (100 - wd_pct) > 70:
            num += 1
            insights.append({
                "rule": 6,
                "title": "Weekend-heavy transaction pattern",
                "detail": (
                    f"{100-wd_pct:.0f}% of transactions in '{col}' occur on weekends. "
                    f"Weekday activity is low — consider adjusting marketing schedules."
                ),
            })
        break  # One check per datetime col

    # ── RULE 07 — GEOGRAPHIC CONCENTRATION ───────────────────────────────
    from ..utils import detect_geo_columns
    geo_cols = detect_geo_columns(df)
    for gc in geo_cols:
        top2 = df[gc].value_counts(normalize=True).head(2)
        if len(top2) >= 2 and top2.sum() > 0.50:
            num += 1
            city1, city2 = top2.index[0], top2.index[1]
            combined = top2.sum() * 100
            insights.append({
                "rule": 7,
                "title": "Geographic concentration",
                "detail": (
                    f'"{city1}" and "{city2}" account for {combined:.0f}% of rows. '
                    f'Heavy geographic concentration — significant expansion opportunity elsewhere.'
                ),
            })
            break

    # ── RULE 08 — DATE GAPS ──────────────────────────────────────────────
    for col in ct["datetime"]:
        try:
            dates = pd.to_datetime(df[col], errors="coerce", format="mixed")
        except Exception:
            dates = pd.to_datetime(df[col], errors="coerce")
        valid = dates.dropna().sort_values()
        if len(valid) < 5:
            continue
        diffs = valid.diff().dropna()
        max_gap = diffs.max()
        if hasattr(max_gap, "days") and max_gap.days > 30:
            gap_idx = diffs.idxmax()
            gap_end = valid.loc[gap_idx]
            gap_start = valid.loc[:gap_idx].iloc[-2] if len(valid.loc[:gap_idx]) > 1 else valid.iloc[0]
            num += 1
            insights.append({
                "rule": 8,
                "title": "Date gap detected",
                "detail": (
                    f"A {max_gap.days}-day gap detected in '{col}' between "
                    f"{gap_start.strftime('%b %d')} and {gap_end.strftime('%b %d')}. "
                    f"This may indicate missing data, a system outage, or a business pause."
                ),
            })
        break

    # ── RULE 09 — ZERO VALUE ANOMALY ─────────────────────────────────────
    zero_check_cols = [c for c in ct["numeric"] if any(k in c.lower() for k in
                       ["revenue", "price", "amount", "total", "sales", "value", "cost", "salary", "income", "compensation", "pay", "wage", "earnings"])]
    for col in zero_check_cols:
        zero_pct = (df[col] == 0).sum() / len(df) * 100
        if zero_pct > 2:
            num += 1
            insights.append({
                "rule": 9,
                "title": "Zero value anomaly",
                "detail": (
                    f"{zero_pct:.1f}% of '{col}' values are exactly zero. "
                    f"These may be cancellations, errors, or free transactions — worth investigating."
                ),
            })

    # ── RULE 10 — RAPID GROWTH SIGNAL ────────────────────────────────────
    for col in ct["datetime"]:
        try:
            dates = pd.to_datetime(df[col], errors="coerce", format="mixed")
        except Exception:
            dates = pd.to_datetime(df[col], errors="coerce")
        valid = dates.dropna()
        if len(valid) < 10:
            continue
        monthly = valid.dt.to_period("M").value_counts().sort_index()
        if len(monthly) >= 2:
            latest = monthly.iloc[-1]
            previous = monthly.iloc[-2]
            if previous > 0 and latest > 1.5 * previous:
                ratio = latest / previous
                num += 1
                insights.append({
                    "rule": 10,
                    "title": "Rapid growth signal",
                    "detail": (
                        f"{monthly.index[-1]} count is {ratio:.1f}× higher than {monthly.index[-2]}. "
                        f"Strong growth signal — verify it is real and not a data entry spike."
                    ),
                })
        break

    # ── RULE 11 — CATEGORY DOMINANCE ─────────────────────────────────────
    for col in ct["categorical"]:
        counts = df[col].value_counts(normalize=True)
        if len(counts) > 0:
            top_val = counts.index[0]
            top_pct = counts.iloc[0] * 100
            if top_pct > 80:
                num += 1
                insights.append({
                    "rule": 11,
                    "title": f"Dominant category in '{col}'",
                    "detail": (
                        f'"{top_val}" dominates the "{col}" column, accounting for {top_pct:.1f}% of all rows. '
                        f'This indicates extremely low variety or high concentration in this field.'
                    ),
                })

    # ── RULE 12 — SEGMENT AVERAGE OUTLIERS ───────────────────────────────
    for cat_col in ct["categorical"]:
        unique_cats = df[cat_col].dropna().unique()
        if not (2 <= len(unique_cats) <= 15):
            continue
        for num_col in ct["numeric"]:
            if not any(k in num_col.lower() for k in ["revenue", "price", "amount", "total", "sales", "value", "cost", "salary", "income", "compensation", "pay", "wage", "earnings"]):
                continue
            overall_mean = df[num_col].mean()
            if pd.isna(overall_mean) or overall_mean == 0:
                continue
            cat_means = df.groupby(cat_col)[num_col].mean()
            for cat_val, cat_mean in cat_means.items():
                if pd.isna(cat_mean) or len(df[df[cat_col] == cat_val]) < 5:
                    continue
                ratio = cat_mean / overall_mean
                if ratio > 1.5:
                    num += 1
                    insights.append({
                        "rule": 12,
                        "title": f"High average {num_col} in segment",
                        "detail": (
                            f'"{cat_val}" segment has an average {num_col} of {fmt_num(cat_mean)} '
                            f'({(ratio-1)*100:.0f}% higher than the overall average of {fmt_num(overall_mean)}). '
                            f'This makes it a highly premium or high-cost segment.'
                        ),
                    })
                    break
                elif ratio < 0.5:
                    num += 1
                    insights.append({
                        "rule": 12,
                        "title": f"Low average {num_col} in segment",
                        "detail": (
                            f'"{cat_val}" segment has an average {num_col} of {fmt_num(cat_mean)} '
                            f'({(1-ratio)*100:.0f}% lower than the overall average of {fmt_num(overall_mean)}). '
                            f'This represents a low-yield or lower-cost segment.'
                        ),
                    })
                    break

    # ── Print results ────────────────────────────────────────────────────
    con.print()
    if insights:
        for i, ins in enumerate(insights, 1):
            con.print(
                f"  💡 Insight {i} — {ins['title']}\n"
                f"     {ins['detail']}"
            )
            con.print()
    else:
        con.print(
            "  No strong patterns detected across all checks.\n"
            "  The data appears evenly distributed."
        )
        con.print()

    con.print(f"[green]Insight scan complete. {len(insights)} insights queued for report builder.[/green]")
    con.print(suggest_next({"insights": insights}, "insights"))

    return {"insights": insights, "count": len(insights)}
