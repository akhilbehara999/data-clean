"""UI components: unified sidebar, cards, badges, and cleaning configuration.

Shared building blocks for the four pages. Visual styling comes from the
design system in ``ui/theme.py``; this module holds the higher-level
compositions (sidebar, metric cards, the per-operation config panel, the
diagnosis table).
"""
import html as py_html
from datetime import datetime

import pandas as pd
import streamlit as st

from ui.theme import badge, empty_state, status_tone


def start_over() -> None:
    """Reset all session state and switch to step 0."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["current_step"] = 0
    st.rerun()





def render_sidebar(variant: str = "default") -> None:
    """Render the sidebar.
    # Not called from app.py — sidebar is hidden via CSS.

    ``variant``:
      - ``default``  — Upload / Report pages: tagline + session log.
      - ``results``  — adds a "Start over" button.
    """
    with st.sidebar:
        st.markdown(
            f"""
            <div class="ds-brand" style="margin-bottom: 24px;">
                <div class="ds-logo">🧹</div>
                <div>
                    <div class="ds-wordmark" style="font-size: 1.05rem; font-weight: 700; color: #0F172A; letter-spacing: -0.02em; line-height: 1.1;">Data Sanitizer</div>
                    <div class="ds-tagline" style="font-size: 0.78rem; color: #64748B; line-height: 1.2;">Clean your Excel and CSV files — fast.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if variant == "results":
            if st.button("↺ Start over", use_container_width=True, key="btn_start_over"):
                start_over()


# Back-compat aliases for the existing call sites during the rollout.
def render_simple_sidebar():
    """# Not called from app.py — sidebar is hidden via CSS."""
    render_sidebar("default")


def render_results_sidebar():
    """# Not called from app.py — sidebar is hidden via CSS."""
    render_sidebar("results")


# ─────────────────────────────────────────────────────────────────────────────
# Content primitives
# ─────────────────────────────────────────────────────────────────────────────
def render_section(title: str, icon: str = "") -> None:
    """Render a consistent uppercase section header."""
    prefix = f"{icon} " if icon else ""
    st.markdown(f'<p class="ds-section">{prefix}{title}</p>', unsafe_allow_html=True)


def render_metric(label: str, value: str, delta: str | None = None) -> None:
    """A single metric value rendered as text + optional delta (no card border)."""
    if delta:
        st.metric(label=label, value=value, delta=delta)
    else:
        st.metric(label=label, value=value)


def render_selection_cards(options, state_key, default_val, key_prefix):
    """Render horizontal visual option cards for customization settings."""
    current_val = st.session_state.get(state_key, default_val)
    if state_key not in st.session_state:
        st.session_state[state_key] = default_val
        current_val = default_val

    # Layout selection cards side-by-side
    cols = st.columns(len(options))
    for i, opt in enumerate(options):
        with cols[i]:
            is_selected = current_val == opt["key"]
            selected_class = "selected" if is_selected else ""
            
            # Format before/after block
            before_val = opt.get("before", "")
            after_val = opt.get("after", "")
            example_html = ""
            if before_val or after_val:
                example_html = (
                    f'<div class="selection-card-example">'
                    f'<span style="font-size:0.65rem; color:#64748B; font-weight:600; text-transform:uppercase; display:block; margin-bottom:4px;">Visual Example</span>'
                    f'<span class="ds-prev-before" style="font-size:0.75rem; padding:2px 6px;">{before_val}</span>'
                    f'<span class="ds-prev-arrow" style="font-size:0.75rem; padding:0 4px;">→</span>'
                    f'<span class="ds-prev-after" style="font-size:0.75rem; padding:2px 6px;">{after_val}</span>'
                    f'</div>'
                )

            card_html = (
                f'<div class="selection-card {selected_class}">'
                f'<div>'
                f'<div class="selection-card-title">{opt["label"]}</div>'
                f'<div style="font-size:0.75rem; color:#64748B; margin-top:6px; line-height:1.35;">{opt["desc"]}</div>'
                f'</div>'
                f'{example_html}'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)
            
            # Button underneath the card
            btn_label = "Selected" if is_selected else "Select option"
            btn_type = "primary" if is_selected else "secondary"
            if st.button(btn_label, key=f"{key_prefix}_sel_btn_{opt['key']}", use_container_width=True, type=btn_type):
                st.session_state[state_key] = opt["key"]
                st.rerun()


def render_configure_cleaning(df, diagnosis, key_prefix=""):
    """Render configuration tabs for missing data handling operations."""
    if not diagnosis:
        return

    all_cols = [d["column_name"] for d in diagnosis]
    p = key_prefix  # shorthand for prefix

    st.markdown("**Choose how missing values should be filled:**")

    options = [
        {"key": "smart", "label": "Smart Fill", "desc": "Uses statistical defaults tailored to each column's type.", "before": "NULL", "after": "34 or 'Unknown'"},
        {"key": "mean", "label": "Average Value", "desc": "Fills empty numeric cells with column average.", "before": "NULL", "after": "34.2"},
        {"key": "mode", "label": "Most Common", "desc": "Fills empty cells with the most common entry.", "before": "NULL", "after": "34"},
        {"key": "custom", "label": "Custom Value", "desc": "Fills empty cells with a custom placeholder.", "before": "NULL", "after": "Custom..."},
    ]

    render_selection_cards(options, f"{p}impute_strategy_card", "smart", p)

    # Show custom value input if 'custom' is selected
    strategy = st.session_state.get(f"{p}impute_strategy_card", "smart")
    if strategy == "custom":
        st.text_input("Custom placeholder value:", value="Unknown", key=f"{p}impute_default_val")

    st.markdown("---")
    st.markdown("**Additional Settings:**")
    c1, c2 = st.columns(2)
    with c1:
        st.checkbox("Drop completely empty rows (all values null)", value=True, key=f"{p}drop_rows")
    with c2:
        st.checkbox("Drop completely empty columns (all values null)", value=True, key=f"{p}drop_cols")
        
    st.multiselect(
        "Drop rows missing critical keys in columns:",
        all_cols,
        key=f"{p}critical_cols",
        help="Any row containing nulls or blanks in these columns will be removed."
    )


def render_configure_duplicates(df, diagnosis, key_prefix=""):
    """Render configuration for duplicate removal operations."""
    if not diagnosis:
        return

    all_cols = [d["column_name"] for d in diagnosis]
    p = key_prefix

    st.markdown("**Choose which duplicate record to keep:**")

    options = [
        {"key": "first", "label": "Keep First Copy", "desc": "Preserves the first duplicate instance found in the dataset.", "before": "Row 1 (copy A), Row 1 (copy B)", "after": "Row 1 (copy A)"},
        {"key": "last", "label": "Keep Last Copy", "desc": "Preserves the last duplicate instance found in the dataset.", "before": "Row 1 (copy A), Row 1 (copy B)", "after": "Row 1 (copy B)"},
        {"key": "all", "label": "Remove All", "desc": "Deletes all matching copies of duplicate rows entirely.", "before": "Row 1 (copy A), Row 1 (copy B)", "after": "(Empty)"},
    ]

    render_selection_cards(options, f"{p}dup_strategy_card", "first", p)

    st.markdown("---")
    st.markdown("**Matching Rules:**")
    st.checkbox("Remove exact matches (rows where every column is identical)", value=True, key=f"{p}dup_exact")
    st.multiselect(
        "Remove partial duplicates based on unique key columns:",
        all_cols,
        key=f"{p}dup_partial_cols",
        help="Rows sharing the same values in these columns will be considered duplicates."
    )


def render_configure_whitespace(df, diagnosis, key_prefix=""):
    """Render configuration for trimming whitespace."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    text_cols = [d["column_name"] for d in diagnosis if d["dtype_detected"] in ("text", "mixed")]
    p = key_prefix
    
    st.markdown("**Choose whitespace cleaning style:**")
    options = [
        {"key": "trim_all", "label": "Clean All Spaces", "desc": "Strip outer spaces and collapse double middle spaces.", "before": "'  John  Doe  '", "after": "'John Doe'"},
        {"key": "trim_ends", "label": "Trim Ends Only", "desc": "Strip leading & trailing spaces but keep inner spaces.", "before": "'  John  Doe  '", "after": "'John  Doe'"},
    ]
    render_selection_cards(options, f"{p}ws_strategy_card", "trim_all", p)
    
    st.markdown("---")
    st.multiselect(
        "Select columns to trim:",
        all_cols,
        default=text_cols,
        key=f"{p}trim_ws_cols",
    )


def render_configure_case(df, diagnosis, key_prefix=""):
    """Render configuration for text case normalization."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    text_cols = [d["column_name"] for d in diagnosis if d["dtype_detected"] in ("text", "mixed")]
    p = key_prefix
    
    st.markdown("**Choose case normalization style:**")
    options = [
        {"key": "title", "label": "Title Case", "desc": "Capitalize first letter of every word.", "before": "'new york'", "after": "'New York'"},
        {"key": "upper", "label": "UPPERCASE", "desc": "Convert all characters to capitals.", "before": "'New York'", "after": "'NEW YORK'"},
        {"key": "lower", "label": "lowercase", "desc": "Convert all characters to small letters.", "before": "'New York'", "after": "'new york'"},
    ]
    render_selection_cards(options, f"{p}case_strategy_card", "title", p)
    
    st.markdown("---")
    st.multiselect(
        "Select columns to normalize casing:",
        all_cols,
        default=text_cols,
        key=f"{p}case_norm_cols",
    )


def render_configure_special_chars(df, diagnosis, key_prefix=""):
    """Render configuration for removing special characters."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    p = key_prefix
    
    st.markdown("**Choose what to remove:**")
    options = [
        {"key": "punctuation", "label": "Punctuation & Symbols", "desc": "Remove symbols like $, !, @, #, etc.", "before": "'John! Doe#'", "after": "'John Doe'"},
        {"key": "alphanumeric", "label": "Letters & Numbers Only", "desc": "Remove all non-alphanumeric characters.", "before": "'John-Doe_123!'", "after": "'JohnDoe123'"},
        {"key": "emojis", "label": "Emojis Only", "desc": "Strip emoji characters but keep standard punctuation.", "before": "'John Doe 😊'", "after": "'John Doe'"},
    ]
    render_selection_cards(options, f"{p}special_strategy_card", "punctuation", p)
    
    st.markdown("---")
    st.multiselect(
        "Select columns to clean special characters:",
        all_cols,
        key=f"{p}special_char_cols",
    )


def render_configure_dates(df, diagnosis, key_prefix=""):
    """Render configuration for date standardization."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    date_cols = [d["column_name"] for d in diagnosis if d["dtype_detected"] in ("date", "mixed")]
    p = key_prefix
    
    st.markdown("**Choose target date format:**")
    options = [
        {"key": "iso", "label": "ISO Standard", "desc": "Format dates as YYYY-MM-DD.", "before": "'23/06/2026'", "after": "'2026-06-23'"},
        {"key": "us", "label": "US Format", "desc": "Format dates as MM/DD/YYYY.", "before": "'2026-06-23'", "after": "'06/23/2026'"},
        {"key": "eur", "label": "European Format", "desc": "Format dates as DD/MM/YYYY.", "before": "'2026-06-23'", "after": "'23/06/2026'"},
        {"key": "slash", "label": "Slash Separated", "desc": "Format dates as YYYY/MM/DD.", "before": "'2026-06-23'", "after": "'2026/06/23'"},
    ]
    render_selection_cards(options, f"{p}date_strategy_card", "iso", p)
    
    st.markdown("---")
    st.multiselect(
        "Select columns for Date Standardization:",
        all_cols,
        default=date_cols,
        key=f"{p}standardize_dates_cols",
    )


