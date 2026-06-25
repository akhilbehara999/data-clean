# -*- coding: utf-8 -*-
"""
Fraud Specialist — Feature 7.

Applies fraud-specific statistical rules on top of v2's general insights.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from .base_specialist import BaseSpecialist, Finding


# Common thresholds
_THRESHOLD_AMOUNTS = [50_000, 10_000, 20_000, 100_000, 1_000, 5_000]  # INR common reporting
_THRESHOLD_PCT = 0.05    # within 5% of a threshold = suspicious
_NIGHT_START = 23        # 11PM
_NIGHT_END = 4           # 4AM
_NIGHT_CLUSTER_PCT = 0.30
_FREQ_MULTIPLIER = 3.0   # flag if account frequency > 3× own average
_ROUND_NUMBER_PCT = 0.15 # flag if >15% of transactions are round numbers


class FraudSpecialist(BaseSpecialist):

    name = "fraud"
    domain = "fraud detection"

    def applicable_rules(self, df: pd.DataFrame, column_types: dict) -> list[str]:
        rules = ["threshold_structuring", "round_number_clustering"]
        if self._find_col(df, ["timestamp", "date", "time", "created_at", "datetime"]):
            rules += ["time_of_day_clustering", "frequency_spike"]
        return rules

    def check_required_columns(self, df: pd.DataFrame) -> list[str]:
        warnings = []
        if not self._find_col(df, ["timestamp", "date", "time", "created_at", "datetime"]):
            warnings.append(
                "Fraud specialist needs a timestamp column to check for time clustering "
                "— I don't see one. I can still run threshold and round-number checks."
            )
        if not self._find_col(df, ["amount", "value", "price", "revenue", "cost", "transaction"]):
            warnings.append(
                "Fraud specialist needs an amount/value column to check for threshold structuring."
            )
        return warnings

    def run(self, df: pd.DataFrame) -> list[Finding]:
        findings = []

        amount_col = self._find_col(df, ["amount", "value", "price", "revenue", "cost", "transaction"])
        id_col = self._find_col(df, ["account", "user", "customer", "id", "entity"])
        ts_col = self._find_col(df, ["timestamp", "date", "time", "created_at", "datetime"])

        # Rule 1: Threshold structuring (transactions just under reporting thresholds)
        if amount_col:
            finding = self._check_threshold_structuring(df, amount_col, id_col)
            if finding:
                findings.append(finding)

        # Rule 2: Time-of-day clustering
        if ts_col and id_col:
            finding = self._check_time_clustering(df, ts_col, id_col)
            if finding:
                findings.append(finding)

        # Rule 3: Frequency spikes
        if ts_col and id_col:
            finding = self._check_frequency_spike(df, ts_col, id_col)
            if finding:
                findings.append(finding)

        # Rule 4: Round-number concentration
        if amount_col:
            finding = self._check_round_numbers(df, amount_col, id_col)
            if finding:
                findings.append(finding)

        return findings

    # ── Rule implementations ──────────────────────────────────────────────────

    def _check_threshold_structuring(
        self, df: pd.DataFrame, amount_col: str, id_col: Optional[str]
    ) -> Optional[Finding]:
        s = pd.to_numeric(df[amount_col], errors="coerce").dropna()
        if len(s) == 0:
            return None

        flagged_rows = []
        for threshold in _THRESHOLD_AMOUNTS:
            lower = threshold * (1 - _THRESHOLD_PCT)
            mask = (s >= lower) & (s < threshold)
            flagged_rows.extend(s[mask].index.tolist())

        unique_flagged = list(set(flagged_rows))
        if not unique_flagged:
            return None

        pct = len(unique_flagged) / len(df) * 100
        sample_vals = s.loc[unique_flagged[:5]].tolist()

        return Finding(
            rule_name="threshold_structuring",
            description=(
                f"{len(unique_flagged):,} transactions ({pct:.1f}%) are just under "
                f"common reporting thresholds ({', '.join(f'₹{t:,}' for t in _THRESHOLD_AMOUNTS[:3])}...). "
                f"Sample values: {[f'₹{v:,.0f}' for v in sample_vals]}"
            ),
            severity="high",
            affected_rows=len(unique_flagged),
            columns_involved=[amount_col],
            sample_values=sample_vals,
        )

    def _check_time_clustering(
        self, df: pd.DataFrame, ts_col: str, id_col: str
    ) -> Optional[Finding]:
        try:
            ts = pd.to_datetime(df[ts_col], errors="coerce")
        except Exception:
            return None

        valid = ts.dropna()
        if len(valid) < 10:
            return None

        hours = valid.dt.hour
        night_mask = (hours >= _NIGHT_START) | (hours < _NIGHT_END)
        night_indices = valid[night_mask].index

        # Check if any entity has >30% of their transactions at night
        if id_col not in df.columns:
            return None

        flagged_accounts = []
        for acct, grp in df.groupby(id_col):
            acct_nights = grp.index.intersection(night_indices)
            if len(grp) >= 5 and len(acct_nights) / len(grp) > _NIGHT_CLUSTER_PCT:
                flagged_accounts.append((acct, len(acct_nights), len(grp)))

        if not flagged_accounts:
            return None

        desc_parts = [f"'{a}' ({n}/{total} txns late night)" for a, n, total in flagged_accounts[:3]]
        return Finding(
            rule_name="time_of_day_clustering",
            description=(
                f"{len(flagged_accounts)} account(s) have >30% of transactions between "
                f"11PM–4AM: {', '.join(desc_parts)}"
            ),
            severity="high" if len(flagged_accounts) > 3 else "medium",
            affected_rows=sum(t for _, n, t in flagged_accounts),
            columns_involved=[ts_col, id_col],
        )

    def _check_frequency_spike(
        self, df: pd.DataFrame, ts_col: str, id_col: str
    ) -> Optional[Finding]:
        if id_col not in df.columns:
            return None

        try:
            df = df.copy()
            df["_ts"] = pd.to_datetime(df[ts_col], errors="coerce")
            df = df.dropna(subset=["_ts"])
        except Exception:
            return None

        if len(df) < 20:
            return None

        # Group by account and compute weekly frequency
        df["_week"] = df["_ts"].dt.isocalendar().week
        weekly_counts = df.groupby([id_col, "_week"]).size().reset_index(name="count")
        acct_avg = weekly_counts.groupby(id_col)["count"].mean()
        acct_max = weekly_counts.groupby(id_col)["count"].max()

        flagged = []
        for acct in acct_avg.index:
            avg = acct_avg[acct]
            max_val = acct_max[acct]
            if avg > 0 and max_val > avg * _FREQ_MULTIPLIER:
                flagged.append((acct, max_val, avg))

        if not flagged:
            return None

        desc_parts = [f"'{a}' (peak {p:.0f} vs avg {av:.1f}/week)" for a, p, av in flagged[:3]]
        return Finding(
            rule_name="frequency_spike",
            description=(
                f"{len(flagged)} account(s) show transaction frequency >3× their own historical "
                f"average in a short window: {', '.join(desc_parts)}"
            ),
            severity="high",
            affected_rows=len(flagged),
            columns_involved=[ts_col, id_col],
        )

    def _check_round_numbers(
        self, df: pd.DataFrame, amount_col: str, id_col: Optional[str]
    ) -> Optional[Finding]:
        s = pd.to_numeric(df[amount_col], errors="coerce").dropna()
        if len(s) < 20:
            return None

        # Round numbers: divisible by 100, 1000, 500
        round_mask = (s % 100 == 0) | (s % 500 == 0) | (s % 1000 == 0)
        round_pct = round_mask.sum() / len(s)

        if round_pct < _ROUND_NUMBER_PCT:
            return None

        common_rounds = s[round_mask].value_counts().head(5).index.tolist()
        return Finding(
            rule_name="round_number_clustering",
            description=(
                f"{round_mask.sum():,} transactions ({round_pct*100:.1f}%) are round numbers "
                f"(e.g. {[f'₹{v:,.0f}' for v in common_rounds[:3]]}). "
                "Disproportionate round-number clustering can indicate fabricated entries."
            ),
            severity="medium",
            affected_rows=int(round_mask.sum()),
            columns_involved=[amount_col],
            sample_values=common_rounds,
        )
