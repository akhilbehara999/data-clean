"""Data quality profiling engine.

Implements a plugin-style detector architecture for checking missing values,
outliers, formatting errors, patterns, and logic violations, calculating a
weighted dataset health score.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class QualityIssue:
    id: str
    name: str
    column: str | None
    severity: Severity
    description: str
    affected_count: int
    affected_pct: float
    examples: list[str] = field(default_factory=list)
    tooltip: str = ""


@dataclass
class ProfilerResult:
    issues: list[QualityIssue]
    health_score: int
    metrics: dict[str, any]


class BaseDetector(ABC):
    """Abstract base class for all data quality detectors."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        pass
        
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def tooltip(self) -> str:
        pass

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        """Scan dataframe and return list of detected quality issues."""
        pass


class MissingValuesDetector(BaseDetector):
    id = "missing_values"
    name = "Missing Values"
    tooltip = "Checks for completely empty/null cells (NaN or None)."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            missing = int(df[col].isna().sum())
            if missing > 0:
                pct = round((missing / len(df)) * 100, 1)
                # Determine severity: critical if > 30% of data is missing, otherwise warning
                severity = Severity.CRITICAL if pct > 30.0 else Severity.WARNING
                issues.append(QualityIssue(
                    id=self.id,
                    name=self.name,
                    column=col,
                    severity=severity,
                    description=f"Column has {missing:,} missing/null cells.",
                    affected_count=missing,
                    affected_pct=pct,
                    examples=["NaN"],
                    tooltip=self.tooltip
                ))
        return issues


class BlankStringsDetector(BaseDetector):
    id = "blank_strings"
    name = "Blank Strings"
    tooltip = "Checks for empty string values or cells consisting of only spaces."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                blanks = int(df[col].dropna().astype(str).str.strip().eq("").sum())
                if blanks > 0:
                    pct = round((blanks / len(df)) * 100, 1)
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {blanks:,} blank/whitespace-only strings.",
                        affected_count=blanks,
                        affected_pct=pct,
                        examples=['"" (Empty string)', '"   " (Spaces)'],
                        tooltip=self.tooltip
                    ))
        return issues


class DuplicateRowsDetector(BaseDetector):
    id = "duplicate_rows"
    name = "Duplicate Rows"
    tooltip = "Checks for completely identical records across all columns."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        dups = int(df.duplicated().sum())
        if dups > 0:
            pct = round((dups / len(df)) * 100, 1)
            severity = Severity.CRITICAL if pct > 20.0 else Severity.WARNING
            return [QualityIssue(
                id=self.id,
                name=self.name,
                column=None,
                severity=severity,
                description=f"Found {dups:,} duplicate records in the dataset.",
                affected_count=dups,
                affected_pct=pct,
                examples=["Entire row is repeated multiple times."],
                tooltip=self.tooltip
            )]
        return []


class NearDuplicatesDetector(BaseDetector):
    id = "near_duplicates"
    name = "Near Duplicates"
    tooltip = "Checks for rows that are identical on all but one column."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        if len(df.columns) <= 2:
            return []
        
        orig_dups = df.duplicated().sum()
        near_dups = 0
        affected_cols = []
        
        # Test dropping each column to see if duplication count spikes
        for col in df.columns:
            drop_dups = df.drop(columns=[col]).duplicated().sum()
            diff = drop_dups - orig_dups
            if diff > 0:
                near_dups += diff
                affected_cols.append(col)
                
        if near_dups > 0:
            pct = round((near_dups / len(df)) * 100, 1)
            cols_str = ", ".join(affected_cols[:3]) + ("..." if len(affected_cols) > 3 else "")
            return [QualityIssue(
                id=self.id,
                name=self.name,
                column=None,
                severity=Severity.WARNING,
                description=f"Found {near_dups:,} records that differ by only a single column (columns: {cols_str}).",
                affected_count=near_dups,
                affected_pct=pct,
                examples=["Rows match perfectly except for salary or currency."],
                tooltip=self.tooltip
            )]
        return []


class MixedDataTypesDetector(BaseDetector):
    id = "mixed_types"
    name = "Mixed Data Types"
    tooltip = "Checks for columns containing values of conflicting types (e.g. text mixed with numbers)."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            non_nulls = df[col].dropna()
            if len(non_nulls) == 0:
                continue
                
            types = non_nulls.map(type).unique()
            if len(types) > 1:
                # Exclude acceptable integer/float mixed numeric types
                is_all_numeric = all(issubclass(t, (int, float, np.integer, np.floating)) for t in types)
                if not is_all_numeric:
                    type_names = [t.__name__ for t in types]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.CRITICAL,
                        description=f"Column has mixed data types: {', '.join(type_names)}.",
                        affected_count=len(types),
                        affected_pct=round((len(types) / len(df.columns)) * 100, 1),
                        examples=[str(non_nulls.iloc[0]), str(non_nulls.iloc[-1])],
                        tooltip=self.tooltip
                    ))
        return issues