def render_configure_numeric(df, diagnosis, key_prefix=""):
    """Render configuration for numeric conversion."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    numeric_cols = [d["column_name"] for d in diagnosis if d["dtype_detected"] in ("number", "mixed")]
    p = key_prefix
    
    st.markdown("**Choose numeric conversion style:**")
    options = [
        {"key": "standard", "label": "Standard Decimal", "desc": "Strip symbols and convert values to decimal numbers.", "before": "'$1,234.50'", "after": "1234.5"},
        {"key": "integer", "label": "Integer Casting", "desc": "Strip symbols and round to whole numbers.", "before": "'$1,234.50'", "after": "1234"},
    ]
    render_selection_cards(options, f"{p}numeric_strategy_card", "standard", p)
    
    st.markdown("---")
    st.multiselect(
        "Select columns for Numeric Conversion:",
        all_cols,
        default=numeric_cols,
        key=f"{p}convert_numeric_cols",
    )


def render_configure_outliers(df, diagnosis, key_prefix=""):
    """Render configuration for outliers."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    numeric_cols = [d["column_name"] for d in diagnosis if d["dtype_detected"] in ("number", "mixed")]
    p = key_prefix
    
    st.markdown("**Choose how to handle statistical outliers:**")
    options = [
        {"key": "cap", "label": "Cap to Boundaries", "desc": "Replace extreme values with boundary limits.", "before": "150 (Limit 100)", "after": "100"},
        {"key": "null", "label": "Set to Null", "desc": "Clear extreme values to empty cells.", "before": "150", "after": "NaN"},
        {"key": "drop", "label": "Drop Rows", "desc": "Delete rows containing outliers entirely.", "before": "Row with outlier", "after": "(Row removed)"},
    ]
    render_selection_cards(options, f"{p}outlier_strategy_card", "cap", p)
    
    st.markdown("---")
    st.markdown("**Outlier Rules:**")
    st.selectbox(
        "Detection Method:",
        ["IQR", "Z-score"],
        key=f"{p}outlier_method",
        help="IQR uses Q1/Q3 boundaries. Z-score uses standard deviation distance from the mean."
    )
    # Adjust default threshold based on selected method
    default_thresh = 1.5 if st.session_state.get(f"{p}outlier_method", "IQR") == "IQR" else 3.0
    st.number_input(
        "Threshold (Multiplier):",
        min_value=0.1,
        max_value=10.0,
        value=default_thresh,
        step=0.1,
        key=f"{p}outlier_threshold",
    )
    st.multiselect(
        "Select columns to check for outliers:",
        numeric_cols,
        key=f"{p}outlier_cols_list",
    )


def render_configure_blank_strings(df, diagnosis, key_prefix=""):
    """Render configuration for cleaning blank strings."""
    if not diagnosis:
        return
    p = key_prefix
    st.markdown("**Choose strategy for blank strings:**")
    options = [
        {"key": "treat_missing", "label": "Treat as Missing", "desc": "Convert blank and whitespace-only strings to empty cells (NaN).", "before": "'   '", "after": "NaN"},
        {"key": "keep_blank", "label": "Keep as Blank", "desc": "Preserve whitespace strings as-is without casting to null.", "before": "'   '", "after": "''"},
    ]
    render_selection_cards(options, f"{p}blank_strategy_card", "treat_missing", p)


def render_configure_empty_rows(df, diagnosis, key_prefix=""):
    """Render configuration for empty rows."""
    p = key_prefix
    st.markdown("**Choose action for empty rows:**")
    options = [
        {"key": "drop", "label": "Drop Rows", "desc": "Remove rows that are completely empty.", "before": "Empty Row", "after": "(Removed)"},
        {"key": "keep", "label": "Keep Rows", "desc": "Keep completely empty rows in the dataset.", "before": "Empty Row", "after": "Empty Row"},
    ]
    render_selection_cards(options, f"{p}empty_rows_strategy_card", "drop", p)


def render_configure_empty_cols(df, diagnosis, key_prefix=""):
    """Render configuration for empty columns."""
    p = key_prefix
    st.markdown("**Choose action for empty columns:**")
    options = [
        {"key": "drop", "label": "Drop Columns", "desc": "Remove columns that are completely empty.", "before": "Empty Column", "after": "(Removed)"},
        {"key": "keep", "label": "Keep Columns", "desc": "Keep completely empty columns in the dataset.", "before": "Empty Column", "after": "Empty Column"},
    ]
    render_selection_cards(options, f"{p}empty_cols_strategy_card", "drop", p)


def render_configure_business_rules(df, diagnosis, key_prefix=""):
    """Render configuration for business rules range validation."""
    if not diagnosis:
        return
    all_cols = [d["column_name"] for d in diagnosis]
    p = key_prefix
    st.markdown("**Choose action for range violations:**")
    options = [
        {"key": "null", "label": "Set to Null", "desc": "Set out-of-range values to empty cells.", "before": "Age: -5", "after": "Age: NaN"},
        {"key": "drop", "label": "Drop Rows", "desc": "Remove rows containing violating values.", "before": "Age: -5", "after": "(Row removed)"},
    ]
    render_selection_cards(options, f"{p}business_strategy_card", "null", p)
    
    st.markdown("---")
    st.text_area(
        "Range validation rules (one per line, format: `Column Operator Value -> Action`):",
        value="Age < 0 -> drop\nScore > 100 -> cap\nPrice <= 0 -> null",
        height=120,
        key=f"{p}range_rules_text",
    )


def render_configure_categories(df, diagnosis, key_prefix=""):
    """Render configuration for standardizing categories."""
    p = key_prefix
    st.markdown("**Choose categorization strategy:**")
    options = [
        {"key": "merge", "label": "Merge Similar", "desc": "Merge spelling variations and small category typos.", "before": "'Apple' / 'Appel'", "after": "'Apple'"},
        {"key": "keep", "label": "Keep Original", "desc": "Keep spelling as entered without merging.", "before": "'Apple' / 'Appel'", "after": "'Apple' / 'Appel'"},
    ]
    render_selection_cards(options, f"{p}categories_strategy_card", "merge", p)


# ─────────────────────────────────────────────────────────────────────────────
# File summary & diagnosis table

# ─────────────────────────────────────────────────────────────────────────────
def format_file_size(size_kb: float) -> str:
    """Format file size for summary display."""
    return f"{size_kb / 1024.0:.1f} MB" if size_kb > 1024.0 else f"{size_kb:.1f} KB"


