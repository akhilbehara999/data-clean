# -*- coding: utf-8 -*-
"""
Feature 10 — Self-Healing Pipeline (Adaptive Cleaning Rules).

During v1 Phase 1 inspection, detects data patterns not covered by
built-in rules and offers to learn new rules, saved to custom_rules.yaml.
"""

from __future__ import annotations

import os
import re
import datetime
from typing import Optional

import pandas as pd
import yaml

RULES_FILE = "custom_rules.yaml"


# ── YAML I/O (no dependency on pyyaml — use simple text format) ──────────────

def _load_rules() -> list[dict]:
    path = os.path.join(os.getcwd(), RULES_FILE)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return []
        if isinstance(data, list):
            return data
        # If the file contains a dict, wrap it in a list for safety
        return [data] if isinstance(data, dict) else []
    except Exception:
        return []


def _append_rule(rule: dict) -> None:
    path = os.path.join(os.getcwd(), RULES_FILE)
    rules = _load_rules()
    rules.append(rule)
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(rules, f, default_flow_style=False, allow_unicode=True)
    except Exception:
        pass


def _rule_name_exists(rule_name: str) -> bool:
    return any(r.get("rule_name") == rule_name for r in _load_rules())


def delete_rule(rule_name: str) -> bool:
    """Remove a custom rule by name. Returns True if found and deleted."""
    rules = _load_rules()
    new_rules = [r for r in rules if r.get("rule_name") != rule_name]
    if len(new_rules) == len(rules):
        return False  # not found

    path = os.path.join(os.getcwd(), RULES_FILE)
    # Rewrite file
    try:
        os.remove(path)
    except Exception:
        pass
    for r in new_rules:
        _append_rule(r)
    return True


def list_rules() -> list[dict]:
    return _load_rules()


# ── Built-in rule names (to detect conflicts) ─────────────────────────────────

_BUILTIN_RULE_DOMAINS = {
    "missing_values": ["missing", "null", "nan", "na"],
    "duplicates": ["duplicate", "dup"],
    "whitespace": ["whitespace", "strip", "trim"],
    "date_format": ["date", "datetime"],
    "type_coercion": ["type", "numeric", "coerce"],
}


def _conflicts_with_builtin(rule: dict, col: str) -> Optional[str]:
    """Return builtin rule name if conflict detected, else None."""
    col_lower = col.lower()
    for builtin_name, keywords in _BUILTIN_RULE_DOMAINS.items():
        if any(kw in col_lower for kw in ["date", "datetime"]) and builtin_name == "date_format":
            return builtin_name
    return None


# ── Pattern detection ─────────────────────────────────────────────────────────

def detect_unknown_patterns(df: pd.DataFrame, filename: str) -> list[dict]:
    """
    Scan a DataFrame for patterns not covered by built-in v1 rules.
    Returns a list of proposed rule dicts:
      {rule_name, col, detection, fix, example_values, applies_to_columns_matching}
    """
    proposals: list[dict] = []
    existing_rules = _load_rules()
    existing_names = {r.get("rule_name") for r in existing_rules}

    for col in df.columns:
        s = df[col].dropna().astype(str)
        if len(s) < 5:
            continue

        col_lower = col.lower()

        # ── Pattern A: Leading-zero loss in postal/zip codes ─────────────────
        if any(kw in col_lower for kw in ["pincode", "zip", "postal", "post_code"]):
            # Check if values have inconsistent digit lengths
            lengths = s.str.len()
            modal_len = int(lengths.mode()[0]) if len(lengths) > 0 else 0
            inconsistent_pct = (lengths != modal_len).sum() / len(lengths)
            if inconsistent_pct > 0.10:
                rule_name = "leading_zero_postal_code"
                examples = s[lengths != modal_len].head(3).tolist()
                if rule_name not in existing_names:
                    proposals.append({
                        "rule_name": rule_name,
                        "col": col,
                        "detection": f"numeric column '{col}', inconsistent digit length ({inconsistent_pct*100:.0f}% variation from modal length {modal_len})",
                        "fix": f"pad with leading zeros to match modal length {modal_len}",
                        "example_values": examples,
                        "applies_to_columns_matching": ["pincode", "zip", "postal"],
                        "source_file": filename,
                    })

        # ── Pattern B: Non-standard sentinel values (not in v1's list) ───────
        _V1_SENTINELS = {"na", "n/a", "nan", "none", "null", "", "-", "?", "unknown"}
        custom_sentinels = {"--", "tbd", "pending", "n.a.", "not applicable", "to be determined", "n.a"}
        if df[col].dtype == object:
            val_lower = s.str.lower().str.strip()
            for sentinel in custom_sentinels:
                pct = (val_lower == sentinel).sum() / len(df)
                if pct > 0.05:
                    rule_name = f"sentinel_value_{sentinel.replace(' ', '_').replace('.', '')}"
                    if rule_name not in existing_names:
                        proposals.append({
                            "rule_name": rule_name,
                            "col": col,
                            "detection": f"column '{col}': sentinel value '{sentinel}' appears in {pct*100:.1f}% of rows",
                            "fix": f"treat '{sentinel}' as NaN/missing value",
                            "example_values": [sentinel],
                            "applies_to_columns_matching": [col_lower],
                            "source_file": filename,
                        })

        # ── Pattern C: Date column with non-standard format ───────────────────
        if any(kw in col_lower for kw in ["date", "dt", "time", "created", "updated"]):
            # v1 handles standard formats; detect exotic ones
            exotic_formats = [
                r"^\d{1,2}-\w{3}-\d{4}$",    # 5-Jan-2024
                r"^\d{8}$",                   # 20240105 (YYYYMMDD no separator)
                r"^\d{1,2}/\d{1,2}/\d{2}$",  # 1/5/24 (two-digit year)
            ]
            sample = s.head(20)
            for fmt_re in exotic_formats:
                match_pct = sample.str.match(fmt_re).sum() / max(len(sample), 1)
                if match_pct > 0.5:
                    rule_name = f"exotic_date_format_{col_lower.replace(' ', '_')[:20]}"
                    if rule_name not in existing_names:
                        proposals.append({
                            "rule_name": rule_name,
                            "col": col,
                            "detection": f"column '{col}': date format matches '{fmt_re}' (not in v1 standard list)",
                            "fix": "parse with pandas to_datetime(infer_datetime_format=True) or explicit format",
                            "example_values": sample.head(3).tolist(),
                            "applies_to_columns_matching": [col_lower],
                            "source_file": filename,
                        })
                    break  # one rule per column

    return proposals