class InvalidDatesDetector(BaseDetector):
    id = "invalid_dates"
    name = "Invalid Dates"
    tooltip = "Checks for date fields containing values that fail parsing or have illogical years."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ["date", "time", "created", "updated"]):
                non_nulls = df[col].dropna()
                if len(non_nulls) == 0:
                    continue
                
                # Check how many values fail to parse
                coerced = pd.to_datetime(non_nulls, errors="coerce")
                failures = int(coerced.isna().sum())
                
                # Check for illogical years (<1800 or >2100)
                valid_years = coerced.dropna().dt.year
                illogical_dates = int(((valid_years < 1800) | (valid_years > 2100)).sum())
                total_invalid = failures + illogical_dates
                
                if total_invalid > 0:
                    pct = round((total_invalid / len(df)) * 100, 1)
                    examples = []
                    if failures > 0:
                        examples.append("Text failing parse")
                    if illogical_dates > 0:
                        examples.append("Year out of bounds (e.g. 9999)")
                        
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {total_invalid:,} invalid or out-of-bounds date values.",
                        affected_count=total_invalid,
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class NumericConversionFailuresDetector(BaseDetector):
    id = "numeric_failures"
    name = "Numeric Conversion Failures"
    tooltip = "Checks for columns meant to be numeric containing non-numeric values."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if df[col].dtype == object:
                non_nulls = df[col].dropna().astype(str)
                # Check if it consists mostly of numbers (e.g., >50% numeric) but has text values
                coerced = pd.to_numeric(non_nulls, errors="coerce")
                valid_numeric = coerced.notna().sum()
                
                if 0 < valid_numeric < len(non_nulls) * 0.95: # If mostly numeric but has errors
                    failures = int(coerced.isna().sum())
                    pct = round((failures / len(df)) * 100, 1)
                    bad_examples = list(non_nulls[coerced.isna()].unique()[:3])
                    
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {failures:,} values failing numeric conversion.",
                        affected_count=failures,
                        affected_pct=pct,
                        examples=bad_examples,
                        tooltip=self.tooltip
                    ))
        return issues


class OutliersDetector(BaseDetector):
    id = "outliers"
    name = "Outliers (IQR)"
    tooltip = "Checks for numerical anomalies outside 1.5x Interquartile Range (IQR)."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                non_nulls = df[col].dropna()
                if len(non_nulls) <= 5:
                    continue
                q1 = non_nulls.quantile(0.25)
                q3 = non_nulls.quantile(0.75)
                iqr = q3 - iqr if 'iqr' in locals() else (q3 - q1)
                iqr = q3 - q1
                if iqr > 0:
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    outliers = int(((non_nulls < lower) | (non_nulls > upper)).sum())
                    if outliers > 0:
                        pct = round((outliers / len(df)) * 100, 1)
                        issues.append(QualityIssue(
                            id=self.id,
                            name=self.name,
                            column=col,
                            severity=Severity.WARNING,
                            description=f"Column has {outliers:,} potential statistical outliers.",
                            affected_count=outliers,
                            affected_pct=pct,
                            examples=[f"Val > {upper:.1f}" if (non_nulls > upper).any() else "",
                                      f"Val < {lower:.1f}" if (non_nulls < lower).any() else ""],
                            tooltip=self.tooltip
                        ))
        return issues


class LeadingTrailingSpacesDetector(BaseDetector):
    id = "whitespace_ends"
    name = "Leading/Trailing Spaces"
    tooltip = "Checks for leading or trailing whitespace strings."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                str_vals = df[col].dropna().astype(str)
                spaces = int(str_vals.str.strip().ne(str_vals).sum())
                if spaces > 0:
                    pct = round((spaces / len(df)) * 100, 1)
                    bad_examples = [x for x in str_vals if x.strip() != x][:2]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {spaces:,} values with leading or trailing spaces.",
                        affected_count=spaces,
                        affected_pct=pct,
                        examples=bad_examples,
                        tooltip=self.tooltip
                    ))
        return issues


