"""
Phase 3 — Data cleaning executor.

Applies the proposed cleaning actions to a copy of the DataFrame
in the exact order listed in the report.
"""

import os
import re
import warnings

import numpy as np
import pandas as pd

from .models import CleaningAction, InspectionReport
from . import reporter

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")


BOOL_TRUE = {"true", "yes", "y", "1", "t", "on"}
BOOL_FALSE = {"false", "no", "n", "0", "f", "off"}


class DataCleaner:
    """Applies cleaning actions to a DataFrame and saves the result."""

    def __init__(self, df: pd.DataFrame, report: InspectionReport):
        self.df = df.copy()
        self.report = report
        self.steps_done = 0

    def clean(self) -> pd.DataFrame:
        """Execute all cleaning actions in order."""
        for action in self.report.cleaning_actions:
            handler = getattr(self, f"_do_{action.action_type}", None)
            if handler is None:
                reporter.console.print(
                    f"  [yellow]⚠  Step {action.step} skipped — "
                    f"unknown action: {action.action_type}[/yellow]"
                )
                continue
            handler(action)
            reporter.render_step_complete(action)
            self.steps_done += 1
        return self.df

    def save(self) -> str:
        """Save the cleaned DataFrame to the output path."""
        out = self.report.output_path
        os.makedirs(os.path.dirname(out) or "output", exist_ok=True)
        ext = os.path.splitext(out)[1].lower()
        if ext in (".xlsx", ".xls"):
            self.df.to_excel(out, index=False)
        elif ext == ".tsv":
            self.df.to_csv(out, sep="\t", index=False)
        else:
            self.df.to_csv(out, index=False)
        return out

    # ── Action handlers ────────────────────────────────────────────────────

    def _do_remove_duplicates(self, _action: CleaningAction):
        self.df = self.df.drop_duplicates(keep="first").reset_index(drop=True)

    def _do_drop_empty_columns(self, action: CleaningAction):
        cols = action.params.get("columns", [])
        existing = [c for c in cols if c in self.df.columns]
        if existing:
            self.df = self.df.drop(columns=existing)

    def _do_drop_trailing_empty_rows(self, _action: CleaningAction):
        while len(self.df) > 0 and self.df.iloc[-1].isna().all():
            self.df = self.df.iloc[:-1]
        self.df = self.df.reset_index(drop=True)

    def _do_remove_embedded_headers(self, action: CleaningAction):
        indices = action.params.get("row_indices", [])
        if indices:
            self.df = self.df.drop(index=indices).reset_index(drop=True)

    def _do_rename_columns(self, action: CleaningAction):
        renames = action.params.get("renames", {})
        self.df = self.df.rename(columns=renames)

    def _do_drop_column(self, action: CleaningAction):
        col = action.params.get("column")
        if col and col in self.df.columns:
            self.df = self.df.drop(columns=[col])

    def _do_drop_missing_rows(self, action: CleaningAction):
        col = action.params.get("column")
        if col and col in self.df.columns:
            mask = self.df[col].isna()
            if self.df[col].dtype == object:
                mask = mask | self.df[col].astype(str).str.strip().eq("")
            self.df = self.df[~mask].reset_index(drop=True)

    def _do_fill_missing(self, action: CleaningAction):
        col = action.params.get("column")
        val = action.params.get("value", "Unknown")
        if col and col in self.df.columns:
            if self.df[col].dtype == object:
                self.df[col] = self.df[col].fillna(val)
                self.df[col] = self.df[col].replace("", val)
            else:
                self.df[col] = self.df[col].fillna(val)

    def _do_strip_whitespace(self, action: CleaningAction):
        cols = action.params.get("columns", [])
        for col in cols:
            if col in self.df.columns and self.df[col].dtype == object:
                self.df[col] = self.df[col].astype(str).str.strip()
                # Restore NaN that was converted to "nan"
                self.df[col] = self.df[col].replace("nan", np.nan)

    def _do_standardize_casing(self, action: CleaningAction):
        col = action.params.get("column")
        case = action.params.get("case", "title")
        if col and col in self.df.columns and self.df[col].dtype == object:
            if case == "title":
                self.df[col] = self.df[col].astype(str).str.strip().str.title()
            elif case == "lower":
                self.df[col] = self.df[col].astype(str).str.strip().str.lower()
            elif case == "upper":
                self.df[col] = self.df[col].astype(str).str.strip().str.upper()
            self.df[col] = self.df[col].replace("Nan", np.nan)

    def _do_convert_numeric(self, action: CleaningAction):
        col = action.params.get("column")
        if col and col in self.df.columns:
            cleaned = (
                self.df[col]
                .astype(str)
                .str.replace(r"[\$€£¥₹₩₽,\s%]", "", regex=True)
            )
            self.df[col] = pd.to_numeric(cleaned, errors="coerce")

    def _do_unify_dates(self, action: CleaningAction):
        col = action.params.get("column")
        fmt = action.params.get("format", "%Y-%m-%d")
        if col and col in self.df.columns:
            parsed = pd.to_datetime(self.df[col], errors="coerce")
            self.df[col] = parsed.dt.strftime(fmt)
            self.df[col] = self.df[col].replace("NaT", np.nan)

    def _do_standardize_boolean(self, action: CleaningAction):
        col = action.params.get("column")
        if col and col in self.df.columns:
            def _to_bool(val):
                if pd.isna(val):
                    return np.nan
                s = str(val).strip().lower()
                if s in BOOL_TRUE:
                    return True
                if s in BOOL_FALSE:
                    return False
                return val
            self.df[col] = self.df[col].apply(_to_bool)

    def _do_replace_outliers(self, action: CleaningAction):
        col = action.params.get("column")
        if col and col in self.df.columns:
            numeric = pd.to_numeric(self.df[col], errors="coerce")
            mean, std = numeric.mean(), numeric.std()
            if std > 0:
                mask = (numeric - mean).abs() > 3 * std
                self.df.loc[mask, col] = np.nan

    def _do_replace_negatives(self, action: CleaningAction):
        col = action.params.get("column")
        if col and col in self.df.columns:
            numeric = pd.to_numeric(self.df[col], errors="coerce")
            self.df.loc[numeric < 0, col] = np.nan
