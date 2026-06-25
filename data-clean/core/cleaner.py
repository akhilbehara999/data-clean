"""Cleaning module for applying data sanitisation operations to DataFrames."""
import pandas as pd
import numpy as np


def drop_missing_structures(df, drop_rows=True, drop_cols=True, critical_cols=None):
    """Remove completely empty rows/columns, and rows missing critical columns."""
    df_copy = df.copy()
    initial_rows = len(df_copy)
    initial_cols = len(df_copy.columns)

    # Temporary df with blank strings treated as NaN for check
    df_temp = df_copy.replace(r"^\s*$", np.nan, regex=True)

    rows_to_keep = [True] * initial_rows
    cols_to_keep = [True] * initial_cols

    if drop_rows:
        # Keep row if not all values are null
        rows_to_keep = df_temp.notna().any(axis=1).tolist()

    if critical_cols:
        for idx in range(initial_rows):
            if not rows_to_keep[idx]:
                continue
            # Check critical columns
            for col in critical_cols:
                if col in df_temp.columns:
                    val = df_temp.iat[idx, df_temp.columns.get_loc(col)]
                    if pd.isna(val):
                        rows_to_keep[idx] = False
                        break

    if drop_cols:
        # Keep col if not all values are null
        cols_to_keep = df_temp.notna().any(axis=0).tolist()

    # Filter columns first
    cols_filtered = [col for idx, col in enumerate(df_copy.columns) if cols_to_keep[idx]]
    df_copy = df_copy[cols_filtered]

    # Filter rows
    df_copy = df_copy[rows_to_keep].reset_index(drop=True)

    rows_removed = initial_rows - len(df_copy)
    cols_dropped = initial_cols - len(df_copy.columns)

    return df_copy, {"rows_removed": rows_removed, "cols_dropped": cols_dropped}


def impute_default_values(df, cols, placeholder):
    """Fill missing or blank cells in selected columns with a default placeholder."""
    df_copy = df.copy()
    cells_filled = 0

    for col in cols:
        if col not in df_copy.columns:
            continue

        null_mask = df_copy[col].isna() | (df_copy[col].astype(str).str.strip() == "")
        count = int(null_mask.sum())
        if count > 0:
            col_placeholder = placeholder
            if pd.api.types.is_numeric_dtype(df_copy[col]):
                try:
                    if "." in str(placeholder):
                        col_placeholder = float(placeholder)
                    else:
                        col_placeholder = int(placeholder)
                except ValueError:
                    pass

            if not pd.api.types.is_numeric_dtype(type(col_placeholder)) and pd.api.types.is_numeric_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].astype(object)

            df_copy.loc[null_mask, col] = col_placeholder
            cells_filled += count

    return df_copy, {"cells_filled": cells_filled}


def impute_statistical(df, cols, strategy):
    """Fill missing numerical values using Mean, Median, or Mode."""
    df_copy = df.copy()
    cells_filled = 0

    for col in cols:
        if col not in df_copy.columns:
            continue

        null_mask = df_copy[col].isna() | (df_copy[col].astype(str).str.strip() == "")
        count = int(null_mask.sum())
        if count > 0:
            df_copy.loc[null_mask, col] = np.nan
            series_clean = pd.to_numeric(df_copy[col], errors="coerce").dropna()
            if len(series_clean) == 0:
                continue

            if strategy == "Mean":
                fill_val = series_clean.mean()
            elif strategy == "Median":
                fill_val = series_clean.median()
            elif strategy == "Mode":
                modes = series_clean.mode()
                fill_val = modes.iloc[0] if not modes.empty else np.nan
            else:
                continue

            if pd.isna(fill_val):
                continue

            if pd.api.types.is_integer_dtype(df_copy[col]):
                fill_val = int(round(fill_val))

            df_copy.loc[null_mask, col] = fill_val
            cells_filled += count

    return df_copy, {"cells_filled": cells_filled}


def impute_fill_direction(df, cols, direction):
    """Fill missing values using Forward Fill or Backward Fill."""
    df_copy = df.copy()
    cells_filled = 0

    for col in cols:
        if col not in df_copy.columns:
            continue

        null_mask = df_copy[col].isna() | (df_copy[col].astype(str).str.strip() == "")
        count = int(null_mask.sum())
        if count > 0:
            df_copy.loc[null_mask, col] = np.nan
            if direction == "Forward fill (ffill)":
                df_copy[col] = df_copy[col].ffill()
            elif direction == "Backward fill (bfill)":
                df_copy[col] = df_copy[col].bfill()
            else:
                continue

            new_nulls = df_copy[col].isna().sum()
            cells_filled += int(count - new_nulls)

    return df_copy, {"cells_filled": cells_filled}


