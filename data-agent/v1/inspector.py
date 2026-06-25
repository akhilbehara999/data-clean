"""
Phase 1 — Comprehensive data inspection engine.

Scans a DataFrame for completeness, duplicates, data-type issues,
formatting inconsistencies, outliers, and structural problems.
"""

import os
import re
import warnings
from collections import Counter

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from .models import CleaningAction, Finding, InspectionReport

# ── Constants ──────────────────────────────────────────────────────────────────

DATE_PATTERNS: dict[str, str] = {
    r"\d{4}-\d{2}-\d{2}": "YYYY-MM-DD",
    r"\d{2}/\d{2}/\d{4}": "MM/DD/YYYY",
    r"\d{2}-\d{2}-\d{4}": "MM-DD-YYYY",
    r"\d{2}\.\d{2}\.\d{4}": "DD.MM.YYYY",
    r"\d{4}/\d{2}/\d{2}": "YYYY/MM/DD",
    r"[A-Za-z]+ \d{1,2},? \d{4}": "Month DD, YYYY",
    r"\d{1,2} [A-Za-z]+ \d{4}": "DD Month YYYY",
}

BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n", "1", "0",
                  "t", "f", "on", "off"}

POSITIVE_ONLY_KW = {"age", "price", "cost", "amount", "quantity", "qty",
                    "count", "total", "salary", "revenue", "weight",
                    "height", "distance", "size", "area", "volume", "fee"}

UNIQUE_COL_KW = {"id", "email", "phone", "ssn", "passport", "license",
                 "username", "account_id", "order_id", "transaction_id",
                 "employee_id", "customer_id", "user_id", "sku"}

CURRENCY_RE = re.compile(r"[\$€£¥₹₩₽]")
NUMERIC_WITH_SYMBOLS_RE = re.compile(
    r"^[\s\$€£¥₹₩₽]*-?[\d,]+\.?\d*\s*%?\s*$"
)


# ── Inspector ──────────────────────────────────────────────────────────────────

