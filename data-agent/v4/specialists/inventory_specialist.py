# -*- coding: utf-8 -*-
"""Inventory Specialist — Feature 7."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from .base_specialist import BaseSpecialist, Finding


class InventorySpecialist(BaseSpecialist):

    name = "inventory"
    domain = "inventory management"

    def applicable_rules(self, df: pd.DataFrame, column_types: dict) -> list[str]:
        rules = []
        if self._find_col(df, ["quantity", "qty", "stock", "units"]):
            rules += ["stockout_patterns", "slow_fast_mover"]
        if self._find_col(df, ["date", "week", "month", "period"]) and \
           self._find_col(df, ["quantity", "qty", "stock"]):
            rules.append("reorder_suggestion")
        return rules

    def check_required_columns(self, df: pd.DataFrame) -> list[str]:
        warnings = []
        if not self._find_col(df, ["quantity", "qty", "stock", "units"]):
            warnings.append(
                "Inventory specialist needs a quantity/stock column to analyze stockout patterns."
            )
        return warnings

    def run(self, df: pd.DataFrame) -> list[Finding]:
        findings = []

        qty_col = self._find_col(df, ["quantity", "qty", "stock", "units", "inventory"])
        sku_col = self._find_col(df, ["sku", "product", "item", "name", "code"])
        ts_col = self._find_col(df, ["date", "week", "month", "created_at", "order_date"])
        demand_col = self._find_col(df, ["demand", "orders", "sold", "sales"])

        if qty_col:
            f = self._check_stockouts(df, qty_col, sku_col, demand_col)
            if f:
                findings.append(f)
            f = self._check_slow_fast(df, qty_col, sku_col, ts_col)
            if f:
                findings.append(f)

        if qty_col and ts_col and sku_col:
            f = self._check_reorder(df, qty_col, sku_col, ts_col)
            if f:
                findings.append(f)

        return findings

    def _check_stockouts(self, df, qty_col, sku_col, demand_col) -> Optional[Finding]:
        try:
            qty = pd.to_numeric(df[qty_col], errors="coerce")
            zero_mask = qty == 0

            if zero_mask.sum() == 0:
                return None

            pct = zero_mask.sum() / len(df) * 100
            if pct < 2:
                return None

            zero_df = df[zero_mask]
            skus = []
            if sku_col and sku_col in df.columns:
                skus = zero_df[sku_col].value_counts().head(5).index.tolist()

            desc = (
                f"{zero_mask.sum():,} rows ({pct:.1f}%) show zero quantity/stock"
            )
            if skus:
                desc += f", most common: {skus[:3]}"
            if demand_col and demand_col in df.columns:
                # Check if there's continued demand signal on zero-stock rows
                demand_on_zero = pd.to_numeric(zero_df.get(demand_col, pd.Series(dtype=float)), errors="coerce").sum()
                if demand_on_zero > 0:
                    desc += f" — with {demand_on_zero:,.0f} demand units still showing (possible stockout)"

            return Finding(
                rule_name="stockout_patterns",
                description=desc,
                severity="high" if pct > 10 else "medium",
                affected_rows=int(zero_mask.sum()),
                columns_involved=[qty_col] + ([sku_col] if sku_col else []),
                sample_values=skus[:5],
            )
        except Exception:
            return None

    def _check_slow_fast(self, df, qty_col, sku_col, ts_col) -> Optional[Finding]:
        if not sku_col or sku_col not in df.columns:
            return None
        try:
            qty = pd.to_numeric(df[qty_col], errors="coerce")
            df = df.copy()
            df["_qty"] = qty
            sku_totals = df.groupby(sku_col)["_qty"].sum().sort_values()

            if len(sku_totals) < 4:
                return None

            q25 = sku_totals.quantile(0.25)
            q75 = sku_totals.quantile(0.75)

            slow = sku_totals[sku_totals <= q25].index.tolist()[:3]
            fast = sku_totals[sku_totals >= q75].index.tolist()[:3]

            return Finding(
                rule_name="slow_fast_mover",
                description=(
                    f"Slow-moving items (bottom 25% by volume): {slow}. "
                    f"Fast-moving items (top 25%): {fast}. "
                    f"Consider rebalancing stock levels or clearance strategy for slow movers."
                ),
                severity="low",
                affected_rows=int(len(sku_totals[sku_totals <= q25])),
                columns_involved=[qty_col, sku_col],
            )
        except Exception:
            return None

    def _check_reorder(self, df, qty_col, sku_col, ts_col) -> Optional[Finding]:
        """Suggest reorder points based on historical depletion rate."""
        try:
            df = df.copy()
            df["_qty"] = pd.to_numeric(df[qty_col], errors="coerce")
            df["_ts"] = pd.to_datetime(df[ts_col], errors="coerce")
            df = df.dropna(subset=["_qty", "_ts"])

            if len(df) < 10:
                return None

            # Sort by time, compute daily depletion rate per SKU
            df = df.sort_values("_ts")
            total_days = (df["_ts"].max() - df["_ts"].min()).days
            if total_days < 7:
                return None

            sku_stats = df.groupby(sku_col)["_qty"].agg(["mean", "sum"])
            sku_stats["daily_rate"] = sku_stats["sum"] / total_days
            sku_stats["reorder_at"] = sku_stats["daily_rate"] * 7  # 1-week lead time

            suggestions = sku_stats.nlargest(3, "daily_rate")
            lines = []
            for sku, row in suggestions.iterrows():
                lines.append(
                    f"'{sku}': reorder at ~{row['reorder_at']:.0f} units "
                    f"(depletes ~{row['daily_rate']:.1f}/day)"
                )

            return Finding(
                rule_name="reorder_suggestion",
                description=(
                    "Suggested reorder points based on historical depletion rate "
                    "(assuming 7-day lead time — adjust to your supplier terms): "
                    + "; ".join(lines) + ". "
                    "⚠ These are SUGGESTIONS based on past patterns only."
                ),
                severity="low",
                affected_rows=int(len(df)),
                columns_involved=[qty_col, sku_col, ts_col],
            )
        except Exception:
            return None