class MultipleSpacesDetector(BaseDetector):
    id = "whitespace_multiple"
    name = "Multiple Spaces"
    tooltip = "Checks for double or consecutive internal spaces (e.g. 'Data  Sanitizer')."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                str_vals = df[col].dropna().astype(str)
                multi = int(str_vals.str.contains(r"\s{2,}").sum())
                if multi > 0:
                    pct = round((multi / len(df)) * 100, 1)
                    bad_examples = [x for x in str_vals if re.search(r"\s{2,}", x)][:2]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.INFO,
                        description=f"Column has {multi:,} values with double/multiple internal spaces.",
                        affected_count=multi,
                        affected_pct=pct,
                        examples=bad_examples,
                        tooltip=self.tooltip
                    ))
        return issues


class CaseInconsistenciesDetector(BaseDetector):
    id = "case_inconsistent"
    name = "Case Inconsistencies"
    tooltip = "Checks for category values that differ only by upper/lower case."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if df[col].dtype == object:
                str_vals = df[col].dropna().astype(str).str.strip()
                if len(str_vals) == 0:
                    continue
                unique_orig = str_vals.unique()
                unique_lower = str_vals.str.lower().unique()
                if len(unique_orig) > len(unique_lower):
                    diff = len(unique_orig) - len(unique_lower)
                    # Find example
                    dup_check = pd.Series(unique_orig).str.lower()
                    dupped_lower = dup_check[dup_check.duplicated()].iloc[0] if len(dup_check[dup_check.duplicated()]) > 0 else ""
                    examples = [x for x in unique_orig if x.lower() == dupped_lower]
                    
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has casing inconsistencies ({diff} duplicate categories).",
                        affected_count=diff,
                        affected_pct=round((diff / len(unique_orig)) * 100, 1),
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class SpecialCharacterAnomaliesDetector(BaseDetector):
    id = "special_characters"
    name = "Special Character Anomalies"
    tooltip = "Checks for control codes or corrupted non-ASCII characters."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        # Match control codes and replacement characters indicating corrupt encoding
        pattern = r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]"
        for col in df.columns:
            if df[col].dtype == object:
                str_vals = df[col].dropna().astype(str)
                corrupts = int(str_vals.str.contains(pattern).sum())
                if corrupts > 0:
                    pct = round((corrupts / len(df)) * 100, 1)
                    examples = [x for x in str_vals if re.search(pattern, x)][:2]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {corrupts:,} values with control codes or corrupted special characters.",
                        affected_count=corrupts,
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class EmptyRowsDetector(BaseDetector):
    id = "empty_rows"
    name = "Empty Rows"
    tooltip = "Checks for rows where every single cell is null/blank."

    def detect(self, pd_df: pd.DataFrame) -> list[QualityIssue]:
        empty = int(pd_df.isna().all(axis=1).sum())
        if empty > 0:
            pct = round((empty / len(pd_df)) * 100, 1)
            return [QualityIssue(
                id=self.id,
                name=self.name,
                column=None,
                severity=Severity.CRITICAL,
                description=f"Found {empty:,} completely empty rows in the dataset.",
                affected_count=empty,
                affected_pct=pct,
                examples=["Row has only NaN values."],
                tooltip=self.tooltip
            )]
        return []


