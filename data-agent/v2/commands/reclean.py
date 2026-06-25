"""Command [R] — Re-clean: return to V1 cleaning mode."""

from __future__ import annotations
from typing import TYPE_CHECKING

from ..utils import safe_input, detect_column_types, detect_geo_columns

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


def run_reclean(agent: DataAnalystAgentV2) -> bool:
    """Return to V1 cleaning. Returns True if V2 should restart after."""
    con = agent.console

    con.print()
    con.print(
        "[yellow]Returning to cleaning mode. The current analysis session will pause.\n"
        "Your cleaned file will be replaced if you apply new cleaning steps.\n"
        "Proceed? (y/n)[/yellow]"
    )

    confirm = safe_input(con, "[bold bright_cyan]  Proceed? (y/n): [/bold bright_cyan]")
    if confirm.lower() not in ("y", "yes"):
        con.print("  Staying in analysis mode.")
        return False

    # Import v1 components
    try:
        from v1.inspector import DataInspector
        from v1.cleaner import DataCleaner
        from v1 import reporter
    except ImportError as e:
        con.print("[red]Cannot reload v1 components. Please restart the application.[/red]")
        return False

    # Reload original file
    original_path = agent.original_filepath
    con.print()
    con.print(f"[bold bright_cyan]🔄  Reloading original file: {original_path}[/bold bright_cyan]")
    con.print()

    try:
        inspector = DataInspector(original_path)
        report = inspector.inspect()
    except Exception as e:
        con.print("[red]Failed to re-inspect the data. Please check that the file is not corrupted and try again.[/red]")
        return False

    # Show report
    md_path = reporter.write_markdown_report(report)
    reporter.render_report_summary(report, md_path)

    if not report.has_issues or not report.cleaning_actions:
        con.print("[green]No issues found. Returning to analysis mode.[/green]")
        return False

    # Prompt
    while True:
        answer = safe_input(
            con,
            "[bold bright_cyan]Proceed with cleaning? (yes / no): [/bold bright_cyan]"
        ).lower()
        if answer in ("yes", "y"):
            break
        elif answer in ("no", "n"):
            con.print("  Staying in analysis mode with current data.")
            return False
        else:
            con.print("[dim]Please type 'yes' or 'no'.[/dim]")

    # Clean
    con.print()
    con.print("[bold bright_cyan]🧹  Applying cleaning actions...[/bold bright_cyan]")
    con.print()

    import os
    cleaner = DataCleaner(inspector.df, report)
    cleaned_df = cleaner.clean()
    output_path = cleaner.save()

    reporter.render_cleaning_summary(
        original_rows=report.rows,
        cleaned_rows=len(cleaned_df),
        original_cols=report.columns,
        cleaned_cols=len(cleaned_df.columns),
        issues_resolved=cleaner.steps_done,
        output_path=output_path,
    )

    # Update agent state with new cleaned data
    agent.df = cleaned_df
    agent.output_path = output_path
    agent.original_shape = (report.rows, report.columns)
    agent.cleaned_shape = (len(cleaned_df), len(cleaned_df.columns))
    agent.applied_actions = [a.description for a in report.cleaning_actions]
    agent.issues_resolved = cleaner.steps_done
    agent.skipped_cleaning = False
    agent.col_types = detect_column_types(cleaned_df)
    agent.geo_cols = detect_geo_columns(cleaned_df)

    # Clear previous results since data changed
    agent.results = {k: None for k in agent.results}

    agent.session.log("[R] Re-clean", original_path,
                      f"Re-cleaned → {len(cleaned_df)} rows × {len(cleaned_df.columns)} cols")

    return True  # Signal to re-show startup header