def remove_duplicates_custom(df, exact_match=True, partial_cols=None, keep_strategy="First occurrence"):
    """Remove exact or partial duplicates from the DataFrame based on custom rules."""
    df_copy = df.copy()
    initial_rows = len(df_copy)

    keep_map = {
        "First occurrence": "first",
        "Last occurrence": "last",
        "Remove all": False
    }
    keep_val = keep_map.get(keep_strategy, "first")

    if exact_match:
        df_copy = df_copy.drop_duplicates(keep=keep_val)

    if partial_cols:
        valid_cols = [c for c in partial_cols if c in df_copy.columns]
        if valid_cols:
            df_copy = df_copy.drop_duplicates(subset=valid_cols, keep=keep_val)

    rows_removed = initial_rows - len(df_copy)
    return df_copy, {"rows_removed": rows_removed}


def trim_whitespace_custom(df, cols):
    """Strip leading/trailing whitespace and collapse multiple spaces in selected columns."""
    import re as _re
    df_copy = df.copy()
    cells_modified = 0

    for col in cols:
        if col not in df_copy.columns:
            continue
        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col].astype(str)
        trimmed = original.str.strip().str.replace(r"\s{2,}", " ", regex=True)
        changed = original != trimmed
        cells_modified += int(changed.sum())
        df_copy.loc[mask, col] = trimmed

    return df_copy, {"cells_modified": cells_modified}


def normalize_case_custom(df, cols, case_type="UPPERCASE"):
    """Convert text in selected columns to a uniform casing standard."""
    df_copy = df.copy()
    cells_modified = 0

    for col in cols:
        if col not in df_copy.columns:
            continue
        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col].astype(str)

        if case_type == "UPPERCASE":
            converted = original.str.upper()
        elif case_type == "lowercase":
            converted = original.str.lower()
        elif case_type == "Title Case":
            converted = original.str.title()
        else:
            continue

        changed = original != converted
        cells_modified += int(changed.sum())
        df_copy.loc[mask, col] = converted

    return df_copy, {"cells_modified": cells_modified}


def remove_special_chars_custom(df, cols, remove_type="Punctuation & symbols"):
    """Remove special characters from text in selected columns."""
    import re as _re
    df_copy = df.copy()
    cells_modified = 0

    for col in cols:
        if col not in df_copy.columns:
            continue
        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col].astype(str)

        if remove_type == "All non-alphanumeric":
            # Keep only letters, digits, and spaces
            cleaned = original.str.replace(r"[^A-Za-z0-9\s]", "", regex=True)
        elif remove_type == "Punctuation & symbols":
            # Remove common punctuation and symbols but keep letters, digits, spaces
            cleaned = original.str.replace(r"[!@#$%^&*()_+=\[\]{};':\"\\|,.<>?/`~\-]", "", regex=True)
        elif remove_type == "Emojis only":
            # Unicode ranges covering most emojis
            emoji_pattern = (
                r"[\U0001F600-\U0001F64F"   # emoticons
                r"\U0001F300-\U0001F5FF"     # symbols & pictographs
                r"\U0001F680-\U0001F6FF"     # transport & map
                r"\U0001F1E0-\U0001F1FF"     # flags
                r"\U00002702-\U000027B0"     # dingbats
                r"\U0000FE00-\U0000FE0F"     # variation selectors
                r"\U0001F900-\U0001F9FF"     # supplemental symbols
                r"\U0001FA00-\U0001FA6F"     # chess symbols
                r"\U0001FA70-\U0001FAFF"     # symbols extended-A
                r"\U00002600-\U000026FF"     # misc symbols
                r"\U0000200D"                # zero-width joiner
                r"\U00002B50]+"              # star
            )
            cleaned = original.str.replace(emoji_pattern, "", regex=True)
        else:
            continue

        # Collapse any resulting double-spaces
        cleaned = cleaned.str.replace(r"\s{2,}", " ", regex=True).str.strip()
        changed = original != cleaned
        cells_modified += int(changed.sum())
        df_copy.loc[mask, col] = cleaned

    return df_copy, {"cells_modified": cells_modified}


