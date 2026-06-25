# -*- coding: utf-8 -*-
"""
Feature 9 — Explainable Methodology Mode.

Every headline numeric result in v2/v3/v4 is logged to
session["calculation_log"]. The user can ask "how did you calculate that"
to retrieve the full trace.
"""

from __future__ import annotations

import os
import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console(force_terminal=True)


# ── Logging helpers ───────────────────────────────────────────────────────────

def log_calculation(
    session_dict: dict,
    description: str,
    result: str,
    formula: str,
    inputs: dict,
    source_file: str = "",
) -> str:
    """
    Append a calculation trace to session["calculation_log"].
    Returns the result_id.
    """
    calc_log = session_dict.setdefault("calculation_log", [])
    result_id = f"calc_{len(calc_log) + 1:03d}"

    entry = {
        "result_id": result_id,
        "description": description,
        "result": str(result),
        "formula": formula,
        "inputs": inputs,
        "source_file": source_file,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    calc_log.append(entry)
    return result_id


def find_calculation(session_dict: dict, query: str = "") -> Optional[dict]:
    """
    Find the most recent relevant calculation log entry.
    If query is empty, returns the most recent entry.
    If query given, finds the entry whose description best matches.
    """
    calc_log = session_dict.get("calculation_log", [])
    if not calc_log:
        return None

    if not query:
        return calc_log[-1]

    q = query.lower()
    # Score by keyword overlap with description
    best_score = 0
    best_entry = calc_log[-1]
    for entry in reversed(calc_log):
        desc = entry.get("description", "").lower()
        score = sum(1 for word in q.split() if word in desc)
        if score > best_score:
            best_score = score
            best_entry = entry

    return best_entry


# ── Display ───────────────────────────────────────────────────────────────────

def explain_calculation(entry: dict) -> None:
    """Print a full trace of a calculation to the console."""
    c = console
    c.print()

    result_id = entry.get("result_id", "?")
    description = entry.get("description", "?")
    result = entry.get("result", "?")
    formula = entry.get("formula", "?")
    inputs = entry.get("inputs", {})
    source_file = entry.get("source_file", "?")

    c.print(f"  [bold cyan]Here's exactly how I calculated that:[/bold cyan]")
    c.print()
    c.print(f"  [bold]{description}[/bold]: [bold green]{result}[/bold green]")
    c.print()
    c.print(f"  [bold dim]Formula:[/bold dim] [italic]{formula}[/italic]")
    c.print()

    for name, details in inputs.items():
        val = details.get("value", "?")
        source = details.get("source", "")
        row_count = details.get("row_count")

        c.print(f"  [bold]{name}[/bold]: [cyan]{val:,}[/cyan]" if isinstance(val, (int, float)) else
                f"  [bold]{name}[/bold]: [cyan]{val}[/cyan]")
        if source:
            c.print(f"    [dim]→ {source}[/dim]")
        if row_count is not None:
            c.print(f"    [dim]→ {row_count:,} rows[/dim]")

    c.print()
    c.print(f"  [dim]Source file: {source_file}[/dim]")
    c.print(f"  [dim]Result ID: {result_id}[/dim]")
    c.print()

    # Offer export
    try:
        ans = input("  Export this calculation as audit trail? (y/n): ").strip().lower()
        if ans in ("y", "yes"):
            export_calculation(entry)
    except (EOFError, KeyboardInterrupt):
        pass


def export_calculation(entry: dict) -> None:
    """Export a calculation trace to output/methodology_log.md."""
    os.makedirs("output", exist_ok=True)
    log_path = os.path.join("output", "methodology_log.md")

    lines = [
        f"## Calculation: {entry.get('description', '?')}",
        f"- **Result:** {entry.get('result', '?')}",
        f"- **Formula:** `{entry.get('formula', '?')}`",
        f"- **Source File:** {entry.get('source_file', '?')}",
        f"- **Result ID:** {entry.get('result_id', '?')}",
        f"- **Logged at:** {entry.get('timestamp', '?')}",
        "",
        "### Inputs",
    ]
    for name, details in entry.get("inputs", {}).items():
        val = details.get("value", "?")
        source = details.get("source", "")
        row_count = details.get("row_count")
        lines.append(f"- **{name}**: `{val}`")
        if source:
            lines.append(f"  - Source: {source}")
        if row_count is not None:
            lines.append(f"  - Rows: {row_count:,}")
    lines.append("")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    console.print(f"  [bold green]✓ Exported to {log_path}[/bold green]")


# ── Handle "explain" command / natural language ───────────────────────────────

def handle_explain_request(query: str, session_dict: dict) -> bool:
    """
    Called when a user asks 'how did you get that', 'show your work', etc.
    Returns True if a calculation was found and explained, False if nothing to explain.
    """
    calc_log = session_dict.get("calculation_log", [])
    if not calc_log:
        console.print(
            "\n  [bold yellow]⚠ No calculation trace available yet.[/bold yellow]\n"
            "  Run an analysis first (EDA, insights, simulation, etc.) and "
            "I'll record the methodology for you."
        )
        return False

    # Extract search keywords from query
    skip_words = {"how", "did", "you", "get", "that", "show", "your", "work",
                  "explain", "calculate", "this", "number", "result", "the"}
    search_terms = [w for w in query.lower().split() if w not in skip_words]
    search = " ".join(search_terms)

    entry = find_calculation(session_dict, search)
    if entry:
        explain_calculation(entry)
        return True
    return False


def is_explain_query(query: str) -> bool:
    """Detect if query is asking for methodology explanation."""
    q = query.lower()
    triggers = [
        "how did you calculate",
        "how did you get",
        "show your work",
        "explain this number",
        "explain that",
        "how was that calculated",
        "what's the formula",
        "how did you arrive",
        "walk me through",
        "methodology",
        "audit trail",
    ]
    return any(t in q for t in triggers)
