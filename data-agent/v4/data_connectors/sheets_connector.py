# -*- coding: utf-8 -*-
"""
Feature 3A — Google Sheets connector.

Usage:
    python main.py --connect sheets --id <sheet_id>

Reads a Google Sheet via the Google Drive API and returns a DataFrame.
Caches the result to output/.cache/ and supports /refresh.
"""

from __future__ import annotations

import os
import json
import hashlib
import datetime
from typing import Optional

import pandas as pd

CACHE_DIR = os.path.join("output", ".cache")


def _cache_path(sheet_id: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5(sheet_id.encode()).hexdigest()[:8]
    return os.path.join(CACHE_DIR, f"sheets_{h}.pkl")


def _meta_path(sheet_id: str) -> str:
    h = hashlib.md5(sheet_id.encode()).hexdigest()[:8]
    return os.path.join(CACHE_DIR, f"sheets_{h}_meta.json")


def load_sheet(sheet_id: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """
    Fetch a Google Sheet and return as a DataFrame.
    Returns None if the Google Drive API / credentials are unavailable.

    Falls back gracefully with a clear setup message if gspread or
    Google auth is not configured.
    """
    cache = _cache_path(sheet_id)
    meta = _meta_path(sheet_id)

    # ── Try to serve from cache first ────────────────────────────────────────
    if not force_refresh and os.path.exists(cache):
        try:
            df = pd.read_pickle(cache)
            if os.path.exists(meta):
                with open(meta) as f:
                    m = json.load(f)
                print(f"  [Sheets] Loaded from cache (fetched {m.get('fetched_at', '?')}). "
                      "Use /refresh to re-fetch.")
            return df
        except Exception:
            pass  # fall through to live fetch

    # ── Live fetch via gspread ────────────────────────────────────────────────
    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError:
        _print_setup_instructions("sheets")
        return None

    cred_path = os.path.join(os.getcwd(), "google_credentials.json")
    if not os.path.exists(cred_path):
        _print_setup_instructions("sheets", missing="google_credentials.json")
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        # Cache
        df.to_pickle(cache)
        with open(meta, "w") as f:
            json.dump({"fetched_at": datetime.datetime.now().isoformat(),
                       "sheet_id": sheet_id}, f)

        print(f"  [Sheets] Loaded {len(df)} rows × {len(df.columns)} cols "
              f"from Sheet '{sh.title}'.")
        return df

    except Exception as e:
        print("  ⚠ Google Sheets fetch failed. Please check your internet connection and try again.")
        print("  Falling back to manual file upload.")
        return None


def refresh_sheet(sheet_id: str) -> Optional[pd.DataFrame]:
    """Force re-fetch from Google Sheets, show diff vs cached version."""
    cache = _cache_path(sheet_id)
    old_df: Optional[pd.DataFrame] = None
    if os.path.exists(cache):
        try:
            old_df = pd.read_pickle(cache)
        except Exception:
            pass

    new_df = load_sheet(sheet_id, force_refresh=True)
    if new_df is not None and old_df is not None:
        _print_diff(old_df, new_df)
    return new_df


def _print_diff(old: pd.DataFrame, new: pd.DataFrame) -> None:
    added = len(new) - len(old)
    changed = 0
    if len(old) > 0 and len(new) > 0:
        # Simple row-count comparison
        pass
    sign = "+" if added >= 0 else ""
    print(f"  [Sheets /refresh] Rows: {len(old)} → {len(new)} ({sign}{added})")
    if len(new.columns.tolist()) != len(old.columns.tolist()):
        print(f"  [Sheets /refresh] Columns changed: {old.columns.tolist()} → {new.columns.tolist()}")


def _print_setup_instructions(source: str, missing: str = "") -> None:
    print()
    print(f"  ⚠ Google Sheets connection requires OAuth / service account setup.")
    if missing:
        print(f"    Missing: {missing}")
    print("    Steps:")
    print("    1. Create a service account at https://console.cloud.google.com/iam-admin/serviceaccounts")
    print("    2. Download the JSON key as 'google_credentials.json' in your project folder.")
    print("    3. Share the sheet with the service account email.")
    print("    4. Install: pip install gspread google-auth")
    print()
    print("  For now, you can upload the file directly instead.")
    print()