def find_replace_custom(df, cols, rules, use_regex=False, case_sensitive=True):
    """Apply find-and-replace rules to text in selected columns.

    ``rules`` is a list of (find_str, replace_str) tuples.
    """
    import re as _re
    df_copy = df.copy()
    cells_modified = 0
    skipped_columns = []

    for col in cols:
        if col not in df_copy.columns:
            continue

        col_dtype = df_copy[col].dtype
        # Skip numeric and datetime columns explicitly
        if pd.api.types.is_numeric_dtype(col_dtype) or pd.api.types.is_datetime64_any_dtype(col_dtype):
            skipped_columns.append(col)
            continue

        # Also skip object columns whose non-null values are entirely numeric strings
        if col_dtype == object:
            non_null = df_copy[col].dropna()
            if len(non_null) > 0:
                numeric_ratio = pd.to_numeric(non_null, errors="coerce").notna().sum() / len(non_null)
                if numeric_ratio > 0.95:
                    skipped_columns.append(col)
                    continue

        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col].astype(str)
        modified = original.copy()

        for find_str, replace_str in rules:
            if not find_str:
                continue
            if use_regex:
                flags = 0 if case_sensitive else _re.IGNORECASE
                try:
                    modified = modified.str.replace(find_str, replace_str, regex=True, flags=flags)
                except _re.error:
                    continue
            else:
                modified = modified.str.replace(
                    find_str, replace_str,
                    regex=False,
                    case=case_sensitive,
                )

        changed = original != modified
        cells_modified += int(changed.sum())
        df_copy.loc[mask, col] = modified

    return df_copy, {"cells_modified": cells_modified, "skipped_columns": skipped_columns}


def standardize_dates_custom(df, cols, target_format="%Y-%m-%d"):
    """Parse dates in cols to standard formats and format as target_format.
    Invalid dates are coerced to NaT / None.
    """
    df_copy = df.copy()
    cells_modified = 0

    for col in cols:
        if col not in df_copy.columns:
            continue

        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col]

        if pd.api.types.is_datetime64_any_dtype(original):
            converted = original
        else:
            try:
                converted = pd.to_datetime(original.astype(str), format='mixed', errors='coerce')
            except TypeError:
                converted = pd.to_datetime(original.astype(str), errors='coerce')

        formatted = converted.dt.strftime(target_format).astype(object)
        formatted = formatted.where(formatted.notna(), np.nan)

        # Check changed cells
        orig_str = original.astype(str)
        changed = (orig_str != formatted.astype(str)) | (formatted.isna() & original.notna())
        cells_modified += int(changed.sum())

        df_copy.loc[mask, col] = formatted

    return df_copy, {"cells_modified": cells_modified}


def convert_numeric_custom(df, cols):
    """Strip currency symbols, commas, percentage signs, and convert strings to floats.
    Invalid values are coerced to NaN.
    """
    df_copy = df.copy()
    cells_modified = 0
    columns_converted = 0

    for col in cols:
        if col not in df_copy.columns:
            continue

        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col]

        if pd.api.types.is_numeric_dtype(original):
            df_copy.loc[mask, col] = original.astype(float)
            continue

        # Strip currency symbols, commas, percentage signs, and spaces
        cleaned = original.astype(str).str.replace(r"[$\u20AC\u00A3\u00A5,%'\s]", "", regex=True)
        # Support parenthesized negative numbers e.g. (1,250.50) -> -1250.50
        has_parens = cleaned.str.startswith("(") & cleaned.str.endswith(")")
        cleaned = cleaned.where(~has_parens, "-" + cleaned.str.slice(1, -1))

        converted = pd.to_numeric(cleaned, errors='coerce')

        changed = (original.astype(str) != converted.astype(str)) | (converted.isna() & original.notna())
        cells_modified += int(changed.sum())
        columns_converted += 1

        df_copy.loc[mask, col] = converted

    return df_copy, {"cells_modified": cells_modified, "columns_converted": columns_converted}


