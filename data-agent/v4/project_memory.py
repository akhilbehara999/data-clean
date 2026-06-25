# -*- coding: utf-8 -*-
"""
Feature 1 — Cross-Session Project Memory.

Maintains project_memory.json across files and sessions.
Never stores raw data — only schema fingerprints and insight text.
"""

from __future__ import annotations

import os
import json
import fnmatch
import datetime
from typing import Optional

import pandas as pd

# ── Config ───────────────────────────────────────────────────────────────────

MAX_FILES_SEEN = 50
SIMILARITY_THRESHOLD = 0.80
MEMORY_FILENAME = "project_memory.json"
_MEMORY_PATH: Optional[str] = None  # resolved lazily


def _memory_path() -> str:
    global _MEMORY_PATH
    if _MEMORY_PATH is None:
        _MEMORY_PATH = os.path.join(os.getcwd(), MEMORY_FILENAME)
    return _MEMORY_PATH


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load_memory() -> dict:
    """Load project_memory.json; return empty structure if missing."""
    path = _memory_path()
    if not os.path.exists(path):
        return _empty_memory()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _empty_memory()


def _save_memory(mem: dict) -> None:
    """Persist project_memory.json silently (never raises)."""
    try:
        path = _memory_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2)
    except Exception:
        pass


def _empty_memory() -> dict:
    project_name = os.path.basename(os.getcwd())
    return {
        "project_name": project_name,
        "files_seen": [],
        "recurring_patterns": [],
    }


# ── Schema fingerprint ───────────────────────────────────────────────────────

def compute_fingerprint(df: pd.DataFrame) -> dict:
    """Compute a lightweight schema fingerprint (no raw data)."""
    col_types = {}
    for col in df.columns:
        dtype = str(df[col].dtype)
        if "int" in dtype or "float" in dtype:
            col_types[col] = "numeric"
        elif "datetime" in dtype:
            col_types[col] = "datetime"
        elif "object" in dtype or "category" in dtype:
            col_types[col] = "categorical"
        else:
            col_types[col] = dtype

    rows = len(df)
    # Store approximate row range (±20%) so minor file-size drift still matches
    lo = int(rows * 0.8)
    hi = int(rows * 1.2)
    return {
        "columns": list(df.columns),
        "column_types": col_types,
        "row_count_range": [lo, hi],
    }


def _fingerprint_similarity(fp_a: dict, fp_b: dict) -> float:
    """
    Return a 0-1 similarity score between two fingerprints.
    Weights: column overlap 70%, type match 30%.
    Adjustments:
        - Exclude ultra-common column names (id, name, date, value) from overlap.
        - Apply a penalty if column counts differ by more than 30%.
    """
    cols_a = set(fp_a.get("columns", []))
    cols_b = set(fp_b.get("columns", []))
    if not cols_a or not cols_b:
        return 0.0

    # Exclude ultra-common column names from overlap calculation
    ultra_common = {"id", "name", "date", "value"}
    cols_a_filtered = {c for c in cols_a if c.lower() not in ultra_common}
    cols_b_filtered = {c for c in cols_b if c.lower() not in ultra_common}
    # If after filtering one side is empty, fall back to original sets
    if not cols_a_filtered or not cols_b_filtered:
        cols_a_filtered, cols_b_filtered = cols_a, cols_b

    col_overlap = len(cols_a_filtered & cols_b_filtered) / max(len(cols_a_filtered), len(cols_b_filtered))

    types_a = fp_a.get("column_types", {})
    types_b = fp_b.get("column_types", {})
    common_cols = cols_a_filtered & cols_b_filtered
    if common_cols:
        matching_types = sum(
            1 for c in common_cols if types_a.get(c) == types_b.get(c)
        )
        type_score = matching_types / len(common_cols)
    else:
        type_score = 0.0

    base_score = 0.70 * col_overlap + 0.30 * type_score

    # Apply penalty if column counts differ by more than 30%
    cnt_a, cnt_b = len(cols_a), len(cols_b)
    if max(cnt_a, cnt_b) > 0:
        ratio = min(cnt_a, cnt_b) / max(cnt_a, cnt_b)  # 1.0 if equal, -> 0 as disparity grows
        if ratio < 0.7:  # more than 30% difference
            base_score *= ratio

    return base_score


# ── Public API ────────────────────────────────────────────────────────────────

