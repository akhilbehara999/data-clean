"""
Phase 2 — Report renderer.

- Writes a DETAILED Markdown report to disk (all findings, examples, actions).
- Prints only a concise bullet-point SUMMARY to the terminal via Rich.
"""

import os
import sys
import io
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .models import InspectionReport, Finding, CleaningAction

# Force UTF-8 on Windows to handle Unicode box-drawing and emoji glyphs
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKDOWN REPORT  (full detail → file)
# ═══════════════════════════════════════════════════════════════════════════════

def _md_finding(f: Finding) -> str:
    """Return a single finding as a Markdown bullet block."""
    lines = [f"- **[{f.column}]** {f.description}"]
    if f.count:
        lines.append(f"  - Affected: **{f.count:,}** values")
    if f.percentage:
        lines.append(f"  - Percentage: **{f.percentage:.1f}%**")
    if f.examples:
        ex = ", ".join(f"`{e}`" for e in f.examples[:5])
        lines.append(f"  - Examples: {ex}")
    return "\n".join(lines)


def _md_action(a: CleaningAction) -> str:
    """Return a single cleaning action as a Markdown numbered item."""
    return f"{a.step}. {a.description}"


def write_markdown_report(report: InspectionReport, filepath: str = "", output_dir: str = "output") -> str:
    """Write the full detailed report to a Markdown file. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    if filepath:
        from v2.utils import get_clean_path_base
        name = get_clean_path_base(filepath)
    else:
        name = os.path.splitext(report.filename)[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(output_dir, f"{name}_report_{timestamp}.md")


    lines: list[str] = []

    # ── Title ──
    lines.append(f"# 📋 Data Quality Report — `{report.filename}`")
    lines.append("")
    lines.append(f"> Generated on **{datetime.now().strftime('%B %d, %Y at %I:%M %p')}**")
    lines.append("")

    # ── Overview ──
    lines.append("## 📊 Overview")
    lines.append("")
    lines.append("| Metric   | Value |")
    lines.append("|----------|-------|")
    lines.append(f"| Rows     | {report.rows:,} |")
    lines.append(f"| Columns  | {report.columns:,} |")
    lines.append(f"| File size| {report.file_size} |")
    lines.append(f"| Total issues | {report.total_issues} |")
    lines.append("")

    if not report.has_issues:
        lines.append("## ✅ Result")
        lines.append("")
        lines.append("**This file is already clean. No issues detected.**")
        _write(md_path, lines)
        return md_path

    # ── Critical ──
    if report.critical:
        lines.append("## 🔴 Critical Issues (must fix)")
        lines.append("")
        for f in report.critical:
            lines.append(_md_finding(f))
            lines.append("")

    # ── Moderate ──
    if report.moderate:
        lines.append("## 🟡 Moderate Issues (recommended to fix)")
        lines.append("")
        for f in report.moderate:
            lines.append(_md_finding(f))
            lines.append("")

    # ── Minor ──
    if report.minor:
        lines.append("## 🟢 Minor Issues (optional)")
        lines.append("")
        for f in report.minor:
            lines.append(_md_finding(f))
            lines.append("")

    # ── Outliers ──
    if report.outliers:
        lines.append("## ⚠️ Outliers Flagged (review before deciding)")
        lines.append("")
        for f in report.outliers:
            lines.append(_md_finding(f))
            lines.append("")

    # ── Clean columns ──
    if report.clean_columns:
        lines.append("## ✅ Clean Columns (no issues)")
        lines.append("")
        lines.append(", ".join(f"`{c}`" for c in report.clean_columns))
        lines.append("")

    # ── Proposed actions ──
    if report.cleaning_actions:
        lines.append("---")
        lines.append("")
        lines.append("## 🧹 Proposed Cleaning Actions")
        lines.append("")
        lines.append("If approved, the following will be applied **in this order**:")
        lines.append("")
        for a in report.cleaning_actions:
            lines.append(_md_action(a))
        lines.append("")
        lines.append(f"**Output file:** `{report.output_path}`")
        lines.append("")
        lines.append("*Original file will NOT be modified.*")
        lines.append("")

    _write(md_path, lines)
    return md_path


def _write(path: str, lines: list[str]):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════════
#  TERMINAL SUMMARY  (concise bullet points only)
# ═══════════════════════════════════════════════════════════════════════════════

def render_report_summary(report: InspectionReport, md_path: str):
    """Print a SHORT terminal summary — only key bullet points."""

    console.print()
    console.rule("[bold bright_white]📋  DATA QUALITY SUMMARY[/bold bright_white]", style="bright_cyan")
    console.print(f"[dim]File:[/dim] [bold]{report.filename}[/bold]   •   "
                  f"[dim]{report.rows:,} rows × {report.columns:,} cols  •  {report.file_size}[/dim]")
    console.print()

    if not report.has_issues:
        console.print(Panel(
            "[bold green]✅  This file is already clean. No issues detected.[/bold green]",
            border_style="green",
        ))
        return

    # Issue counts by severity
    if report.critical:
        console.print(f"  [bold red]🔴  {len(report.critical)} Critical[/bold red]  —  "
                      + ", ".join(_short(f) for f in report.critical))
    if report.moderate:
        console.print(f"  [bold yellow]🟡  {len(report.moderate)} Moderate[/bold yellow]  —  "
                      + ", ".join(_short(f) for f in report.moderate))
    if report.minor:
        console.print(f"  [bold green]🟢  {len(report.minor)} Minor[/bold green]     —  "
                      + ", ".join(_short(f) for f in report.minor))
    if report.outliers:
        console.print(f"  [bold bright_magenta]⚠️   {len(report.outliers)} Outliers[/bold bright_magenta]  —  "
                      + ", ".join(_short(f) for f in report.outliers))

    console.print()

    if report.cleaning_actions:
        console.print(f"  [bold cyan]🧹  {len(report.cleaning_actions)} cleaning action(s) proposed[/bold cyan]")
        console.print()

    if report.clean_columns:
        cols = ", ".join(report.clean_columns)
        console.print(f"  [green]✅  Clean columns:[/green] {cols}")
        console.print()

    # Point user to the full report file
    console.print(f"  [bold bright_white]📄  Full report saved to:[/bold bright_white]  [bold underline]{md_path}[/bold underline]")
    console.print()
    console.rule(style="dim")


def _short(f: Finding) -> str:
    """One-line short description of a finding for the summary."""
    # Extract a concise label: issue_type → readable
    label = f.issue_type.replace("_", " ")
    if f.column not in ("All columns", "Multiple columns"):
        return f"{label} in \"{f.column}\""
    return label


# ═══════════════════════════════════════════════════════════════════════════════
#  LEGACY / SHARED HELPERS  (still used during cleaning phase)
# ═══════════════════════════════════════════════════════════════════════════════

def render_step_complete(action: CleaningAction):
    """Print a single step completion line."""
    console.print(f"  [green]✓[/green] Step {action.step} complete — {action.description}")


def render_cleaning_summary(
    original_rows: int, cleaned_rows: int,
    original_cols: int, cleaned_cols: int,
    issues_resolved: int, output_path: str,
):
    """Print the final cleaning summary."""
    console.print()
    console.rule("[bold bright_white]✅  CLEANING COMPLETE[/bold bright_white]", style="green")

    tbl = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    tbl.add_column(style="bold")
    tbl.add_column(justify="right")
    tbl.add_column(style="dim")
    tbl.add_column(justify="right")
    tbl.add_row("Original rows", f"{original_rows:,}", "→  Cleaned rows", f"{cleaned_rows:,}")
    tbl.add_row("Original cols", f"{original_cols:,}", "→  Cleaned cols", f"{cleaned_cols:,}")
    tbl.add_row("Issues resolved", f"{issues_resolved:,}", "", "")
    tbl.add_row("Saved to", output_path, "", "")
    console.print(tbl)
    console.rule(style="green")
    console.print()


def render_no_changes():
    console.print()
    console.print("[yellow]Understood. No changes made. Your original file is untouched.[/yellow]")
    console.print("[dim]Would you like to adjust the cleaning plan or skip specific steps?[/dim]")
    console.print()


def render_banner():
    banner = Text()
    banner.append("╔══════════════════════════════════════════════════════════════╗\n", style="bright_cyan")
    banner.append("║", style="bright_cyan")
    banner.append("        🧹  DataSanitizer v1.0                              ", style="bold bright_white")
    banner.append("║\n", style="bright_cyan")
    banner.append("║", style="bright_cyan")
    banner.append("        Expert Data Cleaning Agent for CSV & Excel           ", style="dim")
    banner.append("║\n", style="bright_cyan")
    banner.append("╚══════════════════════════════════════════════════════════════╝", style="bright_cyan")
    console.print(banner)
    console.print()


def render_error(message: str):
    console.print(f"\n[bold red]❌  Error:[/bold red] {message}\n")


def render_inspecting(filename: str):
    console.print(f"\n[bold bright_cyan]🔍  Inspecting[/bold bright_cyan] [bold]{filename}[/bold] ...")
    console.print("[dim]   Running comprehensive data quality scan...[/dim]\n")