def normalize_booleans_custom(df, cols, true_values=None, false_values=None):
    """Map case-insensitively truthy and falsy values to standard booleans True and False.
    Default true_values: ["yes", "y", "1", "true", "t"]
    Default false_values: ["no", "n", "0", "false", "f"]
    Values not matching either list are coerced to NaN.
    """
    df_copy = df.copy()
    cells_modified = 0

    if true_values is None:
        true_values = ["yes", "y", "1", "true", "t"]
    else:
        true_values = [str(v).strip().lower() for v in true_values]

    if false_values is None:
        false_values = ["no", "n", "0", "false", "f"]
    else:
        false_values = [str(v).strip().lower() for v in false_values]

    for col in cols:
        if col not in df_copy.columns:
            continue

        mask = df_copy[col].notna()
        if not mask.any():
            continue

        original = df_copy.loc[mask, col]

        def map_val(val):
            if pd.isna(val):
                return np.nan
            if isinstance(val, bool):
                return val
            val_str = str(val).strip().lower()
            if val_str in true_values:
                return True
            elif val_str in false_values:
                return False
            else:
                return np.nan

        mapped = original.apply(map_val)

        changed_count = 0
        for orig_val, mapp_val in zip(original, mapped):
            if pd.isna(orig_val) and pd.isna(mapp_val):
                continue
            if type(orig_val) != type(mapp_val) or orig_val != mapp_val:
                changed_count += 1

        cells_modified += changed_count
        df_copy.loc[mask, col] = mapped

    return df_copy, {"cells_modified": cells_modified}


def rename_columns_custom(df, rename_rules=None, auto_clean=False):
    """Rename columns using manual rules or an automated clean header strategy."""
    df_copy = df.copy()
    columns_renamed = 0

    new_columns = []
    seen_names = set()
    for col in df_copy.columns:
        new_name = col
        if auto_clean:
            import re as _re
            # 1. Lowercase
            new_name = str(new_name).strip().lower()
            # 2. Replace spaces, hyphens, and slashes with underscores
            new_name = _re.sub(r"[\s\-/\\]+", "_", new_name)
            # 3. Strip special characters
            new_name = _re.sub(r"[^\w_]", "", new_name)
            # 4. Collapse multiple underscores
            new_name = _re.sub(r"_+", "_", new_name).strip("_")

        if rename_rules and col in rename_rules:
            new_name = rename_rules[col]

        # Resolve duplicates if new_name has already been assigned to an earlier column
        if new_name in seen_names:
            suffix = 1
            candidate = f"{new_name}_{suffix}"
            while candidate in seen_names:
                suffix += 1
                candidate = f"{new_name}_{suffix}"
            new_name = candidate

        seen_names.add(new_name)
        new_columns.append(new_name)
        if new_name != col:
            columns_renamed += 1

    df_copy.columns = new_columns

    return df_copy, {"columns_renamed": columns_renamed}


def drop_columns_custom(df, cols):
    """Drop specified columns from the DataFrame."""
    df_copy = df.copy()
    columns_dropped = 0

    to_drop = [c for c in cols if c in df_copy.columns]
    if to_drop:
        df_copy = df_copy.drop(columns=to_drop)
        columns_dropped = len(to_drop)

    return df_copy, {"columns_dropped": columns_dropped}


def split_column_custom(df, col, delimiter, new_cols, drop_original=True):
    """Split a column into multiple new columns using a delimiter."""
    df_copy = df.copy()
    if col not in df_copy.columns or not new_cols:
        return df_copy, {"columns_split": 0, "columns_added": 0, "columns_dropped": 0}

    # Convert target column to string and handle NaN values gracefully
    series = df_copy[col].astype(str).fillna("")

    # Split values
    split_df = series.str.split(delimiter, expand=True)

    num_parts = len(new_cols)
    for i, new_col_name in enumerate(new_cols):
        if i < split_df.shape[1]:
            df_copy[new_col_name] = split_df[i]
        else:
            df_copy[new_col_name] = np.nan

    columns_added = num_parts
    columns_dropped = 0
    if drop_original:
        df_copy = df_copy.drop(columns=[col])
        columns_dropped = 1

    return df_copy, {
        "columns_split": 1,
        "columns_added": columns_added,
        "columns_dropped": columns_dropped
    }


