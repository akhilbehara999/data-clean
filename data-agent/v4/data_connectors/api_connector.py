# -*- coding: utf-8 -*-
"""
Feature 3C — Generic REST / JSON API connector.

Usage:
    python main.py --connect api --url <endpoint> [--key <auth_token>]

Auto-flattens JSON → DataFrame. Handles nested structures
interactively (3+ levels prompts user).
"""

from __future__ import annotations

import os
import json
import hashlib
import datetime
from typing import Optional, Union

import pandas as pd

CACHE_DIR = os.path.join("output", ".cache")
_DEEP_NEST_THRESHOLD = 3


def _cache_path(url: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return os.path.join(CACHE_DIR, f"api_{h}.pkl")


def _measure_depth(obj, depth: int = 0) -> int:
    """Recursively measure max nesting depth of a JSON structure."""
    if isinstance(obj, dict):
        if not obj:
            return depth
        return max(_measure_depth(v, depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return depth
        return _measure_depth(obj[0], depth)
    return depth


def _detect_nested_keys(obj: dict) -> list[str]:
    """Return keys whose values are lists of dicts (typical nested relations)."""
    if not isinstance(obj, dict):
        return []
    nested = []
    for k, v in obj.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            nested.append(k)
    return nested


def fetch_api(url: str, auth_key: str = "", force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """
    Fetch JSON from a REST endpoint and return as DataFrame.
    Falls back gracefully if network is unavailable.
    """
    try:
        import requests  # type: ignore
    except ImportError:
        print("  ⚠ 'requests' package not installed. Run: pip install requests")
        print("  For now, you can download the JSON manually and load it as a file.")
        return None

    cache = _cache_path(url)
    if not force_refresh and os.path.exists(cache):
        try:
            df = pd.read_pickle(cache)
            print(f"  [API] Loaded from cache. Use /refresh to re-fetch.")
            return df
        except Exception:
            pass

    headers = {}
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print(f"  ⚠ Cannot reach {url} — no internet or endpoint is down.")
        print("  For now, you can download the data manually and load it as a file.")
        return None
    except requests.exceptions.HTTPError as e:
        print("  ⚠ API returned an error. Please check the endpoint URL and your authentication credentials.")
        return None
    except Exception as e:
        print("  ⚠ API fetch failed. Please check your internet connection and the endpoint URL.")
        return None

    df = _json_to_dataframe(data, url)
    if df is not None:
        df.to_pickle(cache)
    return df


def _json_to_dataframe(data, url: str) -> Optional[pd.DataFrame]:
    """Flatten JSON data to DataFrame, with interactive handling for deep nesting."""

    # Wrap scalars / single dicts
    if isinstance(data, dict):
        # Check if there's a dominant list key (e.g. {"results": [...], "count": 5})
        list_keys = [k for k, v in data.items() if isinstance(v, list)]
        if list_keys and len(list_keys) == 1:
            data = data[list_keys[0]]
        elif list_keys:
            # Multiple list keys — use first as primary
            data = data[list_keys[0]]

    if isinstance(data, list) and data:
        depth = _measure_depth(data[0])
    elif isinstance(data, dict):
        depth = _measure_depth(data)
        data = [data]
    else:
        print("  ⚠ Unexpected JSON structure — cannot auto-flatten.")
        return None

    if depth >= _DEEP_NEST_THRESHOLD and isinstance(data[0], dict):
        nested_keys = _detect_nested_keys(data[0])
        if nested_keys:
            print(f"\n  This JSON has nested structures inside: {nested_keys}")
            for i, k in enumerate(nested_keys, 1):
                print(f"    [{i}] '{k}' records (with parent info attached)")
            print(f"    [{len(nested_keys)+1}] Top-level records only")
            print(f"    [{len(nested_keys)+2}] Both as separate datasets (batch mode)")
            try:
                choice = input("  Analyze as: ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(nested_keys):
                        key = nested_keys[idx]
                        # Flatten: explode the nested list, attach parent fields
                        flat = []
                        parent_keys = [k for k in data[0].keys() if k not in nested_keys]
                        for rec in data:
                            parent_info = {pk: rec.get(pk) for pk in parent_keys}
                            for child in rec.get(key, []):
                                row = {**parent_info, **child}
                                flat.append(row)
                        data = flat
                    # else: use top-level or batch — just fall through
            except Exception:
                pass

    try:
        df = pd.json_normalize(data)
        print(f"  [API] Loaded {len(df):,} rows × {len(df.columns)} cols from {url}")
        return df
    except Exception as e:
        print("  ⚠ Failed to process the API response data. Please check that the endpoint returns valid JSON data.")
        return None


def refresh_api(url: str, auth_key: str = "") -> Optional[pd.DataFrame]:
    """Force re-fetch from API, show diff vs cached version."""
    cache = _cache_path(url)
    old_df: Optional[pd.DataFrame] = None
    if os.path.exists(cache):
        try:
            old_df = pd.read_pickle(cache)
        except Exception:
            pass

    new_df = fetch_api(url, auth_key, force_refresh=True)
    if new_df is not None and old_df is not None:
        added = len(new_df) - len(old_df)
        sign = "+" if added >= 0 else ""
        print(f"  [API /refresh] Rows: {len(old_df)} → {len(new_df)} ({sign}{added})")
    return new_df
