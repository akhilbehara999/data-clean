
# -*- coding: utf-8 -*-
"""
CLI entry point for DataSanitizer.

Usage:
    python -m datasanitizer <filepath>
    python main.py <filepath>
"""

import sys
import os
import shutil

import click
from rich.console import Console

from .inspector import DataInspector
from .cleaner import DataCleaner
from . import reporter

console = Console(force_terminal=True)


def strip_quotes(ctx, param, value):
    if value:
        value = value.strip().strip("'\"").strip()
    if not os.path.exists(value):
        raise click.BadParameter(f"Path '{value}' does not exist.")
    return value


# Removed draw_choices. Unified console is now used directly.

@click.command()
@click.argument("filepath", callback=strip_quotes)
def main(filepath: str):
    """🧹 DataSanitizer — Expert data cleaning for CSV & Excel files."""

    reporter.render_banner()

    # ── Resume session check ──────────────────────────────────────────────
    from v1 import session_manager
    try:
        session_file = session_manager.get_session_filepath(filepath)
        if not os.path.exists(session_file) and os.path.exists("session.json"):
            session_file = "session.json"
            
        if os.path.exists(session_file):
            session_dict = session_manager.load_session(filepath if session_file != "session.json" else None)
            active_ds = session_manager.get_active_dataset(session_dict)
            if not active_ds:
                active_ds = session_dict
            file_info = active_ds.get("file", {})
            orig_path = file_info.get("original", "")
            cleaned_path = file_info.get("cleaned", "")
            abs_filepath = os.path.abspath(filepath)
            
            if abs_filepath in (os.path.abspath(orig_path), os.path.abspath(cleaned_path)):
                console.print()
                console.print(f"[bold yellow]Found an existing saved session for this file.[/bold yellow]")
                
                s_name = active_ds.get("name", os.path.basename(orig_path))
                s_time = session_dict.get("updated_at", "Unknown")
                c_shape = file_info.get("cleaned_shape", [0, 0])
                issues = active_ds.get("v1_summary", {}).get("issues_resolved", 0)
                
                from rich.table import Table
                from rich.panel import Panel
                
                details_table = Table.grid(padding=(0, 2))
                details_table.add_column(style="bold dim")
                details_table.add_column()
                details_table.add_row("Session Name:", f"[cyan]{s_name}[/cyan]")
                details_table.add_row("Last Active:", f"[purple]{s_time}[/purple]")
                details_table.add_row("Cleaned Data:", f"{c_shape[0]} rows × {c_shape[1]} cols")
                details_table.add_row("Issues Resolved:", f"[green]{issues} issues[/green]")
                
                console.print(Panel(details_table, title="[bold]Saved Session Info[/bold]", border_style="yellow", expand=False))
                console.print()
                
                while True:
                    resume = console.input(
                        "[bold bright_cyan]Would you like to resume this session? [Y/n]: [/bold bright_cyan]"
                    ).strip().lower()
                    if resume in ("yes", "y", ""):
                        import pandas as pd
                        
                        if "df" not in session_dict:
                            pkl_path = file_info.get("dataframe_pickle")
                            if pkl_path and os.path.exists(pkl_path):
                                session_dict["df"] = pd.read_pickle(pkl_path)
                            else:
                                session_dict["df"] = pd.read_csv(cleaned_path)
                                
                        session_dict["active_version"] = "v2"
                        session_manager.save_session(session_dict)
                        run_agent_loop(session_dict)
                        sys.exit(0)
                    elif resume in ("no", "n"):
                        break
                    else:
                        console.print("[dim]Please type 'y' or 'n'.[/dim]")
    except Exception as e:
        # Fall back to starting fresh if session loading/resuming fails
        pass

    # ── Validate ──────────────────────────────────────────────────────────
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in (".csv", ".tsv", ".xlsx", ".xls"):
        reporter.render_error(
            f"Unsupported file format: '{ext}'. "
            "Supported: .csv, .tsv, .xlsx, .xls"
        )
        sys.exit(1)

    # ── Phase 1: Inspect ──────────────────────────────────────────────────
    reporter.render_inspecting(os.path.basename(filepath))

    try:
        inspector = DataInspector(filepath)
        report = inspector.inspect()
    except ValueError as e:
        reporter.render_error("There was an issue analyzing your data file. Please check that it's a valid CSV, TSV, or Excel file.")
        sys.exit(1)
    except Exception as e:
        reporter.render_error("Failed to read the file. Please check that the file exists and is not corrupted.")
        sys.exit(1)

    # ── v4 Feature 10: Self-healing pattern detection ─────────────────────
    try:
        from v4.self_healing import detect_unknown_patterns, offer_new_rules
        proposals = detect_unknown_patterns(inspector.df, os.path.basename(filepath))
        if proposals:
            _tmp_session = {}  # temp store — will be merged after init_session
            offer_new_rules(proposals, _tmp_session)
            # Apply approved custom rules immediately
            from v4.self_healing import apply_custom_rules
            inspector.df = apply_custom_rules(inspector.df, os.path.basename(filepath))
    except Exception:
        pass  # degrade gracefully

    # ── Phase 2: Report ───────────────────────────────────────────────────
    # Write FULL detailed report to a Markdown file
    md_path = reporter.write_markdown_report(report, filepath)

    # Print only a concise summary to the terminal
    reporter.render_report_summary(report, md_path)

    if not report.has_issues:
        sys.exit(0)

    if not report.cleaning_actions:
        console.print("[yellow]No automatic cleaning actions could be generated.[/yellow]")
        sys.exit(0)

    # ── Prompt ────────────────────────────────────────────────────────────
    while True:
        answer = console.input(
            "[bold bright_cyan]Proceed with cleaning? [Y: clean & analyze / n: skip cleaning, analyze original / q: quit] [Y/n/q]: [/bold bright_cyan]"
        ).strip().lower()

        if answer in ("y", "yes", ""):
            break
        elif answer in ("n", "no"):
            session_dict = session_manager.init_session(
                original_filepath=filepath,
                cleaned_filepath=filepath,
                original_df=inspector.df,
                cleaned_df=inspector.df,
                applied_actions=[],
                issues_resolved=0
            )
            session_dict["df"] = inspector.df
            session_dict["active_version"] = "v2"
            session_manager.save_session(session_dict)
            run_agent_loop(session_dict)
            sys.exit(0)
        elif answer in ("q", "quit", "exit"):
            console.print("[yellow]Exiting. No changes made.[/yellow]")
            sys.exit(0)
        else:
            console.print("[dim]Please type 'y', 'n', or 'q'.[/dim]")

    # ── Phase 3: Clean ────────────────────────────────────────────────────
    console.print()
    console.print("[bold bright_cyan]🧹  Applying cleaning actions...[/bold bright_cyan]")
    console.print()

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

    # ── Phase 4: Hand-off / Version Selection ─────────────────────────────
    actions_applied = [a.description for a in report.cleaning_actions]
    
    session_dict = session_manager.init_session(
        original_filepath=filepath,
        cleaned_filepath=output_path,
        original_df=inspector.df,
        cleaned_df=cleaned_df,
        applied_actions=actions_applied,
        issues_resolved=cleaner.steps_done
    )
    session_dict["df"] = cleaned_df

    # ── v4 Features 1 & 2: Project memory + template check on load ────────
    try:
        from v4.agent import on_file_load
        on_file_load(os.path.basename(filepath), cleaned_df, session_dict)
        session_manager.save_session(session_dict)
    except Exception:
        pass

    session_dict["active_version"] = "v2"
    session_manager.save_session(session_dict)
    run_agent_loop(session_dict)

def run_agent_loop(session_dict: dict):
    """Run the unified agent console."""
    # Ensure v4 session keys exist (safe no-op if already present)
    try:
        from v4.session_bridge_v4 import init_v4_session_keys
        init_v4_session_keys(session_dict)
    except Exception:
        pass

    import threading
    from v1 import lock_manager
    
    # Set the lock initially
    lock_manager.acquire_lock()
    
    stop_heartbeat = threading.Event()
    
    def heartbeat_worker():
        while not stop_heartbeat.is_set():
            lock_manager.update_heartbeat()
            stop_heartbeat.wait(lock_manager.HEARTBEAT_INTERVAL)
            
    t = threading.Thread(target=heartbeat_worker, daemon=True)
    t.start()
    
    try:
        from v2.agent import DataAnalystAgentV2
        agent = DataAnalystAgentV2(session_dict=session_dict)
        try:
            agent.start()
        except KeyboardInterrupt:
            # Swallow Ctrl+C so the finally block can clean up resources.
            pass
        return getattr(agent, "return_to_browser", False)
    finally:
        stop_heartbeat.set()
        lock_manager.release_lock()


if __name__ == "__main__":
    main()
