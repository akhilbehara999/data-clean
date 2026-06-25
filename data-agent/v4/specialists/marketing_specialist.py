# -*- coding: utf-8 -*-
"""Marketing Specialist — Feature 7."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from .base_specialist import BaseSpecialist, Finding


class MarketingSpecialist(BaseSpecialist):

    name = "marketing"
    domain = "marketing analytics"

    def applicable_rules(self, df: pd.DataFrame, column_types: dict) -> list[str]:
        rules = []
        if self._find_col(df, ["channel", "campaign", "source", "medium"]):
            rules.append("channel_acquisition_cost")
            rules.append("repeat_purchase_by_channel")
        if self._find_col(df, ["funnel", "stage", "step", "conversion", "click", "view", "purchase"]):
            rules.append("funnel_dropoff")
        if self._find_col(df, ["date", "month", "week", "period"]):
            rules.append("campaign_seasonality")
        if self._find_col(df, ["segment", "customer_type", "tier", "category"]):
            rules.append("high_engagement_low_conversion")
        return rules

    def check_required_columns(self, df: pd.DataFrame) -> list[str]:
        warnings = []
        if not self._find_col(df, ["channel", "campaign", "source"]):
            warnings.append(
                "Marketing specialist works best with a channel/campaign column "
                "for acquisition cost and repeat purchase analysis."
            )
        return warnings

    def run(self, df: pd.DataFrame) -> list[Finding]:
        findings = []

        channel_col = self._find_col(df, ["channel", "source", "medium", "campaign"])
        cost_col = self._find_col(df, ["cost", "spend", "budget", "cpc"])
        revenue_col = self._find_col(df, ["revenue", "sales", "value", "amount"])
        customer_col = self._find_col(df, ["customer", "user", "id", "buyer"])
        ts_col = self._find_col(df, ["date", "month", "week", "created_at"])

        # Rule 1: Channel cost-per-acquisition
        if channel_col and cost_col and customer_col:
            finding = self._check_channel_cpa(df, channel_col, cost_col, customer_col)
            if finding:
                findings.append(finding)

        # Rule 2: Repeat purchase by channel
        if channel_col and customer_col:
            finding = self._check_repeat_purchase(df, channel_col, customer_col)
            if finding:
                findings.append(finding)

        # Rule 3: Campaign seasonality
        if channel_col and ts_col and revenue_col:
            finding = self._check_seasonality(df, ts_col, channel_col, revenue_col)
            if finding:
                findings.append(finding)

        # Rule 4: High engagement / low revenue segments
        if channel_col and revenue_col:
            finding = self._check_high_engagement_low_value(df, channel_col, revenue_col)
            if finding:
                findings.append(finding)

        return findings

    def _check_channel_cpa(self, df, channel_col, cost_col, customer_col) -> Optional[Finding]:
        try:
            costs = pd.to_numeric(df[cost_col], errors="coerce")
            grouped = df.groupby(channel_col).agg(
                total_cost=(cost_col, lambda x: pd.to_numeric(x, errors="coerce").sum()),
                customer_count=(customer_col, "nunique"),
            ).reset_index()
            grouped["cpa"] = grouped["total_cost"] / grouped["customer_count"].replace(0, np.nan)
            grouped = grouped.dropna(subset=["cpa"]).sort_values("cpa")

            if len(grouped) < 2:
                return None

            best = grouped.iloc[0]
            worst = grouped.iloc[-1]
            ratio = worst["cpa"] / best["cpa"] if best["cpa"] > 0 else 0

            if ratio < 2:
                return None

            return Finding(
                rule_name="channel_acquisition_cost",
                description=(
                    f"Cost-per-acquisition varies {ratio:.1f}× across channels: "
                    f"'{best[channel_col]}' is most efficient at {best['cpa']:,.0f}/customer, "
                    f"vs '{worst[channel_col]}' at {worst['cpa']:,.0f}/customer."
                ),
                severity="high" if ratio > 5 else "medium",
                affected_rows=int(len(df)),
                columns_involved=[channel_col, cost_col, customer_col],
            )
        except Exception:
            return None

    def _check_repeat_purchase(self, df, channel_col, customer_col) -> Optional[Finding]:
        try:
            purchase_counts = df.groupby([customer_col, channel_col]).size().reset_index(name="orders")
            repeat_by_channel = (
                purchase_counts[purchase_counts["orders"] > 1]
                .groupby(channel_col)[customer_col].count()
            )
            total_by_channel = df.groupby(channel_col)[customer_col].nunique()
            repeat_rate = (repeat_by_channel / total_by_channel * 100).dropna()

            if len(repeat_rate) < 2:
                return None

            best = repeat_rate.idxmax()
            worst = repeat_rate.idxmin()

            if repeat_rate[best] - repeat_rate[worst] < 10:
                return None

            return Finding(
                rule_name="repeat_purchase_by_channel",
                description=(
                    f"Repeat purchase rate varies widely by channel: "
                    f"'{best}' ({repeat_rate[best]:.1f}% repeat) vs "
                    f"'{worst}' ({repeat_rate[worst]:.1f}% repeat). "
                    f"Consider retargeting or loyalty programs for low-repeat channels."
                ),
                severity="medium",
                affected_rows=int(len(df)),
                columns_involved=[channel_col, customer_col],
            )
        except Exception:
            return None

    def _check_seasonality(self, df, ts_col, channel_col, revenue_col) -> Optional[Finding]:
        try:
            df = df.copy()
            df["_ts"] = pd.to_datetime(df[ts_col], errors="coerce")
            df["_month"] = df["_ts"].dt.month
            rev = pd.to_numeric(df[revenue_col], errors="coerce")
            df["_rev"] = rev
            monthly = df.groupby("_month")["_rev"].sum()
            if len(monthly) < 3:
                return None
            peak_month = monthly.idxmax()
            low_month = monthly.idxmin()
            ratio = monthly[peak_month] / monthly[low_month] if monthly[low_month] > 0 else 0
            if ratio < 1.5:
                return None

            import calendar
            peak_name = calendar.month_abbr[peak_month]
            low_name = calendar.month_abbr[low_month]

            return Finding(
                rule_name="campaign_seasonality",
                description=(
                    f"Revenue peaks in {peak_name} ({monthly[peak_month]:,.0f}) and troughs "
                    f"in {low_name} ({monthly[low_month]:,.0f}) — a {ratio:.1f}× seasonal swing. "
                    f"Campaign budgeting may benefit from this seasonality pattern."
                ),
                severity="low",
                affected_rows=int(len(df)),
                columns_involved=[ts_col, revenue_col],
            )
        except Exception:
            return None

    def _check_high_engagement_low_value(self, df, channel_col, revenue_col) -> Optional[Finding]:
        try:
            rev = pd.to_numeric(df[revenue_col], errors="coerce")
            ch_stats = df.groupby(channel_col).agg(
                count=(channel_col, "size"),
                avg_rev=(revenue_col, lambda x: pd.to_numeric(x, errors="coerce").mean()),
            )
            high_vol = ch_stats[ch_stats["count"] > ch_stats["count"].quantile(0.6)]
            low_val = high_vol[high_vol["avg_rev"] < high_vol["avg_rev"].quantile(0.4)]

            if len(low_val) == 0:
                return None

            channels = low_val.index.tolist()[:3]
            desc_parts = [f"'{c}' ({low_val.loc[c,'count']:,} interactions, avg ₹{low_val.loc[c,'avg_rev']:,.0f})" for c in channels]
            return Finding(
                rule_name="high_engagement_low_conversion",
                description=(
                    f"High-volume channels with low average revenue (potential funnel drop-off): "
                    f"{'; '.join(desc_parts)}."
                ),
                severity="medium",
                affected_rows=int(low_val["count"].sum()),
                columns_involved=[channel_col, revenue_col],
            )
        except Exception:
            return None