# ── Interactive proposal flow ─────────────────────────────────────────────────

def offer_new_rules(proposals: list[dict], session_dict: dict) -> None:
    """
    Present each newly detected pattern to the user and offer to save a rule.
    Called during v1 Phase 1 if patterns are found.
    Updates session_dict["custom_rules"]["triggered"].
    """
    if not proposals:
        return

    for proposal in proposals:
        col = proposal["col"]
        detection = proposal["detection"]
        fix = proposal["fix"]
        examples = proposal.get("example_values", [])

        print()
        print("  ────────────────────────────────────────────────────")
        print(f"  This file has a pattern I haven't seen before:")
        print()
        print(f"    Column '{col}': {detection}")
        if examples:
            print(f"    Example values: {examples}")
        print()
        print("  Should I:")
        print("    [1] Add this as a new rule for future files (saved to custom_rules.yaml)")
        print("    [2] Fix just this file, don't save the rule")
        print("    [3] Skip this — leave as-is")
        print()

        try:
            ans = input("  Your choice (1/2/3): ").strip()
        except (EOFError, KeyboardInterrupt):
            ans = "3"

        if ans == "1":
            # Check for conflict with built-in
            conflict = _conflicts_with_builtin(proposal, col)
            if conflict:
                print(f"  [dim]Custom rule '{proposal['rule_name']}' skipped — "
                      f"built-in rule already handles this column.[/dim]")
            else:
                _append_rule({
                    "rule_name": proposal["rule_name"],
                    "applies_to_columns_matching": proposal["applies_to_columns_matching"],
                    "detection": proposal["detection"],
                    "fix": proposal["fix"],
                    "created": datetime.date.today().isoformat(),
                    "source_file": proposal["source_file"],
                })
                print(f"  ✓ Rule '{proposal['rule_name']}' saved to custom_rules.yaml.")
                print(f"    It will be applied automatically on future files with matching column names.")

            # Track triggered
            triggered = session_dict.setdefault("custom_rules", {}).setdefault("triggered", [])
            triggered.append(proposal["rule_name"])

        elif ans == "2":
            print(f"  ✓ Fix applied for this file only.")
            triggered = session_dict.setdefault("custom_rules", {}).setdefault("triggered", [])
            triggered.append(f"{proposal['rule_name']}__once")
        else:
            print(f"  Skipped.")

    print("  ────────────────────────────────────────────────────")
    print()


def apply_custom_rules(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """
    Apply any matching custom rules from custom_rules.yaml to a DataFrame.
    Additive only — never overrides built-in rules.
    Returns (possibly modified) DataFrame.
    """
    rules = _load_rules()
    if not rules:
        return df

    applied = []
    for rule in rules:
        col_patterns = rule.get("applies_to_columns_matching", [])
        if isinstance(col_patterns, str):
            # Handle flat string (parsing artifact)
            col_patterns = [p.strip().strip("'\"") for p in col_patterns.strip("[]").split(",") if p.strip()]

        fix = rule.get("fix", "")
        rule_name = rule.get("rule_name", "")

        # Find matching columns
        for col in df.columns:
            col_lower = col.lower()
            if not any(pat in col_lower for pat in col_patterns):
                continue

            # Apply the fix
            try:
                if "leading zero" in fix or "pad" in fix:
                    # Parse modal length from detection string
                    m = re.search(r"modal length (\d+)", rule.get("detection", ""))
                    modal_len = int(m.group(1)) if m else None
                    if modal_len:
                        df[col] = df[col].astype(str).str.zfill(modal_len)
                        applied.append(f"Rule '{rule_name}': padded '{col}' to {modal_len} digits")

                elif "treat" in fix and "nan" in fix.lower():
                    # Sentinel → NaN
                    m = re.search(r"treat '(.+)' as NaN", fix, re.IGNORECASE)
                    if m:
                        sentinel = m.group(1)
                        df[col] = df[col].replace(sentinel, pd.NA)
                        applied.append(f"Rule '{rule_name}': replaced '{sentinel}' with NaN in '{col}'")

                elif "to_datetime" in fix or "date" in fix.lower():
                    # Date parsing
                    df[col] = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
                    applied.append(f"Rule '{rule_name}': parsed dates in '{col}'")

            except Exception as e:
                pass  # fail silently per spec

    if applied:
        print()
        for msg in applied:
            print(f"  [Custom rule] {msg}")

    return df
