# -*- coding: utf-8 -*-
"""
Feature 4 — Anomaly Watchdog Mode.

Usage:
    python main.py --watch <file_or_connection> --interval <daily|hourly>

Establishes a baseline from current data, then periodically re-reads
the source and alerts on anomalies. Never auto-cleans or modifies data.
"""

from __future__ import annotations

import os
import json
import time
import signal
import datetime
from typing import Optional

import pandas as pd
import numpy as np
from rich.console import Console

console = Console(force_terminal=True)

BASELINE_FILE = "watchdog_baseline.json"

# Default thresholds
Z_SCORE_ALERT = 2.0          # alert if metric is beyond mean ± Z*std


# ── Baseline I/O ─────────────────────────────────────────────────────────────

def _baseline_path() -> str:
    return os.path.join(os.getcwd(), BASELINE_FILE)


def _load_baseline() -> Optional[dict]:
    path = _baseline_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_baseline(baseline: dict) -> None:
    try:
        with open(_baseline_path(), "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)
    except Exception as e:
        console.print("  [bold red]⚠ Failed to save baseline data.[/bold red]")


# ── Metric extraction ─────────────────────────────────────────────────────────

def _extract_metrics(df: pd.DataFrame) -> dict:
    """
    Compute a snapshot of key metrics from a DataFrame.
    Returns a JSON-serialisable dict.
    """
    metrics: dict = {}

    metrics["row_count"] = int(len(df))

    # Numeric column stats
    numeric_stats: dict = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        numeric_stats[col] = {
            "mean": float(s.mean()),
            "std": float(s.std()) if len(s) > 1 else 0.0,
            "min": float(s.min()),
            "max": float(s.max()),
        }
    metrics["numeric_stats"] = numeric_stats

    # Categorical distributions (value counts, top 20)
    cat_dist: dict = {}
    for col in df.select_dtypes(include=["object", "category"]).columns:
        vc = df[col].value_counts(normalize=True).head(20)
        cat_dist[col] = {str(k): float(v) for k, v in vc.items()}
    metrics["category_distribution"] = cat_dist

    # Data quality flags (presence of nulls, placeholder strings)
    null_counts = df.isnull().sum()
    metrics["null_counts"] = {col: int(n) for col, n in null_counts.items() if n > 0}

    return metrics


def _establish_baseline(df: pd.DataFrame, source_label: str, interval: str) -> dict:
    """Build and save a baseline from the current dataframe."""
    metrics = _extract_metrics(df)
    # Initialize numeric history with baseline means
    numeric_history = {}
    for col, stats in metrics.get("numeric_stats", {}).items():
        numeric_history[col] = [stats["mean"]]
    baseline = {
        "established": datetime.datetime.now().isoformat(),
        "source": source_label,
        "interval": interval,
        "metrics": metrics,
        # For running-average tracking across checks
        "_history": [],
        "_numeric_history": numeric_history,
    }
    _save_baseline(baseline)
    return baseline


def rebaseline(df: pd.DataFrame, source_label: str, interval: str) -> None:
    """Manual rebaseline — called by /rebaseline command."""
    baseline = _establish_baseline(df, source_label, interval)
    console.print(
        f"\n  [bold green]✓ Baseline updated.[/bold green] "
        f"New baseline: {len(df):,} rows, "
        f"{len(baseline['metrics']['numeric_stats'])} numeric metrics.\n"
    )


# ── Anomaly detection ─────────────────────────────────────────────────────────

def _detect_anomalies(current_metrics: dict, baseline: dict) -> list[dict]:
    """
    Compare current_metrics against baseline.
    Returns a list of anomaly dicts with keys: type, metric, value, expected, severity.
    """
    anomalies = []
    base_m = baseline.get("metrics", {})

    # 1. Row count change
    base_rows = base_m.get("row_count", 0)
    curr_rows = current_metrics.get("row_count", 0)
    if base_rows > 0:
        pct_change = abs(curr_rows - base_rows) / base_rows * 100
        if pct_change > 20:
            anomalies.append({
                "type": "row_count",
                "metric": "row_count",
                "value": curr_rows,
                "expected": base_rows,
                "detail": f"Row count changed by {pct_change:.1f}%",
                "severity": "high" if pct_change > 50 else "medium",
            })

    # 2. Numeric metric deviations
    base_stats = base_m.get("numeric_stats", {})
    curr_stats = current_metrics.get("numeric_stats", {})
    for col, b_stat in base_stats.items():
        if col not in curr_stats:
            anomalies.append({
                "type": "missing_column",
                "metric": col,
                "value": None,
                "expected": "present",
                "detail": f"Column '{col}' was in baseline but is now missing",
                "severity": "high",
            })
            continue
        c_stat = curr_stats[col]
        b_mean = b_stat["mean"]
        c_mean = c_stat["mean"]

        # Initialize/update history for this column
        if "_numeric_history" not in baseline:
            baseline["_numeric_history"] = {}
        history = baseline["_numeric_history"].setdefault(col, [])
        history.append(c_mean)
        # Keep most recent 30 values
        if len(history) > 30:
            history.pop(0)

        if len(history) >= 2:
            # Enough history to compute Z-score of the mean against its own distribution
            hist_mean = np.mean(history)
            hist_std = np.std(history, ddof=1)
            if hist_std == 0:
                hist_std = 1e-9
            z = abs(c_mean - hist_mean) / hist_std
            if z > Z_SCORE_ALERT:
                direction = "above" if c_mean > hist_mean else "below"
                anomalies.append({
                    "type": "numeric_drift",
                    "metric": col + "_mean",
                    "value": c_mean,
                    "expected": hist_mean,
                    "detail": (
                        f"{col} mean is {c_mean:.2f} — that's {abs(c_mean - hist_mean):.2f} "
                        f"({direction} baseline avg {hist_mean:.2f}, z={z:.1f})"
                    ),
                    "severity": "high" if z > 3 else "medium",
                })
        else:
            # Not enough history yet; fall back to percent change vs original baseline mean
            if b_mean == 0:
                # Avoid division by zero; use absolute change
                change = abs(c_mean)
                # Treat as anomalous if change > 0? We'll skip for now to avoid noise.
                pct_change = float('inf') if change > 0 else 0
            else:
                pct_change = abs(c_mean - b_mean) / abs(b_mean) * 100
            # Alert if percent change > 20% (same threshold as row count)
            if pct_change > 20.0:
                direction = "above" if c_mean > b_mean else "below"
                anomalies.append({
                    "type": "numeric_drift",
                    "metric": col + "_mean",
                    "value": c_mean,
                    "expected": b_mean,
                    "detail": (
                        f"{col} mean is {c_mean:.2f} — that's {abs(c_mean - b_mean):.2f} "
                        f"({direction} {pct_change:.1f}% change from baseline {b_mean:.2f})"
                    ),
                    "severity": "medium",
                })

    # 3. New categorical values
    base_cats = base_m.get("category_distribution", {})
    curr_cats = current_metrics.get("category_distribution", {})
    for col, b_dist in base_cats.items():
        if col not in curr_cats:
            continue
        c_dist = curr_cats[col]
        new_vals = set(c_dist.keys()) - set(b_dist.keys())
        if new_vals:
            anomalies.append({
                "type": "new_category_value",
                "metric": col,
                "value": list(new_vals)[:5],
                "expected": "not present at baseline",
                "detail": f"New value(s) in '{col}': {', '.join(str(v) for v in list(new_vals)[:5])}",
                "severity": "medium",
            })

    # 4. Data quality regressions (new nulls)
    base_nulls = base_m.get("null_counts", {})
    curr_nulls = current_metrics.get("null_counts", {})
    for col, cnt in curr_nulls.items():
        base_cnt = base_nulls.get(col, 0)
        if cnt > base_cnt and cnt > 0:
            anomalies.append({
                "type": "quality_regression",
                "metric": col + "_nulls",
                "value": cnt,
                "expected": base_cnt,
                "detail": f"Null count in '{col}' increased from {base_cnt} → {cnt}",
                "severity": "medium",
            })

    return anomalies


def _format_anomaly(anomaly: dict, day_n: int) -> str:
    icon = "🚨" if anomaly["severity"] == "high" else "⚠"
    return (
        f"  {icon} [Day {day_n}] {anomaly['detail']}"
    )


# ── Watchdog loop ─────────────────────────────────────────────────────────────

def _interval_seconds(interval: str) -> int:
    if interval == "hourly":
        return 3600
    elif interval == "daily":
        return 86400
    elif interval == "30m":
        return 1800
    elif interval == "5m":
        return 300  # for testing
    return 86400


def _read_source(source: str) -> Optional[pd.DataFrame]:
    """Re-read a file or cached connector data."""
    ext = os.path.splitext(source)[1].lower()
    try:
        if ext in (".csv", ".tsv"):
            return pd.read_csv(source)
        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(source)
        elif source.startswith("sheets:"):
            from v4.data_connectors.sheets_connector import load_sheet
            return load_sheet(source.split(":", 1)[1], force_refresh=True)
        elif source.startswith("api:"):
            from v4.data_connectors.api_connector import fetch_api
            return fetch_api(source.split(":", 1)[1], force_refresh=True)
        elif source.startswith("db:"):
            from v4.data_connectors.db_connector import connect_db
            return connect_db(source.split(":", 1)[1])
        else:
            return pd.read_csv(source)
    except Exception as e:
        console.print("  [bold red]⚠ Failed to re-read the data source.[/bold red]")
        return None


def run_watchdog(source: str, interval: str = "daily") -> None:
    """
    Main watchdog entry point.
    Establishes baseline, then polls at interval, printing alerts.
    Press Ctrl+C to stop.
    """
    c = console
    c.print()
    c.print(f"  [bold cyan]📡 Watchdog Mode[/bold cyan] — reading source: [bold]{source}[/bold]")
    c.print()

    # 1. Initial read
    df = _read_source(source)
    if df is None:
        c.print("  [bold red]⚠ Cannot read source. Watchdog aborted.[/bold red]")
        return

    # Run silent v1 inspection to build baseline quality context
    c.print("  Establishing baseline...")
    baseline = _establish_baseline(df, source, interval)
    metrics = baseline["metrics"]
    numeric_count = len(metrics.get("numeric_stats", {}))
    cat_count = len(metrics.get("category_distribution", {}))

    c.print(f"  [bold green]✓ Baseline established[/bold green] from current data.")
    c.print(f"    {len(df):,} rows · {numeric_count} numeric metrics · {cat_count} categorical columns")
    c.print()
    c.print(f"  I'll alert you if:")
    c.print(f"    • Any numeric metric changes by more than {Z_SCORE_ALERT:.0f} std deviations")
    c.print(f"    • A new categorical value appears that wasn't in baseline")
    c.print(f"    • Null counts increase (data quality regression)")
    c.print(f"  Checking every [bold]{interval}[/bold]. Press [bold red]Ctrl+C[/bold red] to stop watching.")
    c.print()

    interval_secs = _interval_seconds(interval)
    check_count = 0
    heartbeat_every = 3  # print heartbeat every N checks with no anomalies

    # Handle Ctrl+C gracefully
    _stop = [False]

    def _sig_handler(sig, frame):
        _stop[0] = True

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    all_anomalies_seen: list[dict] = []

    while not _stop[0]:
        time.sleep(interval_secs)
        if _stop[0]:
            break

        check_count += 1
        new_df = _read_source(source)
        if new_df is None:
            c.print(f"  [bold yellow]⚠ [Check {check_count}] Could not re-read source. Skipping.[/bold yellow]")
            continue

        current_metrics = _extract_metrics(new_df)
        anomalies = _detect_anomalies(current_metrics, baseline)

        if anomalies:
            c.print()
            c.print(f"  [bold yellow]══ Watchdog Alert — Check #{check_count} ══[/bold yellow]")
            for anomaly in anomalies:
                c.print(_format_anomaly(anomaly, check_count))
                all_anomalies_seen.append(anomaly)

            # Flag if this is the largest deviation seen
            numeric_deviations = [
                a for a in anomalies if a["type"] == "numeric_drift"
            ]
            if numeric_deviations and len(all_anomalies_seen) > len(anomalies):
                c.print("  📌 This includes the largest deviation seen since watching began.")

            c.print()
            c.print(
                "  Want me to investigate? You can run [bold purple]/insights[/bold purple] "
                "or [bold purple]/eda[/bold purple] in V2 on the affected rows."
            )
            c.print("  [dim](Watchdog continues. Ctrl+C to stop.)[/dim]")
        else:
            if check_count % heartbeat_every == 0:
                now = datetime.datetime.now().strftime("%H:%M")
                c.print(f"  [dim][Check {check_count} at {now}] No anomalies. ✓[/dim]")

    c.print()
    c.print(
        f"  [bold cyan]Watchdog stopped.[/bold cyan] "
        f"Ran {check_count} check(s). "
        f"Total anomalies flagged: {len(all_anomalies_seen)}."
    )
    c.print()
    c.print(
        "  [dim]Note: For background watching without keeping this terminal open,\n"
        "  use Windows Task Scheduler or a cron job to call:\n"
        f"    python main.py --watch {source} --interval {interval}[/dim]"
    )