def check_on_load(filename: str, df: pd.DataFrame) -> Optional[str]:
    """
    Compare new file's fingerprint against memory.
    Returns a message string if a similar file is found, else None.
    Called at file-load time (any version).
    """
    new_fp = compute_fingerprint(df)
    mem = _load_memory()

    best_score = 0.0
    best_entry = None
    for entry in mem.get("files_seen", []):
        stored_fp = entry.get("schema_fingerprint", {})
        score = _fingerprint_similarity(new_fp, stored_fp)
        if score > best_score and entry.get("filename") != filename:
            best_score = score
            best_entry = entry

    if best_score >= SIMILARITY_THRESHOLD and best_entry:
        prev_name = best_entry.get("filename", "?")
        prev_date = best_entry.get("date_processed", "?")
        insights = best_entry.get("key_insights", [])
        bullets = "\n".join(f"  • {i}" for i in insights[:3]) if insights else "  • (no insights recorded)"
        return (
            f"This looks similar to [bold cyan]{prev_name}[/bold cyan] "
            f"from [bold]{prev_date}[/bold]. Last time I found:\n"
            f"{bullets}\n\n"
            "Want me to check if those patterns still hold, "
            "or compare the two files directly? (y/n)"
        )
    return None


def record_session(
    filename: str,
    df: pd.DataFrame,
    session_dict: dict,
) -> None:
    """
    Append a new entry to project_memory.json after any session ends.
    Pulls insights from v2_summary and v3_summary if available.
    """
    mem = _load_memory()
    fp = compute_fingerprint(df)

    from v1 import session_manager
    active_ds = session_manager.get_active_dataset(session_dict)
    if not active_ds:
        active_ds = session_dict

    # Gather key insights text from v2/v3 session data
    insights: list[str] = []
    v2_ins = active_ds.get("v2_summary", {}).get("insights_triggered")
    if isinstance(v2_ins, dict):
        for item in v2_ins.get("insights", [])[:5]:
            title = item.get("title", "")
            detail = item.get("detail", "")
            if title:
                insights.append(f"{title}: {detail}"[:120])

    v3_hist = session_dict.get("v3_summary", {}).get("conversation_history", [])
    for msg in v3_hist:
        if msg.get("role") == "assistant":
            text = msg.get("content", "")
            if len(text) > 10:
                insights.append(text[:100].replace("\n", " "))
            if len(insights) >= 5:
                break

    v1_actions = active_ds.get("v1_summary", {}).get("actions_log", [])

    new_entry = {
        "filename": filename,
        "date_processed": datetime.date.today().isoformat(),
        "schema_fingerprint": fp,
        "key_insights": insights[:5],
        "v1_actions_applied": v1_actions[:10],
        "custom_rules_triggered": session_dict.get("custom_rules", {}).get("triggered", []),
    }

    files_seen: list = mem.get("files_seen", [])

    # Remove old entry for same filename if present
    files_seen = [e for e in files_seen if e.get("filename") != filename]

    files_seen.append(new_entry)

    # FIFO cap
    if len(files_seen) > MAX_FILES_SEEN:
        files_seen = files_seen[-MAX_FILES_SEEN:]

    mem["files_seen"] = files_seen

    # Update recurring patterns if 3+ files share an insight pattern
    _update_recurring_patterns(mem)

    _save_memory(mem)


def _update_recurring_patterns(mem: dict) -> None:
    """Detect if 3+ files share the same leading insight — add to recurring_patterns."""
    files = mem.get("files_seen", [])
    insight_counts: dict[str, int] = {}
    for entry in files:
        for ins in entry.get("key_insights", [])[:1]:  # only first insight
            key = ins[:60].lower().strip()
            insight_counts[key] = insight_counts.get(key, 0) + 1

    new_patterns = []
    for pattern, count in insight_counts.items():
        if count >= 3:
            # Build a human-readable description
            desc = f"'{pattern[:80]}' observed in {count} files"
            if desc not in mem.get("recurring_patterns", []):
                new_patterns.append(desc)

    existing = mem.get("recurring_patterns", [])
    mem["recurring_patterns"] = existing + new_patterns


def get_memory_summary() -> str:
    """Return a short human-readable summary of project memory for display."""
    mem = _load_memory()
    files_seen = mem.get("files_seen", [])
    patterns = mem.get("recurring_patterns", [])
    lines = [
        f"Project: [bold]{mem.get('project_name', '?')}[/bold]",
        f"Files seen: [cyan]{len(files_seen)}[/cyan] (max {MAX_FILES_SEEN})",
    ]
    if patterns:
        lines.append("Recurring patterns:")
        for p in patterns[:3]:
            lines.append(f"  • {p}")
    return "\n".join(lines)
