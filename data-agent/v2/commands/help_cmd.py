"""Command [H] — Help & Menu: explain any command and show structured menu."""

from __future__ import annotations
from typing import TYPE_CHECKING
from rich.table import Table
from rich import box

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2

COMMAND_HELP: dict[str, dict[str, str]] = {
    "eda": {
        "title": "Auto EDA (/eda)",
        "desc": "Runs a full exploratory data analysis on the loaded dataset, producing profile cards for numeric, categorical, and datetime columns along with correlation highlights.",
        "usage": "/eda",
        "example": "/eda",
        "parameters": "None"
    },
    "relationships": {
        "title": "Relationships (/relationships)",
        "desc": "Scans for Pearson correlations between numeric columns, redundant columns, and potential join keys in multi-file sessions.",
        "usage": "/relationships",
        "example": "/relationships",
        "parameters": "None"
    },
    "geographic": {
        "title": "Geographic Analysis (/geographic)",
        "desc": "Detects location columns (city, state, country) and groups records by state, region, and tier with India city/pincode fuzzy mapping.",
        "usage": "/geographic",
        "example": "/geographic",
        "parameters": "None"
    },
    "pivot": {
        "title": "Pivot Table Builder (/pivot)",
        "desc": "Interactively build pivot and aggregation tables by specifying row groups, column groups, values, and agg functions.",
        "usage": "/pivot",
        "example": "/pivot",
        "parameters": "None"
    },
    "comparative": {
        "title": "Comparative Analysis (/comparative)",
        "desc": "Compares two time periods, segments (e.g. category values), or files, returning percentage changes and statistical summaries.",
        "usage": "/comparative",
        "example": "/comparative",
        "parameters": "None"
    },
    "insights": {
        "title": "Insight Engine (/insights)",
        "desc": "Executes statistical checks (seasonality, concentrations, date gaps, growth signals, outliers) and returns formatted findings.",
        "usage": "/insights",
        "example": "/insights",
        "parameters": "None"
    },
    "simulate": {
        "title": "What-If Simulator (/simulate)",
        "desc": "Simulate business metrics under custom conditions. Enter expression, bounds, steps, and base values.",
        "usage": "/simulate",
        "example": "/simulate",
        "parameters": "Prompted step-by-step or automatically parsed."
    },
    "specialist": {
        "title": "Domain Specialists (/specialist)",
        "desc": "Routes analysis to specific domain modules (Marketing, Inventory, Fraud Detection, Customer, Finance).",
        "usage": "/specialist [specialist_name]",
        "example": "/specialist marketing",
        "parameters": "specialist_name: marketing, inventory, fraud, customer, finance"
    },
    "explain": {
        "title": "Methodology Explainer (/explain)",
        "desc": "Shows step-by-step mathematical reasoning, statistical logic, or column selection path for any metric.",
        "usage": "/explain [concept_or_metric]",
        "example": "/explain correlations",
        "parameters": "concept_or_metric: e.g., skewness, Pearson r, outlier detection"
    },
    "rules": {
        "title": "Self-Healing Rules (/rules)",
        "desc": "View, enable, disable, or delete active data cleaning and self-healing validation rules.",
        "usage": "/rules [view/disable/delete] [rule_id]",
        "example": "/rules view",
        "parameters": "action: view, disable, delete; rule_id: ID of specific rule"
    },
    "templates": {
        "title": "Report Templates (/templates)",
        "desc": "Manage saved report generation templates to run standardized analysis pipelines.",
        "usage": "/templates [view/delete] [template_name]",
        "example": "/templates view",
        "parameters": "action: view, delete; template_name: Name of target template"
    },
    "files": {
        "title": "Return to Ingestion (/files)",
        "desc": "Return to the browser file ingestion interface to stage, review, or remove datasets.",
        "usage": "/files",
        "example": "/files",
        "parameters": "None"
    },
    "report": {
        "title": "Report Builder (/report)",
        "desc": "Compile all session results into a beautiful HTML file (styled single page) or standard Markdown document.",
        "usage": "/report",
        "example": "/report",
        "parameters": "None"
    },
    "export": {
        "title": "Export Dataset (/export)",
        "desc": "Save the current cleaned active dataset. Supports CSV, XLSX, Parquet, JSON, Markdown, and HTML.",
        "usage": "/export",
        "example": "/export",
        "parameters": "None"
    },
    "reclean": {
        "title": "Re-clean Phase (/reclean)",
        "desc": "Return to the interactive clean phase to apply additional row/column cleaning or validation filters.",
        "usage": "/reclean",
        "example": "/reclean",
        "parameters": "None"
    },
    "settings": {
        "title": "System Settings (/settings)",
        "desc": "Configure AI model API keys (e.g. OpenAI/Gemini/Anthropic), model selection, provider endpoints, and output preferences.",
        "usage": "/settings",
        "example": "/settings",
        "parameters": "None"
    },
    "menu": {
        "title": "Console Menu (/menu)",
        "desc": "Display a beautiful grouped panel of all available core, proactive, and system console commands.",
        "usage": "/menu",
        "example": "/menu",
        "parameters": "None"
    },
    "help": {
        "title": "Help System (/help)",
        "desc": "Get syntax help, description, parameters, and examples for any console command.",
        "usage": "/help [command_name]",
        "example": "/help eda",
        "parameters": "command_name: Any command keyword (with or without / prefix)"
    },
    "exit": {
        "title": "Exit Console (/exit)",
        "desc": "Save session history and exit the DataSanitizer environment safely.",
        "usage": "/exit",
        "example": "/exit",
        "parameters": "None"
    }
}

