# -*- coding: utf-8 -*-
"""Session manager for state sharing across DataSanitizer versions (v1, v2, v3)."""

import os
import json
import numpy as np
import pandas as pd

def classify_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    """Classify columns into numeric, categorical, datetime, identifier, and text."""
    numeric: list[str] = []
    categorical: list[str] = []
    datetime_cols: list[str] = []
    identifier: list[str] = []
    text: list[str] = []
    
    n_rows = len(df)
    
    for col in df.columns:
        # Check if datetime
        is_dt = False
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            is_dt = True
        elif not pd.api.types.is_numeric_dtype(df[col]):
            try:
                # Use a larger sample to check for datetime format
                sample = df[col].dropna().head(200)
                if len(sample) > 0:
                    # If it can be converted to numeric, it's not a datetime string
                    try:
                        numeric_sample = pd.to_numeric(sample)
                        is_numeric_str = True
                    except Exception:
                        is_numeric_str = False

                    if not is_numeric_str:
                        # Not numeric, try datetime
                        try:
                            pd.to_datetime(sample, format="mixed")
                            is_dt = True
                        except Exception:
                            pass
                    else:
                        # Numeric: check if looks like years (e.g., years 1900-2100)
                        # Drop NA, ensure integer, within year range
                        num_clean = numeric_sample.dropna()
                        if len(num_clean) > 0 and (
                            (num_clean % 1 == 0).all() and  # integer
                            (num_clean >= 1900).all() and
                            (num_clean <= 2100).all()
                        ):
                            # Looks like years, still attempt datetime parse
                            try:
                                pd.to_datetime(sample, format="mixed")
                                is_dt = True
                            except Exception:
                                pass
            except Exception:
                pass
                
        if is_dt:
            datetime_cols.append(col)
            continue
            
        col_lower = str(col).lower()
        
        # Check if numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            # Check if it could be an identifier (e.g. name contains 'id', 'key', 'code', etc.)
            is_id = False
            if any(kw in col_lower for kw in ["id", "key", "code", "index", "pk"]):
                # If unique or mostly unique integers/strings
                s_dropna = df[col].dropna()
                if len(s_dropna) > 0 and (s_dropna.nunique() == len(s_dropna) or s_dropna.nunique() >= n_rows * 0.9):
                    is_id = True
            if is_id:
                identifier.append(col)
            else:
                numeric.append(col)
            continue
            
        # Object/string columns
        s_clean = df[col].dropna().astype(str).str.strip()
        if len(s_clean) == 0:
            categorical.append(col)
            continue
            
        # Check if it's an identifier
        is_id = False
        if any(kw in col_lower for kw in ["id", "key", "code", "pk"]):
            if df[col].nunique() >= n_rows * 0.9:
                is_id = True
                
        if is_id:
            identifier.append(col)
            continue
            
        # Check if text (long strings) or categorical (low cardinality)
        unique_pct = df[col].nunique() / n_rows if n_rows > 0 else 0
        avg_len = s_clean.str.len().mean()
        avg_words = s_clean.str.split().str.len().mean()
        
        if avg_words > 3 or (avg_len > 30 and unique_pct > 0.5):
            text.append(col)
        else:
            categorical.append(col)
            
    return {
        "numeric": numeric,
        "categorical": categorical,
        "datetime": datetime_cols,
        "identifier": identifier,
        "text": text
    }

def new_session_id() -> str:
    """Generate a short unique session ID."""
    import uuid
    return uuid.uuid4().hex[:8]

def get_session_filepath(dataset_path: str) -> str:
    """Get the path to the session JSON file for a given dataset filepath (legacy)."""
    sessions_dir = "sessions"
    os.makedirs(sessions_dir, exist_ok=True)
    import hashlib
    abs_path = os.path.abspath(dataset_path)
    path_hash = hashlib.md5(abs_path.encode('utf-8')).hexdigest()[:8]
    base_name = os.path.basename(abs_path)
    return os.path.join(sessions_dir, f"{base_name}_{path_hash}.json")

def write_current_session(session_id: str):
    """Write the session continuity pointer."""
    current_file = os.path.join("sessions", "current_session.json")
    os.makedirs(os.path.dirname(current_file), exist_ok=True)
    with open(current_file, "w", encoding="utf-8") as f:
        json.dump({"session_id": session_id}, f, indent=2)