def merge_columns_custom(df, cols, separator, new_col, drop_original=False):
    """Merge multiple columns into a single column using a separator."""
    df_copy = df.copy()
    valid_cols = [c for c in cols if c in df_copy.columns]
    if not valid_cols or not new_col:
        return df_copy, {"columns_merged": 0, "columns_added": 0, "columns_dropped": 0}

    def merge_row(row):
        vals = [str(val).strip() for val in row if pd.notna(val) and str(val).strip() != ""]
        return separator.join(vals)

    df_copy[new_col] = df_copy[valid_cols].apply(merge_row, axis=1)

    columns_added = 1
    columns_dropped = 0
    if drop_original:
        to_drop = [c for c in valid_cols if c != new_col]
        df_copy = df_copy.drop(columns=to_drop)
        columns_dropped = len(to_drop)

    return df_copy, {
        "columns_merged": len(valid_cols),
        "columns_added": columns_added,
        "columns_dropped": columns_dropped
    }


def validate_ranges_custom(df, rules):
    """Identify and clean values that violate specified numerical range rules."""
    df_copy = df.copy()
    cells_modified = 0
    rows_removed = 0

    rows_to_drop = set()

    for col, op_str, value_limit, action in rules:
        if col not in df_copy.columns:
            continue

        series_numeric = pd.to_numeric(df_copy[col], errors='coerce')

        if op_str == "<":
            violating_mask = series_numeric < value_limit
        elif op_str == ">":
            violating_mask = series_numeric > value_limit
        elif op_str == "<=":
            violating_mask = series_numeric <= value_limit
        elif op_str == ">=":
            violating_mask = series_numeric >= value_limit
        elif op_str == "==":
            violating_mask = series_numeric == value_limit
        elif op_str == "!=":
            violating_mask = series_numeric != value_limit
        else:
            continue

        violating_mask = violating_mask & series_numeric.notna()

        if not violating_mask.any():
            continue

        if action == "drop":
            indices = df_copy[violating_mask].index
            rows_to_drop.update(indices)
        elif action == "null":
            if not pd.api.types.is_float_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].astype(float)
            cells_modified += int(violating_mask.sum())
            df_copy.loc[violating_mask, col] = np.nan
        elif action == "cap":
            if isinstance(value_limit, float) and not pd.api.types.is_float_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].astype(float)
            cells_modified += int(violating_mask.sum())
            df_copy.loc[violating_mask, col] = value_limit

    if rows_to_drop:
        df_copy = df_copy.drop(index=list(rows_to_drop))
        rows_removed = len(rows_to_drop)

    return df_copy, {"cells_modified": cells_modified, "rows_removed": rows_removed}


def filter_statistical_outliers_custom(df, cols, method="IQR", threshold=1.5, action="cap"):
    """Detect outliers using IQR or Z-score methods and apply cap, null, or drop actions."""
    df_copy = df.copy()
    cells_modified = 0
    rows_removed = 0

    rows_to_drop = set()

    for col in cols:
        if col not in df_copy.columns:
            continue

        series = pd.to_numeric(df_copy[col], errors='coerce')
        non_null_mask = series.notna()
        if not non_null_mask.any():
            continue

        vals = series[non_null_mask]

        if method == "IQR":
            q1 = vals.quantile(0.25)
            q3 = vals.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
        elif method == "Z-score":
            mean = vals.mean()
            std = vals.std()
            if std == 0:
                continue
            lower_bound = mean - threshold * std
            upper_bound = mean + threshold * std
        else:
            continue

        below_mask = series < lower_bound
        above_mask = series > upper_bound
        violating_mask = (below_mask | above_mask) & non_null_mask

        if not violating_mask.any():
            continue

        if action == "drop":
            indices = df_copy[violating_mask].index
            rows_to_drop.update(indices)
        elif action == "null":
            if not pd.api.types.is_float_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].astype(float)
            cells_modified += int(violating_mask.sum())
            df_copy.loc[violating_mask, col] = np.nan
        elif action == "cap":
            if not pd.api.types.is_float_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].astype(float)
            below_indices = violating_mask & below_mask
            above_indices = violating_mask & above_mask

            if below_indices.any():
                cells_modified += int(below_indices.sum())
                df_copy.loc[below_indices, col] = lower_bound
            if above_indices.any():
                cells_modified += int(above_indices.sum())
                df_copy.loc[above_indices, col] = upper_bound

    if rows_to_drop:
        df_copy = df_copy.drop(index=list(rows_to_drop))
        rows_removed = len(rows_to_drop)

    return df_copy, {"cells_modified": cells_modified, "rows_removed": rows_removed}