# Normalizes aliases or index keys to canonical command keywords
HELP_MAPPING = {
    "1": "eda",
    "eda": "eda",
    "2": "relationships",
    "relationships": "relationships",
    "relations": "relationships",
    "3": "geographic",
    "geographic": "geographic",
    "geo": "geographic",
    "4": "pivot",
    "pivot": "pivot",
    "5": "comparative",
    "comparative": "comparative",
    "compare": "comparative",
    "6": "insights",
    "insights": "insights",
    "insight": "insights",
    "simulate": "simulate",
    "simulation": "simulate",
    "specialist": "specialist",
    "specialists": "specialist",
    "explain": "explain",
    "rules": "rules",
    "rule": "rules",
    "templates": "templates",
    "template": "templates",
    "files": "files",
    "8": "report",
    "report": "report",
    "9": "export",
    "export": "export",
    "r": "reclean",
    "reclean": "reclean",
    "clean": "reclean",
    "settings": "settings",
    "menu": "menu",
    "help": "help",
    "h": "help",
    "exit": "exit",
}


def run_help(agent: DataAnalystAgentV2, args: str = ""):
    """Print help details for a specific command or fallback to the menu."""
    con = agent.console
    con.print()

    # Clean the arguments
    key = args.strip().lower().replace("[", "").replace("]", "").lstrip("/")
    
    if key in HELP_MAPPING:
        cmd_key = HELP_MAPPING[key]
        info = COMMAND_HELP[cmd_key]
        
        con.print(f"  [bold bright_cyan]{info['title']}[/bold bright_cyan]")
        con.print(f"  [dim]──────────────────────────────────────────────────────────[/dim]")
        con.print(f"  [bold]Description:[/bold] {info['desc']}")
        con.print(f"  [bold]Usage/Syntax:[/bold] [yellow]{info['usage']}[/yellow]")
        con.print(f"  [bold]Example:[/bold]      [green]{info['example']}[/green]")
        con.print(f"  [bold]Parameters:[/bold]   {info['parameters']}")
    else:
        if args:
            con.print(f"[yellow]  No detailed help available for '{args}'. Showing menu.[/yellow]")
            con.print()
        run_menu(agent)

    con.print()


def run_menu(agent: DataAnalystAgentV2):
    """Print a beautiful grouped table of all available commands."""
    con = agent.console
    
    table = Table(
        title="[bold purple]DataSanitizer Console Menu[/bold purple]",
        box=box.DOUBLE_EDGE,
        border_style="purple",
        show_header=True,
        header_style="bold magenta"
    )
    table.title_align = "left"
    table.add_column("Group", style="bold white", width=12)
    table.add_column("Command", style="bold cyan", width=18)
    table.add_column("Description", style="dim", width=55)

    groups = [
        ("Explore", [
            ("/eda", "Run Exploratory Data Analysis & profiling"),
            ("/relationships", "Analyze correlations & redundant columns"),
            ("/geographic",    "Enrich and break down geo columns"),
            ("/insights",      "Run rule-based anomaly & pattern checks"),
        ]),
        ("Build", [
            ("/pivot",         "Interactively build custom pivot tables"),
            ("/comparative",   "Compare segments, periods, or files"),
        ]),
        ("Automate", [
            ("/simulate",      "Run what-if scenario simulations"),
            ("/specialist",    "Specialized domain-specific analysis"),
            ("/explain",       "Examine mathematical calculation logic"),
            ("/rules",         "List/manage self-healing cleaning rules"),
            ("/templates",     "List/delete report templates"),
        ]),
        ("Data", [
            ("/files",         "Return to browser ingestion center"),
            ("/report",        "Export HTML/MD session reports"),
            ("/export",        "Save active dataset to file"),
            ("/reclean",       "Return to interactive cleaning phase"),
        ]),
        ("System", [
            ("/settings",      "Configure AI keys, models, and provider"),
            ("/menu",          "Show this grouped command menu"),
            ("/help [cmd]",    "Get syntax/parameter details for a command"),
            ("/exit",          "Save history and exit console"),
        ])
    ]

    for group_name, cmds in groups:
        first = True
        for cmd, desc in cmds:
            table.add_row(group_name if first else "", cmd, desc)
            first = False
        table.add_section()

    con.print()
    con.print(table)
    con.print()