def migrate_session_to_multi_dataset(old_session: dict) -> dict:
    """Detects the old single-dataset session shape and converts it to the new multi-dataset shape."""
    if not isinstance(old_session, dict):
        return old_session
        
    if "datasets" in old_session:
        if "session_id" not in old_session:
            old_session["session_id"] = new_session_id()
        return old_session
        
    # It's an old session. Convert it.
    new_sess = {
        "session_id": old_session.get("session_id", new_session_id()),
        "created_at": old_session.get("created_at", ""),
        "updated_at": old_session.get("updated_at", ""),
        "active_dataset_id": "ds_001",
        "datasets": {
            "ds_001": {
                "name": old_session.get("name", "dataset"),
                "file": old_session.get("file", {}),
                "v1_summary": old_session.get("v1_summary", {
                    "issues_resolved": 0,
                    "actions_log": []
                }),
                "v2_summary": old_session.get("v2_summary", {
                    "analyses_run": [],
                    "eda_results": None,
                    "insights_triggered": None,
                    "pivot_results": None,
                    "comparison_results": None,
                    "geo_results": None
                }),
                "column_types": old_session.get("column_types", {})
            }
        },
        "v3_summary": old_session.get("v3_summary", {
            "conversation_history": [],
            "queries_run": []
        }),
        "active_version": old_session.get("active_version", "v2"),
        "active_provider": old_session.get("active_provider", None),
        "active_model_id": old_session.get("active_model_id", None)
    }
    
    for k, v in old_session.items():
        if k not in ["session_id", "created_at", "updated_at", "active_dataset_id", "datasets", "v3_summary", "active_version", "active_provider", "active_model_id", "file", "v1_summary", "v2_summary", "column_types"]:
            new_sess[k] = v
            
    return new_sess

def add_dataset(
    session: dict,
    name: str,
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    applied_actions: list[str],
    issues_resolved: int,
    was_cleaned: bool
) -> str:
    """Builds a dataset entry, saves pickle, inserts into session, returns new ds_XXX id."""
    existing_ids = [k for k in session.get("datasets", {}).keys() if k.startswith("ds_")]
    if existing_ids:
        indices = []
        for eid in existing_ids:
            try:
                indices.append(int(eid.split("_")[1]))
            except ValueError:
                pass
        next_idx = max(indices) + 1 if indices else 1
    else:
        next_idx = 1
    ds_id = f"ds_{next_idx:03d}"
    
    session_id = session.get("session_id")
    if not session_id:
        session_id = new_session_id()
        session["session_id"] = session_id
        
    pkl_name = f".session_df_{session_id}_{ds_id}.pkl"
    pkl_path = os.path.abspath(os.path.join("output", pkl_name))
    
    os.makedirs("output", exist_ok=True)
    cleaned_df.to_pickle(pkl_path)
    
    col_types = classify_columns(cleaned_df)
    
    dataset_entry = {
        "name": name,
        "file": {
            "original": name,
            "cleaned": pkl_path,
            "original_shape": [int(original_df.shape[0]), int(original_df.shape[1])],
            "cleaned_shape": [int(cleaned_df.shape[0]), int(cleaned_df.shape[1])],
            "columns": list(cleaned_df.columns),
            "dataframe_pickle": pkl_path
        },
        "v1_summary": {
            "issues_resolved": int(issues_resolved),
            "actions_log": list(applied_actions)
        },
        "v2_summary": {
            "analyses_run": [],
            "eda_results": None,
            "insights_triggered": None,
            "pivot_results": None,
            "comparison_results": None,
            "geo_results": None
        },
        "column_types": col_types
    }
    
    if "datasets" not in session:
        session["datasets"] = {}
    session["datasets"][ds_id] = dataset_entry
    
    return ds_id

def remove_dataset(session: dict, dataset_id: str) -> None:
    """Deletes the entry and its pickle file."""
    # Check if dataset exists in session
    if "datasets" not in session or dataset_id not in session["datasets"]:
        return

    # Remove the pickle file if it exists
    entry = session["datasets"][dataset_id]
    pkl_path = entry.get("file", {}).get("dataframe_pickle")
    if pkl_path and os.path.exists(pkl_path):
        try:
            os.remove(pkl_path)
        except Exception:
            # If we can't remove the pickle file, continue anyway to remove the session entry
            # This prevents stale session entries which are worse than orphaned files
            pass

    # Remove the dataset entry from session
    del session["datasets"][dataset_id]

    # Update active dataset if needed
    if session.get("active_dataset_id") == dataset_id:
        remaining_datasets = session.get("datasets", {})
        if remaining_datasets:
            session["active_dataset_id"] = list(remaining_datasets.keys())[0]
        else:
            session["active_dataset_id"] = ""

def get_active_dataset(session: dict) -> dict:
    """Returns the active dataset entry."""
    active_id = session.get("active_dataset_id")
    if active_id and "datasets" in session and active_id in session["datasets"]:
        return session["datasets"][active_id]
    return {}

def load_dataset_df(session: dict, dataset_id: str) -> pd.DataFrame:
    """Unpickles that dataset's dataframe."""
    if "datasets" in session and dataset_id in session["datasets"]:
        entry = session["datasets"][dataset_id]
        pkl_path = entry.get("file", {}).get("dataframe_pickle")
        if pkl_path and os.path.exists(pkl_path):
            return pd.read_pickle(pkl_path)
        cleaned_path = entry.get("file", {}).get("cleaned")
        if cleaned_path and os.path.exists(cleaned_path):
            if cleaned_path.endswith(".csv"):
                return pd.read_csv(cleaned_path)
            elif cleaned_path.endswith((".xlsx", ".xls")):
                return pd.read_excel(cleaned_path)
    raise FileNotFoundError(f"Dataframe pickle for dataset '{dataset_id}' not found.")

