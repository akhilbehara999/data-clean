# -*- coding: utf-8 -*-
"""
Feature 2 — Recurring Report Automation.

Detects repeated analysis patterns across sessions and offers to
template them. Templates are stored in report_templates.json and
matched on filename patterns.
"""

from __future__ import annotations

import os
import json
import fnmatch
import datetime
from typing import Optional

from rich.console import Console

console = Console(force_terminal=True)

TEMPLATES_FILE = "report_templates.json"
MEMORY_FILE = "project_memory.json"

# Sequence of v2 commands that are considered "report-relevant"
REPORT_RELEVANT_COMMANDS = {
    "eda", "relationships", "geographic", "pivot",
    "comparative", "insights", "report", "export",
}


# ── I/O helpers ──────────────────────────────────────────────────────────────

def _load_templates() -> dict:
    path = os.path.join(os.getcwd(), TEMPLATES_FILE)
    if not os.path.exists(path):
        return {"templates": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"templates": []}


def _save_templates(data: dict) -> None:
    path = os.path.join(os.getcwd(), TEMPLATES_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_memory() -> dict:
    path = os.path.join(os.getcwd(), MEMORY_FILE)
    if not os.path.exists(path):
        return {"files_seen": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"files_seen": []}


# ── Wildcard matching ─────────────────────────────────────────────────────────

def _infer_pattern(filename: str) -> str:
    """
    Infer a simple wildcard pattern from a filename.
    e.g. 'weekly_sales_jan.csv' → 'weekly_sales_*.csv'
         'report_2024_Q1.xlsx'  → 'report_*_*.xlsx'
    """
    name, ext = os.path.splitext(filename)
    import re
    # Replace trailing numeric/date-like suffixes with *
    pattern = re.sub(r"[_\-]?(\d{4}|\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|q[1-4]|week\d+)",
                     "_*", name, flags=re.IGNORECASE)
    pattern = re.sub(r"_\*+", "_*", pattern)  # collapse consecutive _*
    return f"{pattern}{ext}"


def _matches_pattern(filename: str, pattern: str) -> bool:
    return fnmatch.fnmatch(filename.lower(), pattern.lower())


# ── Session sequence logging ──────────────────────────────────────────────────

def log_session_sequence(filename: str, analyses_run: list[str]) -> None:
    """
    Record the analysis sequence for a session in project_memory.json.
    Called at session end (after update_session).
    """
    mem = _load_memory()
    sequence = [a for a in analyses_run if a in REPORT_RELEVANT_COMMANDS]
    if not sequence:
        return

    # Find the entry for this file
    for entry in mem.get("files_seen", []):
        if entry.get("filename") == filename:
            entry["session_sequence"] = sequence
            break

    path = os.path.join(os.getcwd(), MEMORY_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2)
    except Exception:
        pass


# ── Detection ────────────────────────────────────────────────────────────────

def check_for_template_offer(filename: str, analyses_run: list[str]) -> Optional[str]:
    """
    After a session ends, check if this is the 3rd+ time a matching pattern
    was run. If so, return an offer message. Otherwise None.
    """
    sequence = [a for a in analyses_run if a in REPORT_RELEVANT_COMMANDS]
    if not sequence:
        return None

    # Check if a template already exists for this file
    templates = _load_templates().get("templates", [])
    for t in templates:
        if _matches_pattern(filename, t.get("file_pattern", "")):
            return None  # Already templated

    mem = _load_memory()
    pattern = _infer_pattern(filename)
    matching_files = [
        e for e in mem.get("files_seen", [])
        if _matches_pattern(e.get("filename", ""), pattern)
        and e.get("session_sequence") == sequence
    ]

    n = len(matching_files)
    if n >= 3:
        seq_str = " → ".join(f"[bold purple]{s}[/bold purple]" for s in sequence)
        ordinal = {3: "3rd", 4: "4th", 5: "5th"}.get(n, f"{n}th")
        return (
            f"I notice this is the [bold]{ordinal}[/bold] time you've uploaded a file "
            f"matching '[bold cyan]{pattern}[/bold cyan]' and run the same sequence:\n"
            f"  {seq_str}\n\n"
            "Want me to save this as a template? Next time a file matches this pattern,\n"
            "I'll run this sequence automatically — you'll just review and approve the export. (y/n)"
        )
    return None


# ── Template management ───────────────────────────────────────────────────────

def save_template(name: str, file_pattern: str, sequence: list[str],
                  auto_approve_cleaning: bool = False) -> None:
    """Save a new template to report_templates.json."""
    data = _load_templates()
    # Deduplicate by name
    data["templates"] = [t for t in data["templates"] if t.get("name") != name]
    data["templates"].append({
        "name": name,
        "file_pattern": file_pattern,
        "sequence": sequence,
        "auto_approve_cleaning": auto_approve_cleaning,
        "created": datetime.date.today().isoformat(),
    })
    _save_templates(data)


def list_templates() -> list[dict]:
    """Return all saved templates."""
    return _load_templates().get("templates", [])


def delete_template(name: str) -> bool:
    """Delete a template by name. Returns True if deleted."""
    data = _load_templates()
    before = len(data["templates"])
    data["templates"] = [t for t in data["templates"] if t.get("name") != name]
    _save_templates(data)
    return len(data["templates"]) < before


def check_template_on_load(filename: str) -> Optional[dict]:
    """
    Check if filename matches any saved template.
    Returns the template dict if matched, else None.
    """
    for t in list_templates():
        if _matches_pattern(filename, t.get("file_pattern", "")):
            return t
    return None


def format_template_offer(template: dict) -> str:
    """Format the 'run template?' message shown to the user."""
    seq_str = " → ".join(f"[bold purple]{s}[/bold purple]" for s in template.get("sequence", []))
    return (
        f"This file matches your '[bold cyan]{template['name']}[/bold cyan]' template.\n"
        f"Run the saved sequence automatically?\n"
        f"  {seq_str}\n"
        "(y/n)"
    )


# ── Template execution ────────────────────────────────────────────────────────

def run_template_sequence(template: dict, agent_v2) -> None:
    """
    Execute a template's sequence on an existing V2 agent instance.
    Still shows v1 cleaning gate — never skips it unless auto_approve_cleaning=True
    AND user confirmed it.
    """
    c = console
    sequence = template.get("sequence", [])
    # Filter out v1_clean — that is handled by v1 before we get here
    analysis_steps = [s for s in sequence if s != "v1_clean"]

    total = len(analysis_steps)
    step_map = {
        "eda": agent_v2._cmd_eda,
        "relationships": agent_v2._cmd_relationships,
        "geographic": agent_v2._cmd_geographic,
        "pivot": agent_v2._cmd_pivot,
        "comparative": agent_v2._cmd_comparative,
        "insights": agent_v2._cmd_insights,
        "report": agent_v2._cmd_report,
        "export": agent_v2._cmd_export,
        "report:html": agent_v2._cmd_report,
    }

    for i, step in enumerate(analysis_steps, 1):
        fn = step_map.get(step.lower())
        if fn:
            c.print(f"  [[bold cyan]{i}/{total}[/bold cyan]] Running [bold purple]{step}[/bold purple]...")
            try:
                fn()
            except Exception as e:
                c.print(f"  [bold red]⚠ Step '{step}' failed. Please check your data and try again.[/bold red]")
        else:
            c.print(f"  [dim]  Step '{step}' not recognized — skipping.[/dim]")

    c.print()
    c.print(f"  [bold green]✓ Template '[bold cyan]{template['name']}[/bold cyan]' complete.[/bold green]")