class EmptyColumnsDetector(BaseDetector):
    id = "empty_columns"
    name = "Empty Columns"
    tooltip = "Checks for columns containing only null/blank values."

    def detect(self, pd_df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in pd_df.columns:
            if pd_df[col].isna().all():
                issues.append(QualityIssue(
                    id=self.id,
                    name=self.name,
                    column=col,
                    severity=Severity.CRITICAL,
                    description=f"Column '{col}' is completely empty.",
                    affected_count=len(pd_df),
                    affected_pct=100.0,
                    examples=["NaN values only"],
                    tooltip=self.tooltip
                ))
        return issues


class DuplicateColumnNamesDetector(BaseDetector):
    id = "duplicate_columns"
    name = "Duplicate Columns"
    tooltip = "Checks for duplicate column headers in the uploaded data."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        cols = list(df.columns)
        # Pandas renames duplicate columns as col.1, col.2, etc.
        dups = []
        for c in cols:
            if re.search(r"\.\d+$", str(c)):
                dups.append(str(c))
        if dups:
            pct = round((len(dups) / len(cols)) * 100, 1)
            return [QualityIssue(
                id=self.id,
                name=self.name,
                column=None,
                severity=Severity.CRITICAL,
                description=f"Found {len(dups)} duplicate column headers (indicated by pandas as {', '.join(dups[:3])}).",
                affected_count=len(dups),
                affected_pct=pct,
                examples=dups,
                tooltip=self.tooltip
            )]
        return []


class UniquenessViolationsDetector(BaseDetector):
    id = "uniqueness_violations"
    name = "Uniqueness Violations"
    tooltip = "Checks for duplicate values in columns representing unique keys or IDs."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        id_indicators = ["id", "key", "code", "uuid", "email", "phone", "pk", "fk"]
        for col in df.columns:
            col_lower = str(col).lower()
            if any(ind in col_lower for ind in id_indicators):
                non_nulls = df[col].dropna()
                if len(non_nulls) == 0:
                    continue
                dups = int(non_nulls.duplicated().sum())
                if dups > 0:
                    pct = round((dups / len(df)) * 100, 1)
                    examples = list(non_nulls[non_nulls.duplicated()].unique()[:2])
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.CRITICAL,
                        description=f"Potential ID column has {dups:,} duplicate key values.",
                        affected_count=dups,
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class EmailPatternDetector(BaseDetector):
    id = "email_pattern"
    name = "Invalid Email Patterns"
    tooltip = "Checks for invalid email formats in email fields."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        for col in df.columns:
            if "email" in str(col).lower():
                str_vals = df[col].dropna().astype(str)
                if len(str_vals) == 0:
                    continue
                invalid = int(str_vals.apply(lambda x: not bool(re.match(email_regex, x))).sum())
                if invalid > 0:
                    pct = round((invalid / len(df)) * 100, 1)
                    examples = [x for x in str_vals if not re.match(email_regex, x)][:2]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {invalid:,} values that fail email regex validation.",
                        affected_count=invalid,
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class PhonePatternDetector(BaseDetector):
    id = "phone_pattern"
    name = "Invalid Phone Patterns"
    tooltip = "Checks for invalid phone formats (digits and symbols) in phone fields."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        # Simple phone regex checking for minimum 7 digits and permitted symbols
        phone_regex = r"^\+?[\d\s\-()]{7,20}$"
        for col in df.columns:
            if "phone" in str(col).lower() or "tel" in str(col).lower():
                str_vals = df[col].dropna().astype(str)
                if len(str_vals) == 0:
                    continue
                invalid = int(str_vals.apply(lambda x: not bool(re.match(phone_regex, x))).sum())
                if invalid > 0:
                    pct = round((invalid / len(df)) * 100, 1)
                    examples = [x for x in str_vals if not re.match(phone_regex, x)][:2]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {invalid:,} values that fail phone formatting checks.",
                        affected_count=invalid,
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class UrlPatternDetector(BaseDetector):
    id = "url_pattern"
    name = "Invalid URL Patterns"
    tooltip = "Checks for invalid URL formats in website/link fields."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        url_regex = r"^https?://[^\s/$.?#].[^\s]*$"
        for col in df.columns:
            col_lower = str(col).lower()
            if "url" in col_lower or "link" in col_lower or "website" in col_lower:
                str_vals = df[col].dropna().astype(str)
                if len(str_vals) == 0:
                    continue
                invalid = int(str_vals.apply(lambda x: not bool(re.match(url_regex, x))).sum())
                if invalid > 0:
                    pct = round((invalid / len(df)) * 100, 1)
                    examples = [x for x in str_vals if not re.match(url_regex, x)][:2]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {invalid:,} values that fail URL format validation.",
                        affected_count=invalid,
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class CategoryInconsistenciesDetector(BaseDetector):
    id = "category_inconsistent"
    name = "Category Inconsistencies"
    tooltip = "Checks for potential typos in category names by identifying very similar strings."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            if df[col].dtype == object:
                non_nulls = df[col].dropna().astype(str).str.strip()
                unique_vals = list(non_nulls.unique())
                
                # Limit check to columns with reasonable cardinality to ensure speed
                if len(unique_vals) <= 1 or len(unique_vals) > 100:
                    continue
                
                typos = []
                # Simple Levenshtein distance check for similarity (differs by 1 character)
                def edit_distance(s1, s2):
                    if abs(len(s1) - len(s2)) > 1:
                        return 9
                    s1_l, s2_l = s1.lower(), s2.lower()
                    if s1_l == s2_l:
                        return 0
                    m, n = len(s1_l), len(s2_l)
                    dist = 0
                    i = j = 0
                    while i < m and j < n:
                        if s1_l[i] != s2_l[j]:
                            dist += 1
                            if m > n:
                                i += 1
                            elif n > m:
                                j += 1
                            else:
                                i += 1
                                j += 1
                        else:
                            i += 1
                            j += 1
                        if dist > 1:
                            return 9
                    return dist + (m - i) + (n - j)
                
                for idx, v1 in enumerate(unique_vals):
                    for v2 in unique_vals[idx+1:]:
                        if 0 < edit_distance(v1, v2) <= 1:
                            typos.append((v1, v2))
                            
                if typos:
                    pct = round((len(typos) / len(unique_vals)) * 100, 1)
                    examples = [f"{t[0]} vs {t[1]}" for t in typos[:2]]
                    issues.append(QualityIssue(
                        id=self.id,
                        name=self.name,
                        column=col,
                        severity=Severity.WARNING,
                        description=f"Column has {len(typos)} pairs of highly similar categorical values (potential typos).",
                        affected_count=len(typos),
                        affected_pct=pct,
                        examples=examples,
                        tooltip=self.tooltip
                    ))
        return issues


class BusinessRuleViolationsDetector(BaseDetector):
    id = "business_rules"
    name = "Business Rule Violations"
    tooltip = "Checks for illogical numeric ranges (e.g., negative values in age, salary, or price columns)."

    def detect(self, df: pd.DataFrame) -> list[QualityIssue]:
        issues = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ["age", "salary", "price", "revenue", "cost"]):
                if pd.api.types.is_numeric_dtype(df[col]):
                    non_nulls = df[col].dropna()
                    violations = int((non_nulls < 0).sum())
                    
                    if violations > 0:
                        pct = round((violations / len(df)) * 100, 1)
                        issues.append(QualityIssue(
                            id=self.id,
                            name=self.name,
                            column=col,
                            severity=Severity.WARNING,
                            description=f"Column contains {violations:,} negative values violating basic ranges.",
                            affected_count=violations,
                            affected_pct=pct,
                            examples=["Negative number (e.g. -240)"],
                            tooltip=self.tooltip
                        ))
        return issues