def set_active_dataset(session: dict, dataset_id: str) -> None:
    """Sets the active dataset."""
    if "datasets" in session and dataset_id in session["datasets"]:
        session["active_dataset_id"] = dataset_id

def init_session(
    original_filepath: str,
    cleaned_filepath: str,
    original_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    applied_actions: list[str],
    issues_resolved: int
) -> dict:
    """Initialize a brand-new session object containing one dataset."""
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sid = new_session_id()
    
    session = {
        "session_id": sid,
        "created_at": now_str,
        "updated_at": now_str,
        "active_dataset_id": "",
        "datasets": {},
        "v3_summary": {
            "conversation_history": [],
            "queries_run": []
        },
        "active_version": "v1"
    }
    
    name = os.path.basename(original_filepath)
    ds_id = add_dataset(
        session=session,
        name=name,
        original_df=original_df,
        cleaned_df=cleaned_df,
        applied_actions=applied_actions,
        issues_resolved=issues_resolved,
        was_cleaned=bool(applied_actions)
    )
    session["active_dataset_id"] = ds_id
    
    # Store absolute paths in the dataset entry
    session["datasets"][ds_id]["file"]["original"] = os.path.abspath(original_filepath)
    session["datasets"][ds_id]["file"]["cleaned"] = os.path.abspath(cleaned_filepath)
    
    save_session(session)
    write_current_session(sid)
    
    return session

def save_session(session_dict: dict, df: pd.DataFrame = None):
    """Save the session object to its unique session JSON file in the sessions directory."""
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Migration is now performed only during load_session().

    session_id = session_dict.get("session_id")
    if not session_id:
        session_id = new_session_id()
        session_dict["session_id"] = session_id

    session_dict["updated_at"] = now_str
    
    session_to_save = session_dict.copy()
    if "df" in session_to_save:
        del session_to_save["df"]
        
    def clean_types(obj):
        if isinstance(obj, dict):
            return {k: clean_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_types(x) for x in obj]
        elif isinstance(obj, tuple):
            return [clean_types(x) for x in obj]
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, pd.Period):
            return str(obj)
        elif hasattr(obj, "item"):
            return obj.item()
        else:
            try:
                if pd.isna(obj):
                    return None
            except (TypeError, ValueError):
                return str(obj)
            return obj
        
    session_to_save = clean_types(session_to_save)
    
    session_file = os.path.join("sessions", f"{session_id}.json")
    os.makedirs(os.path.dirname(session_file), exist_ok=True)
    
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session_to_save, f, indent=2)
        
    if df is not None:
        active_ds_id = session_dict.get("active_dataset_id")
        if active_ds_id and active_ds_id in session_dict.get("datasets", {}):
            file_info = session_dict["datasets"][active_ds_id].setdefault("file", {})
            pkl_path = file_info.get("dataframe_pickle")
            if not pkl_path:
                pkl_path = os.path.join("output", f"{active_ds_id}_df.pkl")
                file_info["dataframe_pickle"] = pkl_path
            os.makedirs(os.path.dirname(pkl_path) or "output", exist_ok=True)
            df.to_pickle(pkl_path)

def load_session(dataset_path: str = None) -> dict:
    """Load the session object from its JSON file in the sessions directory."""
    session_file = None
    
    current_pointer_path = os.path.join("sessions", "current_session.json")
    if os.path.exists(current_pointer_path):
        try:
            with open(current_pointer_path, "r", encoding="utf-8") as f:
                pointer = json.load(f)
            sid = pointer.get("session_id")
            if sid:
                candidate = os.path.join("sessions", f"{sid}.json")
                if os.path.exists(candidate):
                    session_file = candidate
        except Exception:
            pass

    if not session_file:
        if dataset_path:
            session_file = get_session_filepath(dataset_path)
        else:
            sessions_dir = "sessions"
            if os.path.exists(sessions_dir):
                files = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".json") and not f.endswith("current_session.json")]
                if files:
                    files.sort(key=os.path.getmtime, reverse=True)
                    session_file = files[0]
                else:
                    session_file = os.path.join(sessions_dir, "session.json")
            else:
                session_file = "session.json"
                
    if not os.path.exists(session_file):
        raise FileNotFoundError(f"Session file '{session_file}' not found. No active session exists.")
        
    with open(session_file, "r", encoding="utf-8") as f:
        sess = json.load(f)

    # Ensure the session dictionary conforms to the latest multi‑dataset schema.
    migrated_sess = migrate_session_to_multi_dataset(sess)
    return migrated_sess

