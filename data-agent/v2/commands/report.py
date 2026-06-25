"""Command [8] — Report Builder: compile session into formatted report."""

from __future__ import annotations
from typing import TYPE_CHECKING
import os
from datetime import datetime

import pandas as pd

from ..utils import safe_input, ensure_output_dir, fmt_size, fmt_num, get_clean_path_base
from .export import run_export_df

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


# Section labels and keys
_SECTIONS = [
    ("cleaned_data",  "Cleaned dataset"),
    ("overview",      "Dataset overview"),
    ("v1_summary",    "v1 cleaning summary"),
    ("eda",           "EDA - full profile"),
    ("relationships", "Relationship findings"),
    ("geographic",    "Geographic breakdown"),
    ("pivot",         "Pivot table"),
    ("comparative",   "Comparative analysis"),
    ("insights",      "Insight suggestions"),
    ("session_log",   "Session log"),
]


def run_report(agent: DataAnalystAgentV2) -> dict | None:
    """Build and export a report from all completed session sections."""
    con = agent.console

    # Determine which sections are available
    completed = {
        "cleaned_data": True,  # Always available
        "overview": True,      # Always available
        "v1_summary": True,    # Always available
        "eda": agent.results.get("eda") is not None,
        "relationships": agent.results.get("relationships") is not None,
        "geographic": agent.results.get("geographic") is not None,
        "pivot": agent.results.get("pivot") is not None,
        "comparative": agent.results.get("comparative") is not None,
        "insights": agent.results.get("insights") is not None,
        "session_log": True,   # Always available
    }

    con.print()
    con.print("  ─────────────────────────────────────────────────────────")
    con.print("  🗂️  REPORT BUILDER")
    con.print("  ─────────────────────────────────────────────────────────")
    con.print("  Sections available for this session:")
    con.print()

    for i, (key, label) in enumerate(_SECTIONS, 1):
        mark = "✓" if completed[key] else " "
        suffix = ""
        if key == "cleaned_data":
            suffix = "  ← always included"
        elif key == "v1_summary":
            suffix = "  ← always included"
        elif key == "session_log":
            suffix = "  ← always included"
        elif not completed[key]:
            if key in ("eda", "relationships", "insights"):
                suffix = "  ← not run this session (will auto-run if selected)"
            else:
                suffix = "  ← not run this session"
    from ..utils import multi_select
    options = []
    for key, label in _SECTIONS:
        suffix = ""
        if key in ("cleaned_data", "v1_summary", "session_log"):
            suffix = " (always included)"
        elif not completed[key]:
            if key in ("eda", "relationships", "insights"):
                suffix = " (not run; will auto-run)"
            else:
                suffix = " (not run yet)"
        else:
            suffix = " (✓ available)"
        options.append(f"{label}{suffix}")

    preselected = [i for i, (key, _) in enumerate(_SECTIONS) if completed[key]]
    selected_indices = multi_select(
        con,
        prompt="Select Sections to Include in Report",
        options=options,
        preselected=preselected
    )

    included_keys = {_SECTIONS[idx][0] for idx in selected_indices}

    included = []
    for key, label in _SECTIONS:
        if key in included_keys:
            if not completed[key]:
                if key == "eda":
                    con.print(f"  [dim]Running EDA dynamically to include in report...[/dim]")
                    from .eda import run_eda
                    agent.results["eda"] = run_eda(agent, silent=True)
                    completed["eda"] = True
                elif key == "relationships":
                    con.print(f"  [dim]Running Relationship scan dynamically to include in report...[/dim]")
                    from .relationships import run_relationships
                    agent.results["relationships"] = run_relationships(agent)
                    completed["relationships"] = True
                elif key == "insights":
                    con.print(f"  [dim]Running Insight engine dynamically to include in report...[/dim]")
                    from .insights import run_insights
                    agent.results["insights"] = run_insights(agent)
                    completed["insights"] = True
                else:
                    # For sections requiring manual configuration (geographic, pivot, comparative), skip and warn
                    con.print(f"  [yellow]⚠ Section '{label}' has not been run and cannot be generated automatically. Skipping.[/yellow]")

            if completed[key]:
                included.append((key, label))

    if not included:
        con.print("[red]No sections selected/available for report. Generation cancelled.[/red]")
        con.print()
        con.print("[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
        return None

    # Ask export format
    con.print()
    con.print("  Export report as:")
    con.print("    [1] HTML  — styled single page")
    con.print("    [2] Markdown (.md)")

    while True:
        pick = safe_input(con, "[bold bright_cyan]  Format: [/bold bright_cyan]")
        if pick in ("1", "2"):
            break
        con.print("[dim]Enter 1–2.[/dim]")

    base = get_clean_path_base(agent.original_filepath)
    default_name = f"{base}_report_{datetime.now().strftime('%Y-%m-%d')}"

    name = safe_input(
        con,
        f"[bold bright_cyan]  Filename (Enter for '{default_name}'): [/bold bright_cyan]"
    )
    if not name:
        name = default_name

    out_dir = ensure_output_dir()

    if pick == "1":
        path = _export_html(agent, included, out_dir, name)
    else:
        path = _export_markdown(agent, included, out_dir, name)

    if path:
        size = os.path.getsize(path)
        con.print(f"  [green]✓ Report saved → {path}  |  Size: {fmt_size(size)}[/green]")

    con.print()
    con.print("[bold bright_cyan]What would you like to do next?[/bold bright_cyan]")
    return {"path": path, "sections": [k for k, _ in included]}



# ── HTML export ──────────────────────────────────────────────────────────────

def _export_html(agent, sections, out_dir, name) -> str | None:
    """Single styled HTML page with TOC."""
    path = os.path.join(out_dir, f"{name}.html")
    date = datetime.now().strftime("%Y-%m-%d")

    toc_links = []
    body_blocks = []

    for key, label in sections:
        anchor = key
        toc_links.append(f'<li><a href="#{anchor}"><span>{label}</span></a></li>')

        df_section = _section_to_df(agent, key)
        if df_section is not None and not df_section.empty:
            if key == "cleaned_data":
                preview_df = df_section.head(100)
                table_html = preview_df.to_html(index=False, classes="data-table", border=0)
                if len(df_section) > 100:
                    table_html += (
                        f'<div class="note-box">'
                        f'ℹ️ <strong>Note:</strong> Only the first 100 rows are displayed in this HTML preview. '
                        f'The full dataset contains {len(df_section):,} rows.'
                        f'</div>'
                    )
            else:
                table_html = df_section.to_html(index=False, classes="data-table", border=0)
        else:
            table_html = "<p class='note-box'>No data for this section.</p>"

        # Wrap in data-table-wrapper for beautiful styling and horizontal scroll
        table_styled = f'<div class="data-table-wrapper">{table_html}</div>'

        body_blocks.append(
            f'<section id="{anchor}" class="section-card">'
            f'<h2 class="section-title">{label}</h2>'
            f'{table_styled}'
            f'</section>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DataSanitizer v2.0 — Report for {agent.filename}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-dark: #0f0f1b;
  --bg-card: #18182c;
  --accent: #00d4ff;
  --accent-purple: #9d4edd;
  --text-primary: #f8f9fa;
  --text-secondary: #a0a5c0;
  --border-color: rgba(255, 255, 255, 0.08);
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Outfit', sans-serif;
  background: var(--bg-dark);
  color: var(--text-primary);
  line-height: 1.6;
  padding: 0;
  display: flex;
  min-height: 100vh;
}}
.sidebar {{
  width: 280px;
  background: #141424;
  border-right: 1px solid var(--border-color);
  padding: 2rem 1.5rem;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  overflow-y: auto;
  z-index: 10;
}}
.sidebar-logo {{
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  letter-spacing: 0.5px;
}}
.sidebar-menu {{
  list-style: none;
}}
.sidebar-menu li {{
  margin-bottom: 0.5rem;
}}
.sidebar-menu a {{
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  transition: all 0.3s ease;
}}
.sidebar-menu a:hover {{
  background: rgba(0, 212, 255, 0.1);
  color: var(--accent);
  padding-left: 1.25rem;
}}
.main-content {{
  margin-left: 280px;
  flex: 1;
  padding: 3rem 4rem;
  max-width: 1400px;
}}
.header-card {{
  background: linear-gradient(135deg, #1d1d36 0%, #151528 100%);
  padding: 2.5rem;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  margin-bottom: 3rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  position: relative;
  overflow: hidden;
}}
.header-title {{
  font-size: 2.25rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  background: linear-gradient(90deg, #00d4ff, #9d4edd);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}
.header-meta {{
  color: var(--text-secondary);
  font-size: 1.05rem;
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}}
.section-card {{
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--border-color);
  padding: 2rem;
  margin-bottom: 3rem;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
}}
.section-title {{
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.75rem;
}}
.data-table-wrapper {{
  overflow-x: auto;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}}
.data-table {{
  border-collapse: collapse;
  width: 100%;
  text-align: left;
}}
.data-table th {{
  background: rgba(255, 255, 255, 0.03);
  color: var(--accent);
  padding: 1rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 600;
  border-bottom: 2px solid var(--border-color);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.data-table td {{
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
  font-size: 0.95rem;
}}
.data-table tr:last-child td {{
  border-bottom: none;
}}
.data-table tr:hover {{
  background: rgba(255, 255, 255, 0.02);
}}
.data-table tr:nth-child(even) {{
  background: rgba(255, 255, 255, 0.01);
}}
.note-box {{
  background: rgba(0, 212, 255, 0.05);
  border-left: 4px solid var(--accent);
  padding: 1rem;
  border-radius: 4px;
  margin-top: 1rem;
  font-size: 0.9rem;
  color: var(--text-secondary);
}}
@media (max-width: 992px) {{
  body {{ flex-direction: column; }}
  .sidebar {{ width: 100%; position: relative; border-right: none; border-bottom: 1px solid var(--border-color); }}
  .main-content {{ margin-left: 0; padding: 2rem; }}
}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-logo">🧹 DataSanitizer v2.0</div>
  <ul class="sidebar-menu">
    {''.join(toc_links)}
  </ul>
</div>
<div class="main-content">
  <div class="header-card">
    <h1 class="header-title">📊 Analysis Report — {agent.filename}</h1>
    <div class="header-meta">
      <span>📅 Date: {date}</span>
      <span>📈 Rows: {len(agent.df):,}</span>
      <span>📋 Columns: {len(agent.df.columns)}</span>
    </div>
  </div>
  {''.join(body_blocks)}
</div>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ── Markdown export ──────────────────────────────────────────────────────────

def _export_markdown(agent, sections, out_dir, name) -> str | None:
    """Clean Markdown report."""
    path = os.path.join(out_dir, f"{name}.md")
    date = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# 📊 Analysis Report — {agent.filename}",
        f"Date: {date} | Rows: {len(agent.df):,} | Columns: {len(agent.df.columns)}",
        "",
    ]

    for key, label in sections:
        lines.append(f"## {label}")
        lines.append("")
        df_section = _section_to_df(agent, key)
        if df_section is not None and not df_section.empty:
            if key == "cleaned_data":
                preview_df = df_section.head(100)
                lines.append(preview_df.to_markdown(index=False))
                if len(df_section) > 100:
                    lines.append(f"\n_Note: Only the first 100 rows are displayed in this Markdown preview. The full dataset contains {len(df_section):,} rows._\n")
            else:
                lines.append(df_section.to_markdown(index=False))
        else:
            lines.append("_No data for this section._")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# ── Section → DataFrame converter ───────────────────────────────────────────

def _section_to_df(agent, key: str) -> pd.DataFrame | None:
    """Convert a stored result section into a DataFrame for export."""
    if key == "cleaned_data":
        return agent.df

    if key == "overview":
        return pd.DataFrame([{
            "Filename": agent.filename,
            "Rows": len(agent.df),
            "Columns": len(agent.df.columns),
            "Memory (MB)": round(agent.df.memory_usage(deep=True).sum() / 1_048_576, 2),
            "Session Date": datetime.now().strftime("%Y-%m-%d"),
        }])

    if key == "v1_summary":
        summary_rows = [
            {"Metric / Clean Step": "Issues Resolved", "Value": str(agent.issues_resolved)},
            {"Metric / Clean Step": "Rows Removed", "Value": f"{agent.original_shape[0] - agent.cleaned_shape[0]}"},
            {"Metric / Clean Step": "Columns Removed", "Value": f"{agent.original_shape[1] - agent.cleaned_shape[1]}"},
        ]
        for i, act in enumerate(agent.applied_actions, 1):
            summary_rows.append({"Metric / Clean Step": f"Applied Action {i}", "Value": act})
        return pd.DataFrame(summary_rows)

    if key == "eda":
        eda = agent.results.get("eda")
        if not eda:
            return None
        rows = []
        for p in eda.get("numeric", []):
            rows.append({
                "Column": p["column"], "Type": "numeric",
                "Mean": fmt_num(p["mean"]), "Median": fmt_num(p["median"]),
                "Std": fmt_num(p["std"]), "Min": fmt_num(p["min"]),
                "Max": fmt_num(p["max"]), "Nulls": p["nulls"],
                "Skew": p["skew_label"],
            })
        for p in eda.get("categorical", []):
            top = ", ".join(f'{t["value"]} ({t["pct"]}%)' for t in p["top5"])
            rows.append({
                "Column": p["column"], "Type": "categorical",
                "Unique": p["unique"], "Nulls": p["nulls"], "Top Values": top,
            })
        for p in eda.get("datetime", []):
            if p.get("empty"):
                rows.append({
                    "Column": p["column"], "Type": "datetime",
                })
            else:
                rows.append({
                    "Column": p["column"], "Type": "datetime",
                    "Min": p["earliest"], "Max": p["latest"],
                    "Top Values": f"Busiest: {p['busiest_day']} ({fmt_num(p['busiest_day_pct'])}%), Gap: {p['gap_str']}",
                })
        return pd.DataFrame(rows) if rows else None

    if key == "relationships":
        rel = agent.results.get("relationships")
        if not rel:
            return None
        rows = []
        for c in rel.get("correlations", []):
            rows.append({"Type": "Correlation", "Detail": f"{c['col_a']} ↔ {c['col_b']} r={c['r']}", "Note": c["note"]})
        for r in rel.get("redundant", []):
            rows.append({"Type": "Redundant", "Detail": f"{r['derived']} ← {r['source']}"})
        return pd.DataFrame(rows) if rows else None

    if key == "geographic":
        geo = agent.results.get("geographic")
        if not geo or not geo.get("breakdown"):
            return None
        return pd.DataFrame(geo["breakdown"])

    if key == "pivot":
        piv = agent.results.get("pivot")
        if not piv or piv.get("pivot_df") is None:
            return None
        return piv["pivot_df"].reset_index()

    if key == "comparative":
        comp = agent.results.get("comparative")
        if not comp:
            return None
        return pd.DataFrame(comp.get("metrics", []))

    if key == "insights":
        ins = agent.results.get("insights")
        if not ins:
            return None
        return pd.DataFrame(ins.get("insights", []))

    if key == "session_log":
        entries = agent.session.as_table_rows()
        return pd.DataFrame(entries) if entries else None

    return None