class Profiler:
    """Orchestrates standard profiling runs, registering all detectors and calculating weighted health scores."""
    
    def __init__(self):
        self.detectors: list[BaseDetector] = [
            MissingValuesDetector(),
            BlankStringsDetector(),
            DuplicateRowsDetector(),
            NearDuplicatesDetector(),
            MixedDataTypesDetector(),
            InvalidDatesDetector(),
            NumericConversionFailuresDetector(),
            OutliersDetector(),
            LeadingTrailingSpacesDetector(),
            MultipleSpacesDetector(),
            CaseInconsistenciesDetector(),
            SpecialCharacterAnomaliesDetector(),
            EmptyRowsDetector(),
            EmptyColumnsDetector(),
            DuplicateColumnNamesDetector(),
            UniquenessViolationsDetector(),
            EmailPatternDetector(),
            PhonePatternDetector(),
            UrlPatternDetector(),
            CategoryInconsistenciesDetector(),
            BusinessRuleViolationsDetector()
        ]

    def profile(self, df: pd.DataFrame) -> ProfilerResult:
        all_issues: list[QualityIssue] = []
        for detector in self.detectors:
            try:
                detector_issues = detector.detect(df)
                all_issues.extend(detector_issues)
            except Exception:
                pass

        # Calculate weighted health score
        # Deduct penalties based on issue severity and percentage of records affected.
        penalty = 0.0
        for issue in all_issues:
            weight = 15.0 if issue.severity == Severity.CRITICAL else (5.0 if issue.severity == Severity.WARNING else 1.0)
            deduction = weight * (issue.affected_pct / 100.0)
            min_deduct = 1.5 if issue.severity == Severity.CRITICAL else (0.5 if issue.severity == Severity.WARNING else 0.1)
            penalty += max(deduction, min_deduct)

        health_score = max(0, min(100, int(100 - penalty)))

        num_rows = len(df)
        num_cols = len(df.columns)
        
        metrics = {
            "rows": num_rows,
            "columns": num_cols,
            "total_cells": num_rows * num_cols,
            "critical_count": sum(1 for i in all_issues if i.severity == Severity.CRITICAL),
            "warning_count": sum(1 for i in all_issues if i.severity == Severity.WARNING),
            "info_count": sum(1 for i in all_issues if i.severity == Severity.INFO),
            "total_issues": len(all_issues)
        }

        return ProfilerResult(issues=all_issues, health_score=health_score, metrics=metrics)