class DataInspector:
    """Runs all Phase-1 checks on a loaded DataFrame."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.file_size = self._human_size()
        self.df = self._load()
        self.original_rows = len(self.df)
        self.original_cols = len(self.df.columns)
        self._findings: dict[str, list[Finding]] = {
            "critical": [], "moderate": [], "minor": [], "outlier": [],
        }
        self._actions: list[CleaningAction] = []
        self._columns_with_issues: set[str] = set()

    # ── File helpers ───────────────────────────────────────────────────────

    def _human_size(self) -> str:
        b = os.path.getsize(self.filepath)
        if b > 100 * 1024 * 1024:
            raise ValueError(
                f"File too large ({b / (1024**2):.1f} MB). Max supported: 100 MB."
            )
        for unit in ("bytes", "KB", "MB"):
            if b < 1024 or unit == "MB":
                return f"{b:.1f} {unit}" if unit != "bytes" else f"{b} bytes"
            b /= 1024
        return f"{b:.1f} GB"

    def _load(self) -> pd.DataFrame:
        ext = os.path.splitext(self.filepath)[1].lower()
        loaders = {
            ".csv": lambda: pd.read_csv(self.filepath),
            ".tsv": lambda: pd.read_csv(self.filepath, sep="\t"),
            ".xlsx": lambda: pd.read_excel(self.filepath),
            ".xls": lambda: pd.read_excel(self.filepath),
        }
        loader = loaders.get(ext)
        if loader is None:
            raise ValueError(
                f"Unsupported format: {ext}. Use CSV, XLSX, XLS, or TSV."
            )
        return loader()

    # ── Public entry point ─────────────────────────────────────────────────

    def inspect(self) -> InspectionReport:
        self._check_structural()
        self._check_completeness()
        self._check_duplicates()
        self._check_data_types()
        self._check_formatting()
        self._check_outliers()
        clean = self._clean_columns()
        self._build_cleaning_plan()

        # Derive a clean name that preserves relative subdirectory paths to avoid collisions
        try:
            rel = os.path.relpath(self.filepath)
            if rel.startswith(".."):
                parent = os.path.basename(os.path.dirname(os.path.abspath(self.filepath)))
                base = os.path.basename(self.filepath)
                if parent:
                    rel = os.path.join(parent, base)
                else:
                    rel = base
        except Exception:
            rel = self.filename

        name, ext = os.path.splitext(rel)
        name_clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        name_clean = re.sub(r'_{2,}', '_', name_clean)
        name_clean = name_clean.strip('_')

        return InspectionReport(
            filename=self.filename,
            rows=self.original_rows,
            columns=self.original_cols,
            file_size=self.file_size,
            critical=self._findings["critical"],
            moderate=self._findings["moderate"],
            minor=self._findings["minor"],
            outliers=self._findings["outlier"],
            clean_columns=clean,
            cleaning_actions=self._actions,
            output_path=os.path.join("output", f"{name_clean}_cleaned{ext}"),
        )


    # ── helpers ────────────────────────────────────────────────────────────

    def _add(self, severity: str, **kw):
        f = Finding(severity=severity, **kw)
        self._findings[severity].append(f)
        if f.column not in ("All columns", "Multiple columns"):
            self._columns_with_issues.add(f.column)

    def _clean_columns(self) -> list[str]:
        return [c for c in self.df.columns if c not in self._columns_with_issues]

    # ── 1. Structural ─────────────────────────────────────────────────────

    def _check_structural(self):
        # Unnamed columns
        unnamed = [c for c in self.df.columns
                    if str(c).startswith("Unnamed") or str(c).startswith("Column")]
        if unnamed:
            self._add("moderate", column=", ".join(unnamed),
                       issue_type="unnamed_columns",
                       description=f"Your file has {len(unnamed)} column(s) without proper names (like \"{unnamed[0]}\"). These were probably created by accident during a data export. They add confusion and make your data harder to reference.",
                       count=len(unnamed),
                       details={"columns": unnamed})

        # Trailing empty rows
        tail = self.df.tail(20)
        trailing = 0
        for i in range(len(tail) - 1, -1, -1):
            if tail.iloc[i].isna().all():
                trailing += 1
            else:
                break
        if trailing:
            self._add("minor", column="All columns",
                       issue_type="trailing_empty_rows",
                       description=f"The last {trailing} row(s) of your file are completely blank. They were probably left over from manual editing or a copy-paste. They'll pad your row count and could throw off summaries that count rows.",
                       count=trailing)

        # Embedded header rows (rows whose values match column names)
        if len(self.df) > 1:
            col_set = set(str(c).lower().strip() for c in self.df.columns)
            header_rows = []
            check_range = min(len(self.df), 200)
            for idx in range(check_range):
                row_vals = set(str(v).lower().strip() for v in self.df.iloc[idx] if pd.notna(v))
                overlap = row_vals & col_set
                if len(overlap) > len(self.df.columns) * 0.5:
                    header_rows.append(idx)
            if header_rows:
                self._add("moderate", column="All columns",
                           issue_type="embedded_headers",
                           description=f"{len(header_rows)} row(s) inside your data look like duplicated column headers (at row index {header_rows}). This usually happens when multiple spreadsheets were pasted together. These fake data rows will cause errors in any calculations.",
                           count=len(header_rows),
                           details={"row_indices": header_rows})

    # ── 2. Completeness ───────────────────────────────────────────────────

    def _check_completeness(self):
        empty_cols: list[str] = []
        for col in self.df.columns:
            na_mask = self.df[col].isna()
            if self.df[col].dtype == object:
                na_mask = na_mask | self.df[col].astype(str).str.strip().eq("")
            cnt = int(na_mask.sum())
            if cnt == 0:
                continue
            pct = cnt / len(self.df) * 100

            if cnt == len(self.df):
                empty_cols.append(col)
                self._add("critical", column=col, issue_type="empty_column",
                           description=f"The \"{col}\" column is completely empty — every single row is blank. This column adds no information to your data and will just clutter your analysis.",
                           count=cnt, percentage=100.0)
            elif pct > 50:
                self._add("critical", column=col, issue_type="missing_values",
                           description=f"The \"{col}\" column is missing {cnt:,} out of {len(self.df):,} values ({pct:.1f}%). More than half the data is gone, which means any analysis on this column will be unreliable.",
                           count=cnt, percentage=pct)
            elif pct > 10:
                self._add("moderate", column=col, issue_type="missing_values",
                           description=f"The \"{col}\" column has {cnt:,} blank entries ({pct:.1f}% of your data). If you're filtering or grouping by this column, those {cnt:,} rows will silently drop out of your results.",
                           count=cnt, percentage=pct)
            else:
                self._add("minor", column=col, issue_type="missing_values",
                           description=f"The \"{col}\" column has {cnt:,} blank values ({pct:.1f}%). It's a small number, but they could still cause unexpected gaps in reports or summaries.",
                           count=cnt, percentage=pct)

        # Rows with >50 % missing
        row_miss = self.df.isna().sum(axis=1)
        mostly = int((row_miss > len(self.df.columns) * 0.5).sum())
        if mostly:
            self._add("moderate", column="All columns",
                       issue_type="mostly_missing_rows",
                       description=f"{mostly:,} row(s) have more than half their values missing — they're mostly blank. These rows contribute very little usable data and may distort any summaries or averages.",
                       count=mostly,
                       percentage=mostly / len(self.df) * 100)

    # ── 3. Duplicates ─────────────────────────────────────────────────────

    def _check_duplicates(self):
        dup_count = int(self.df.duplicated(keep="first").sum())
        if dup_count:
            self._add("critical", column="All columns",
                       issue_type="duplicate_rows",
                       description=f"There are {dup_count:,} rows that are exact copies of other rows. If you're counting records, calculating totals, or doing any aggregation, these duplicates will inflate your numbers.",
                       count=dup_count,
                       percentage=dup_count / len(self.df) * 100)

        for col in self.df.columns:
            cl = col.lower().replace(" ", "_").replace("-", "_")
            if not any(kw in cl for kw in UNIQUE_COL_KW):
                continue
            nn = self.df[col].dropna()
            if len(nn) == 0:
                continue
            dup_vals = int(nn.duplicated(keep="first").sum())
            if dup_vals:
                examples = nn[nn.duplicated(keep=False)].unique()[:5].tolist()
                ex_str = ", ".join(str(e) for e in examples[:3])
                self._add("critical", column=col,
                           issue_type="duplicate_unique_values",
                           description=f"The \"{col}\" column looks like it should contain unique values, but {dup_vals:,} values appear more than once (e.g. {ex_str}). This could mean the same record was entered twice, which will throw off counts and lookups.",
                           count=dup_vals, examples=examples)

    # ── 4. Data-type issues ────────────────────────────────────────────────

    def _check_data_types(self):
        for col in self.df.columns:
            nn = self.df[col].dropna()
            if len(nn) == 0:
                continue
            if nn.dtype != object:
                continue
            sv = nn.astype(str)

            # Currency / numeric-with-symbols
            cur_mask = sv.str.contains(r"[\$€£¥₹₩₽]", regex=True, na=False)
            if cur_mask.sum() > len(nn) * 0.3:
                ex = ", ".join(sv[cur_mask].head(3).tolist())
                self._add("moderate", column=col,
                           issue_type="numeric_with_symbols",
                           description=f"The \"{col}\" column contains currency symbols and commas (e.g. {ex}). Python sees these as text, not numbers, so you cannot sort by {col}, calculate averages, or do any math on it until the symbols are removed.",
                           count=int(cur_mask.sum()),
                           percentage=cur_mask.sum() / len(nn) * 100,
                           examples=sv[cur_mask].head(3).tolist())
                continue

            # Percentage symbols
            pct_mask = sv.str.fullmatch(r"\s*-?\d+\.?\d*\s*%\s*", na=False)
            if pct_mask.sum() > len(nn) * 0.3:
                ex = ", ".join(sv[pct_mask].head(3).tolist())
                self._add("moderate", column=col,
                           issue_type="numeric_with_percent",
                           description=f"The \"{col}\" column has percentage signs in the values (e.g. {ex}). Python treats these as text, which means you can't calculate with them until the % signs are removed and the values are converted to numbers.",
                           count=int(pct_mask.sum()),
                           examples=sv[pct_mask].head(3).tolist())
                continue

            # Commas in numbers
            comma_num = sv.str.fullmatch(r"\s*-?[\d,]+\.?\d*\s*", na=False)
            has_comma = sv.str.contains(",", na=False)
            both = comma_num & has_comma
            if both.sum() > len(nn) * 0.3:
                ex = ", ".join(sv[both].head(3).tolist())
                self._add("moderate", column=col,
                           issue_type="numeric_with_commas",
                           description=f"The \"{col}\" column has commas in the numbers (e.g. {ex}). Python reads these as text instead of numbers, so math operations like sum, average, and sorting won't work until the commas are removed.",
                           count=int(both.sum()),
                           examples=sv[both].head(3).tolist())
                continue

            # Dates stored as text
            if self._looks_like_dates(sv):
                fmts = self._detect_date_formats(sv)
                if len(fmts) > 1:
                    ex = ", ".join(sv.head(3).tolist())
                    self._add("moderate", column=col,
                               issue_type="inconsistent_dates",
                               description=f"The \"{col}\" column uses {len(fmts)} different date formats ({', '.join(fmts)}) — for example: {ex}. Sorting, filtering by date range, or comparing dates will give unreliable results because Python can't consistently interpret them.",
                               count=len(nn), details={"formats": fmts},
                               examples=sv.head(3).tolist())
                elif fmts:
                    self._add("minor", column=col,
                               issue_type="date_as_text",
                               description=f"The \"{col}\" column contains dates stored as plain text. Python doesn't recognize them as actual dates, so date sorting, date arithmetic, and date-range filters won't work reliably.",
                               count=len(nn), details={"formats": fmts})
                continue

            # Boolean inconsistency
            uniq_low = set(sv.str.strip().str.lower().unique())
            bool_hit = uniq_low & BOOLEAN_VALUES
            if len(bool_hit) >= 2 and len(uniq_low) <= 6:
                groups = [{"true", "false"} & bool_hit,
                          {"yes", "no"} & bool_hit,
                          {"1", "0"} & bool_hit,
                          {"y", "n"} & bool_hit]
                if sum(bool(g) for g in groups) > 1:
                    vals = ", ".join(sorted(bool_hit))
                    self._add("moderate", column=col,
                               issue_type="boolean_inconsistency",
                               description=f"The \"{col}\" column uses a mix of {vals} to mean the same thing (yes/no). If you filter for records using just one of these spellings, you'll miss the ones written differently.",
                               count=len(nn), examples=sorted(bool_hit))
                    continue

            # Mixed types
            numeric_ok = pd.to_numeric(sv, errors="coerce").notna().sum()
            text_count = len(nn) - numeric_ok
            if 0 < numeric_ok < len(nn) and numeric_ok > len(nn) * 0.3:
                if not self._looks_like_dates(sv):
                    non_num = sv[pd.to_numeric(sv, errors="coerce").isna()].head(3).tolist()
                    ex = ", ".join(str(e) for e in non_num)
                    self._add("moderate", column=col,
                               issue_type="mixed_types",
                               description=f"The \"{col}\" column is a mix of {numeric_ok:,} numbers and {text_count:,} text values (like {ex}). Python can't decide how to treat this column, so math operations will fail and sorting won't work as expected.",
                               count=text_count, examples=non_num)

    # ── 5. Formatting ─────────────────────────────────────────────────────

    def _check_formatting(self):
        for col in self.df.columns:
            if self.df[col].dtype != object:
                continue
            nn = self.df[col].dropna()
            if len(nn) == 0:
                continue
            sv = nn.astype(str)

            # Whitespace
            ws = sv.str.len() != sv.str.strip().str.len()
            wsc = int(ws.sum())
            if wsc:
                ex = ", ".join(sv[ws].head(3).apply(repr).tolist())
                self._add("minor", column=col, issue_type="whitespace",
                           description=f"{wsc:,} values in the \"{col}\" column have invisible spaces at the start or end (e.g. {ex}). This means searching for a value or filtering won't find these entries because the hidden spaces make them look different.",
                           count=wsc, percentage=wsc / len(nn) * 100,
                           examples=sv[ws].head(3).apply(repr).tolist())

            # Casing inconsistency
            stripped = sv.str.strip()
            low_map: dict[str, list] = {}
            for v in stripped.unique():
                low_map.setdefault(v.lower(), []).append(v)
            inconsistent = {k: v for k, v in low_map.items() if len(v) > 1}
            if inconsistent:
                total = sum(stripped.str.lower().eq(k).sum() for k in inconsistent)
                ex_list = []
                for variants in list(inconsistent.values())[:3]:
                    ex_list.append(" / ".join(variants))
                ex_str = ", ".join(ex_list[:3])
                self._add("moderate", column=col, issue_type="inconsistent_casing",
                           description=f"The \"{col}\" column has the same values written in different cases: {ex_str}. Python treats these as completely different values, so any grouping, counting, or filtering will split them into separate categories instead of combining them.",
                           count=int(total), examples=ex_list)

    # ── 6. Outliers ────────────────────────────────────────────────────────

    def _check_outliers(self):
        for col in self.df.columns:
            nn = pd.to_numeric(self.df[col], errors="coerce").dropna()
            if len(nn) < 10:
                continue

            # 3-sigma
            mean, std = nn.mean(), nn.std()
            if std > 0:
                beyond = nn[(nn - mean).abs() > 3 * std]
                if len(beyond):
                    vals = sorted(beyond.unique().tolist())
                    vals_str = ", ".join(str(v) for v in vals[:5])
                    self._add("outlier", column=col,
                               issue_type="statistical_outlier",
                               description=f"{len(beyond)} value(s) in the \"{col}\" column are far outside the normal range (found: {vals_str}, compared to an average of {mean:.2f}). These are likely data entry errors. Leaving them in will pull your averages and other statistics in the wrong direction.",
                               count=len(beyond), examples=vals[:5])

            # Negative in positive-only columns
            cl = col.lower().replace(" ", "_").replace("-", "_")
            if any(kw in cl for kw in POSITIVE_ONLY_KW):
                neg = nn[nn < 0]
                if len(neg):
                    neg_ex = ", ".join(str(v) for v in neg.head(5).tolist())
                    self._add("outlier", column=col,
                               issue_type="negative_in_positive",
                               description=f"The \"{col}\" column has {len(neg)} negative value(s) (e.g. {neg_ex}), but this column should only contain positive numbers. A negative {col} doesn't make sense — these are almost certainly data entry mistakes that will skew your totals and averages.",
                               count=len(neg), examples=neg.head(5).tolist())

        # Date outliers
        for col in self.df.columns:
            dt = pd.to_datetime(self.df[col], errors="coerce")
            valid = dt.dropna()
            if len(valid) < 5:
                continue
            future = valid[valid > pd.Timestamp.now()]
            ancient = valid[valid < pd.Timestamp("1900-01-01")]
            if len(future):
                f_ex = ", ".join(future.head(3).dt.strftime("%Y-%m-%d").tolist())
                self._add("outlier", column=col,
                           issue_type="future_dates",
                           description=f"The \"{col}\" column has {len(future)} date(s) set in the future (e.g. {f_ex}). If this is historical data, future dates are likely typos that will confuse any time-based analysis or reporting.",
                           count=len(future),
                           examples=future.head(3).dt.strftime("%Y-%m-%d").tolist())
            if len(ancient):
                a_ex = ", ".join(ancient.head(3).dt.strftime("%Y-%m-%d").tolist())
                self._add("outlier", column=col,
                           issue_type="ancient_dates",
                           description=f"The \"{col}\" column has {len(ancient)} date(s) before the year 1900 (e.g. {a_ex}). Unless you're working with very old historical data, these are likely data entry errors.",
                           count=len(ancient),
                           examples=ancient.head(3).dt.strftime("%Y-%m-%d").tolist())

    # ── Date helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _looks_like_dates(series: pd.Series) -> bool:
        sample = series.head(30).astype(str)
        hits = 0
        for val in sample:
            for pat in DATE_PATTERNS:
                if re.search(pat, val):
                    hits += 1
                    break
        return hits > len(sample) * 0.4

    @staticmethod
    def _detect_date_formats(series: pd.Series) -> list[str]:
        sample = series.head(100).astype(str)
        found: set[str] = set()
        for val in sample:
            v = val.strip()
            for pat, name in DATE_PATTERNS.items():
                if re.fullmatch(pat, v):
                    found.add(name)
        return sorted(found)

    # ── Cleaning plan builder ──────────────────────────────────────────────

    def _build_cleaning_plan(self):
        step = 0
        all_f = (self._findings["critical"] + self._findings["moderate"] +
                 self._findings["minor"] + self._findings["outlier"])
        types_seen: set[str] = {f.issue_type for f in all_f}
        col_for = lambda t: [f for f in all_f if f.issue_type == t]

        # 1. Duplicates
        if "duplicate_rows" in types_seen:
            f = col_for("duplicate_rows")[0]
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="remove_duplicates",
                description=f"There are {f.count:,} rows that are exact copies of other rows. I'll remove the duplicates and keep just one copy of each, so your counts and totals are accurate.",
                affected_count=f.count))

        # 2. Empty columns
        if "empty_column" in types_seen:
            cols = [f.column for f in col_for("empty_column")]
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="drop_empty_columns",
                description=f"The following {len(cols)} column(s) are completely empty and contain no data at all: {', '.join(cols)}. I'll remove them to keep your dataset clean and focused.",
                affected_count=len(cols), params={"columns": cols}))

        # 3. Trailing empty rows
        if "trailing_empty_rows" in types_seen:
            f = col_for("trailing_empty_rows")[0]
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="drop_trailing_empty_rows",
                description=f"The last {f.count} row(s) at the bottom of your file are completely blank. I'll remove them so they don't inflate your row count.",
                affected_count=f.count))

        # 4. Embedded headers
        if "embedded_headers" in types_seen:
            f = col_for("embedded_headers")[0]
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="remove_embedded_headers",
                description=f"There are {f.count} row(s) inside your data that look like duplicated column headers. I'll remove them so they don't get treated as actual data.",
                affected_count=f.count,
                params={"row_indices": f.details.get("row_indices", [])}))

        # 5. Rename unnamed columns (skip those already being dropped)
        if "unnamed_columns" in types_seen:
            f = col_for("unnamed_columns")[0]
            dropped = set()
            if "empty_column" in types_seen:
                dropped = {fi.column for fi in col_for("empty_column")}
            cols = [c for c in f.details.get("columns", []) if c not in dropped]
            if cols:
                renames = {c: f"col_{i}" for i, c in enumerate(cols)}
                step += 1
                names_str = ", ".join(f'"{k}"' for k in renames.keys())
                new_str = ", ".join(f'"{v}"' for v in renames.values())
                self._actions.append(CleaningAction(
                    step=step, action_type="rename_columns",
                    description=f"These {len(cols)} column(s) don't have proper names: {names_str}. I'll give them clear names ({new_str}) so they're easier to reference.",
                    affected_count=len(cols), params={"renames": renames}))

        # 6. Missing values — drop column if >50%, drop rows if critical, fill otherwise
        for f in col_for("missing_values"):
            if f.severity == "critical" and f.percentage > 50:
                step += 1
                self._actions.append(CleaningAction(
                    step=step, action_type="drop_column",
                    description=f"The \"{f.column}\" column is {f.percentage:.0f}% empty — more data is missing than present. I'll remove this column since it doesn't have enough data to be useful.",
                    affected_count=f.count, params={"column": f.column}))
            elif f.severity == "critical":
                step += 1
                self._actions.append(CleaningAction(
                    step=step, action_type="drop_missing_rows",
                    description=f"The \"{f.column}\" column has {f.count:,} rows with missing values. Since this appears to be important data, I'll remove those incomplete rows rather than guess at what should be there.",
                    affected_count=f.count, params={"column": f.column}))
            else:
                step += 1
                self._actions.append(CleaningAction(
                    step=step, action_type="fill_missing",
                    description=f"The \"{f.column}\" column has {f.count:,} blank entries. I'll fill them with \"Unknown\" as a placeholder so they don't silently disappear from your analysis.",
                    affected_count=f.count, params={"column": f.column, "value": "Unknown"}))

        # 7. Whitespace
        ws_cols = [f.column for f in col_for("whitespace")]
        if ws_cols:
            total = sum(f.count for f in col_for("whitespace"))
            step += 1
            cols_str = ", ".join(f'"{c}"' for c in ws_cols)
            self._actions.append(CleaningAction(
                step=step, action_type="strip_whitespace",
                description=f"{total:,} values across the {cols_str} column(s) have invisible spaces at the start or end. I'll remove those hidden spaces so searches, filters, and grouping work correctly.",
                affected_count=total, params={"columns": ws_cols}))

        # 8. Casing
        for f in col_for("inconsistent_casing"):
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="standardize_casing",
                description=f"The \"{f.column}\" column has the same values written in different cases (e.g. upper, lower, mixed). I'll standardize everything to Title Case so they all group together properly.",
                affected_count=f.count, params={"column": f.column, "case": "title"}))

        # 9. Numeric conversion
        for f in col_for("numeric_with_symbols") + col_for("numeric_with_commas") + col_for("numeric_with_percent"):
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="convert_numeric",
                description=f"The \"{f.column}\" column has values with currency symbols, commas, or percentage signs that prevent math operations. I'll strip those characters and convert the column to proper numbers so you can sort, sum, and calculate with it.",
                affected_count=f.count, params={"column": f.column}))

        # 10. Date unification
        for f in col_for("inconsistent_dates"):
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="unify_dates",
                description=f"The \"{f.column}\" column has dates written in multiple formats. I'll convert them all to a single, consistent format (YYYY-MM-DD) so sorting and date comparisons work correctly.",
                affected_count=f.count, params={"column": f.column, "format": "%Y-%m-%d"}))

        # 11. Boolean standardization
        for f in col_for("boolean_inconsistency"):
            step += 1
            self._actions.append(CleaningAction(
                step=step, action_type="standardize_boolean",
                description=f"The \"{f.column}\" column uses a mix of words like 'yes', 'no', '1', '0' to mean the same thing. I'll convert all of these to True or False so the column is consistent and easy to filter.",
                affected_count=f.count, params={"column": f.column}))

        # 12. Outliers
        for f in col_for("statistical_outlier"):
            step += 1
            vals_str = ", ".join(str(v) for v in f.examples[:5])
            self._actions.append(CleaningAction(
                step=step, action_type="replace_outliers",
                description=f"The \"{f.column}\" column has {f.count} value(s) that are statistically extreme ({vals_str}) and likely data entry errors. I'll mark them as missing so they don't distort your averages and analysis.",
                affected_count=f.count, params={"column": f.column, "examples": f.examples}))

        for f in col_for("negative_in_positive"):
            step += 1
            neg_str = ", ".join(str(v) for v in f.examples[:5])
            self._actions.append(CleaningAction(
                step=step, action_type="replace_negatives",
                description=f"The \"{f.column}\" column has {f.count} negative value(s) ({neg_str}) where only positive numbers make sense. I'll mark them as missing since they're almost certainly data entry mistakes.",
                affected_count=f.count, params={"column": f.column}))

