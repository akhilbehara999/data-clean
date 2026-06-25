"""Loader module for reading Excel and CSV files into pandas DataFrames."""
import os
import io
import pandas as pd
import chardet


def get_file_size_kb(file_obj) -> float:
    """Calculate file size in KB from a file path or file-like object."""
    if isinstance(file_obj, (str, os.PathLike)):
        try:
            return os.path.getsize(file_obj) / 1024.0
        except Exception:
            return 0.0

    if hasattr(file_obj, "size"):
        return file_obj.size / 1024.0

    try:
        current_pos = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(0)
        return size / 1024.0
    except Exception:
        return 0.0


def detect_csv_encoding(file_obj) -> str:
    """Detect encoding of a CSV file using chardet."""
    try:
        if isinstance(file_obj, (str, os.PathLike)):
            with open(file_obj, "rb") as f:
                raw_data = f.read(50000)
            return chardet.detect(raw_data).get("encoding") or "utf-8"
        else:
            current_pos = file_obj.tell()
            file_obj.seek(0)
            raw_data = file_obj.read(50000)
            file_obj.seek(current_pos)
            return chardet.detect(raw_data).get("encoding") or "utf-8"
    except Exception:
        return "utf-8"


def load_file(file_obj, filename: str, sheet_name: str = None) -> dict:
    """Load Excel or CSV files and return detailed metadata or error messages.

    Returns:
        dict: {
            "df": DataFrame or None,
            "filename": str,
            "sheet_names": list or None,
            "encoding": str or None,
            "file_size_kb": float,
            "error": str or None
        }
    """
    result = {
        "df": None,
        "filename": filename,
        "sheet_names": None,
        "encoding": None,
        "file_size_kb": 0.0,
        "error": None,
    }

    try:
        result["file_size_kb"] = round(get_file_size_kb(file_obj), 2)

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".csv":
            encoding = detect_csv_encoding(file_obj)
            result["encoding"] = encoding

            if not isinstance(file_obj, (str, os.PathLike)) and hasattr(file_obj, "seek"):
                file_obj.seek(0)

            try:
                if isinstance(file_obj, (str, os.PathLike)):
                    with open(file_obj, "r", encoding=encoding, errors="replace") as f:
                        sample = f.read(2048)
                else:
                    if hasattr(file_obj, "seek"):
                        file_obj.seek(0)
                    sample = file_obj.read(2048)
                    if isinstance(sample, bytes):
                        sample = sample.decode(encoding, errors="replace")
                    file_obj.seek(0)

                delimiters = [",", ";", "\t"]
                delim_counts = {d: sample.count(d) for d in delimiters}
                best_delim = max(delim_counts, key=delim_counts.get)
                if delim_counts[best_delim] == 0:
                    best_delim = ","

                result["df"] = pd.read_csv(file_obj, encoding=encoding, sep=best_delim)
            except Exception:
                if not isinstance(file_obj, (str, os.PathLike)) and hasattr(file_obj, "seek"):
                    file_obj.seek(0)
                result["df"] = pd.read_csv(file_obj, encoding=encoding)

        elif ext == ".xlsx":
            xls_file = pd.ExcelFile(file_obj, engine="openpyxl")
            result["sheet_names"] = xls_file.sheet_names
            target_sheet = sheet_name if sheet_name else xls_file.sheet_names[0]
            result["df"] = xls_file.parse(sheet_name=target_sheet)

        elif ext == ".xls":
            xls_file = pd.ExcelFile(file_obj, engine="xlrd")
            result["sheet_names"] = xls_file.sheet_names
            target_sheet = sheet_name if sheet_name else xls_file.sheet_names[0]
            result["df"] = xls_file.parse(sheet_name=target_sheet)

        else:
            result["error"] = f"Unsupported file extension: {ext}. Only .csv, .xlsx, and .xls are supported."
            return result

        if result["df"] is not None:
            # Let empty DataFrame pass through; app.py will handle warning
            # Resolve duplicate column names
            df = result["df"]
            new_cols = []
            seen = set()
            for col in df.columns:
                col_str = str(col)
                if col_str in seen:
                    suffix = 1
                    candidate = f"{col_str}_{suffix}"
                    while candidate in seen:
                        suffix += 1
                        candidate = f"{col_str}_{suffix}"
                    col_str = candidate
                seen.add(col_str)
                new_cols.append(col_str)
            df.columns = new_cols
            result["df"] = df
        else:
            result["error"] = "Failed to load data into a DataFrame."

    except Exception as e:
        result["error"] = f"Error reading file '{filename}': {str(e)}"
        result["df"] = None

    return result
