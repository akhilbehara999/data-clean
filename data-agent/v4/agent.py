# -*- coding: utf-8 -*-
"""
DataAnalystAgent v4 — main agent entry point.

v4 is not a replacement for v1/v2/v3. It is a persistent, proactive,
and automated layer that:
  • Sits alongside v1-v3 (a user can be in v3 and trigger v4 features)
  • Hooks into every file-load (features 1, 2, 10 activate automatically)
  • Adds /simulate, /specialist, /explain, /rules, /templates, /watch commands
  • Degrades gracefully when dependencies are unavailable

Entry: called from v1/cli.py's run_agent_loop() when active_version == 'v4',
       or from the --connect / --watch CLI flags in main.py.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
from rich.console import Console
from rich.markdown import Markdown
from rich import box
from rich.panel import Panel

from .session_bridge_v4 import init_v4_session_keys, autosave, save_and_switch_to_v2, save_and_switch_to_v3

console = Console(force_terminal=True)

# ── Feature imports (with graceful fallback) ──────────────────────────────────

def _try_import(module_path: str):
    """Import a v4 module gracefully — return None if unavailable."""
    try:
        import importlib
        return importlib.import_module(module_path)
    except Exception:
        return None


# ── On-load hooks (called from any version on file load) ─────────────────────

def on_file_load(filename: str, df: pd.DataFrame, session_dict: dict) -> None:
    """
    Called immediately after any file is loaded (v1-v4).
    Runs: Feature 1 (project memory check), Feature 2 (template check),
          Feature 10 (self-healing pattern detection).
    """
    c = console
    init_v4_session_keys(session_dict)

    # ── Feature 1: Cross-session project memory ───────────────────────────────
    try:
        from v4.project_memory import check_on_load
        msg = check_on_load(filename, df)
        if msg:
            c.print()
            c.print(Panel(
                Markdown(msg.replace("[bold cyan]", "**").replace("[/bold cyan]", "**")
                         .replace("[bold]", "**").replace("[/bold]", "**")),
                title="[bold yellow]📚 Project Memory[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
            ))
            c.print()
    except Exception:
        pass

    # ── Feature 2: Template check ─────────────────────────────────────────────
    try:
        from v4.report_scheduler import check_template_on_load, format_template_offer
        template = check_template_on_load(filename)
        if template:
            c.print()
            offer = format_template_offer(template)
            c.print(Panel(offer, title="[bold cyan]📋 Template Match[/bold cyan]",
                          border_style="cyan", box=box.ROUNDED))
            c.print()
            # Note: actual template execution is deferred to the agent loop
            # (we store it in session so agent can act on it)
            session_dict["_pending_template"] = template
    except Exception:
        pass


def on_session_end(filename: str, df: pd.DataFrame, session_dict: dict) -> None:
    """
    Called at session end (any version). Persists memory + checks for
    template offer.
    """
    # Feature 1: Record session in project memory
    try:
        from v4.project_memory import record_session
        record_session(filename, df, session_dict)
    except Exception:
        pass

    # Feature 2: Log sequence and check for template offer
    try:
        from v4.report_scheduler import log_session_sequence, check_for_template_offer
        from v1 import session_manager
        active_ds = session_manager.get_active_dataset(session_dict)
        if not active_ds:
            active_ds = session_dict
        analyses_run = active_ds.get("v2_summary", {}).get("analyses_run", [])
        log_session_sequence(filename, analyses_run)
        offer = check_for_template_offer(filename, analyses_run)
        if offer:
            console.print()
            console.print(Panel(offer, title="[bold cyan]📋 Template Offer[/bold cyan]",
                                border_style="cyan", box=box.ROUNDED))
            console.print()
            try:
                ans = input("  Save template? (y/n): ").strip().lower()
                if ans in ("y", "yes"):
                    _save_template_interactive(filename, analyses_run)
            except Exception:
                pass
    except Exception:
        pass


def _save_template_interactive(filename: str, analyses_run: list[str]) -> None:
    """Interactively name and save a new template."""
    from v4.report_scheduler import _infer_pattern, save_template
    pattern = _infer_pattern(filename)
    try:
        name = input(f"  Template name (default: 'report_{pattern.split('_')[0]}'): ").strip()
        if not name:
            name = f"report_{filename.split('.')[0][:20]}"
        save_template(name=name, file_pattern=pattern, sequence=analyses_run)
        console.print(f"  [bold green]✓ Template '{name}' saved.[/bold green]")
    except Exception:
        pass


# ── Specialist routing ────────────────────────────────────────────────────────

SPECIALIST_KEYWORDS = {
    "fraud": ["fraud", "suspicious", "money laundering", "structuring", "fake"],
    "marketing": ["marketing", "campaign", "funnel", "acquisition", "churn", "conversion"],
    "inventory": ["inventory", "stock", "warehouse", "sku", "reorder", "supply"],
}


def detect_domain(query: str) -> str | None:
    """Return domain name if query mentions a specialist domain, else None."""
    q = query.lower()
    for domain, keywords in SPECIALIST_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return domain
    return None


def run_specialist(domain: str, df: pd.DataFrame, col_types: dict,
                   session_dict: dict) -> str:
    """
    Route to the appropriate specialist and return formatted findings string.
    Falls back gracefully if specialist module unavailable.
    """
    c = console
    specialist = None

    try:
        if domain == "fraud":
            from v4.specialists.fraud_specialist import FraudSpecialist
            specialist = FraudSpecialist()
        elif domain == "marketing":
            from v4.specialists.marketing_specialist import MarketingSpecialist
            specialist = MarketingSpecialist()
        elif domain == "inventory":
            from v4.specialists.inventory_specialist import InventorySpecialist
            specialist = InventorySpecialist()
        else:
            return (
                "I have specialist rule sets for: **fraud detection**, "
                "**marketing analytics**, **inventory management**. "
                "Which best fits what you're looking for? Or should I use "
                "the general insight engine instead?"
            )
    except ImportError as e:
        return "⚠ Specialist module unavailable. Falling back to general insights."

    # Check for missing columns
    warnings = specialist.check_required_columns(df)
    for w in warnings:
        c.print(f"\n  [bold yellow]⚠ {w}[/bold yellow]")

    # Run rules
    findings = specialist.run(df)

    # Store findings in session
    specialist_store = session_dict.setdefault("specialist_findings", [])
    specialist_store.append({
        "domain": domain,
        "finding_count": len(findings),
        "findings": [
            {
                "rule": f.rule_name,
                "description": f.description[:200],
                "severity": f.severity,
            }
            for f in findings
        ],
    })
    autosave(session_dict)

    return specialist.format_findings(findings)


# ── Main DataAnalystAgentV4 class ─────────────────────────────────────────────

class DataAnalystAgentV4:
    """
    v4 agent — wraps v2 with additional slash commands for v4 features.
    Runs within the same session object as v1-v3.
    """

    def __init__(self, session_dict: dict):
        self.console = console
        init_v4_session_keys(session_dict)
        self.session_dict = session_dict

        from v1 import session_manager
        active_ds = session_manager.get_active_dataset(session_dict)
        if not active_ds:
            active_ds = session_dict
            
        file_info = active_ds.get("file", {})
        self.filename = os.path.basename(file_info.get("original", ""))
        self.cleaned_path = file_info.get("cleaned", "")

        # Load dataframe
        if "df" in session_dict:
            self.df = session_dict["df"]
        else:
            pkl = file_info.get("dataframe_pickle")
            if pkl and os.path.exists(pkl):
                self.df = pd.read_pickle(pkl)
            else:
                try:
                    self.df = pd.read_csv(self.cleaned_path)
                except Exception:
                    self.df = pd.DataFrame()
            session_dict["df"] = self.df

        ct = active_ds.get("column_types", {})
        self.col_types = {
            "numeric": ct.get("numeric", []),
            "categorical": ct.get("categorical", []),
            "datetime": ct.get("datetime", []),
            "identifier": ct.get("identifier", []),
            "text": ct.get("text", []),
        }

    def start(self) -> None:
        """Entry point — print header, enter REPL."""
        self._print_startup()
        self._repl()

    def _print_startup(self) -> None:
        c = self.console
        c.print()
        c.print(Panel(
            f" [bold white]DataSanitizer v4.0.0[/bold white]\n"
            f" File: [bold cyan]{self.filename}[/bold cyan]\n"
            f" Session: [dim]{self.session_dict.get('created_at', '?')}[/dim]\n\n"
            f" [bold dim]v4 Features:[/bold dim] memory · templates · simulate · specialists · explain · rules · watch",
            title="[bold green] DataSanitizer v4 [/bold green]",
            border_style="green",
            box=box.ROUNDED,
        ))
        c.print()
        c.print("  [bold dim]Commands:[/bold dim] "
                "[bold green]/simulate[/bold green] · "
                "[bold green]/specialist[/bold green] · "
                "[bold green]/explain[/bold green] · "
                "[bold green]/rules[/bold green] · "
                "[bold green]/templates[/bold green] · "
                "[bold green]/switch[/bold green] · "
                "[bold green]/help[/bold green] · "
                "[bold green]/exit[/bold green]")
        c.print("  [dim]" + "─" * 85 + "[/dim]")

        # Execute any pending template
        if self.session_dict.get("_pending_template"):
            template = self.session_dict.pop("_pending_template")
            self._execute_template(template)

    def _repl(self) -> None:
        """V4 REPL loop — handles v4 commands + delegates to v2 for standard commands."""
        from v2.utils import safe_input
        from prompt_toolkit.completion import WordCompleter

        completer = WordCompleter(
            ["/simulate", "/specialist", "/explain", "/rules", "/rules list",
             "/rules remove", "/templates", "/templates delete", "/watch",
             "/switch", "/help", "/exit", "/quit"],
            sentence=True,
        )

        while True:
            user_input = safe_input(
                self.console,
                "[bold bright_green]v4 ❯ [/bold bright_green]",
                completer=completer,
            )
            if not user_input:
                continue

            cmd = user_input.strip()
            cmd_lower = cmd.lower()

            if cmd_lower in ("/exit", "/quit", "exit", "quit"):
                self._do_exit()
                break

            if cmd_lower in ("/switch", "switch"):
                self._do_switch()
                break

            if cmd_lower.startswith("/simulate"):
                self._do_simulate(cmd[9:].strip())
                continue

            if cmd_lower.startswith("/specialist"):
                self._do_specialist(cmd[11:].strip())
                continue

            if cmd_lower.startswith("/explain"):
                self._do_explain(cmd[8:].strip())
                continue

            if cmd_lower.startswith("/rules"):
                self._do_rules(cmd[6:].strip())
                continue

            if cmd_lower.startswith("/templates"):
                self._do_templates(cmd[10:].strip())
                continue

            if cmd_lower.startswith("/help"):
                self._do_help()
                continue

            # Natural language — check for v4 triggers before delegating to v2
            from v4.simulation_engine import is_simulation_query
            from v4.methodology import is_explain_query

            if is_simulation_query(cmd):
                self._do_simulate(cmd)
                continue

            if is_explain_query(cmd):
                self._do_explain(cmd)
                continue

            domain = detect_domain(cmd)
            if domain:
                self._do_specialist(domain)
                continue

            # Delegate to v2 for unhandled commands
            self.console.print(
                f"\n  [dim]v4: Use [bold]/simulate[/bold], [bold]/specialist[/bold], "
                f"[bold]/explain[/bold] — or [bold]/switch[/bold] to V2/V3.[/dim]"
            )
            self.console.print()

    # ── Command handlers ──────────────────────────────────────────────────────

    def _do_simulate(self, query: str) -> None:
        if not query:
            self.console.print(
                "\n  Usage: [bold]/simulate what if we increased [column] by 10%[/bold]\n"
                "  Or just type a 'what if' question naturally."
            )
            return
        try:
            from v4.simulation_engine import run_simulation
            result = run_simulation(query, self.df, self.col_types, self.session_dict)
            self.console.print()
            self.console.print(Markdown(result))
            autosave(self.session_dict)
        except Exception as e:
            self.console.print("\n  [bold red]⚠ Simulation failed. Please check your query and try again.[/bold red]")
        self.console.print()

    def _do_specialist(self, domain_or_query: str) -> None:
        c = self.console
        query = domain_or_query.strip().lower()

        # Try to extract domain from query or direct name
        domain = None
        for d in SPECIALIST_KEYWORDS:
            if d in query or any(kw in query for kw in SPECIALIST_KEYWORDS[d]):
                domain = d
                break

        if not domain:
            c.print(
                "\n  I have specialist rule sets for:\n"
                "    [bold cyan]fraud[/bold cyan] — fraud detection patterns\n"
                "    [bold cyan]marketing[/bold cyan] — marketing analytics\n"
                "    [bold cyan]inventory[/bold cyan] — inventory management\n\n"
                "  Usage: [bold]/specialist fraud[/bold] or [bold]/specialist marketing[/bold]\n"
                "  Or describe your data: 'this is fraud data, look for suspicious patterns'"
            )
            return

        c.print(f"\n  [bold cyan]Running {domain} specialist...[/bold cyan]")
        with c.status(f"  [dim]Analyzing with {domain} rule set...[/dim]"):
            result = run_specialist(domain, self.df, self.col_types, self.session_dict)
        c.print()
        # Rich markup in result
        c.print(result)
        c.print()

    def _do_explain(self, query: str) -> None:
        try:
            from v4.methodology import handle_explain_request
            handle_explain_request(query, self.session_dict)
        except Exception as e:
            self.console.print("\n  [bold red]⚠ Explanation failed. Please try a different query.[/bold red]")
        self.console.print()

    def _do_rules(self, args: str) -> None:
        c = self.console
        args = args.strip()

        try:
            from v4.self_healing import list_rules, delete_rule
        except ImportError:
            c.print("\n  [bold red]⚠ Self-healing module unavailable.[/bold red]\n")
            return

        if args.startswith("remove") or args.startswith("delete"):
            rule_name = args.split(maxsplit=1)[1].strip() if len(args.split()) > 1 else ""
            if not rule_name:
                c.print("\n  Usage: [bold]/rules remove [rule_name][/bold]\n")
                return
            deleted = delete_rule(rule_name)
            if deleted:
                c.print(f"\n  [bold green]✓ Rule '{rule_name}' removed.[/bold green]\n")
            else:
                c.print(f"\n  [bold yellow]Rule '{rule_name}' not found.[/bold yellow]\n")
            return

        # List
        rules = list_rules()
        c.print()
        if not rules:
            c.print("  No custom rules saved yet.")
            c.print("  Custom rules are learned automatically during v1 cleaning.")
        else:
            c.print(f"  [bold]Custom Rules ({len(rules)} saved)[/bold]")
            c.print()
            for r in rules:
                c.print(f"  • [bold cyan]{r.get('rule_name', '?')}[/bold cyan]")
                c.print(f"    [dim]Detection: {r.get('detection', '?')}[/dim]")
                c.print(f"    [dim]Fix: {r.get('fix', '?')}[/dim]")
                c.print(f"    [dim]Applies to: {r.get('applies_to_columns_matching', [])}[/dim]")
                c.print(f"    [dim]Created: {r.get('created', '?')} from '{r.get('source_file', '?')}'[/dim]")
                c.print()
        c.print("  Use [bold]/rules remove [name][/bold] to delete a rule.")
        c.print()

    def _do_templates(self, args: str) -> None:
        c = self.console
        args = args.strip()

        try:
            from v4.report_scheduler import list_templates, delete_template
        except ImportError:
            c.print("\n  [bold red]⚠ Report scheduler module unavailable.[/bold red]\n")
            return

        if args.startswith("delete") or args.startswith("remove"):
            name = args.split(maxsplit=1)[1].strip() if len(args.split()) > 1 else ""
            if not name:
                c.print("\n  Usage: [bold]/templates delete [name][/bold]\n")
                return
            deleted = delete_template(name)
            if deleted:
                c.print(f"\n  [bold green]✓ Template '{name}' deleted.[/bold green]\n")
            else:
                c.print(f"\n  [bold yellow]Template '{name}' not found.[/bold yellow]\n")
            return

        # List
        templates = list_templates()
        c.print()
        if not templates:
            c.print("  No templates saved yet.")
            c.print("  Templates are created automatically after you repeat the same")
            c.print("  analysis sequence 3+ times on matching file patterns.")
        else:
            c.print(f"  [bold]Report Templates ({len(templates)} saved)[/bold]")
            c.print()
            for t in templates:
                seq = " → ".join(t.get("sequence", []))
                c.print(f"  • [bold cyan]{t['name']}[/bold cyan]")
                c.print(f"    [dim]Pattern: {t.get('file_pattern', '?')}[/dim]")
                c.print(f"    [dim]Sequence: {seq}[/dim]")
                c.print(f"    [dim]Created: {t.get('created', '?')}[/dim]")
                c.print()
        c.print("  Use [bold]/templates delete [name][/bold] to remove a template.")
        c.print()

    def _do_help(self) -> None:
        c = self.console
        c.print()
        c.print("  [bold]DataSanitizer v4 Commands:[/bold]")
        c.print()
        c.print("  [bold green]/simulate [query][/bold green]")
        c.print("    What-if simulation engine. Try: /simulate what if revenue increased by 15%")
        c.print()
        c.print("  [bold green]/specialist [domain][/bold green]")
        c.print("    Domain-specific analysis. Domains: fraud, marketing, inventory")
        c.print()
        c.print("  [bold green]/explain [topic][/bold green]")
        c.print("    Show methodology trace for a calculation. Or ask: 'how did you calculate that?'")
        c.print()
        c.print("  [bold green]/rules[/bold green]  /  [bold green]/rules remove [name][/bold green]")
        c.print("    List or remove custom self-healing cleaning rules.")
        c.print()
        c.print("  [bold green]/templates[/bold green]  /  [bold green]/templates delete [name][/bold green]")
        c.print("    List or delete saved report templates.")
        c.print()
        c.print("  [bold green]/switch[/bold green]")
        c.print("    Switch to v2 (command mode) or v3 (AI chat mode).")
        c.print()
        c.print("  [bold green]/exit[/bold green]   — Save session and quit")
        c.print()
        c.print("  [dim]You can also just type naturally — v4 auto-detects 'what if' queries,[/dim]")
        c.print("  [dim]'how did you calculate', and domain descriptions.[/dim]")
        c.print()

    def _do_switch(self) -> None:
        c = self.console
        c.print()
        c.print("  Switch to: [bold]v2[/bold] (command mode) or [bold]v3[/bold] (AI chat)?")
        try:
            choice = input("  Enter v2 / v3: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

        if choice in ("v2", "2"):
            c.print("\n  [bold purple]Switching to V2 Command Mode...[/bold purple]")
            save_and_switch_to_v2(self.session_dict, self.df)
        elif choice in ("v3", "3"):
            c.print("\n  [bold cyan]Switching to V3 AI Chat Mode...[/bold cyan]")
            save_and_switch_to_v3(self.session_dict, self.df)
        else:
            c.print("  [dim]Cancelled — staying in v4.[/dim]")
        c.print()

    def _do_exit(self) -> None:
        self.console.print()
        on_session_end(self.filename, self.df, self.session_dict)
        autosave(self.session_dict, self.df)
        self.console.print("[bold yellow]Session saved. Goodbye![/bold yellow]")
        self.console.print()

    def _execute_template(self, template: dict) -> None:
        """Execute a matched template sequence on startup."""
        c = self.console
        from v4.report_scheduler import format_template_offer
        c.print(Panel(
            format_template_offer(template),
            title="[bold cyan]📋 Template Matched[/bold cyan]",
            border_style="cyan", box=box.ROUNDED,
        ))
        try:
            ans = input("  Run template? (y/n): ").strip().lower()
        except Exception:
            return

        if ans not in ("y", "yes"):
            c.print("  [dim]Template skipped.[/dim]")
            return

        # Instantiate V2 agent for execution
        try:
            from v2.agent import DataAnalystAgentV2
            v2_agent = DataAnalystAgentV2(session_dict=self.session_dict)
            from v4.report_scheduler import run_template_sequence
            run_template_sequence(template, v2_agent)
        except Exception as e:
            c.print("\n  [bold red]⚠ Template execution failed. Please check your template and try again.[/bold red]")