def render_file_summary(file_meta: dict):
    """Render the Executive Summary Cards, Health Score Gauge, and Dataset Overview."""
    df = file_meta.get("df")
    if df is None:
        return

    # Trigger or retrieve the cached profiler results
    filename = file_meta.get("filename", "Unknown")
    if "profiler_result" not in st.session_state or st.session_state.get("last_loaded_name") != filename:
        from core.profiler import Profiler
        profiler = Profiler()
        st.session_state["profiler_result"] = profiler.profile(df)
        st.session_state["last_loaded_name"] = filename

    res = st.session_state["profiler_result"]
    metrics = res.metrics
    quality_score = res.health_score

    # Layout: Overview metrics on the left, Data Quality Score on the right
    col_left, col_right = st.columns([2, 1])

    with col_left:
        render_section("📊 Dataset Overview", "")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(label="🔢 Rows", value=f"{metrics['rows']:,}")
        m_col2.metric(label="📊 Columns", value=f"{metrics['columns']:,}")
        m_col3.metric(label="💾 File Size", value=format_file_size(file_meta.get("file_size_kb", 0.0)))

        m_col4, m_col5, m_col6 = st.columns(3)
        m_col4.metric(label="🔴 Critical Issues", value=f"{metrics['critical_count']:,}")
        m_col5.metric(label="🟡 Warnings", value=f"{metrics['warning_count']:,}")
        m_col6.metric(label="🔵 Info Items", value=f"{metrics['info_count']:,}")

    with col_right:
        render_section("🎯 Health Score", "")
        if quality_score >= 90:
            status_color = "#10B981" # Green
            status_text = "Excellent Health"
            status_desc = "Your dataset looks clean and ready for production pipelines."
        elif quality_score >= 70:
            status_color = "#F59E0B" # Amber
            status_text = "Good Health"
            status_desc = "Minor issues detected. We recommend running cleaning operations."
        else:
            status_color = "#EF4444" # Red
            status_text = "Needs Cleaning"
            status_desc = "Significant data quality issues found. Review the configurations."

        st.markdown(
            f"""
            <div class="ds-health-card">
                <div style="font-weight:700; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.05em; color:#64748B; margin-bottom: 4px;">Health Score</div>
                <div class="ds-health-ring-wrap">
                    <div class="ds-health-ring" style="background: conic-gradient({status_color} {quality_score}%, #E2E8F0 0);" data-score="{quality_score}%"></div>
                </div>
                <div style="font-weight:700; font-size:1.1rem; color:{status_color}; margin-bottom:4px;">{status_text}</div>
                <div style="font-size:0.8rem; color:#64748B; line-height:1.4; padding:0 8px;">{status_desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_diagnosis_table(diagnosis: list):
    """Display the column-health diagnosis table, issue explorer accordions, and recommended actions."""
    if "profiler_result" not in st.session_state:
        st.warning("No profiling results found. Please upload a dataset first.")
        return

    res = st.session_state["profiler_result"]
    metrics = res.metrics
    issues = res.issues
    total_issues = metrics["total_issues"]

    # 1. Severity Distribution Progress Bar
    if total_issues > 0:
        crit_pct = (metrics["critical_count"] / total_issues) * 100
        warn_pct = (metrics["warning_count"] / total_issues) * 100
        info_pct = (metrics["info_count"] / total_issues) * 100

        st.markdown(
            f"""
            <div style="margin-bottom: 24px; background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: #64748B; margin-bottom: 8px; letter-spacing:0.05em;">Issue Severity Distribution</div>
                <div style="display: flex; height: 10px; border-radius: 999px; overflow: hidden; background: #E2E8F0;">
                    <div style="width: {crit_pct}%; background: #EF4444;" title="Critical: {metrics['critical_count']}"></div>
                    <div style="width: {warn_pct}%; background: #F59E0B;" title="Warning: {metrics['warning_count']}"></div>
                    <div style="width: {info_pct}%; background: #3B82F6;" title="Info: {metrics['info_count']}"></div>
                </div>
                <div style="display: flex; gap: 16px; margin-top: 8px; font-size: 0.8rem; color: #64748B;">
                    <div><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#EF4444; margin-right:4px;"></span>Critical: {metrics['critical_count']}</div>
                    <div><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#F59E0B; margin-right:4px;"></span>Warning: {metrics['warning_count']}</div>
                    <div><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#3B82F6; margin-right:4px;"></span>Info: {metrics['info_count']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Legacy Column Health Matrix Table
    render_section("Column health diagnosis matrix", "🔍")

    rows_html = []
    status_styles = {
        "clean":     ("✅ Clean",     "#059669", "#ECFDF5", "#A7F3D0"),
        "attention": ("⚠️ Attention", "#D97706", "#FFFBEB", "#FDE68A"),
        "critical":  ("🔴 Critical",  "#DC2626", "#FEF2F2", "#FECACA"),
    }

    for col_diag in diagnosis:
        total_rows = col_diag.get("total_rows", 0)
        duplicate_values = col_diag.get("duplicate_values", 0)
        pct = round((duplicate_values / total_rows) * 100, 1) if total_rows > 0 else 0.0
        status = col_diag["status"]
        label, text_color, bg_color, border_color = status_styles.get(
            status, (status, "#64748B", "#F1F5F9", "#E2E8F0")
        )
        badge_html = (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'font-size:0.72rem;font-weight:600;padding:3px 9px;border-radius:999px;'
            f'color:{text_color};background:{bg_color};border:1px solid {border_color};'
            f'white-space:nowrap;">{label}</span>'
        )
        rows_html.append(
            f"<tr>"
            f"<td>{col_diag['column_name']}</td>"
            f"<td>{col_diag['dtype_detected']}</td>"
            f"<td>{col_diag['missing_pct']:.1f}%</td>"
            f"<td>{duplicate_values:,} ({pct}%)</td>"
            f"<td>{badge_html}</td>"
            f"</tr>"
        )

    table_html = """
<style>
.ds-diag-table { width:100%; border-collapse:collapse; font-size:0.875rem; }
.ds-diag-table th {
    background:#F8FAFC; color:#64748B; font-weight:600; font-size:0.72rem;
    text-transform:uppercase; letter-spacing:0.05em;
    padding:10px 14px; text-align:left;
    border-bottom:2px solid #E2E8F0;
}
.ds-diag-table td {
    padding:10px 14px; border-bottom:1px solid #F1F5F9;
    color:#334155; vertical-align:middle;
}
.ds-diag-table tr:hover td { background:#F8FAFC; }
.ds-diag-table-wrap {
    border:1px solid #E2E8F0; border-radius:12px; overflow:hidden;
    margin-bottom:24px;
}
</style>
<div class="ds-diag-table-wrap">
<table class="ds-diag-table">
<thead><tr>
  <th>Column</th><th>Type</th><th>Missing %</th><th>Duplicates</th><th>Status</th>
</tr></thead>
<tbody>""" + "".join(rows_html) + """</tbody>
</table>
</div>"""

    st.markdown(table_html, unsafe_allow_html=True)

    # 3. Issue Explorer (accordions prioritizing Critical first)
    render_section("Issue Explorer", "🚨")

    from core.profiler import Severity

    # Group issues by severity
    critical_issues = [i for i in issues if i.severity == Severity.CRITICAL]
    warning_issues = [i for i in issues if i.severity == Severity.WARNING]
    info_issues = [i for i in issues if i.severity == Severity.INFO]

    # Critical Expanders
    with st.expander(f"🔴 Critical Issues ({len(critical_issues)})", expanded=len(critical_issues) > 0):
        if critical_issues:
            for issue in critical_issues:
                col_info = f" · Column <code>{issue.column}</code>" if issue.column else ""
                st.markdown(
                    f"""
                    <div class="ds-issue-card" style="border-left: 4px solid #EF4444 !important;">
                        <div class="issue-icon">🔴</div>
                        <div class="issue-content">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <h5 style="margin:0; font-size:0.95rem;">{issue.name}{col_info}</h5>
                                <span style="font-size:0.75rem; color:#94A3B8; cursor:help;" title="{issue.tooltip}">❓ What is this?</span>
                            </div>
                            <p style="margin: 6px 0 !important; font-size:0.82rem; color:#64748B;">{issue.description}</p>
                            <div style="display:flex; gap:16px; margin-top:6px; font-size:0.78rem; color:#64748B; flex-wrap:wrap;">
                                <div><strong>Affected:</strong> {issue.affected_count:,} items ({issue.affected_pct}%)</div>
                                {f"<div><strong>Examples:</strong> <code>{', '.join(map(str, issue.examples))}</code></div>" if issue.examples else ""}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No critical issues found.")

    # Warning Expanders
    with st.expander(f"🟡 Warnings ({len(warning_issues)})", expanded=len(critical_issues) == 0 and len(warning_issues) > 0):
        if warning_issues:
            for issue in warning_issues:
                col_info = f" · Column <code>{issue.column}</code>" if issue.column else ""
                st.markdown(
                    f"""
                    <div class="ds-issue-card" style="border-left: 4px solid #F59E0B !important;">
                        <div class="issue-icon">⚠️</div>
                        <div class="issue-content">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <h5 style="margin:0; font-size:0.95rem;">{issue.name}{col_info}</h5>
                                <span style="font-size:0.75rem; color:#94A3B8; cursor:help;" title="{issue.tooltip}">❓ What is this?</span>
                            </div>
                            <p style="margin: 6px 0 !important; font-size:0.82rem; color:#64748B;">{issue.description}</p>
                            <div style="display:flex; gap:16px; margin-top:6px; font-size:0.78rem; color:#64748B; flex-wrap:wrap;">
                                <div><strong>Affected:</strong> {issue.affected_count:,} items ({issue.affected_pct}%)</div>
                                {f"<div><strong>Examples:</strong> <code>{', '.join(map(str, issue.examples))}</code></div>" if issue.examples else ""}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No warnings found.")

    # Info Expanders
    with st.expander(f"🔵 Info Items ({len(info_issues)})", expanded=False):
        if info_issues:
            for issue in info_issues:
                col_info = f" · Column <code>{issue.column}</code>" if issue.column else ""
                st.markdown(
                    f"""
                    <div class="ds-issue-card" style="border-left: 4px solid #3B82F6 !important;">
                        <div class="issue-icon">ℹ️</div>
                        <div class="issue-content">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <h5 style="margin:0; font-size:0.95rem;">{issue.name}{col_info}</h5>
                                <span style="font-size:0.75rem; color:#94A3B8; cursor:help;" title="{issue.tooltip}">❓ What is this?</span>
                            </div>
                            <p style="margin: 6px 0 !important; font-size:0.82rem; color:#64748B;">{issue.description}</p>
                            <div style="display:flex; gap:16px; margin-top:6px; font-size:0.78rem; color:#64748B; flex-wrap:wrap;">
                                <div><strong>Affected:</strong> {issue.affected_count:,} items ({issue.affected_pct}%)</div>
                                {f"<div><strong>Examples:</strong> <code>{', '.join(map(str, issue.examples))}</code></div>" if issue.examples else ""}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No info findings found.")

    # 4. Recommendations Checklist
    st.markdown('<p class="ds-section" style="margin-top:24px;">💡 Recommended Actions</p>', unsafe_allow_html=True)
    rec_html = []
    
    # Compile smart recommendations
    for issue in issues:
        if issue.id == "duplicate_rows":
            rec_html.append(f"<li><strong>👯 Deduplication:</strong> Remove {issue.affected_count:,} exact duplicate records.</li>")
        elif issue.id == "missing_values":
            rec_html.append(f"<li><strong>🩹 Impute Nulls:</strong> Fill {issue.affected_count:,} blank cells in column <code>{issue.column}</code>.</li>")
        elif issue.id == "whitespace_ends":
            rec_html.append(f"<li><strong>🧼 Trim Spaces:</strong> Remove boundary spaces on column <code>{issue.column}</code>.</li>")
        elif issue.id == "outliers":
            rec_html.append(f"<li><strong>🚨 Outliers:</strong> Cap extreme values in column <code>{issue.column}</code> using IQR thresholds.</li>")
        elif issue.id == "case_inconsistent":
            rec_html.append(f"<li><strong>🔤 Casing:</strong> Align mixed case values in column <code>{issue.column}</code>.</li>")
        elif issue.id == "mixed_types":
            rec_html.append(f"<li><strong>🧬 Mixed Types:</strong> Clean inconsistent value structures in column <code>{issue.column}</code>.</li>")

    if rec_html:
        st.markdown(
            f"""
            <div style="background:#F5F3FF; border:1px solid #DDD6FE; border-radius:16px; padding:20px; color:#5B21B6; margin-bottom:12px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-weight:700; margin-bottom:12px; font-size:0.98rem; text-transform:uppercase; letter-spacing:0.04em;">Audit Recommendations Checklist</div>
                <ul style="margin:0; padding-left:22px; font-size:0.85rem; line-height:1.65; color:#4C1D95;">
                    {"".join(rec_html[:6])}
                </ul>
                <div style="margin-top:14px; font-size:0.78rem; opacity:0.85; border-top:1px solid #EDE9FE; padding-top:10px;">
                    These actions are fully configurable in Step 3 (Clean) and will restore health indicators to 100%.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.success("All columns are fully clean. No recommended cleaning actions required!")


# ─────────────────────────────────────────────────────────────────────────────
# Review & Apply Fixes — Issue-Based Guided Cleaning Workflow
# ─────────────────────────────────────────────────────────────────────────────

_WHY_RECOMMENDED = {
    "fix_missing_values": "Recommended because it preserves data distribution and minimizes distortion without introducing bias.",
    "fix_blank_strings": "Recommended because empty space cells behave like data but contain no information, which skews counts.",
    "fix_duplicates": "Recommended because identical duplicate records double-count events and distort all statistical metrics.",
    "fix_near_duplicates": "Recommended because minor differences (like typos in keys) require human review to merge safely.",
    "fix_whitespace": "Recommended because invisible spaces cause lookup errors and split identical text groups (e.g. 'USA' vs ' USA').",
    "fix_case": "Recommended because capitalization differences create duplicate categories in charts, pivot tables, and filters.",
    "fix_special_chars": "Recommended because hidden control characters and corrupted symbols can break CSV exports or database insertions.",
    "fix_dates": "Recommended because a consistent, parseable date format is required for timeline sorting and trend calculations.",
    "fix_numeric": "Recommended because columns containing currency symbols or commas are treated as text, preventing mathematical calculations.",
    "fix_outliers": "Recommended because extreme outlier anomalies heavily distort averages, while capping them retains the records.",
    "fix_empty_rows": "Recommended because completely blank rows add noise to the dataset and slow down database queries.",
    "fix_empty_cols": "Recommended because empty columns clutter your dataset and provide zero useful information.",
    "fix_business_rules": "Recommended because negative or impossible values violate business logic and corrupt analytical reports.",
    "fix_mixed_types": "Recommended because columns with mixed types prevent database indexing and proper mathematical type casting.",
    "fix_categories": "Recommended because small spelling variations (e.g., 'Apple' vs. 'Appel') create duplicate categories in analysis.",
    "fix_uniqueness": "Recommended because ID or key columns must be completely unique to maintain primary key database integrity.",
}


def generate_fix_recommendations(df, profiler_result, diagnosis):
    """Map profiler issues to actionable fix recommendations.

    Groups detected issues by type and creates one fix recommendation per
    issue category, complete with affected columns, confidence level,
    and the cleaning operations needed.
    """
    from core.profiler import Severity

    issues = profiler_result.issues if profiler_result else []
    recs = []

    # Group issues by their id
    issue_groups = {}
    for issue in issues:
        issue_groups.setdefault(issue.id, []).append(issue)

    # ── Missing Values ──
    if "missing_values" in issue_groups:
        grp = issue_groups["missing_values"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        sev = "critical" if any(i.severity == Severity.CRITICAL for i in grp) else "warning"
        recs.append({
            "id": "fix_missing_values", "title": "Fill Missing Values", "icon": "🩹",
            "severity": sev,
            "description": f"Found {total:,} empty cells across {len(cols)} column(s). We'll fill them with intelligent defaults based on each column's data type.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Fill missing values with statistical defaults (mean/median for numbers, 'Unknown' for text)",
            "confidence": "High", "category": "Missing Data",
            "estimated_improvement": min(15, total * 100 // max(profiler_result.metrics.get("total_cells", 1), 1)),
            "preview_type": "missing",
        })

    # ── Blank Strings ──
    if "blank_strings" in issue_groups:
        grp = issue_groups["blank_strings"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_blank_strings", "title": "Clean Blank Strings", "icon": "🧹",
            "severity": "warning",
            "description": f"Found {total:,} blank or whitespace-only cells in {len(cols)} column(s). These will be treated as missing values.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Trim whitespace and treat blank strings as missing values",
            "confidence": "High", "category": "Text Quality",
            "estimated_improvement": 3, "preview_type": "blank",
        })

    # ── Duplicate Records ──
    if "duplicate_rows" in issue_groups:
        grp = issue_groups["duplicate_rows"]
        total = sum(i.affected_count for i in grp)
        sev = "critical" if any(i.severity == Severity.CRITICAL for i in grp) else "warning"
        recs.append({
            "id": "fix_duplicates", "title": "Remove Duplicate Records", "icon": "👯",
            "severity": sev,
            "description": f"Found {total:,} exact duplicate rows. Removing duplicates ensures each record is unique.",
            "affected_columns": ["All columns"], "affected_count": total,
            "recommended_action": "Remove exact duplicate rows, keeping the first occurrence",
            "confidence": "High", "category": "Duplicates",
            "estimated_improvement": min(10, total * 100 // max(len(df), 1)),
            "preview_type": "duplicates",
        })

    # ── Near Duplicates ──
    if "near_duplicates" in issue_groups:
        grp = issue_groups["near_duplicates"]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_near_duplicates", "title": "Review Near Duplicates", "icon": "🔍",
            "severity": "warning",
            "description": f"Found {total:,} records that are almost identical (differ by only one column). Manual review recommended.",
            "affected_columns": [], "affected_count": total,
            "recommended_action": "Review and manually decide which near-duplicate records to keep",
            "confidence": "Low", "category": "Duplicates",
            "estimated_improvement": 2, "preview_type": None,
        })

    # ── Whitespace Issues (merged) ──
    ws_ids = [i for i in ["whitespace_ends", "whitespace_multiple"] if i in issue_groups]
    if ws_ids:
        all_ws = []
        for wid in ws_ids:
            all_ws.extend(issue_groups[wid])
        cols = list(set(i.column for i in all_ws if i.column))
        total = sum(i.affected_count for i in all_ws)
        recs.append({
            "id": "fix_whitespace", "title": "Trim Whitespace", "icon": "✂️",
            "severity": "warning",
            "description": f"Found {total:,} values with leading, trailing, or extra spaces across {len(cols)} column(s).",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Remove leading/trailing spaces and collapse multiple spaces",
            "confidence": "High", "category": "Text Quality",
            "estimated_improvement": 3, "preview_type": "whitespace",
        })

    # ── Case Inconsistencies ──
    if "case_inconsistent" in issue_groups:
        grp = issue_groups["case_inconsistent"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_case", "title": "Normalize Text Case", "icon": "🔤",
            "severity": "warning",
            "description": f"Found {total:,} case variations in {len(cols)} column(s). Values like 'usa', 'USA', 'Usa' will be unified.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Convert text to Title Case for consistency",
            "confidence": "High", "category": "Text Quality",
            "estimated_improvement": 3, "preview_type": "case",
        })

    # ── Special Characters ──
    if "special_characters" in issue_groups:
        grp = issue_groups["special_characters"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_special_chars", "title": "Remove Special Characters", "icon": "🚫",
            "severity": "warning",
            "description": f"Found {total:,} values with corrupted or control characters in {len(cols)} column(s).",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Remove control codes and corrupted characters",
            "confidence": "Medium", "category": "Text Quality",
            "estimated_improvement": 2, "preview_type": None,
        })

    # ── Invalid Dates ──
    if "invalid_dates" in issue_groups:
        grp = issue_groups["invalid_dates"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_dates", "title": "Standardize Dates", "icon": "📅",
            "severity": "warning",
            "description": f"Found {total:,} invalid or inconsistently formatted dates in {len(cols)} column(s).",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Parse dates to ISO format (YYYY-MM-DD), set unparseable values to blank",
            "confidence": "Medium", "category": "Data Types",
            "estimated_improvement": 3, "preview_type": None,
        })

    # ── Numeric Conversion Failures ──
    if "numeric_failures" in issue_groups:
        grp = issue_groups["numeric_failures"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_numeric", "title": "Convert to Numbers", "icon": "🔢",
            "severity": "warning",
            "description": f"Found {total:,} non-numeric values in {len(cols)} column(s) that should be numbers.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Strip currency symbols and commas, convert to numeric values",
            "confidence": "High", "category": "Data Types",
            "estimated_improvement": 3, "preview_type": None,
        })

    # ── Outliers ──
    if "outliers" in issue_groups:
        grp = issue_groups["outliers"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_outliers", "title": "Handle Statistical Outliers", "icon": "📊",
            "severity": "warning",
            "description": f"Found {total:,} outlier values in {len(cols)} column(s) using IQR method.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Cap extreme values to IQR boundaries (Q1 - 1.5×IQR to Q3 + 1.5×IQR)",
            "confidence": "Medium", "category": "Data Quality",
            "estimated_improvement": 2, "preview_type": None,
        })

    # ── Empty Rows ──
    if "empty_rows" in issue_groups:
        grp = issue_groups["empty_rows"]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_empty_rows", "title": "Remove Empty Rows", "icon": "🗑️",
            "severity": "critical",
            "description": f"Found {total:,} completely empty rows. These contain no data and should be removed.",
            "affected_columns": ["All columns"], "affected_count": total,
            "recommended_action": "Drop rows where every cell is empty",
            "confidence": "High", "category": "Structure",
            "estimated_improvement": 5, "preview_type": None,
        })

    # ── Empty Columns ──
    if "empty_columns" in issue_groups:
        grp = issue_groups["empty_columns"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        col_str = ', '.join(cols[:3]) + ('...' if len(cols) > 3 else '')
        recs.append({
            "id": "fix_empty_cols", "title": "Remove Empty Columns", "icon": "🗑️",
            "severity": "critical",
            "description": f"Found {len(cols)} empty column(s) ({col_str}). These contain no data.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Drop columns where every cell is empty",
            "confidence": "High", "category": "Structure",
            "estimated_improvement": 5, "preview_type": None,
        })

    # ── Business Rule Violations ──
    if "business_rules" in issue_groups:
        grp = issue_groups["business_rules"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_business_rules", "title": "Fix Range Violations", "icon": "⚠️",
            "severity": "warning",
            "description": f"Found {total:,} values violating logical ranges (e.g., negative age) in {len(cols)} column(s).",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Set out-of-range values to null for manual review",
            "confidence": "Medium", "category": "Data Quality",
            "estimated_improvement": 2, "preview_type": None,
        })

    # ── Mixed Types ──
    if "mixed_types" in issue_groups:
        grp = issue_groups["mixed_types"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_mixed_types", "title": "Resolve Mixed Data Types", "icon": "🧬",
            "severity": "critical",
            "description": f"Found {len(cols)} column(s) with mixed data types. These columns contain values of different types.",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Review columns manually — mixed types may indicate data entry errors",
            "confidence": "Low", "category": "Data Quality",
            "estimated_improvement": 1, "preview_type": None,
        })

    # ── Category Inconsistencies ──
    if "category_inconsistent" in issue_groups:
        grp = issue_groups["category_inconsistent"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        recs.append({
            "id": "fix_categories", "title": "Standardize Categories", "icon": "🏷️",
            "severity": "warning",
            "description": f"Found {total:,} potential typos in category names in {len(cols)} column(s).",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Review similar category values for potential typos",
            "confidence": "Low", "category": "Text Quality",
            "estimated_improvement": 2, "preview_type": None,
        })

    # ── Uniqueness Violations ──
    if "uniqueness_violations" in issue_groups:
        grp = issue_groups["uniqueness_violations"]
        cols = [i.column for i in grp if i.column]
        total = sum(i.affected_count for i in grp)
        col_str = ', '.join(cols[:3]) + ('...' if len(cols) > 3 else '')
        recs.append({
            "id": "fix_uniqueness", "title": "Fix Duplicate Keys", "icon": "🔑",
            "severity": "critical",
            "description": f"Found {total:,} duplicate values in ID/key columns ({col_str}).",
            "affected_columns": cols, "affected_count": total,
            "recommended_action": "Review duplicate key values — these may indicate data errors",
            "confidence": "Low", "category": "Data Quality",
            "estimated_improvement": 3, "preview_type": None,
        })

    # Sort: critical first, then by estimated improvement
    sev_order = {"critical": 0, "warning": 1, "info": 2}
    recs.sort(key=lambda r: (sev_order.get(r["severity"], 3), -r.get("estimated_improvement", 0)))

    # Inject why_recommended
    for r in recs:
        r["why_recommended"] = _WHY_RECOMMENDED.get(r["id"], "Recommended to resolve detected data inconsistencies.")

    return recs
def _get_fix_operations(rec, df):
    """Return a list of cleaning operation dicts for a given fix recommendation."""
    from core.cleaner import (
        drop_missing_structures, impute_default_values, impute_statistical,
        remove_duplicates_custom, trim_whitespace_custom, normalize_case_custom,
        remove_special_chars_custom, standardize_dates_custom, convert_numeric_custom,
        filter_statistical_outliers_custom,
    )
    cols = [c for c in rec.get("affected_columns", []) if c in df.columns]
    rid = rec["id"]
    _cols = list(cols)
    prefix = f"{rid}_"

    if rid == "fix_missing_values":
        strategy = st.session_state.get(f"{prefix}impute_strategy_card", "smart")
        ops = []
        _numeric_cols = [c for c in _cols if pd.api.types.is_numeric_dtype(df[c])]
        _text_cols = [c for c in _cols if c not in _numeric_cols]
        
        if strategy == "smart":
            if _numeric_cols:
                ops.append({"key": "impute_statistical", "name": "Statistical Fill (Mean)",
                            "func": lambda d, c=_numeric_cols: impute_statistical(d, c, "Mean")})
            if _text_cols:
                ops.append({"key": "impute_defaults", "name": "Default Values ('Unknown')",
                            "func": lambda d, c=_text_cols: impute_default_values(d, c, "Unknown")})
        elif strategy == "mean":
            if _numeric_cols:
                ops.append({"key": "impute_statistical", "name": "Statistical Fill (Mean)",
                            "func": lambda d, c=_numeric_cols: impute_statistical(d, c, "Mean")})
            if _text_cols:
                ops.append({"key": "impute_defaults", "name": "Default Values ('Unknown')",
                            "func": lambda d, c=_text_cols: impute_default_values(d, c, "Unknown")})
        elif strategy == "mode":
            if _numeric_cols:
                ops.append({"key": "impute_statistical", "name": "Statistical Fill (Mode)",
                            "func": lambda d, c=_numeric_cols: impute_statistical(d, c, "Mode")})
            if _text_cols:
                ops.append({"key": "impute_defaults", "name": "Default Values ('Unknown')",
                            "func": lambda d, c=_text_cols: impute_default_values(d, c, "Unknown")})
        elif strategy == "custom":
            val = st.session_state.get(f"{prefix}impute_default_val", "Unknown")
            ops.append({"key": "impute_defaults", "name": f"Default Values ('{val}')",
                        "func": lambda d, c=_cols: impute_default_values(d, c, val)})

        drop_rows = st.session_state.get(f"{prefix}drop_rows", True)
        drop_cols = st.session_state.get(f"{prefix}drop_cols", True)
        crit_cols = st.session_state.get(f"{prefix}critical_cols", [])
        if drop_rows or drop_cols or crit_cols:
            ops.append({"key": "drop_missing_structures", "name": "Drop Empty Structures",
                        "func": lambda d: drop_missing_structures(d, drop_rows, drop_cols, crit_cols)})
        return ops

    if rid == "fix_blank_strings":
        strategy = st.session_state.get(f"{prefix}blank_strategy_card", "treat_missing")
        if strategy == "treat_missing":
            return [{"key": "trim_whitespace", "name": "Clean Blanks",
                     "func": lambda d, c=_cols: trim_whitespace_custom(d, c)}]
        return []

    if rid == "fix_duplicates":
        strategy = st.session_state.get(f"{prefix}dup_strategy_card", "first")
        keep_map = {"first": "First occurrence", "last": "Last occurrence", "all": "Remove all"}
        keep_val = keep_map.get(strategy, "First occurrence")
        exact_match = st.session_state.get(f"{prefix}dup_exact", True)
        partial_cols = st.session_state.get(f"{prefix}dup_partial_cols", [])
        return [{"key": "remove_duplicates", "name": "Deduplication",
                 "func": lambda d: remove_duplicates_custom(d, exact_match, partial_cols, keep_val)}]

    if rid == "fix_whitespace":
        strategy = st.session_state.get(f"{prefix}ws_strategy_card", "trim_all")
        target_cols = st.session_state.get(f"{prefix}trim_ws_cols", _cols)
        if strategy == "trim_all":
            return [{"key": "trim_whitespace", "name": "Trim Whitespace",
                     "func": lambda d, c=target_cols: trim_whitespace_custom(d, c)}]
        else:
            def _trim_ends_func(d, c=target_cols):
                d_copy = d.copy()
                modified = 0
                for col in c:
                    if col in d_copy.columns:
                        mask = d_copy[col].notna()
                        original = d_copy.loc[mask, col].astype(str)
                        trimmed = original.str.strip()
                        modified += int((original != trimmed).sum())
                        d_copy.loc[mask, col] = trimmed
                return d_copy, {"cells_modified": modified}
            return [{"key": "trim_whitespace_ends", "name": "Trim Ends Only", "func": _trim_ends_func}]

    if rid == "fix_case":
        strategy = st.session_state.get(f"{prefix}case_strategy_card", "title")
        target_cols = st.session_state.get(f"{prefix}case_norm_cols", _cols)
        case_map = {"title": "Title Case", "upper": "UPPERCASE", "lower": "lowercase"}
        case_type = case_map.get(strategy, "Title Case")
        return [{"key": "normalize_case", "name": f"Normalize Case ({case_type})",
                 "func": lambda d, c=target_cols: normalize_case_custom(d, c, case_type)}]

    if rid == "fix_special_chars":
        strategy = st.session_state.get(f"{prefix}special_strategy_card", "punctuation")
        target_cols = st.session_state.get(f"{prefix}special_char_cols", _cols)
        char_map = {"punctuation": "Punctuation & symbols", "alphanumeric": "All non-alphanumeric", "emojis": "Emojis only"}
        remove_type = char_map.get(strategy, "Punctuation & symbols")
        return [{"key": "remove_special_chars", "name": f"Remove Special Chars ({remove_type})",
                 "func": lambda d, c=target_cols: remove_special_chars_custom(d, c, remove_type)}]

    if rid == "fix_dates":
        strategy = st.session_state.get(f"{prefix}date_strategy_card", "iso")
        target_cols = st.session_state.get(f"{prefix}standardize_dates_cols", _cols)
        format_map = {"iso": "%Y-%m-%d", "us": "%m/%d/%Y", "eur": "%d/%m/%Y", "slash": "%Y/%m/%d"}
        date_format = format_map.get(strategy, "%Y-%m-%d")
        return [{"key": "standardize_dates", "name": "Standardize Dates",
                 "func": lambda d, c=target_cols: standardize_dates_custom(d, c, date_format)}]

    if rid == "fix_numeric":
        strategy = st.session_state.get(f"{prefix}numeric_strategy_card", "standard")
        target_cols = st.session_state.get(f"{prefix}convert_numeric_cols", _cols)
        if strategy == "standard":
            return [{"key": "convert_numeric", "name": "Numeric Conversion (Decimal)",
                     "func": lambda d, c=target_cols: convert_numeric_custom(d, c)}]
        else:
            def _convert_numeric_int_func(d, c=target_cols):
                d_copy = d.copy()
                modified = 0
                for col in c:
                    if col in d_copy.columns:
                        d_copy, res = convert_numeric_custom(d_copy, [col])
                        mask = d_copy[col].notna()
                        rounded = pd.to_numeric(d_copy.loc[mask, col], errors="coerce").round()
                        d_copy.loc[mask, col] = rounded
                        modified += res.get("cells_modified", 0)
                return d_copy, {"cells_modified": modified}
            return [{"key": "convert_numeric_int", "name": "Numeric Conversion (Integer)",
                     "func": _convert_numeric_int_func}]

    if rid == "fix_outliers":
        strategy = st.session_state.get(f"{prefix}outlier_strategy_card", "cap")
        method = st.session_state.get(f"{prefix}outlier_method", "IQR")
        threshold = st.session_state.get(f"{prefix}outlier_threshold", 1.5)
        target_cols = st.session_state.get(f"{prefix}outlier_cols_list", _cols)
        return [{"key": "statistical_outliers", "name": f"Filter Outliers ({method})",
                 "func": lambda d, c=target_cols: filter_statistical_outliers_custom(d, c, method, threshold, strategy)}]

    if rid == "fix_empty_rows":
        strategy = st.session_state.get(f"{prefix}empty_rows_strategy_card", "drop")
        if strategy == "drop":
            return [{"key": "drop_empty_keys", "name": "Drop Empty Rows",
                     "func": lambda d: drop_missing_structures(d, True, False, [])}]
        return []

    if rid == "fix_empty_cols":
        strategy = st.session_state.get(f"{prefix}empty_cols_strategy_card", "drop")
        if strategy == "drop":
            return [{"key": "drop_empty_keys", "name": "Drop Empty Columns",
                     "func": lambda d: drop_missing_structures(d, False, True, [])}]
        return []

    if rid == "fix_business_rules":
        strategy = st.session_state.get(f"{prefix}business_strategy_card", "null")
        rules_text = st.session_state.get(f"{prefix}range_rules_text", "")
        def _business_rules_func(d):
            d_copy = d.copy()
            rows_removed = 0
            cells_nulled = 0
            cells_capped = 0
            for line in rules_text.strip().splitlines():
                if "->" not in line:
                    continue
                rule_part, action = line.split("->")
                rule_part = rule_part.strip()
                action = action.strip().lower()
                
                import re as _re
                m = _re.match(r"^([\w\s\-]+)\s+(<|>|<=|>=|==|!=)\s+(.+)$", rule_part)
                if not m:
                    continue
                col_name, op, val_str = m.groups()
                col_name = col_name.strip()
                if col_name not in d_copy.columns:
                    continue
                try:
                    val = float(val_str)
                except ValueError:
                    val = val_str.strip("'\"")
                
                series = d_copy[col_name]
                if op == "<": mask = series < val
                elif op == ">": mask = series > val
                elif op == "<=": mask = series <= val
                elif op == ">=": mask = series >= val
                elif op == "==": mask = series == val
                elif op == "!=": mask = series != val
                else: continue
                
                if action == "drop":
                    rows_removed += int(mask.sum())
                    d_copy = d_copy[~mask].reset_index(drop=True)
                elif action == "null":
                    cells_nulled += int(mask.sum())
                    d_copy.loc[mask, col_name] = np.nan
                elif action == "cap":
                    cells_capped += int(mask.sum())
                    d_copy.loc[mask, col_name] = val
                    
            return d_copy, {"rows_removed": rows_removed, "cells_nulled": cells_nulled, "cells_capped": cells_capped}
        return [{"key": "business_rules", "name": "Range Violations", "func": _business_rules_func}]

    return []


def render_fix_summary_section(recommendations, profiler_result):
    """Render the 4-card summary at the top of the Review & Apply page."""
    metrics = profiler_result.metrics
    total_issues = metrics.get("total_issues", 0)
    total_recs = len(recommendations)
    current_score = profiler_result.health_score
    n_critical = metrics.get("critical_count", 0)

    score_color = '#DC2626' if current_score < 70 else '#D97706' if current_score < 90 else '#059669'
    est_improvement = min(100 - current_score, sum(r.get("estimated_improvement", 5) for r in recommendations))

    st.markdown(
        f"""
        <div class="ds-fix-summary">
            <div class="ds-fix-summary-card">
                <div class="ds-fix-summary-value">{total_issues}</div>
                <div class="ds-fix-summary-label">Issues Found</div>
            </div>
            <div class="ds-fix-summary-card">
                <div class="ds-fix-summary-value">{total_recs}</div>
                <div class="ds-fix-summary-label">Recommended Fixes</div>
            </div>
            <div class="ds-fix-summary-card">
                <div class="ds-fix-summary-value" style="color:{score_color}">{current_score}%</div>
                <div class="ds-fix-summary-label">Current Score</div>
            </div>
            <div class="ds-fix-summary-card">
                <div class="ds-fix-summary-value" style="color:#059669">+{est_improvement}%</div>
                <div class="ds-fix-summary-label">Estimated After Fix</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_quality_journey_section(current_score, estimated_score):
    """Render the before → after quality score journey."""
    est_color = '#059669' if estimated_score >= 90 else '#D97706' if estimated_score >= 70 else '#DC2626'
    st.markdown(
        f"""
        <div class="ds-quality-journey">
            <div class="ds-qj-score ds-qj-score--before">
                <div class="ds-qj-value" style="color:#DC2626">{current_score}%</div>
                <div class="ds-qj-label" style="color:#991B1B">Current Quality</div>
            </div>
            <div class="ds-qj-arrow">→</div>
            <div class="ds-qj-score ds-qj-score--after">
                <div class="ds-qj-value" style="color:{est_color}">{estimated_score}%</div>
                <div class="ds-qj-label" style="color:#065F46">After Cleaning</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _generate_preview_html(rec, df):
    """Generate a small before/after preview table for a fix recommendation."""
    ptype = rec.get("preview_type")
    if not ptype:
        return None
    cols = [c for c in rec.get("affected_columns", []) if c in df.columns]
    if not cols:
        return None
    # Use first affected column for preview
    col = cols[0]
    sample = df[col].dropna().head(8)
    if len(sample) == 0:
        return None
    rows_html = ""
    if ptype == "missing":
        strategy = st.session_state.get("fix_missing_values_impute_strategy_card", "smart")
        mask = df[col].isna()
        missing_rows = df[mask].head(5)
        if len(missing_rows) == 0:
            return None
        for _, row in missing_rows.iterrows():
            val = str(row[col]) if pd.notna(row[col]) else "NaN"
            if strategy == "custom":
                fill = st.session_state.get("fix_missing_values_impute_default_val", "Unknown")
            elif strategy == "mode":
                fill = str(df[col].mode().iloc[0]) if not df[col].mode().empty else "Unknown"
            elif strategy == "mean":
                fill = str(round(df[col].mean(), 1)) if pd.api.types.is_numeric_dtype(df[col]) else "Unknown"
            else:
                fill = "Unknown" if df[col].dtype == object else str(round(df[col].mean(), 1)) if pd.api.types.is_numeric_dtype(df[col]) else "—"
            rows_html += f"<tr><td>{py_html.escape(val)}</td><td><span class='ds-prev-arrow'>→</span></td><td><span class='ds-prev-after'>{py_html.escape(fill)}</span></td></tr>"
    elif ptype == "whitespace":
        strategy = st.session_state.get("fix_whitespace_ws_strategy_card", "trim_all")
        str_vals = sample.astype(str)
        bad = str_vals[str_vals.str.strip() != str_vals].head(5)
        if len(bad) == 0:
            return None
        for val in bad:
            if strategy == "trim_all":
                import re as _re
                after_val = _re.sub(r"\s{2,}", " ", val.strip())
            else:
                after_val = val.strip()
            rows_html += f"<tr><td><span class='ds-prev-before'>{py_html.escape(val)}</span></td><td><span class='ds-prev-arrow'>→</span></td><td><span class='ds-prev-after'>{py_html.escape(after_val)}</span></td></tr>"
    elif ptype == "case":
        strategy = st.session_state.get("fix_case_case_strategy_card", "title")
        str_vals = sample.astype(str)
        for val in str_vals.head(5):
            if strategy == "upper":
                after_val = val.upper()
            elif strategy == "lower":
                after_val = val.lower()
            else:
                after_val = val.title()
            rows_html += f"<tr><td><span class='ds-prev-before'>{py_html.escape(val)}</span></td><td><span class='ds-prev-arrow'>→</span></td><td><span class='ds-prev-after'>{py_html.escape(after_val)}</span></td></tr>"
    elif ptype == "duplicates":
        strategy = st.session_state.get("fix_duplicates_dup_strategy_card", "first")
        dup_mask = df.duplicated(keep='first')
        dups = df[dup_mask].head(3)
        if len(dups) == 0:
            return None
        for _, row in dups.iterrows():
            first_vals = ' | '.join(str(row[c])[:20] for c in cols[:3])
            rows_html += f"<tr><td>{py_html.escape(first_vals)}</td><td><span class='ds-prev-arrow'>→</span></td><td><span class='ds-prev-after' style='text-decoration:line-through; opacity:0.6'>removed</span></td></tr>"
    elif ptype == "blank":
        blank_mask = df[col].dropna().astype(str).str.strip().eq("")
        blanks = df[col][blank_mask].head(5)
        if len(blanks) == 0:
            return None
        for val in blanks:
            rows_html += f"<tr><td><span class='ds-prev-before'>{py_html.escape(str(val))}</span></td><td><span class='ds-prev-arrow'>→</span></td><td><span class='ds-prev-after'>NaN (treated as missing)</span></td></tr>"
    else:
        return None

    if not rows_html:
        return None
    return (
        f'<div class="ds-preview-wrap">'
        f'<table class="ds-preview-table">'
        f'<thead><tr><th>Before</th><th></th><th>After</th></tr></thead>'
        f'<tbody>{rows_html}</tbody></table></div>'
    )


# Map fix recommendation IDs to their configuration renderers
_CONFIG_RENDERER_MAP = {
    "fix_missing_values": "cleaning",
    "fix_blank_strings": "blank_strings",
    "fix_duplicates": "duplicates",
    "fix_near_duplicates": "duplicates",
    "fix_whitespace": "whitespace",
    "fix_case": "case",
    "fix_special_chars": "special_chars",
    "fix_categories": "categories",
    "fix_dates": "dates",
    "fix_numeric": "numeric",
    "fix_empty_rows": "empty_rows",
    "fix_empty_cols": "empty_cols",
    "fix_outliers": "outliers",
    "fix_business_rules": "business_rules",
}

# Default summary labels shown before Advanced Settings expansion
_ADVANCED_SUMMARY = {
    "fix_missing_values": "Median Imputation · Custom Placeholders",
    "fix_blank_strings": "Trim Whitespace · Treat as Missing",
    "fix_duplicates": "Keep First Duplicate · Exact Match",
    "fix_near_duplicates": "Manual Review Required",
    "fix_whitespace": "Trim Whitespace · Collapse Multiples",
    "fix_case": "Title Case Normalization",
    "fix_special_chars": "Remove Punctuation & Symbols",
    "fix_categories": "Review Similar Values",
    "fix_dates": "ISO Format (YYYY-MM-DD)",
    "fix_numeric": "Strip Currency Symbols · Cast to Float",
    "fix_empty_rows": "Drop Empty Rows",
    "fix_empty_cols": "Drop Empty Columns",
    "fix_outliers": "IQR Method · Cap Boundaries",
    "fix_business_rules": "Set Out-of-Range to Null",
}


def reset_recommendation_settings(rid, df, diagnosis):
    """Reset customization settings to recommended defaults by clearing session state keys."""
    prefix = f"{rid}_"
    keys_to_clear = [
        f"{prefix}impute_strategy_card",
        f"{prefix}drop_rows",
        f"{prefix}drop_cols",
        f"{prefix}critical_cols",
        f"{prefix}impute_default_val",
        f"{prefix}dup_strategy_card",
        f"{prefix}dup_exact",
        f"{prefix}dup_partial_cols",
        f"{prefix}ws_strategy_card",
        f"{prefix}trim_ws_cols",
        f"{prefix}case_strategy_card",
        f"{prefix}case_norm_cols",
        f"{prefix}special_strategy_card",
        f"{prefix}special_char_cols",
        f"{prefix}blank_strategy_card",
        f"{prefix}date_strategy_card",
        f"{prefix}standardize_dates_cols",
        f"{prefix}numeric_strategy_card",
        f"{prefix}convert_numeric_cols",
        f"{prefix}outlier_strategy_card",
        f"{prefix}outlier_method",
        f"{prefix}outlier_threshold",
        f"{prefix}outlier_cols_list",
        f"{prefix}empty_rows_strategy_card",
        f"{prefix}empty_cols_strategy_card",
        f"{prefix}business_strategy_card",
        f"{prefix}range_rules_text",
        f"{prefix}categories_strategy_card"
    ]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]


def _render_config_controls(rid, df, diagnosis, key_prefix=""):
    """Render the appropriate configuration controls for a fix recommendation."""
    renderer_key = _CONFIG_RENDERER_MAP.get(rid)
    if not renderer_key:
        st.info("No configuration controls available for this recommendation.")
        return
    prefix = key_prefix or f"{rid}_"
    if renderer_key == "cleaning":
        render_configure_cleaning(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "blank_strings":
        render_configure_blank_strings(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "duplicates":
        render_configure_duplicates(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "whitespace":
        render_configure_whitespace(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "case":
        render_configure_case(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "special_chars":
        render_configure_special_chars(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "categories":
        render_configure_categories(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "dates":
        render_configure_dates(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "numeric":
        render_configure_numeric(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "empty_rows":
        render_configure_empty_rows(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "empty_cols":
        render_configure_empty_cols(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "outliers":
        render_configure_outliers(df, diagnosis, key_prefix=prefix)
    elif renderer_key == "business_rules":
        render_configure_business_rules(df, diagnosis, key_prefix=prefix)


def render_fix_card(rec, df, idx, diagnosis=None):
    """Render a single issue-based fix card with toggle, preview, and info."""
    sev = rec["severity"]
    rid = rec["id"]
    toggle_key = f"fix_enabled_{rid}"
    show_customize_key = f"show_customize_{rid}"
    
    # Initialize state variables
    if toggle_key not in st.session_state:
        st.session_state[toggle_key] = True
    if show_customize_key not in st.session_state:
        st.session_state[show_customize_key] = False

    cols_list = rec.get("affected_columns", [])
    col_display = ', '.join(cols_list[:2]) + (f' +{len(cols_list) - 2} more' if len(cols_list) > 2 else '') if cols_list else 'N/A'
    col_display_full = ', '.join(cols_list) if cols_list else 'N/A'
    conf = rec.get("confidence", "Medium")
    conf_class = conf.lower()

    sev_label = sev.capitalize()
    sev_emoji = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(sev, '⚪')
    why_recommended = rec.get("why_recommended", "Recommended to maintain dataset completeness.")

    preview_html = _generate_preview_html(rec, df)
    preview_section_html = ""
    if preview_html:
        preview_section_html = f"""
<div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#64748B; margin-top:14px; margin-bottom:6px;">Live Preview</div>
{preview_html}
"""

    # Render entire card HTML in a single st.html call to bypass the Markdown parser and ensure proper DOM containment.
    st.html(
        f"""<div class="ds-fix-card ds-fix-card--{sev}" role="article" aria-label="{py_html.escape(rec['title'])} fix">
<div class="ds-fix-card-header">
<div class="ds-fix-card-icon">{rec['icon']}</div>
<div class="ds-fix-card-title-area">
<div class="ds-fix-card-title">{rec['title']}</div>
<div class="ds-fix-card-subtitle">{rec.get('category', '')}</div>
</div>
<span class="ds-severity-pill ds-severity-pill--{sev}">{sev_emoji} {sev_label}</span>
</div>
<div class="ds-fix-card-body">
<div class="ds-fix-card-desc">{rec['description']}</div>
<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:12px; padding:12px 16px; margin-bottom:14px;">
<span style="font-size:0.7rem; font-weight:700; color:#15803D; text-transform:uppercase; letter-spacing:0.04em; display:block; margin-bottom:4px;">💡 Recommended Action</span>
<div style="font-size:0.88rem; font-weight:600; color:#166534; margin-bottom:4px;">{rec['recommended_action']}</div>
<div style="font-size:0.78rem; color:#15803D; line-height:1.35;"><strong>Reason:</strong> {why_recommended}</div>
</div>
<div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:12px; margin:14px 0;">
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px; text-align:center;">
<span style="font-size:0.65rem; color:#64748B; font-weight:600; text-transform:uppercase; display:block; margin-bottom:4px;">Affected Rows</span>
<span style="font-size:0.95rem; font-weight:700; color:#0F172A;">{rec.get('affected_count', 0):,}</span>
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px; text-align:center;">
<span style="font-size:0.65rem; color:#64748B; font-weight:600; text-transform:uppercase; display:block; margin-bottom:4px;">Affected Columns</span>
<span style="font-size:0.85rem; font-weight:700; color:#0F172A;" title="{col_display_full}">{col_display}</span>
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px; text-align:center; display:flex; flex-direction:column; align-items:center; justify-content:center;">
<span style="font-size:0.65rem; color:#64748B; font-weight:600; text-transform:uppercase; display:block; margin-bottom:2px;">Confidence</span>
<span class="ds-confidence-badge ds-confidence-badge--{conf_class}" style="font-size:0.75rem; border:none; padding:1px 8px; font-weight:600; margin:0;">🎯 {conf}</span>
</div>
</div>
{preview_section_html}
</div>
</div>"""
    )

    # Action bar below the card
    has_config = rid in _CONFIG_RENDERER_MAP
    
    c1, c2 = st.columns([1, 1])
    with c1:
        st.toggle(
            "✅ Enable this fix",
            value=st.session_state[toggle_key],
            key=toggle_key,
        )
    with c2:
        if has_config and diagnosis:
            is_open = st.session_state[show_customize_key]
            btn_label = "⚙️ Close Customization" if is_open else "⚙️ Customize How This Fix Works"
            if st.button(btn_label, key=f"btn_cust_toggle_{rid}", use_container_width=True):
                st.session_state[show_customize_key] = not is_open
                st.rerun()

    # Customization Area below the card
    if has_config and diagnosis and st.session_state[show_customize_key]:
        with st.container():
            st.markdown(
                f"""
                <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:18px; margin-top:8px; margin-bottom:16px;">
                    <h4 style="font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#0F172A; margin:0 0 14px 0;">🔧 Customize How This Fix Works: {rec['title']}</h4>
                """,
                unsafe_allow_html=True,
            )
            
            _render_config_controls(rid, df, diagnosis)

            st.markdown("<div style='margin-top:14px; border-top:1px dashed #E2E8F0; padding-top:12px;'></div>", unsafe_allow_html=True)
            r_col1, r_col2 = st.columns([2, 3])
            with r_col1:
                if st.button("↩️ Reset to Recommended", key=f"reset_rec_btn_{rid}", use_container_width=True):
                    reset_recommendation_settings(rid, df, diagnosis)
                    st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
            
    # Add a visual spacer at the very end
    st.markdown("<div style='margin-bottom:24px;'></div>", unsafe_allow_html=True)


def render_cleaning_plan_section(enabled_recs):
    """Render an auto-generated, human-readable Cleaning Plan summary panel."""
    if not enabled_recs:
        st.html(
            """
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:20px; text-align:center;">
                <span style="font-size:2rem;">📋</span>
                <div style="font-weight:600; font-size:0.9rem; color:#0F172A; margin-top:8px;">No fixes selected</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:4px;">Toggle on at least one fix to build your cleaning plan.</div>
            </div>
            """
        )
        return

    items_html = ""
    for rec in enabled_recs:
        rid = rec["id"]
        prefix = f"{rid}_"
        
        # Build user-friendly summary of the configuration
        desc = ""
        if rid == "fix_missing_values":
            strategy = st.session_state.get(f"{prefix}impute_strategy_card", "smart")
            strategy_labels = {
                "smart": "Smart Fill",
                "mean": "Average Value",
                "mode": "Most Common Value",
                "custom": f"Custom Value ('{st.session_state.get(f'{prefix}impute_default_val', 'Unknown')}')"
            }
            desc = f"Fill missing values using {strategy_labels.get(strategy, 'Smart Fill')}"
        elif rid == "fix_duplicates":
            strategy = st.session_state.get(f"{prefix}dup_strategy_card", "first")
            strategy_labels = {
                "first": "Keep First Copy",
                "last": "Keep Last Copy",
                "all": "Remove All Copies"
            }
            desc = f"Remove duplicate rows ({strategy_labels.get(strategy, 'Keep First Copy')})"
        elif rid == "fix_whitespace":
            strategy = st.session_state.get(f"{prefix}ws_strategy_card", "trim_all")
            desc = "Trim whitespace (Clean All Spaces)" if strategy == "trim_all" else "Trim whitespace (Ends Only)"
        elif rid == "fix_case":
            strategy = st.session_state.get(f"{prefix}case_strategy_card", "title")
            case_labels = {"title": "Title Case", "upper": "UPPERCASE", "lower": "lowercase"}
            desc = f"Normalize text case to {case_labels.get(strategy, 'Title Case')}"
        elif rid == "fix_special_chars":
            strategy = st.session_state.get(f"{prefix}special_strategy_card", "punctuation")
            char_labels = {"punctuation": "Punctuation & symbols", "alphanumeric": "Letters & numbers only", "emojis": "Emojis only"}
            desc = f"Strip special characters ({char_labels.get(strategy, 'Punctuation & symbols')})"
        elif rid == "fix_dates":
            strategy = st.session_state.get(f"{prefix}date_strategy_card", "iso")
            date_labels = {"iso": "ISO Standard", "us": "US Format", "eur": "European Format", "slash": "Slash Separated"}
            desc = f"Standardize dates to {date_labels.get(strategy, 'ISO Standard')}"
        elif rid == "fix_numeric":
            strategy = st.session_state.get(f"{prefix}numeric_strategy_card", "standard")
            desc = "Convert columns to numbers (Decimal)" if strategy == "standard" else "Convert columns to numbers (Integer)"
        elif rid == "fix_outliers":
            strategy = st.session_state.get(f"{prefix}outlier_strategy_card", "cap")
            outlier_labels = {"cap": "Cap to Boundaries", "null": "Set to Null", "drop": "Drop Rows"}
            desc = f"Handle outliers by {outlier_labels.get(strategy, 'Cap to Boundaries')}"
        elif rid == "fix_empty_rows":
            desc = "Remove completely empty rows"
        elif rid == "fix_empty_cols":
            desc = "Remove completely empty columns"
        elif rid == "fix_categories":
            desc = "Standardize category typos and spelling variations"
        elif rid == "fix_business_rules":
            desc = "Apply range validation rules"
        elif rid == "fix_blank_strings":
            desc = "Clean blank strings and treat as missing"
        else:
            desc = rec.get("recommended_action", rec["title"])

        items_html += (
            f'<div style="display:flex; align-items:flex-start; gap:10px; padding:10px 0; border-bottom:1px solid #F1F5F9;">'
            f'<span style="color:#059669; font-weight:700; font-size:1.1rem; line-height:1.2;">✓</span>'
            f'<div style="flex:1;">'
            f'<div style="font-weight:600; font-size:0.85rem; color:#0F172A; line-height:1.3;">{rec["title"]}</div>'
            f'<div style="font-size:0.75rem; color:#64748B; margin-top:2px; line-height:1.35;">{desc}</div>'
            f'</div>'
            f'</div>'
        )

    plan_html = (
        f'<div style="background:#ffffff; border:1px solid #E2E8F0; border-radius:12px; padding:18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom:20px;">'
        f'<div style="font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#64748B; margin-bottom:14px; border-bottom:1px solid #E2E8F0; padding-bottom:10px;">Current Cleaning Plan ({len(enabled_recs)} active)</div>'
        f'{items_html}'
        f'</div>'
    )
    st.html(plan_html)


def render_configuration_summary_panel(enabled_recs, df, diagnosis):
    """Render a Configuration Summary Panel showing the active cleaning plan. (Redundant under new layout)"""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# What Changed? — Premium Transformation Explorer
# ─────────────────────────────────────────────────────────────────────────────

# Operation key → human-readable category mapping
_CATEGORY_MAP = {
    "impute_statistical": ("Missing Values", "🩹", "Missing Value Replacements"),
    "impute_defaults": ("Missing Values", "🩹", "Missing Value Replacements"),
    "impute_directional": ("Missing Values", "🩹", "Missing Value Replacements"),
    "remove_duplicates": ("Duplicates", "👯", "Duplicate Rows Removed"),
    "trim_whitespace": ("Text Cleanup", "✂️", "Text Cleanup"),
    "normalize_case": ("Text Cleanup", "🔤", "Text Cleanup"),
    "remove_special_chars": ("Text Cleanup", "🚫", "Text Cleanup"),
    "find_replace": ("Text Cleanup", "🔍", "Text Cleanup"),
    "standardize_dates": ("Date Corrections", "📅", "Date Corrections"),
    "convert_numeric": ("Data Type Conversions", "🔢", "Data Type Conversions"),
    "normalize_booleans": ("Data Type Conversions", "💡", "Data Type Conversions"),
    "rename_columns": ("Column Renaming", "🏷️", "Column Renaming"),
    "drop_columns": ("Column Renaming", "🗑️", "Column Renaming"),
    "drop_empty_keys": ("Structure", "🗑️", "Structure Changes"),
    "split_column": ("Column Renaming", "✂️", "Column Renaming"),
    "merge_columns": ("Column Renaming", "🔗", "Column Renaming"),
    "validate_ranges": ("Outlier Handling", "⚠️", "Outlier Handling"),
    "statistical_outliers": ("Outlier Handling", "📊", "Outlier Handling"),
}

_OP_DISPLAY = {
    "impute_statistical": "Statistical Fill",
    "impute_defaults": "Default Value Fill",
    "impute_directional": "Directional Fill",
    "remove_duplicates": "Duplicate Removal",
    "trim_whitespace": "Whitespace Trim",
    "normalize_case": "Case Normalization",
    "remove_special_chars": "Special Char Removal",
    "find_replace": "Find & Replace",
    "standardize_dates": "Date Standardization",
    "convert_numeric": "Numeric Conversion",
    "normalize_booleans": "Boolean Normalization",
    "rename_columns": "Column Renaming",
    "drop_columns": "Column Drop",
    "drop_empty_keys": "Empty Structure Removal",
    "split_column": "Column Split",
    "merge_columns": "Column Merge",
    "validate_ranges": "Range Validation",
    "statistical_outliers": "Outlier Filtering",
}

# Max sample rows shown in any before/after table
_MAX_SAMPLES = 8


def _compute_transformation_analysis(df_original, df_cleaned, op_results, rename_map):
    """Compute a rich analysis of all transformations applied.

    Returns a dict with keys:
        cell_diffs       – list of dicts {col, row, before, after, op_key}
        categories        – dict {category_name: {icon, title, rows: [...]}}
        column_impact     – list of dicts {col, cells_modified, change_types, pct}
        rows_removed      – list of dicts {row_id, action, detail}
        timeline          – list of dicts {step, op_key, op_name, detail, icon}
        summary_metrics   – dict {cells_modified, rows_removed, cols_renamed, cols_dropped, ...}
    """
    cell_diffs = []
    category_groups = {}
    column_stats = {}  # col -> {cells_modified: int, change_types: set}
    rows_removed = []
    timeline = []
    summary = {
        "cells_modified": 0,
        "rows_removed": 0,
        "cols_renamed": 0,
        "cols_dropped": 0,
        "missing_filled": 0,
        "duplicates_removed": 0,
        "dates_corrected": 0,
        "type_conversions": 0,
    }

    # Build common-column alignment for cell-level diff
    common_cols = []
    for col_c in df_cleaned.columns:
        orig_col = None
        for o, c in rename_map.items():
            if c == col_c:
                orig_col = o
                break
        if orig_col is None:
            orig_col = col_c if col_c in df_original.columns else None
        if orig_col is not None:
            common_cols.append((orig_col, col_c))

    # Build aligned subsets for comparison using tracked original indices to prevent row shift mismatches
    if common_cols:
        row_map = st.session_state.get("cleaned_row_to_original_row")
        for orig_col, clean_col in common_cols:
            for clean_row_idx in range(len(df_cleaned)):
                if orig_col not in df_original.columns:
                    continue
                orig_row_idx = row_map[clean_row_idx] if row_map and clean_row_idx < len(row_map) else clean_row_idx
                if orig_row_idx >= len(df_original):
                    continue
                orig_val = df_original[orig_col].iloc[orig_row_idx]
                clean_val = df_cleaned[clean_col].iloc[clean_row_idx]

                # Normalize for comparison
                o_str = str(orig_val) if pd.notna(orig_val) else ""
                c_str = str(clean_val) if pd.notna(clean_val) else ""

                if o_str != c_str:
                    # Determine which op affected this cell
                    op_key = _infer_op_for_cell(orig_val, clean_val)
                    cell_diffs.append({
                        "col": clean_col,
                        "row": clean_row_idx,
                        "before": orig_val,
                        "after": clean_val,
                        "op_key": op_key,
                    })
                    # Column stats
                    if clean_col not in column_stats:
                        column_stats[clean_col] = {"cells_modified": 0, "change_types": set()}
                    column_stats[clean_col]["cells_modified"] += 1
                    cat_info = _CATEGORY_MAP.get(op_key, ("Other", "📋", "Other Changes"))
                    column_stats[clean_col]["change_types"].add(cat_info[0])

    # Count rows removed
    n_rows_removed = len(df_original) - len(df_cleaned) if len(df_original) > len(df_cleaned) else 0
    if n_rows_removed > 0:
        summary["rows_removed"] = n_rows_removed
        for i in range(n_rows_removed):
            rows_removed.append({
                "row_id": len(df_cleaned) + i,
                "action": "Removed",
                "detail": "Exact duplicate / empty row",
            })

    # Count columns dropped
    dropped_cols = set(df_original.columns) - set(df_cleaned.columns)
    renamed_cols = rename_map
    summary["cols_dropped"] = len(dropped_cols)
    summary["cols_renamed"] = len(renamed_cols)

    # Parse operation results for summary
    for entry in op_results or []:
        op_key = entry["op"]
        result = entry.get("result", {})
        if isinstance(result, dict):
            if "error" in result:
                continue
            summary["cells_modified"] += int(result.get("cells_modified", 0) or 0)
            summary["cells_modified"] += int(result.get("cells_filled", 0) or 0)
            summary["duplicates_removed"] += int(result.get("rows_removed", 0) or 0)
            if op_key in ("impute_statistical", "impute_defaults", "impute_directional"):
                summary["missing_filled"] += int(result.get("cells_filled", 0) or 0)
            if op_key == "standardize_dates":
                summary["dates_corrected"] += int(result.get("cells_modified", 0) or 0)
            if op_key in ("convert_numeric", "normalize_booleans"):
                summary["type_conversions"] += int(result.get("cells_modified", 0) or 0)

    # If summary.cells_modified is 0 but we have diffs, use diff count
    if summary["cells_modified"] == 0 and cell_diffs:
        summary["cells_modified"] = len(cell_diffs)

    # Build timeline
    for i, entry in enumerate(op_results or []):
        op_key = entry["op"]
        result = entry.get("result", {})
        if isinstance(result, dict) and "error" in result:
            timeline.append({
                "step": i + 1, "op_key": op_key,
                "op_name": _OP_DISPLAY.get(op_key, op_key),
                "detail": f"Error: {result['error']}",
                "icon": "⚠️",
            })
            continue
        cat_info = _CATEGORY_MAP.get(op_key, ("Other", "📋", "Other"))
        detail = _format_op_detail(op_key, result)
        timeline.append({
            "step": i + 1, "op_key": op_key,
            "op_name": _OP_DISPLAY.get(op_key, op_key),
            "detail": detail,
            "icon": cat_info[1],
        })

    # Build category groups from cell_diffs
    for cd in cell_diffs:
        cat_info = _CATEGORY_MAP.get(cd["op_key"], ("Other", "📋", "Other Changes"))
        cat_key = cat_info[0]
        if cat_key not in category_groups:
            category_groups[cat_key] = {
                "icon": cat_info[1],
                "title": cat_info[2],
                "rows": [],
                "count": 0,
            }
        category_groups[cat_key]["rows"].append(cd)
        category_groups[cat_key]["count"] += 1

    # Build column impact sorted by most changed
    column_impact = []
    for col, stats in sorted(column_stats.items(), key=lambda x: -x[1]["cells_modified"]):
        col_pct = round((stats["cells_modified"] / max(len(df_original), 1)) * 100, 1)
        column_impact.append({
            "col": col,
            "cells_modified": stats["cells_modified"],
            "change_types": ", ".join(sorted(stats["change_types"])),
            "pct": col_pct,
        })

    return {
        "cell_diffs": cell_diffs,
        "categories": category_groups,
        "column_impact": column_impact,
        "rows_removed": rows_removed,
        "timeline": timeline,
        "summary_metrics": summary,
    }


def _infer_op_for_cell(before_val, after_val):
    """Heuristic to infer which operation type affected a single cell."""
    if pd.isna(before_val) and pd.notna(after_val):
        return "impute_defaults"
    if pd.notna(before_val) and pd.isna(after_val):
        return "remove_duplicates"
    b_str = str(before_val).strip() if pd.notna(before_val) else ""
    a_str = str(after_val).strip() if pd.notna(after_val) else ""
    if b_str != b_str.strip():
        return "trim_whitespace"
    if b_str.lower() == a_str.lower() and b_str != a_str:
        return "normalize_case"
    try:
        float(b_str.replace(",", "").replace("$", "").replace("%", "").strip())
        if b_str != a_str:
            return "convert_numeric"
    except (ValueError, TypeError):
        pass
    return "find_replace"


def _format_op_detail(op_key, result):
    """Format a human-readable detail string for an operation."""
    if not result:
        return "Completed"
    parts = []
    for k, v in result.items():
        if k == "rows_removed" and v:
            parts.append(f"{v} rows removed")
        elif k == "cells_filled" and v:
            parts.append(f"{v} cells filled")
        elif k == "cells_modified" and v:
            parts.append(f"{v} cells modified")
        elif k == "columns_renamed" and v:
            parts.append(f"{v} columns renamed")
        elif k == "columns_converted" and v:
            parts.append(f"{v} columns converted")
        elif k == "cols_dropped" and v:
            parts.append(f"{v} columns dropped")
    return ", ".join(parts) if parts else "Completed"


def _esc(val):
    """HTML-escape a value safely for use in inline HTML."""
    if pd.isna(val) or val is None:
        return '<span class="ds-cell-null">NULL</span>'
    return py_html.escape(str(val))


def render_what_changed_hero():
    """Render the "What Changed?" hero banner."""
    st.markdown(
        '<div class="ds-changed-hero">'
        '<h2>✨ What Changed?</h2>'
        '<p>Review all transformations applied to your dataset.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_trust_banner():
    """Render the trust & transparency banner."""
    st.markdown(
        """
        <div class="ds-trust-banner">
            <span class="ds-trust-badge">🔒 All transformations applied locally</span>
            <span class="ds-trust-badge">✅ Data never leaves your machine</span>
            <span class="ds-trust-badge">📋 Full audit trail preserved</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_change_overview(analysis):
    """Section 1: Transformation Overview with metric cards."""
    m = analysis["summary_metrics"]
    render_section("📊 Transformation Overview", "")
    cards = []
    if m["cells_modified"] > 0:
        cards.append(("✏️", f"{m['cells_modified']:,}", "Cells Modified"))
    if m["duplicates_removed"] > 0:
        cards.append(("👯", f"{m['duplicates_removed']:,}", "Duplicates Removed"))
    if m["missing_filled"] > 0:
        cards.append(("🩹", f"{m['missing_filled']:,}", "Missing Values Filled"))
    if m["dates_corrected"] > 0:
        cards.append(("📅", f"{m['dates_corrected']:,}", "Dates Corrected"))
    if m["type_conversions"] > 0:
        cards.append(("🔢", f"{m['type_conversions']:,}", "Type Conversions"))
    if m["cols_renamed"] > 0:
        cards.append(("🏷️", f"{m['cols_renamed']:,}", "Columns Renamed"))
    if m["rows_removed"] > 0:
        cards.append(("🗑️", f"{m['rows_removed']:,}", "Rows Removed"))
    if m["cols_dropped"] > 0:
        cards.append(("❌", f"{m['cols_dropped']:,}", "Columns Dropped"))
    if not cards:
        cards.append(("✅", "0", "No Changes"))

    cards_html = "".join(
        f'<div class="ds-change-overview-card">'
        f'<span class="ds-change-overview-icon">{icon}</span>'
        f'<div class="ds-change-overview-value">{val}</div>'
        f'<div class="ds-change-overview-label">{label}</div>'
        f'</div>'
        for icon, val, label in cards[:8]
    )
    st.markdown(f'<div class="ds-change-overview">{cards_html}</div>', unsafe_allow_html=True)


def render_change_categories(analysis):
    """Section 2-3: Expandable category cards with before/after comparisons."""
    categories = analysis["categories"]
    if not categories:
        return
    render_section("📂 Change Categories", "")
    # Priority order
    priority = ["Missing Values", "Duplicates", "Date Corrections", "Text Cleanup",
                "Data Type Conversions", "Column Renaming", "Outlier Handling", "Structure", "Other"]
    sorted_cats = sorted(categories.keys(), key=lambda k: priority.index(k) if k in priority else 99)

    for cat_key in sorted_cats:
        cat = categories[cat_key]
        count = cat["count"]
        rows_sample = cat["rows"][:_MAX_SAMPLES]
        total = len(cat["rows"])

        with st.expander(f"{cat['icon']} {cat['title']} — {count:,} changes", expanded=count > 0):
            if total > _MAX_SAMPLES:
                st.markdown(
                    f'<div class="ds-change-sample-info">\n'
                    f'Showing {_MAX_SAMPLES} of {total:,} changes\n'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            # Build before/after table
            table_html = (
                '<table class="ds-diff-table">'
                '<thead><tr><th>Before</th><th></th><th>After</th></tr></thead>'
                '<tbody>'
            )
            for r in rows_sample:
                before_html = _esc(r["before"])
                after_html = _esc(r["after"])
                table_html += (
                    f'<tr>'
                    f'<td>{before_html}</td>'
                    f'<td><span class="ds-cell-arrow">→</span></td>'
                    f'<td>{after_html}</td>'
                    f'</tr>'
                )
            table_html += '</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)


def render_missing_value_details(analysis, df_original, df_cleaned):
    """Section 4: Detailed missing value replacement view."""
    missing_ops = ["impute_statistical", "impute_defaults", "impute_directional"]
    missing_diffs = [d for d in analysis["cell_diffs"] if d["op_key"] in missing_ops]
    if not missing_diffs:
        return
    render_section("🩹 Missing Value Replacements", "")
    sample = missing_diffs[:_MAX_SAMPLES]
    table_html = (
        '<table class="ds-diff-table">'
        '<thead><tr><th>Column</th><th>Row</th><th>Before</th><th></th><th>After</th></tr></thead>'
        '<tbody>'
    )
    for r in sample:
        table_html += (
            f'<tr>'
            f'<td><code>{py_html.escape(r["col"])}</code></td>'
            f'<td>#{r["row"] + 1}</td>'
            f'<td>{_esc(r["before"])}</td>'
            f'<td><span class="ds-cell-arrow">→</span></td>'
            f'<td>{_esc(r["after"])}</td>'
            f'</tr>'
        )
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    if len(missing_diffs) > _MAX_SAMPLES:
        st.markdown(
            f'<div class="ds-change-sample-info">'
            f'Showing {_MAX_SAMPLES} of {len(missing_diffs):,} replacements'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div style="font-size:0.82rem; color:#64748B; margin-top:8px;">'
        '💡 <strong>Replacement Method:</strong> Statistical fill (mean/median) for numeric columns, '
        'default placeholder ("Unknown") for text columns.'
        '</div>',
        unsafe_allow_html=True,
    )


def render_duplicate_removal_details(analysis):
    """Section 5: Duplicate removal explorer."""
    if not analysis["rows_removed"]:
        return
    render_section("👯 Duplicate Rows Removed", "")
    n = len(analysis["rows_removed"])
    st.markdown(
        f'<div style="font-size:0.88rem; font-weight:600; color:#0F172A; margin-bottom:12px;">'
        f'{n:,} rows removed — <span style="color:#64748B;">exact duplicate detected</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    sample = analysis["rows_removed"][:min(20, n)]
    table_html = (
        '<table class="ds-diff-table">'
        '<thead><tr><th>Row ID</th><th>Action</th><th>Reason</th></tr></thead>'
        '<tbody>'
    )
    for r in sample:
        table_html += (
            f'<tr>'
            f'<td>#{r["row_id"] + 1}</td>'
            f'<td><span class="ds-cell-removed">{py_html.escape(r["action"])}</span></td>'
            f'<td>{py_html.escape(r["detail"])}</td>'
            f'</tr>'
        )
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    if n > 20:
        st.markdown(
            f'<div class="ds-change-sample-info">'
            f'Showing 20 of {n:,} removed rows'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_text_cleanup_details(analysis):
    """Section 7: Text cleanup diffs (whitespace, case, special chars)."""
    text_ops = ["trim_whitespace", "normalize_case", "remove_special_chars", "find_replace"]
    text_diffs = [d for d in analysis["cell_diffs"] if d["op_key"] in text_ops]
    if not text_diffs:
        return
    render_section("✂️ Text Cleanup", "")
    # Group by op_key
    groups = {}
    for d in text_diffs:
        groups.setdefault(d["op_key"], []).append(d)
    op_labels = {
        "trim_whitespace": ("Whitespace Cleanup", "✂️"),
        "normalize_case": ("Case Standardization", "🔤"),
        "remove_special_chars": ("Special Character Cleanup", "🚫"),
        "find_replace": ("Find & Replace", "🔍"),
    }
    for op_key, diffs in groups.items():
        label, icon = op_labels.get(op_key, (op_key, "📋"))
        sample = diffs[:5]
        with st.expander(f"{icon} {label} — {len(diffs):,} cells", expanded=False):
            table_html = (
                '<table class="ds-diff-table">'
                '<thead><tr><th>Column</th><th>Before</th><th></th><th>After</th></tr></thead>'
                '<tbody>'
            )
            for r in sample:
                table_html += (
                    f'<tr>'
                    f'<td><code>{py_html.escape(r["col"])}</code></td>'
                    f'<td>{_esc(r["before"])}</td>'
                    f'<td><span class="ds-cell-arrow">→</span></td>'
                    f'<td>{_esc(r["after"])}</td>'
                    f'</tr>'
                )
            table_html += '</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)
            if len(diffs) > 5:
                st.markdown(
                    f'<div class="ds-change-sample-info">'
                    f'Showing 5 of {len(diffs):,} changes'
                    f'</div>',
                    unsafe_allow_html=True,
                )


def render_date_correction_details(analysis):
    """Section 6: Date correction before/after."""
    date_diffs = [d for d in analysis["cell_diffs"] if d["op_key"] == "standardize_dates"]
    if not date_diffs:
        return
    render_section("📅 Date Corrections", "")
    sample = date_diffs[:_MAX_SAMPLES]
    table_html = (
        '<table class="ds-diff-table">'
        '<thead><tr><th>Column</th><th>Before</th><th></th><th>After</th></tr></thead>'
        '<tbody>'
    )
    for r in sample:
        table_html += (
            f'<tr>'
            f'<td><code>{py_html.escape(r["col"])}</code></td>'
            f'<td>{_esc(r["before"])}</td>'
            f'<td><span class="ds-cell-arrow">→</span></td>'
            f'<td>{_esc(r["after"])}</td>'
            f'</tr>'
        )
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    if len(date_diffs) > _MAX_SAMPLES:
        st.markdown(
            f'<div class="ds-change-sample-info">'
            f'Showing {_MAX_SAMPLES} of {len(date_diffs):,} date corrections'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div style="font-size:0.82rem; color:#64748B; margin-top:8px;">'
        '💡 Dates standardized to ISO format (YYYY-MM-DD). Unparseable values set to blank.'
        '</div>',
        unsafe_allow_html=True,
    )


def render_type_conversion_details(analysis):
    """Section 8: Data type conversion details."""
    type_ops = ["convert_numeric", "normalize_booleans"]
    type_diffs = [d for d in analysis["cell_diffs"] if d["op_key"] in type_ops]
    if not type_diffs:
        return
    render_section("🔢 Data Type Conversions", "")
    # Show unique columns affected
    affected = {}
    for d in type_diffs:
        col = d["col"]
        if col not in affected:
            affected[col] = {"before_type": "Text", "after_type": "Numeric", "count": 0}
        affected[col]["count"] += 1
        if d["op_key"] == "normalize_booleans":
            affected[col]["after_type"] = "Boolean"

    table_html = (
        '<table class="ds-diff-table">'
        '<thead><tr><th>Column</th><th>Before Type</th><th>After Type</th><th>Cells Changed</th></tr></thead>'
        '<tbody>'
    )
    for col, info in list(affected.items())[:_MAX_SAMPLES]:
        table_html += (
            f'<tr>'
            f'<td><code>{py_html.escape(col)}</code></td>'
            f'<td><span class="ds-cell-type-before">{info["before_type"]}</span></td>'
            f'<td><span class="ds-cell-type-after">{info["after_type"]}</span></td>'
            f'<td>{info["count"]:,}</td>'
            f'</tr>'
        )
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.82rem; color:#64748B; margin-top:8px;">'
        '💡 Columns converted to support accurate analysis and computation.'
        '</div>',
        unsafe_allow_html=True,
    )


def render_column_impact_dashboard(analysis):
    """Section 9: Column impact dashboard."""
    impact = analysis["column_impact"]
    if not impact:
        return
    render_section("📊 Column Impact Dashboard", "")
    st.markdown(
        '<div style="font-size:0.82rem; color:#64748B; margin-bottom:12px;">'
        'Columns sorted by number of cells modified.'
        '</div>',
        unsafe_allow_html=True,
    )
    max_cells = max(r["cells_modified"] for r in impact) if impact else 1
    for r in impact[:12]:
        bar_pct = round((r["cells_modified"] / max(max_cells, 1)) * 100, 1)
        st.markdown(
            f'<div class="ds-column-impact-row">'
            f'<span class="ds-column-impact-name">{py_html.escape(r["col"])}</span>'
            f'<div class="ds-column-impact-bar"><div class="ds-column-impact-fill" style="width:{bar_pct}%"></div></div>'
            f'<span class="ds-column-impact-count">{r["cells_modified"]:,}</span>'
            f'<span class="ds-column-impact-types">{py_html.escape(r["change_types"])}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    if len(impact) > 12:
        st.markdown(
            f'<div class="ds-change-sample-info">'
            f'Showing top 12 of {len(impact)} affected columns'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_transformation_timeline(analysis):
    """Section 10: Transformation timeline (audit trail)."""
    timeline = analysis["timeline"]
    if not timeline:
        return
    render_section("📋 Transformation Timeline", "")
    timeline_html = '<div class="ds-change-timeline">'
    for item in timeline:
        timeline_html += (
            f'<div class="ds-change-timeline-item">'
            f'<div class="ds-change-timeline-step">{item["icon"]} Step {item["step"]}: {py_html.escape(item["op_name"])}</div>'
            f'<div class="ds-change-timeline-detail">{py_html.escape(item["detail"])}</div>'
            f'</div>'
        )
    timeline_html += '</div>'
    st.markdown(timeline_html, unsafe_allow_html=True)


def render_changelog_download(analysis, op_results, df_original, df_cleaned, base_name):
    """Section 14: Downloadable change log."""
    render_section("📥 Download Change Log", "")
    # Build CSV change log
    log_rows = []
    for cd in analysis["cell_diffs"]:
        op_key = cd["op_key"]
        log_rows.append({
            "Column": cd["col"],
            "Row": cd["row"] + 1,
            "Before": str(cd["before"]) if pd.notna(cd["before"]) else "",
            "After": str(cd["after"]) if pd.notna(cd["after"]) else "",
            "Operation": _OP_DISPLAY.get(op_key, op_key),
            "Applied": "Applied Automatically",
        })
    for rr in analysis["rows_removed"]:
        log_rows.append({
            "Column": "(entire row)",
            "Row": rr["row_id"] + 1,
            "Before": "(row existed)",
            "After": "(removed)",
            "Operation": "Duplicate Removal",
            "Applied": "Applied Automatically",
        })

    if log_rows:
        log_df = pd.DataFrame(log_rows)
        log_csv = log_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Full Change Log (CSV)",
            log_csv,
            f"{base_name}_change_log.csv",
            "text/csv",
            key="dl_changelog",
            use_container_width=True,
        )
    else:
        st.info("No cell-level changes to export.")


def compute_and_store_analysis(df_original, df_cleaned, op_results, rename_map):
    """Compute transformation analysis and cache in session state."""
    if "what_changed_analysis" not in st.session_state:
        st.session_state["what_changed_analysis"] = _compute_transformation_analysis(
            df_original, df_cleaned, op_results, rename_map
        )
    return st.session_state["what_changed_analysis"]
