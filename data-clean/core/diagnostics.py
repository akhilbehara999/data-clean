"""Diagnostics module for analyzing DataFrame column health and identifying quality issues."""
import pandas as pd
import numpy as np


def detect_column_type(series: pd.Series) -> str:
    """Infer the type of a column based on its non-null values.

    Returns one of: "text", "number", "date", "boolean", "mixed", "empty"
    """
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]

    non_nulls = series.dropna()
    if len(non_nulls) == 0:
        return "empty"

    if pd.api.types.is_bool_dtype(series.dtype):
        return "boolean"

    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return "date"

    if pd.api.types.is_numeric_dtype(series.dtype):
        return "number"

    str_vals = non_nulls.astype(str).str.strip().str.lower()
    unique_str_vals = set(str_vals.unique())
    boolean_indicators = {"true", "false", "yes", "no", "t", "f", "y", "n", "1", "0", "1.0", "0.0"}
    if unique_str_vals.issubset(boolean_indicators) and len(unique_str_vals) > 0:
        return "boolean"

    try:
        pd.to_numeric(non_nulls, errors="raise")
        return "number"
    except (ValueError, TypeError):
        pass

    has_date_delimiters = str_vals.str.contains(r"[-/:]").any()
    if has_date_delimiters:
        try:
            pd.to_datetime(non_nulls, errors="raise")
            return "date"
        except (ValueError, TypeError):
            pass

    types_present = non_nulls.map(type).unique()
    if len(types_present) > 1:
        is_all_numeric = all(issubclass(t, (int, float, np.integer, np.floating)) for t in types_present)
        if not is_all_numeric:
            return "mixed"

    coerced_numeric = pd.to_numeric(non_nulls, errors="coerce")
    num_numeric = coerced_numeric.notna().sum()
    num_total = len(non_nulls)
    if 0 < num_numeric < num_total:
        return "mixed"

    if has_date_delimiters:
        coerced_dates = pd.to_datetime(non_nulls, errors="coerce")
        num_dates = coerced_dates.notna().sum()
        if 0 < num_dates < num_total:
            return "mixed"

    return "text"


def analyze_dataframe(df: pd.DataFrame) -> list:
    """Analyze dataframe columns using the new Profiler engine.
    
    Converts ProfilerResult back to a list of dicts for backward compatibility.
    """
    from core.profiler import Profiler
    
    profiler = Profiler()
    result = profiler.profile(df)
    
    column_reports = []
    total_rows = len(df)

    for i, col in enumerate(df.columns):
        series = df.iloc[:, i]
        dtype_detected = detect_column_type(series)
        
        # Calculate base missing details
        missing_count = int(series.isna().sum())
        if dtype_detected in ["text", "mixed"]:
            whitespace_missing = series.dropna().astype(str).str.strip().eq("").sum()
            missing_count += int(whitespace_missing)
            
        missing_pct = 0.0
        if total_rows > 0:
            missing_pct = round((missing_count / total_rows) * 100.0, 1)

        non_null_series = series.dropna()
        duplicate_values = int(non_null_series.duplicated().sum())

        # Pull matching issues from profiler result
        col_issues = [issue for issue in result.issues if issue.column == str(col)]
        issues_found = [f"{issue.name}: {issue.description}" for issue in col_issues]

        # Determine status
        if missing_pct > 30.0 or dtype_detected == "empty":
            status = "critical"
        elif missing_pct > 5.0 or len(col_issues) > 0:
            status = "attention"
        else:
            status = "clean"

        column_reports.append({
            "column_name": str(col),
            "dtype_detected": dtype_detected,
            "missing_count": int(missing_count),
            "missing_pct": missing_pct,
            "duplicate_values": duplicate_values,
            "total_rows": total_rows,
            "status": status,
            "issues_found": issues_found,
        })

    return column_reports

    return column_reports
