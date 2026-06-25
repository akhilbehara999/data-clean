"""DataAnalystAgent v2 — main agent with REPL loop and command dispatch."""

from __future__ import annotations

import sys
import os
from datetime import datetime

import pandas as pd
from rich.console import Console
from rich.markdown import Markdown

from .session import SessionLog
from .utils import detect_column_types, detect_geo_columns, safe_input, command_completer

console = Console(force_terminal=True)


class DataAnalystAgentV2:
    """Stateful analysis session — receives cleaned data from V1."""

    def __init__(
        self,
        df: pd.DataFrame = None,
        filename: str = None,
        original_shape: tuple[int, int] = None,
        cleaned_shape: tuple[int, int] = None,
        applied_actions: list[str] = None,
        issues_resolved: int = None,
        output_path: str = None,
        skipped_cleaning: bool = False,
        original_filepath: str = "",
        session_dict: dict = None,
    ):
        import os
        if session_dict is not None:
            from v1 import session_manager
            active_ds = session_manager.get_active_dataset(session_dict)
            if not active_ds:
                active_ds = session_dict
            file_info = active_ds.get("file", {})
            self.session_dict = session_dict

            self.original_filepath = file_info.get("original", "")
            self.output_path = file_info.get("cleaned", "")
            self.filename = os.path.basename(self.original_filepath)
            self.original_shape = tuple(file_info.get("original_shape", (0, 0)))
            self.cleaned_shape = tuple(file_info.get("cleaned_shape", (0, 0)))
            
            v1_sum = active_ds.get("v1_summary", {})
            self.applied_actions = v1_sum.get("actions_log", [])
            self.issues_resolved = v1_sum.get("issues_resolved", 0)
            
            self.skipped_cleaning = (self.issues_resolved == 0 and not self.applied_actions)
            
            if "df" in session_dict:
                self.df = session_dict["df"]
            else:
                pkl_path = file_info.get("dataframe_pickle")
                if pkl_path and os.path.exists(pkl_path):
                    self.df = pd.read_pickle(pkl_path)
                elif self.output_path and os.path.exists(self.output_path):
                    if self.output_path.endswith((".xlsx", ".xls")):
                        self.df = pd.read_excel(self.output_path, engine="openpyxl")
                    elif self.output_path.endswith(".tsv"):
                        self.df = pd.read_csv(self.output_path, sep="\t")
                    else:
                        self.df = pd.read_csv(self.output_path)
                else:
                    self.df = pd.DataFrame()
        else:
            self.df = df
            self.filename = filename
            self.original_shape = original_shape
            self.cleaned_shape = cleaned_shape
            self.applied_actions = applied_actions
            self.issues_resolved = issues_resolved
            self.output_path = output_path
            self.skipped_cleaning = skipped_cleaning
            self.original_filepath = original_filepath or output_path
            
            # Create session dict
            from v1 import session_manager
            self.session_dict = session_manager.init_session(
                original_filepath=self.original_filepath,
                cleaned_filepath=self.output_path,
                original_df=df,
                cleaned_df=df,
                applied_actions=applied_actions,
                issues_resolved=issues_resolved
            )
            self.session_dict["df"] = df
            active_ds = session_manager.get_active_dataset(self.session_dict)
            if not active_ds:
                active_ds = self.session_dict

        self.console = console
        v2_sum = active_ds.setdefault("v2_summary", {})
        v2_log = v2_sum.setdefault("session_log", [])
        self.session = SessionLog(v2_log)
        
        if session_dict is not None:
            ct = active_ds.get("column_types", {})
            self.col_types = {
                "numeric": ct.get("numeric", []),
                "categorical": ct.get("categorical", []),
                "datetime": ct.get("datetime", []),
            }
        else:
            self.col_types = detect_column_types(self.df)
            
        self.geo_cols = detect_geo_columns(self.df)
        self.batch_files: list[dict] = []

        # Results store — keyed by command name
        v2_sum = active_ds.get("v2_summary", {}) if active_ds else {}
        if v2_sum:
            self.results = {
                "eda": v2_sum.get("eda_results"),
                "relationships": v2_sum.get("relationships_results") or v2_sum.get("relationships_results"),
                "geographic": v2_sum.get("geo_results"),
                "pivot": v2_sum.get("pivot_results"),
                "comparative": v2_sum.get("comparison_results"),
                "insights": v2_sum.get("insights_triggered"),
            }
        else:
            self.results = {
                "eda": None,
                "relationships": None,
                "geographic": None,
                "pivot": None,
                "comparative": None,
                "insights": None,
            }

        # Initialize V3 Memory and LLM configurations
        from v3.memory import Memory
        from v3.llm import detect_provider, get_model_label, MODEL_REGISTRY, get_api_key_for_provider
        self.memory = Memory(self.session_dict)
        self.provider = self.session_dict.get("active_provider")
        self.model_id = self.session_dict.get("active_model_id")

        # Fall back to defaults if not set/detected
        default_prov, default_key = detect_provider()
        if not self.provider or not get_api_key_for_provider(self.provider):
            self.provider = default_prov
            if self.provider:
                self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")
        
        if self.provider and not self.model_id:
            self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")

        # Hard safeguard for nvidia models loaded from session to ensure they are chat-compatible
        if self.provider == "nvidia" and self.model_id:
            m_id_lower = self.model_id.lower()
            excludes = [
                "embed", "embedding", "rerank", "kosmos", "sdxl", "neva", "stable-diffusion",
                "reward", "safety", "guard", "translate", "pii", "parse", "detector", "calibration", "clip", "vila"
            ]
            includes = [
                "instruct", "chat", "-it", "large", "glm", "kimi", "minimax", "step",
                "deepseek", "palmyra", "medium", "small", "yi-", "dracarys"
            ]
            is_valid = True
            if any(ex in m_id_lower for ex in excludes):
                is_valid = False
            elif not any(inc in m_id_lower for inc in includes):
                is_valid = False
            if not is_valid:
                old_model = self.model_id
                self.model_id = MODEL_REGISTRY["nvidia"]["default"]
                if old_model != self.model_id:
                    self.console.print(f"⚠️ Warning: Model '{old_model}' is not chat-compatible; falling back to default '{self.model_id}'.")

        self.api_key = get_api_key_for_provider(self.provider) if self.provider else None
        self.model_label = get_model_label(self.provider, self.model_id)

        # Track last operation for /export code
        self.last_operation = self.session_dict.get("last_operation")
        self.columns = list(self.df.columns)

    # ── Startup ──────────────────────────────────────────────────────────

    def start(self):
        """Entry point — print header, show menu, enter REPL."""
        self._print_startup()
        self._show_menu()
        self._repl()

    def _render_dashboard(self):
        """Render a clean, minimalist Claude Code style split dashboard."""
        import os
        from rich.table import Table
        from rich.panel import Panel
        from rich import box

        c = self.console
        c.print()

        # Build columns inside the panel
        header_table = Table.grid(expand=True)
        header_table.add_column(ratio=6, justify="left")  # Left column
        header_table.add_column(width=3, justify="center") # Vertical separator
        header_table.add_column(ratio=7, justify="left")  # Right column

        try:
            mem_bytes = self.df.memory_usage(deep=True).sum()
            mem_str = f"{mem_bytes / 1_048_576:.2f} MB"
        except Exception:
            mem_str = "Unknown"

        # Left Column content: logo, active session details
        left_lines = [
            " [bold white]DATASET STATISTICS[/bold white]",
            " ──────────────────────────────────────────────",
            f"  • [bold dim]Source File:[/bold dim] [bold cyan]{self.filename}[/bold cyan]",
            f"  • [bold dim]Current Shape:[/bold dim] [bold green]{self.df.shape[0]:,} rows × {self.df.shape[1]} cols[/bold green]",
            f"  • [bold dim]Original Shape:[/bold dim] {self.original_shape[0]:,} rows × {self.original_shape[1]} cols",
            f"  • [bold dim]Memory Usage:[/bold dim] {mem_str}",
            f"  • [bold dim]Issues Resolved:[/bold dim] {self.issues_resolved}",
        ]

        # Right Column content: tips & LLM status
        key_status = "[green]✓ Configured[/green]" if self.api_key else "[red]✗ Missing[/red]"
        model_str = self.model_id or "None"
        prov_str = self.provider.upper() if self.provider else "NONE"
        right_lines = [
            " [bold white]QUICK STATUS & TIPS[/bold white]",
            " ──────────────────────────────────────────────",
            f"  • [bold dim]AI Provider:[/bold dim] [purple]{prov_str}[/purple] ({key_status})",
            f"  • [bold dim]Active Model:[/bold dim] [purple]{model_str}[/purple]",
            "  • [bold dim]Autocompletion:[/bold dim] Type [bold purple]/[/bold purple] for command suggestions",
            "  • [bold dim]Help Center:[/bold dim] Run [bold purple]/help <command>[/bold purple] or [bold purple]/menu[/bold purple]",
            "  • [bold dim]Questions:[/bold dim] Ask anything directly to talk with the model",
        ]

        # Combine lines
        max_len = max(len(left_lines), len(right_lines))
        for i in range(max_len):
            l_val = left_lines[i] if i < len(left_lines) else ""
            r_val = right_lines[i] if i < len(right_lines) else ""
            header_table.add_row(l_val, "│", r_val)

        panel = Panel(
            header_table,
            box=box.ROUNDED,
            border_style="purple",
            title="[bold purple] DataSanitizer Dashboard v2.0.0 [/bold purple]",
            title_align="left"
        )
        c.print(panel)

        # Print session banner alert and inline command list
        c.print()
        c.print("  [bold purple]▎[/bold purple] [bold]Session Active[/bold] · Type a slash command or ask a question")
        
        # Check if V3 ran any queries
        v3_sum = self.session_dict.get("v3_summary", {})
        queries_run = v3_sum.get("queries_run", [])
        if queries_run:
            c.print(f"  [bold yellow]Note:[/bold yellow] {len(queries_run)} AI queries ran in this session.")
            c.print()
            
        c.print("  [bold dim]Commands:[/bold dim] "
                "[bold purple]/eda[/bold purple] · "
                "[bold purple]/insights[/bold purple] · "
                "[bold purple]/pivot[/bold purple] · "
                "[bold purple]/report[/bold purple] · "
                "[bold purple]/simulate[/bold purple] · "
                "[bold purple]/menu[/bold purple] for more")
        c.print("  [dim]" + "─" * 85 + "[/dim]")

    def _print_startup(self):
        """Wrapper for backward compatibility."""
        self._render_dashboard()
        
        if self.session.entries:
            c = self.console
            c.print()
            c.print("  [bold dim]── Session History ────────────────────────────────────────────────────────[/bold dim]")
            for line in self.session.format_entries():
                c.print(line)
            c.print("  [bold dim]───────────────────────────────────────────────────────────────────────────[/bold dim]")
            c.print()

        self.session.log(
            "V2 startup",
            f"{self.filename} ({self.cleaned_shape[0]:,} rows × "
            f"{self.cleaned_shape[1]} cols)",
        )
        self.update_session()

    def _show_menu(self):
        """Wrapper for backward compatibility."""
        pass


    # ── REPL ─────────────────────────────────────────────────────────────

    def _repl(self):
        """Main interactive read-eval-print loop."""
        while True:
            user_input = safe_input(
                self.console,
                "[bold bright_cyan]❯ [/bold bright_cyan]",
                completer=command_completer
            )

            if not user_input:
                continue

            cmd = user_input.strip().lower()
            # Handle slash commands routing
            if cmd.startswith("/"):
                parts = cmd.split(maxsplit=1)
                base_cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""

                if base_cmd in ("/exit", "/quit"):
                    self.update_session()
                    self.console.print(
                        "\n[yellow]Exiting analysis mode. Goodbye![/yellow]\n"
                    )
                    break

                if base_cmd == "/files":
                    self.update_session()
                    self.console.print(
                        "\n[yellow]Returning to browser interface...[/yellow]\n"
                    )
                    self.return_to_browser = True
                    break

                # Translate slash commands to internal dispatch codes
                mapping = {
                    "/eda": "1",
                    "/relationships": "2",
                    "/relations": "2",
                    "/geographic": "3",
                    "/geo": "3",
                    "/pivot": "4",
                    "/comparative": "5",
                    "/compare": "5",
                    "/insights": "6",
                    "/report": "8",
                    "/export": "9",
                    "/reclean": "r",
                    "/re-clean": "r",
                    "/clean": "r",
                    "/menu": "v2_menu",
                    "/help": "h",
                    "/h": "h",
                    "/?": "h",
                    "/settings": "v2_settings",
                    # v4 commands — delegate to v4 agent handlers
                    "/simulate": "v4_simulate",
                    "/specialist": "v4_specialist",
                    "/explain": "v4_explain",
                    "/rules": "v4_rules",
                    "/templates": "v4_templates",
                    "/watch": "v4_watch",
                }

                if base_cmd in mapping:
                    mapped_cmd = mapping[base_cmd]
                    cmd = mapped_cmd
                    user_input = f"{mapped_cmd} {args}".strip()
                else:
                    import difflib
                    known_commands = list(mapping.keys()) + ["/exit", "/quit", "/files"]
                    matches = difflib.get_close_matches(base_cmd, known_commands, n=1, cutoff=0.6)
                    if matches:
                        suggested = matches[0]
                        self.console.print(f"  [yellow]Command '{base_cmd}' not recognized. Did you mean [bold]{suggested}[/bold]?[/yellow]")
                        confirm = safe_input(self.console, f"  [bold bright_cyan]Run {suggested}? (y/n): [/bold bright_cyan]").strip().lower()
                        if confirm in ("yes", "y"):
                            if suggested in ("/exit", "/quit"):
                                self.update_session()
                                self.console.print("\n[yellow]Exiting analysis mode. Goodbye![/yellow]\n")
                                break
                            if suggested == "/files":
                                self.update_session()
                                self.console.print("\n[yellow]Returning to browser interface...[/yellow]\n")
                                self.return_to_browser = True
                                break
                            mapped_cmd = mapping[suggested]
                            cmd = mapped_cmd
                            user_input = f"{mapped_cmd} {args}".strip()
                        else:
                            continue
                    else:
                        self.console.print(f"  [red]Command '{base_cmd}' not recognized. Type /menu to see available commands.[/red]")
                        continue

            handled = self._dispatch(cmd, user_input)
            if not handled:
                # Check if it's a plain English question
                self._handle_natural_query(user_input)

            self.console.print()

    def _dispatch(self, cmd: str, raw: str) -> bool:
        """Route command to the right handler. Returns True if handled."""

        if cmd == "1":
            return self._cmd_eda()
        elif cmd == "2":
            return self._cmd_relationships()
        elif cmd == "3":
            return self._cmd_geographic()
        elif cmd == "4":
            return self._cmd_pivot()
        elif cmd == "5":
            return self._cmd_comparative()
        elif cmd == "6":
            return self._cmd_insights()
        elif cmd == "7":
            return self._cmd_batch()
        elif cmd == "8":
            return self._cmd_report()
        elif cmd == "9":
            return self._cmd_export()
        elif cmd in ("r", "re-clean", "reclean", "go back", "redo cleaning"):
            return self._cmd_reclean()
        elif cmd == "v2_menu":
            return self._cmd_menu()
        elif cmd == "v2_settings":
            return self._cmd_settings()
        elif cmd in ("h", "help") or cmd.startswith("h ") or cmd.startswith("help "):
            raw_lower = raw.lower()
            if raw_lower.startswith("help "):
                args = raw[5:].strip()
            elif raw_lower.startswith("h "):
                args = raw[2:].strip()
            else:
                args = ""
            
            # If the command starts with "h " or "help " directly (not a slash command),
            # verify that the argument is a known command or alias. If not, return False
            # so that it falls through to the V3/V4 natural query handlers.
            if args and len(cmd) > 1:
                from .commands.help_cmd import HELP_MAPPING
                if args.lower().lstrip("/") not in HELP_MAPPING:
                    return False
                    
            return self._cmd_help(args)
        # v4 commands
        elif cmd.startswith("v4_simulate"):
            return self._cmd_v4_simulate(raw)
        elif cmd.startswith("v4_specialist"):
            return self._cmd_v4_specialist(raw)
        elif cmd.startswith("v4_explain"):
            return self._cmd_v4_explain(raw)
        elif cmd.startswith("v4_rules"):
            return self._cmd_v4_rules(raw)
        elif cmd.startswith("v4_templates"):
            return self._cmd_v4_templates(raw)

        return False

    # ── Command handlers ─────────────────────────────────────────────────

    def _cmd_eda(self) -> bool:
        from .commands.eda import run_eda
        self.results["eda"] = run_eda(self)
        self.session.log("[1] EDA", "", "5 sections completed")
        self.update_session("eda")
        return True

    def _cmd_relationships(self) -> bool:
        from .commands.relationships import run_relationships
        result = run_relationships(self)
        self.results["relationships"] = result
        corr_count = len(result.get("correlations", []))
        red_count = len(result.get("redundant", []))
        self.session.log("[2] Relationships", "",
                         f"{corr_count} correlations, {red_count} redundant columns")
        self.update_session("relationships")
        return True

    def _cmd_geographic(self) -> bool:
        if not self.geo_cols:
            self.console.print(
                "\n[yellow]No location column detected in this file. "
                "Command [3] unavailable.[/yellow]"
            )
            self._show_menu()
            return True
        from .commands.geographic import run_geographic
        result = run_geographic(self)
        self.results["geographic"] = result
        self.session.log("[3] Geographic", "",
                         "Geographic analysis complete" if result else "Skipped")
        self.update_session("geographic")
        return True

    def _cmd_pivot(self) -> bool:
        from .commands.pivot import run_pivot
        result = run_pivot(self)
        self.results["pivot"] = result
        if result:
            self.session.log(
                "[4] Pivot",
                f"{result.get('row_col')} × {result.get('col_col', 'none')} "
                f"→ {result.get('val_col')} ({result.get('agg_label')})",
                f"{result['shape'][0]}×{result['shape'][1]}",
                result.get("export_path", ""),
            )
        self.update_session("pivot")
        return True

    def _cmd_comparative(self) -> bool:
        from .commands.comparative import run_comparative
        result = run_comparative(self)
        self.results["comparative"] = result
        if result:
            self.session.log("[5] Comparative", result.get("type", ""),
                             f"{result.get('label_a')} vs {result.get('label_b')}")
        self.update_session("comparative")
        return True

    def _cmd_insights(self) -> bool:
        from .commands.insights import run_insights
        result = run_insights(self)
        self.results["insights"] = result
        count = result.get("count", 0)
        self.session.log("[6] Insights", "",
                         f"{count} of 10 rules triggered")
        self.update_session("insights")
        return True

    def _cmd_batch(self) -> bool:
        from .commands.batch import run_batch
        result = run_batch(self)
        if result:
            self.session.log("[7] Batch", result.get("mode", ""),
                             f"{len(self.batch_files)} additional files")
            self.update_session()
        return True

    def _cmd_report(self) -> bool:
        from .commands.report import run_report
        result = run_report(self)
        if result:
            sections = result.get("sections", [])
            path = result.get("path", "")
            self.session.log("[8] Report", f"{len(sections)} sections",
                              export=path or "")
            self.update_session()
        return True

    def _cmd_export(self) -> bool:
        from .commands.export import run_export
        path = run_export(self)
        if path:
            self.session.log("[9] Export", "", export=path)
            self.update_session()
        return True

    def _cmd_reclean(self) -> bool:
        from .commands.reclean import run_reclean
        should_restart = run_reclean(self)
        if should_restart:
            self._print_startup()
            self._show_menu()
        return True

    def _cmd_help(self, args: str) -> bool:
        from .commands.help_cmd import run_help
        run_help(self, args)
        return True

    def _cmd_menu(self) -> bool:
        from .commands.help_cmd import run_menu
        run_menu(self)
        return True

    def update_session(self, command_name: str = None):
        """Update session dict and save it."""
        if not hasattr(self, "session_dict") or self.session_dict is None:
            return
            
        from v1 import session_manager
        active_ds = session_manager.get_active_dataset(self.session_dict)
        if not active_ds:
            active_ds = self.session_dict
            
        v2_sum = active_ds.setdefault("v2_summary", {})
        
        if command_name:
            ar = v2_sum.setdefault("analyses_run", [])
            if command_name not in ar:
                ar.append(command_name)
            self.session_dict["last_operation"] = command_name
                
        v2_sum["eda_results"] = self.results["eda"]
        v2_sum["relationships_results"] = self.results["relationships"]
        v2_sum["geo_results"] = self.results["geographic"]
        v2_sum["pivot_results"] = self.results["pivot"]
        v2_sum["comparison_results"] = self.results["comparative"]
        v2_sum["insights_triggered"] = self.results["insights"]
        
        session_manager.save_session(self.session_dict, self.df)

    def _as_v2_agent(self):
        """For backward compatibility with V3 adapters/methods."""
        return self

    # ── v4 command bridges ────────────────────────────────────────────────────

    def _get_v4_agent(self):
        """Return a lightweight V4 agent instance for v4 command delegation."""
        try:
            from v4.agent import DataAnalystAgentV4
            return DataAnalystAgentV4(session_dict=self.session_dict)
        except Exception as e:
            self.console.print("  [bold red]\u26a0 V4 features are not available. This may be due to missing dependencies.[/bold red]")
            return None

    def _cmd_v4_simulate(self, raw: str) -> bool:
        # Extract query after the command keyword
        parts = raw.split(maxsplit=1)
        query = parts[1] if len(parts) > 1 else ""
        a = self._get_v4_agent()
        if a:
            a._do_simulate(query)
        return True

    def _cmd_v4_specialist(self, raw: str) -> bool:
        parts = raw.split(maxsplit=1)
        domain = parts[1] if len(parts) > 1 else ""
        a = self._get_v4_agent()
        if a:
            a._do_specialist(domain)
        return True

    def _cmd_v4_explain(self, raw: str) -> bool:
        parts = raw.split(maxsplit=1)
        query = parts[1] if len(parts) > 1 else ""
        a = self._get_v4_agent()
        if a:
            a._do_explain(query)
        return True

    def _cmd_v4_rules(self, raw: str) -> bool:
        parts = raw.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else ""
        a = self._get_v4_agent()
        if a:
            a._do_rules(args)
        return True

    def _cmd_v4_templates(self, raw: str) -> bool:
        parts = raw.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else ""
        a = self._get_v4_agent()
        if a:
            a._do_templates(args)
        return True

    # ── Natural query fallback ───────────────────────────────────────────

    def _handle_natural_query(self, query: str):
        """Handle unrecognized input — checks v4 simulation, v4 explain, and v3 LLM chat loop."""
        from v4.simulation_engine import is_simulation_query
        from v4.methodology import is_explain_query
        from v3.llm import detect_provider, get_api_key_for_provider

        # Check simulation
        if is_simulation_query(query):
            self._cmd_v4_simulate(f"/simulate {query}")
            return

        # Check explanation
        if is_explain_query(query):
            self._cmd_v4_explain(f"/explain {query}")
            return

        # Check domain routing
        try:
            from v4.agent import detect_domain
            domain = detect_domain(query)
            if domain:
                self._cmd_v4_specialist(f"/specialist {domain}")
                return
        except Exception:
            pass

        # If LLM key is configured/detected, route to V3 natural language pipeline
        prov, key = detect_provider()
        if self.provider and get_api_key_for_provider(self.provider):
            self._process_query(query)
        elif prov and key:
            self.provider = prov
            self.api_key = key
            from v3.llm import MODEL_REGISTRY, get_model_label
            self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")
            self.model_label = get_model_label(self.provider, self.model_id)
            self._process_query(query)
        else:
            # Fall back to existing offline keyword logic
            self._handle_natural_query_offline(query)

    def _handle_natural_query_offline(self, query: str):
        """Handle unrecognized input — check EDA results or suggest (offline)."""
        c = self.console
        q = query.lower()

        # If EDA results exist, try to answer from them
        eda = self.results.get("eda")
        if eda:
            # Check if user is asking about a specific column
            for p in eda.get("numeric", []):
                if p["column"].lower() in q:
                    c.print(f"\n  From EDA results for [{p['column']}]:")
                    c.print(f"    Mean: {p['mean']:.2f} | Median: {p['median']:.2f} | "
                            f"Min: {p['min']:.2f} | Max: {p['max']:.2f}")
                    c.print("\n[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
                    return
            for p in eda.get("categorical", []):
                if p["column"].lower() in q:
                    top = ", ".join(f'{t["value"]} ({t["pct"]}%)' for t in p["top5"])
                    c.print(f"\n  From EDA results for [{p['column']}]:")
                    c.print(f"    Unique: {p['unique']} | Top: {top}")
                    c.print("\n[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
                    return

        # Check insights
        ins = self.results.get("insights")
        if ins and ins.get("insights"):
            for insight in ins["insights"]:
                # Check if query relates to any insight topic
                if any(word in q for word in insight["title"].lower().split()):
                    c.print(f"\n  💡 {insight['title']}: {insight['detail']}")
                    c.print("\n[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
                    return

        # Suggest which command to run
        suggestions = {
            "average": "1", "mean": "1", "median": "1", "profile": "1",
            "correlat": "2", "relationship": "2", "redundant": "2",
            "city": "3", "state": "3", "region": "3", "geo": "3",
            "pivot": "4", "group": "4", "aggregate": "4",
            "compare": "5", "vs": "5", "versus": "5", "diff": "5",
            "insight": "6", "pattern": "6", "anomal": "6",
            "batch": "7", "merge": "7", "load": "7",
            "report": "8", "export": "9",
        }

        for keyword, cmd_num in suggestions.items():
            if keyword in q:
                c.print(
                    f"\n  I haven't run that analysis yet.\n"
                    f"  Try command [{cmd_num}] and I'll have that answer for you."
                )
                c.print("\n[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
                return

        # Truly unrecognized
        c.print("\n  [yellow]I didn't recognize that command.[/yellow]")
        self._show_menu()

    # ── V3 Chat Engine ported methods ──────────────────────────────────────────

    def _process_query(self, query: str):
        """Steps 2-6 of the core loop."""
        c = self.console

        # Step 2 — Intent parsing
        from v3.intent_parser import parse_intent, Intent
        intent = parse_intent(query, self.columns)

        # Step 5 — Add user message to memory
        self.memory.add_user(query)

        # Step 3 — Execute
        response = ""
        func_called = None

        if intent.category == Intent.DATA_QUERY:
            response, func_called = self._handle_data_query(intent)

        elif intent.category == Intent.EXPLANATION:
            response = self._handle_explanation(intent)

        elif intent.category == Intent.REPORT:
            response, func_called = self._handle_report()

        elif intent.category == Intent.CODE:
            if not self.last_operation:
                response = "⚠️ **No analysis operation has been run in this session yet.** Please ask a question or run an analysis command first."
            else:
                from v3.code_exporter import get_code_for_operation
                response = get_code_for_operation(self.last_operation, self.filename)

        elif intent.category == Intent.GENERAL:
            from v3.narrator import narrate_general_greeting
            response = self._handle_with_llm(query, narrate_general_greeting())

        elif intent.category == Intent.AMBIGUOUS:
            from v3.narrator import narrate_ambiguous
            response = self._handle_with_llm(
                query, narrate_ambiguous(query, self.columns))

        # Step 4 — Render response
        c.print()
        c.print(Markdown(response))

        # Step 5 cont — save assistant response
        self.memory.add_assistant(response, func_called)

        # Step 6 — Autosave
        self.update_session()

    def _handle_data_query(self, intent) -> tuple[str, str | None]:
        func = intent.v2_function

        if func == "eda":
            return self._run_eda(), "eda"

        elif func == "relationships":
            return self._run_relationships(), "relationships"

        elif func == "insights":
            return self._run_insights(), "insights"

        elif func == "geographic":
            return self._run_geographic(), "geographic"

        elif func == "column_detail":
            col = intent.column_ref
            if col:
                self.last_operation = "column_detail"
                from v3.narrator import narrate_column_detail
                raw = narrate_column_detail(col, self.df, self.col_types)
                return self._handle_with_llm(intent.raw_query, raw), f"column_detail({col})"
            from v3.narrator import narrate_ambiguous
            return narrate_ambiguous(intent.raw_query, self.columns), None

        elif func == "pivot":
            return self._handle_with_llm(
                intent.raw_query,
                "Pivot tables require interactive column selection. "
                "Please run /pivot to use the interactive builder."
            ), None

        elif func == "comparative":
            return self._handle_with_llm(
                intent.raw_query,
                "Comparisons require segment selection. "
                "Please run /comparative to use the interactive comparison builder."
            ), None

        from v3.narrator import narrate_ambiguous
        return narrate_ambiguous(intent.raw_query, self.columns), None

    def _run_eda(self) -> str:
        if self.results.get("eda"):
            from v3.narrator import narrate_eda
            raw = narrate_eda(self.results["eda"], self.col_types)
            return self._handle_with_llm("run eda", raw)

        # Run V2 EDA silently
        self.console.print("  [dim]⏳ Running EDA analysis...[/dim]")
        from v2.commands.eda import run_eda
        self.results["eda"] = run_eda(self, silent=True)
        self.last_operation = "eda"

        from v3.narrator import narrate_eda
        raw = narrate_eda(self.results["eda"], self.col_types)
        return self._handle_with_llm("run eda", raw)

    def _run_relationships(self) -> str:
        if self.results.get("relationships"):
            from v3.narrator import narrate_relationships
            raw = narrate_relationships(self.results["relationships"])
            return self._handle_with_llm("check relationships", raw)

        self.console.print("  [dim]⏳ Running relationship scan...[/dim]")
        from v2.commands.relationships import run_relationships
        self.results["relationships"] = run_relationships(self)
        self.last_operation = "relationships"

        from v3.narrator import narrate_relationships
        raw = narrate_relationships(self.results["relationships"])
        return self._handle_with_llm("check relationships", raw)

    def _run_insights(self) -> str:
        if self.results.get("insights"):
            from v3.narrator import narrate_insights
            raw = narrate_insights(self.results["insights"])
            return self._handle_with_llm("find insights", raw)

        self.console.print("  [dim]⏳ Running insight engine...[/dim]")
        # Insights needs EDA first
        if not self.results.get("eda"):
            from v2.commands.eda import run_eda
            self.results["eda"] = run_eda(self, silent=True)

        from v2.commands.insights import run_insights
        self.results["insights"] = run_insights(self)
        self.last_operation = "insights"

        from v3.narrator import narrate_insights
        raw = narrate_insights(self.results["insights"])
        return self._handle_with_llm("find insights", raw)

    def _run_geographic(self) -> str:
        if self.results.get("geographic"):
            from v3.narrator import narrate_geographic
            raw = narrate_geographic(self.results["geographic"])
            return self._handle_with_llm("geographic breakdown", raw)

        return self._handle_with_llm(
            "geographic analysis",
            "Geographic analysis requires interactive column confirmation. "
            "Please run /geographic to use the interactive builder."
        )

    def _handle_report(self) -> tuple[str, str | None]:
        return self._handle_with_llm(
            "generate report",
            "Report generation is interactive (section selection, format choice). "
            "Please run /report to use the interactive builder."
        ), None

    def _handle_explanation(self, intent) -> str:
        col = intent.column_ref
        context_parts = []

        if col:
            from v3.narrator import narrate_column_detail
            raw = narrate_column_detail(col, self.df, self.col_types)
            context_parts.append(raw)

        if self.results.get("eda"):
            context_parts.append("EDA results are available.")

        if self.results.get("insights"):
            ins = self.results["insights"]
            titles = [i["title"] for i in ins.get("insights", [])[:5]]
            context_parts.append(f"Insights found: {', '.join(titles)}")

        context = "\n".join(context_parts) if context_parts else "No prior analysis available."
        return self._handle_with_llm(intent.raw_query, context)

    def _format_api_error(self, e: Exception) -> str:
        import json
        import re
        msg = str(e)
        if "LLM request failed:" in msg:
            inner = msg.replace("LLM request failed:", "").strip()
            if "getaddrinfo failed" in inner or "timed out" in inner or "connection" in inner.lower():
                return "Connection Error: Failed to reach the AI server. Please verify your internet connection."
            return f"Request Failed: {inner}"

        if "LLM API HTTP" not in msg:
            return msg

        try:
            parts = msg.split(":", 1)
            if len(parts) < 2:
                return msg

            header = parts[0].strip()
            code_str = header.replace("LLM API HTTP", "").strip()
            code = int(code_str) if code_str.isdigit() else 0
            body_str = parts[1].strip()

            try:
                body = json.loads(body_str)
            except Exception:
                body = {}

            details = ""
            if isinstance(body, dict):
                if "error" in body and isinstance(body["error"], dict):
                    details = body["error"].get("message", "")
                elif "error" in body and isinstance(body["error"], str):
                    details = body["error"]
                elif "message" in body:
                    details = body["message"]

            if code == 429:
                clean_details = "You exceeded your current quota. Please check your plan and billing details."
                m = re.search(r"Please retry in ([\d\.]+)s", details)
                if m:
                    seconds = int(float(m.group(1)))
                    clean_details += f" Please try again in {seconds} seconds."
                else:
                    clean_details += " Please wait a moment and try again."
                return f"Quota Exceeded (HTTP 429): {clean_details}"

            if code == 401:
                return "Invalid API Key (HTTP 401): The provided API key is invalid or unauthorized. Please check your config."

            if code == 403:
                return f"Access Forbidden (HTTP 403): The request was forbidden by the AI provider. Details: {details if details else 'Permission denied.'}"

            if code == 404:
                msg_404 = f"Not Found (HTTP 404): The requested model endpoint was not found or is not supported. Details: {details if details else 'Endpoint not found.'}"
                if getattr(self, "provider", None) == "nvidia":
                    msg_404 += " Try switching to a different model using /model."
                return msg_404

            if details:
                return f"HTTP {code}: {details}"
        except Exception:
            pass

        return msg

    def _handle_with_llm(self, query: str, local_context: str) -> str:
        """Try LLM enrichment; display friendly error inline on failure or missing API key."""
        from v3.llm import get_api_key_for_provider, detect_provider, get_model_label, MODEL_REGISTRY, call_llm
        from rich.markdown import Markdown
        c = self.console
        
        # Always check/refresh current key
        if self.provider:
            self.api_key = get_api_key_for_provider(self.provider)

        if not self.provider or not self.api_key:
            self.provider, self.api_key = detect_provider()
            if self.provider:
                self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")
            self.model_label = get_model_label(self.provider, self.model_id)

        if not self.provider or not self.api_key:
            c.print()
            c.print("  [bold yellow]⚠️ No LLM API Key Found[/bold yellow]")
            c.print("  To use AI features, please configure your system settings.")
            self._cmd_settings()
            
            # Re-check key after settings run
            if self.provider:
                self.api_key = get_api_key_for_provider(self.provider)
            if not self.provider or not self.api_key:
                return (
                    "⚠️ **No LLM API Key Found**\n\n"
                    "DataSanitizer requires an API key to communicate with the model. Please check the following:\n"
                    "- Ensure one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY` is set in your environment variables.\n"
                    "- Or verify your `.env` file in the project root.\n"
                )

        try:
            from v3.agent import _build_system_prompt
            system = _build_system_prompt(self.session_dict, self.df)
            enriched_query = f"{query}\n\n[LOCAL ANALYSIS RESULT]:\n{local_context}"
            
            with c.status(f"  [bold dim]Thinking ({self.model_label})...[/bold dim]"):
                response = call_llm(
                    system, enriched_query,
                    self.memory.recent(4),
                    self.provider, self.api_key,
                    self.model_id,
                )
            return response
        except Exception as e:
            friendly_err = self._format_api_error(e)
            return (
                "⚠️ **AI Call Failed**\n\n"
                f"I encountered an error trying to request a response:\n"
                f"**{friendly_err}**\n\n"
                "Please verify your network connection, API key configuration, or model limits."
            )

    def _cmd_settings(self) -> bool:
        """Unified Settings Manager (Phase 5)."""
        import os
        import json
        from rich.table import Table
        from rich import box
        from v2.utils import safe_input
        from v3.llm import (
            SUPPORTED_PROVIDERS,
            verify_api_key,
            fetch_available_models,
            get_api_key_for_provider,
            detect_provider,
            MODEL_REGISTRY,
            get_model_label,
        )

        c = self.console

        # Initial detection
        if not self.provider:
            default_prov, default_key = detect_provider()
            self.provider = default_prov or "gemini"
        if not self.model_id:
            self.model_id = MODEL_REGISTRY.get(self.provider, {}).get("default")
        self.api_key = get_api_key_for_provider(self.provider)

        key_vars = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "nvidia": "NVIDIA_API_KEY",
        }

        while True:
            c.print()
            c.print("  [bold]⚙️  SYSTEM SETTINGS MANAGER[/bold]")
            c.print("  ─────────────────────────────────────────────────────────")

            table = Table(box=box.ROUNDED)
            table.add_column("Provider", style="bold cyan")
            table.add_column("API Key Status")
            table.add_column("Active Model", style="purple")
            table.add_column("Active Flag", justify="center")

            for p in SUPPORTED_PROVIDERS:
                key = get_api_key_for_provider(p)
                if key:
                    masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
                    key_status = f"[green]✓ Configured ({masked})[/green]"
                else:
                    key_status = "[red]✗ Missing[/red]"

                is_active_prov = (self.provider == p)
                active_flag = "[bold green]★ Active[/bold green]" if is_active_prov else "[dim]--[/dim]"
                
                # Active model display
                if is_active_prov:
                    m_display = self.model_id or "Default"
                else:
                    m_display = MODEL_REGISTRY.get(p, {}).get("default", "Default")

                table.add_row(p.upper(), key_status, m_display, active_flag)

            c.print(table)
            c.print()
            c.print("  [bold]Options:[/bold] 1 = Change Active Provider  ·  2 = Change Active Model  ·  3 = Update API Key  ·  4 = Test Connection  ·  5 = Cancel/Exit")
            c.print()

            choice = safe_input(c, "  [bold bright_cyan]Select option (1-5): [/bold bright_cyan]").strip()

            if choice == "1":
                c.print("\n  [bold]Select Provider:[/bold]")
                for idx, p in enumerate(SUPPORTED_PROVIDERS, 1):
                    c.print(f"    [{idx}] {p.upper()}")
                p_choice = safe_input(c, f"  Choose provider (1-{len(SUPPORTED_PROVIDERS)}): ").strip()
                if p_choice.isdigit():
                    p_idx = int(p_choice) - 1
                    if 0 <= p_idx < len(SUPPORTED_PROVIDERS):
                        target = SUPPORTED_PROVIDERS[p_idx]
                        self.provider = target
                        self.model_id = MODEL_REGISTRY.get(target, {}).get("default")
                        self.api_key = get_api_key_for_provider(target)
                        self.model_label = get_model_label(self.provider, self.model_id)
                        c.print(f"  [green]Provider switched to {target.upper()}[/green]")

            elif choice == "2":
                c.print("\n  [bold]Select Model for " + self.provider.upper() + ":[/bold]")
                c.print("  [dim]Querying available models...[/dim]")
                models = fetch_available_models(self.provider, self.api_key)
                if not models:
                    c.print("  [yellow]No models returned from API. Enter custom model name manually.[/yellow]")
                    custom = safe_input(c, "  Model ID: ").strip()
                    if custom:
                        self.model_id = custom
                        self.model_label = get_model_label(self.provider, self.model_id)
                else:
                    m_keys = list(models.keys())
                    for idx, m_id in enumerate(m_keys, 1):
                        c.print(f"    [{idx}] {models[m_id]['name']} ({m_id})")
                    c.print(f"    [{len(m_keys)+1}] Enter custom model ID...")
                    m_choice = safe_input(c, f"  Select model (1-{len(m_keys)+1}): ").strip()
                    if m_choice.isdigit():
                        m_idx = int(m_choice) - 1
                        if 0 <= m_idx < len(m_keys):
                            self.model_id = m_keys[m_idx]
                            self.model_label = get_model_label(self.provider, self.model_id)
                            c.print(f"  [green]Model switched to {self.model_id}[/green]")
                        elif m_idx == len(m_keys):
                            custom = safe_input(c, "  Enter custom model ID: ").strip()
                            if custom:
                                self.model_id = custom
                                self.model_label = get_model_label(self.provider, self.model_id)

            elif choice == "3":
                var_name = key_vars.get(self.provider, "API_KEY")
                new_key = safe_input(c, f"  Enter new API Key for {self.provider.upper()} ({var_name}): ").strip()
                if new_key:
                    c.print("  [dim]Verifying API key...[/dim]")
                    ok, err = verify_api_key(self.provider, new_key)
                    if ok:
                        os.environ[var_name] = new_key
                        self.api_key = new_key
                        c.print("  [bold green]✓ API Key successfully verified![/bold green]")
                        
                        # Save config & env
                        config_path = os.path.join(os.getcwd(), "config.json")
                        cfg = {}
                        if os.path.exists(config_path):
                            try:
                                with open(config_path, "r", encoding="utf-8") as f:
                                    cfg = json.load(f)
                            except Exception:
                                pass
                        cfg[var_name] = new_key
                        cfg["ACTIVE_PROVIDER"] = self.provider
                        if self.model_id:
                            cfg["ACTIVE_MODEL"] = self.model_id
                        try:
                            with open(config_path, "w", encoding="utf-8") as f:
                                json.dump(cfg, f, indent=2)
                        except Exception:
                            pass

                        # Write to .env
                        env_path = os.path.join(os.getcwd(), ".env")
                        lines = []
                        updated = False
                        if os.path.exists(env_path):
                            try:
                                with open(env_path, "r", encoding="utf-8") as f:
                                    for line in f:
                                        if line.strip().startswith(f"{var_name}="):
                                            lines.append(f"{var_name}={new_key}\n")
                                            updated = True
                                        else:
                                            lines.append(line)
                            except Exception:
                                pass
                        if not updated:
                            lines.append(f"{var_name}={new_key}\n")
                        try:
                            with open(env_path, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                        except Exception:
                            pass
                    else:
                        c.print(f"  [bold red]✗ Verification failed: {err}[/bold red]")

            elif choice == "4":
                if not self.api_key:
                    c.print("  [bold red]✗ Connection failed: No API Key configured for provider.[/bold red]")
                else:
                    c.print(f"  [dim]Testing connection to {self.provider.upper()}...[/dim]")
                    ok, err = verify_api_key(self.provider, self.api_key)
                    if ok:
                        c.print(f"  [bold green]✓ Connection successful! Active model: {self.model_id}[/bold green]")
                    else:
                        c.print(f"  [bold red]✗ Connection failed: {err}[/bold red]")

            elif choice == "5" or choice == "":
                # Save current active configuration to config.json
                config_path = os.path.join(os.getcwd(), "config.json")
                cfg = {}
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                    except Exception:
                        pass
                cfg["ACTIVE_PROVIDER"] = self.provider
                if self.model_id:
                    cfg["ACTIVE_MODEL"] = self.model_id
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2)
                except Exception:
                    pass
                
                # Update session
                if self.session_dict:
                    self.session_dict["active_provider"] = self.provider
                    self.session_dict["active_model_id"] = self.model_id
                    
                c.print("  [dim]Exiting settings manager.[/dim]")
                break
            else:
                c.print("  [dim]Invalid choice. Enter 1-5.[/dim]")

        return True
