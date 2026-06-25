"""Main Streamlit application entry point for the Data Sanitizer (single-page wizard refactor)."""
import os
import time
import zipfile
from datetime import datetime
from io import BytesIO
import html as py_html

import pandas as pd
import streamlit as st

try:
    st.set_page_config(
        page_title="Data Sanitizer",
        page_icon="🧹",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
except st.errors.StreamlitAPIException:
    pass



# ── Imports from core and ui ──
from core.diagnostics import analyze_dataframe
from core.loader import load_file
from ui.components import (
    start_over,
    render_section,
    render_file_summary,
    render_diagnosis_table,
    generate_fix_recommendations,
    render_fix_summary_section,
    render_quality_journey_section,
    render_fix_card,
    render_cleaning_plan_section,
    render_configuration_summary_panel,
    _get_fix_operations,
    render_what_changed_hero,
    render_trust_banner,
    render_change_overview,
    render_change_categories,
    render_missing_value_details,
    render_duplicate_removal_details,
    render_text_cleanup_details,
    render_date_correction_details,
    render_type_conversion_details,
    render_column_impact_dashboard,
    render_transformation_timeline,
    render_changelog_download,
    compute_and_store_analysis,
)
from ui.shell import _render_header, render_stepper

_DISPLAY_NAMES = {
    "drop_empty_keys": "Drop Empty / Keys",
    "impute_defaults": "Impute Defaults",
    "impute_statistical": "Statistical Fill",
    "impute_directional": "Forward/Backward Fill",
    "remove_duplicates": "Removing Duplicates",
    "trim_whitespace": "Trim Whitespace",
    "normalize_case": "Case Normalization",
    "remove_special_chars": "Remove Special Characters",
    "find_replace": "Find & Replace",
    "standardize_dates": "Date Standardization",
    "convert_numeric": "Numeric Conversion",
    "normalize_booleans": "Boolean Normalization",
    "rename_columns": "Column Renaming",
    "drop_columns": "Drop Columns",
    "split_column": "Split Column",
    "merge_columns": "Merge Columns",
    "validate_ranges": "Range Validations",
    "statistical_outliers": "Statistical Outliers",
}
from ui.theme import (
    badge,
    chip,
    chip_arrow,
    inject_design_system,
    page_title,
    C as _c,
    R as _r,
    TOKENS as _tokens,
)

# ── Session state: current_step key ──
if "current_step" not in st.session_state:
    st.session_state["current_step"] = 0

# ── Session state: operations run count ──
if "n_ops_run" not in st.session_state:
    st.session_state["n_ops_run"] = 0

# ── Session state: file & log keys ──
if "df_original" not in st.session_state:
    st.session_state["df_original"] = None
if "selected_sheet" not in st.session_state:
    st.session_state["selected_sheet"] = None
if "last_loaded_key" not in st.session_state:
    st.session_state["last_loaded_key"] = None
if "diagnosis" not in st.session_state:
    st.session_state["diagnosis"] = None
if "file_meta" not in st.session_state:
    st.session_state["file_meta"] = None

if "df_cleaned" not in st.session_state:
    st.session_state["df_cleaned"] = None
if "cleaned_row_to_original_row" not in st.session_state:
    st.session_state["cleaned_row_to_original_row"] = None
if "operation_results" not in st.session_state:
    st.session_state["operation_results"] = None
if "last_loaded_name" not in st.session_state:
    st.session_state["last_loaded_name"] = None
if "is_empty_file" not in st.session_state:
    st.session_state["is_empty_file"] = False
if "orig_diagnosis_for_report" not in st.session_state:
    st.session_state["orig_diagnosis_for_report"] = None
if "find_regex_valid" not in st.session_state:
    st.session_state["find_regex_valid"] = True

# Cleaning session states are not used since default cleaning methods were removed.


# ── Step 0: Upload Helper functions ──
def render_step_upload():
    # Check if a dataset is already loaded in the session state
    df = st.session_state.get("df_original")

    if df is not None:
        # ── POST-UPLOAD STATE (Hide uploader, show preview) ──
        res = st.session_state["profiler_result"]
        metrics = res.metrics
        filename = st.session_state.get("last_loaded_name", "dataset")
        dup_rows = sum(issue.affected_count for issue in res.issues if issue.id == "duplicate_rows")

        # Show Hero title and subtitle
        st.markdown(
            '<div class="ds-hero"><h1>Prepare Your Data</h1>'
            '<p>Your dataset is loaded and ready for analysis.</p></div>',
            unsafe_allow_html=True,
        )

        st.success(f"🎉 **{filename}** loaded successfully!")
        
        # Layout elements: File details card & Smart metrics
        st.markdown('<p class="ds-section" style="margin-top:12px;">📊 Dataset Overview</p>', unsafe_allow_html=True)
        
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Rows", f"{metrics['rows']:,}")
        m_col2.metric("Columns", f"{metrics['columns']}")
        m_col3.metric("Missing Cells", f"{sum(issue.affected_count for issue in res.issues if issue.id == 'missing_values'):,}")
        m_col4.metric("Duplicate Rows", f"{dup_rows:,}")
        
        # Dataset Preview (first 5 rows)
        st.markdown('<p class="ds-section" style="margin-top:18px;">📋 Dataset Preview (First 5 rows)</p>', unsafe_allow_html=True)
        st.dataframe(df.head(5), use_container_width=True)
        
        # Action CTA Buttons
        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([1, 4])
        with btn_col1:
            if st.button("↺ Change file", use_container_width=True, key="btn_change_file"):
                # Clear all file states to show empty uploader again
                st.session_state.update(
                    df_original=None, df_cleaned=None, cleaned_row_to_original_row=None, file_meta=None, diagnosis=None,
                    last_loaded_name=None, is_empty_file=False, orig_diagnosis_for_report=None,
                    selected_sheet=None, last_loaded_key=None, profiler_result=None
                )
                st.rerun()
        with btn_col2:
            if st.button("Proceed to Diagnose →", type="primary", use_container_width=True, key="btn_proceed_diagnose"):
                st.session_state["current_step"] = 1
                st.rerun()
    else:
        # ── PRE-UPLOAD STATE (Show uploader) ──
        st.markdown(
            '<div class="ds-hero"><h1>Prepare Your Data</h1>'
            '<p>Upload your dataset to run a comprehensive quality audit and instantly discover anomalies.</p></div>',
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload your CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed",
            key="main_file_uploader",
        )

        if uploaded_file is not None:
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            sheet_names = []
            selected_sheet = None

            if ext in (".xlsx", ".xls"):
                try:
                    if hasattr(uploaded_file, "seek"):
                        uploaded_file.seek(0)
                    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
                    excel_file = pd.ExcelFile(uploaded_file, engine=engine)
                    sheet_names = excel_file.sheet_names
                except Exception as e:
                    st.error(f"Error reading Excel sheet list: {e}. Try another file.")
                    sheet_names = []

            if len(sheet_names) > 1:
                current_selected = st.session_state.get("selected_sheet")
                default_idx = sheet_names.index(current_selected) if current_selected in sheet_names else 0
                selected_sheet = st.selectbox("Select sheet", sheet_names, index=default_idx)
                st.session_state["selected_sheet"] = selected_sheet
            elif len(sheet_names) == 1:
                st.session_state["selected_sheet"] = sheet_names[0]
                selected_sheet = sheet_names[0]
            else:
                st.session_state["selected_sheet"] = None
                selected_sheet = None

            current_key = (uploaded_file.name, selected_sheet)
            
            # Trigger staged loading if this file is not loaded yet
            if st.session_state.get("last_loaded_key") != current_key:
                # Clear old states
                st.session_state["df_original"] = None
                st.session_state["diagnosis"] = None
                st.session_state["profiler_result"] = None
                
                # Show Staged Loading Experience
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.markdown("⏳ **Reading file...**")
                time.sleep(0.3)
                progress_bar.progress(25)
                
                status_text.markdown("🔍 **Detecting schema...**")
                time.sleep(0.3)
                progress_bar.progress(50)
                
                status_text.markdown("📊 **Profiling dataset...**")
                result = load_file(uploaded_file, uploaded_file.name, sheet_name=selected_sheet)
                progress_bar.progress(75)
                
                if result.get("error"):
                    status_text.empty()
                    progress_bar.empty()
                    st.error(f"{result['error']} Try another file.")
                    st.session_state.update(df_original=None, diagnosis=None, file_meta=None,
                                            is_empty_file=False, last_loaded_key=None)
                    return
                
                df = result["df"]
                if df is not None and len(df) == 0:
                    status_text.empty()
                    progress_bar.empty()
                    st.error("This file appears to be empty. Please upload a file with at least one row of data.")
                    st.session_state.update(df_original=None, diagnosis=None, file_meta=None,
                                            is_empty_file=True, last_loaded_key=None)
                    return
                    
                # Finish load
                status_text.markdown("✨ **Preparing diagnostics...**")
                time.sleep(0.3)
                progress_bar.progress(100)
                
                # Save loaded data
                st.session_state["df_original"] = df
                st.session_state["file_meta"] = result
                st.session_state["is_empty_file"] = False
                st.session_state["last_loaded_key"] = current_key
                st.session_state["last_loaded_name"] = uploaded_file.name
                if sheet_names:
                    result["sheet_names"] = sheet_names
                    
                # Cache profiler results immediately
                from core.profiler import Profiler
                profiler = Profiler()
                st.session_state["profiler_result"] = profiler.profile(df)
                
                # Map back to old diagnosis format to keep compatibility
                st.session_state["diagnosis"] = analyze_dataframe(df)
                
                # Clear loading elements
                time.sleep(0.2)
                progress_bar.empty()
                status_text.empty()
                st.rerun()
        else:
            st.session_state.update(
                df_original=None, df_cleaned=None, cleaned_row_to_original_row=None, file_meta=None, diagnosis=None,
                last_loaded_name=None, is_empty_file=False, orig_diagnosis_for_report=None,
                selected_sheet=None, last_loaded_key=None, profiler_result=None
            )
            # Trust indicators and format chips
            st.markdown(
                """
                <div style="text-align: center; margin-top: -12px; margin-bottom: 28px;">
                    <span class="ds-format">CSV</span>
                    <span class="ds-format">XLSX</span>
                    <span class="ds-format">XLS</span>
                </div>
                <div class="ds-trust-grid">
                    <div class="ds-trust-card">
                        <span class="icon">🔒</span>
                        <h4>Secure Processing</h4>
                        <p>Files processed locally and safely</p>
                    </div>
                    <div class="ds-trust-card">
                        <span class="icon">⚡</span>
                        <h4>Large File Support</h4>
                        <p>Up to 200MB uploads</p>
                    </div>
                    <div class="ds-trust-card">
                        <span class="icon">📊</span>
                        <h4>Multiple Formats</h4>
                        <p>CSV, XLSX, XLS</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── Step 1: Report Helper functions ──
def render_step_report():
    if st.session_state["df_original"] is None:
        st.warning("No file loaded.")
        if st.button("← Upload a file", use_container_width=True):
            st.session_state["current_step"] = 0
            st.rerun()
        st.stop()

    render_file_summary(st.session_state["file_meta"])

    file_meta = st.session_state["file_meta"]
    if file_meta and file_meta.get("sheet_names") and len(file_meta["sheet_names"]) > 1:
        selected_sheet = st.session_state.get("selected_sheet")
        if selected_sheet:
            st.caption(f"Sheet: {selected_sheet}")

    st.divider()

    diagnosis = st.session_state["diagnosis"]
    n_critical = sum(1 for d in diagnosis if d["status"] == "critical")
    n_attention = sum(1 for d in diagnosis if d["status"] == "attention")
    n_clean = sum(1 for d in diagnosis if d["status"] == "clean")

    # Fetch dataset duplicates
    df = st.session_state["df_original"]
    dup_rows = int(df.duplicated().sum()) if df is not None else 0

    summary_parts = []
    if n_critical:
        summary_parts.append(badge(f"{n_critical} critical", "danger"))
    if n_attention:
        summary_parts.append(badge(f"{n_attention} attention", "warning"))
    if dup_rows > 0:
        summary_parts.append(badge(f"{dup_rows:,} duplicate rows", "warning"))
    if n_clean and not (n_critical or n_attention or dup_rows > 0):
        summary_parts.append(badge(f"{n_clean} clean columns", "success"))

    if n_critical:
        headline = "Some columns need attention before cleaning."
    elif n_attention:
        headline = "A few columns have minor issues that should be addressed."
    elif dup_rows > 0:
        headline = "Duplicate records detected in your dataset."
    else:
        headline = "Your data looks healthy."

    if n_critical:
        border_color = "#DC2626"
        bg_color = "#FEF2F2"
    elif n_attention or dup_rows > 0:
        border_color = "#D97706"
        bg_color = "#FFFBEB"
    else:
        border_color = "#059669"
        bg_color = "#ECFDF5"

    st.markdown(
        f'<div style="margin-bottom:18px; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; border-left: 4px solid {border_color}; background-color: {bg_color};">'
        f'<div style="font-weight:600;color:#0F172A;margin-bottom:6px;">{headline}</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;">{"".join(summary_parts)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    render_diagnosis_table(diagnosis)

    if st.button("→ Review & Apply Fixes", type="primary", use_container_width=True, key="btn_go_clean"):
        st.session_state["current_step"] = 2
        st.rerun()


# ── Step 2: Review & Apply Fixes (issue-based guided workflow) ──
def render_step_clean():
    if st.session_state["df_original"] is None:
        st.session_state["current_step"] = 0
        st.rerun()
        return

    df = st.session_state["df_original"]
    profiler_result = st.session_state.get("profiler_result")
    diagnosis = st.session_state.get("diagnosis")

    if not profiler_result or not diagnosis:
        st.warning("No profiling data found. Please re-upload your file.")
        if st.button("← Upload a file"):
            st.session_state["current_step"] = 0
            st.rerun()
        return

    # Generate fix recommendations from profiler results
    recommendations = generate_fix_recommendations(df, profiler_result, diagnosis)

    # ── 1. Cleaning Summary ──
    render_fix_summary_section(recommendations, profiler_result)

    # ── 2. Quality Score Journey ──
    current_score = profiler_result.health_score
    enabled_count = sum(1 for r in recommendations if st.session_state.get(f"fix_enabled_{r['id']}", True))
    estimated_score = min(100, current_score + sum(r.get("estimated_improvement", 5) for r in recommendations if st.session_state.get(f"fix_enabled_{r['id']}", True)))
    render_quality_journey_section(current_score, estimated_score)

    st.divider()

    if not recommendations:
        st.markdown(
            '<div class="ds-fix-empty">'
            '<div class="ds-fix-empty-icon">✨</div>'
            '<div class="ds-fix-empty-title">No issues detected</div>'
            '<div class="ds-fix-empty-hint">Your data is clean and ready to use. Proceed to download your results.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("→ Proceed to results", type="primary", use_container_width=True, key="btn_proceed_clean"):
            st.session_state["df_cleaned"] = df.copy()
            st.session_state["cleaned_row_to_original_row"] = list(range(len(df)))
            st.session_state["operation_results"] = []
            st.session_state["n_ops_run"] = 0
            st.session_state["current_step"] = 3
            st.rerun()
        return

    # ── 3. Split 2-Column Layout ──
    col_left, col_right = st.columns([2, 1])

    with col_left:
        # ── 4. Issue-Based Fix Cards ──
        for i, rec in enumerate(recommendations):
            render_fix_card(rec, df, i, diagnosis=diagnosis)

    with col_right:
        # ── 4b. Cleaning Plan Summary Panel ──
        enabled_recs = [r for r in recommendations if st.session_state.get(f"fix_enabled_{r['id']}", True)]
        render_cleaning_plan_section(enabled_recs)

        # ── 5. Apply All Button & Pipeline ──
        if enabled_recs:
            from ui.theme import chip, chip_arrow
            pieces = []
            for idx, r in enumerate(enabled_recs):
                if idx > 0:
                    pieces.append(chip_arrow())
                pieces.append(chip(f"{r['icon']} {r['title']}"))
            pipeline_html = (
                '<div style="background:#EEF2FF;border:1px solid #C7D2FE;'
                'border-left:4px solid #4F46E5;border-radius:12px;'
                'padding:16px 20px;margin-bottom:16px;">'
                '<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                'letter-spacing:0.08em;color:#4338CA;margin:0 0 10px 0;">'
                'Cleaning Pipeline · Execution Order</p>'
                + "".join(pieces)
                + '</div>'
            )
            st.markdown(pipeline_html, unsafe_allow_html=True)

        if enabled_recs:
            if st.button("✨ Apply All Recommended Fixes", type="primary", use_container_width=True, key="clean_btn_main"):
                df_cleaned = df.copy()
                df_cleaned["_ds_original_idx"] = range(len(df_cleaned))
                operation_results = []

                # Build ordered operations list
                steps_to_run = []
                for rec in enabled_recs:
                    ops = _get_fix_operations(rec, df_cleaned)
                    for op in ops:
                        steps_to_run.append((rec["title"], op))

                total_ops = len(steps_to_run)
                if total_ops == 0:
                    st.session_state["df_cleaned"] = df.copy()
                    st.session_state["operation_results"] = []
                    st.session_state["n_ops_run"] = 0
                    st.session_state["current_step"] = 3
                    st.rerun()

                progress = st.progress(0, text="Starting cleaning...")
                curr = 0
                for rec_title, op in steps_to_run:
                    curr += 1
                    progress.progress(curr / total_ops, text=f"Running: {op['name']}...")
                    try:
                        result = op["func"](df_cleaned)
                        if isinstance(result, tuple):
                            df_cleaned, op_result = result
                        else:
                            df_cleaned = result
                            op_result = {}
                        operation_results.append({"op": op["key"], "result": op_result})
                    except Exception as e:
                        operation_results.append({"op": op["key"], "result": {"error": str(e)}})

                progress.progress(1.0, text="✅ Cleaning complete!")
                time.sleep(0.5)
                progress.empty()

                if "_ds_original_idx" in df_cleaned.columns:
                    original_idx_mapping = df_cleaned["_ds_original_idx"].tolist()
                    df_cleaned = df_cleaned.drop(columns=["_ds_original_idx"])
                else:
                    original_idx_mapping = list(range(len(df_cleaned)))
                st.session_state["cleaned_row_to_original_row"] = original_idx_mapping
                st.session_state["df_cleaned"] = df_cleaned
                st.session_state["operation_results"] = operation_results
                st.session_state["orig_diagnosis_for_report"] = diagnosis
                st.session_state["n_ops_run"] = len(operation_results)
                st.session_state["current_step"] = 3
                st.rerun()
        else:
            st.info("Toggle on at least one fix above to proceed.")

        # ── 6. Skip Option ──
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if st.button("→ Proceed without changes", type="secondary", use_container_width=True, key="btn_proceed_no_changes"):
            st.session_state["df_cleaned"] = df.copy()
            st.session_state["cleaned_row_to_original_row"] = list(range(len(df)))
            st.session_state["operation_results"] = []
            st.session_state["n_ops_run"] = 0
            st.session_state["current_step"] = 3
            st.rerun()


# ── Step 3: Results Helper functions ──
def format_visible_whitespace(val):
    if val is None or pd.isna(val):
        return ""
    val_str = str(val)
    l_spaces = len(val_str) - len(val_str.lstrip(" "))
    r_spaces = len(val_str) - len(val_str.rstrip(" "))

    if l_spaces == 0 and r_spaces == 0:
        return val_str.replace("  ", "··") if "  " in val_str else val_str

    middle = val_str[l_spaces:len(val_str) - r_spaces] if r_spaces > 0 else val_str[l_spaces:]
    middle = middle.replace("  ", "··")
    return ("·" * l_spaces) + middle + ("·" * r_spaces)


def get_size_str(n_bytes) -> str:
    return f"{n_bytes / (1024 * 1024):.2f} MB" if n_bytes > 1024 * 1024 else f"{n_bytes / 1024:.2f} KB"


def render_step_results():
    if st.session_state["df_cleaned"] is None:
        st.warning("No cleaned data found.")
        if st.button("← Upload a file", use_container_width=True):
            st.session_state["current_step"] = 0
            st.rerun()
        st.stop()

    df_original = st.session_state["df_original"]
    df_cleaned = st.session_state["df_cleaned"]
    op_results = st.session_state["operation_results"]
    file_meta = st.session_state["file_meta"]
    orig_name = file_meta.get("filename", "data")
    base_name = orig_name.rsplit(".", 1)[0]
    orig_ext = orig_name.rsplit(".", 1)[-1] if "." in orig_name else "csv"

    n_rows_before = len(df_original)
    n_cols_before = len(df_original.columns)
    n_rows_after = len(df_cleaned)
    n_cols_after = len(df_cleaned.columns)
    n_ops_run = st.session_state.get("n_ops_run", 0)

    # ── 0. Trust Banner ──
    render_trust_banner()

    # ── 1. What Changed? Hero ──
    render_what_changed_hero()

    # ── 2. Compute transformation analysis ──
    rename_map = st.session_state.get("column_rename_mapping", {})
    analysis = compute_and_store_analysis(df_original, df_cleaned, op_results, rename_map)
    m = analysis["summary_metrics"]

    # ── 3. Transformation Overview ──
    render_change_overview(analysis)

    # ── 4. Before vs After Health Score ──
    original_profiler_res = st.session_state.get("profiler_result")
    if original_profiler_res is not None:
        from core.profiler import Profiler
        clean_profiler_res = Profiler().profile(df_cleaned)
        orig_score = original_profiler_res.health_score
        clean_score = clean_profiler_res.health_score
        orig_issues = original_profiler_res.metrics["total_issues"]
        clean_issues = clean_profiler_res.metrics["total_issues"]

        st.markdown("<h4 style='margin-top:20px; margin-bottom:12px;'>📈 Data Quality Improvement</h4>", unsafe_allow_html=True)
        col_score1, col_score2 = st.columns(2)
        with col_score1:
            st.markdown(
                f"""
                <div style="background:#FEE2E2; border:1px solid #FCA5A5; border-radius:14px; padding:16px 20px; text-align:center; color:#991B1B; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; opacity:0.85;">Original Health Score</div>
                    <div style="font-size:2.8rem; font-weight:800; margin:8px 0; line-height:1;">{orig_score}%</div>
                    <div style="font-size:0.8rem; font-weight:500;">{orig_issues} quality issues detected</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_score2:
            score_bg = "#D1FAE5"
            text_color = "#065F46"
            border_color_s = "#A7F3D0"
            if clean_score < 90:
                score_bg = "#FEF3C7"
                text_color = "#92400E"
                border_color_s = "#FDE68A"
            st.markdown(
                f"""
                <div style="background:{score_bg}; border:1px solid {border_color_s}; border-radius:14px; padding:16px 20px; text-align:center; color:{text_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; opacity:0.85;">Cleaned Health Score</div>
                    <div style="font-size:2.8rem; font-weight:800; margin:8px 0; line-height:1;">{clean_score}%</div>
                    <div style="font-size:0.8rem; font-weight:500;">{clean_issues} issues remaining</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ── 5. Change Categories (expandable, with before/after) ──
    render_change_categories(analysis)

    st.divider()

    # ── 6-8. Detailed breakdowns ──
    render_missing_value_details(analysis, df_original, df_cleaned)
    render_duplicate_removal_details(analysis)
    render_date_correction_details(analysis)
    render_text_cleanup_details(analysis)
    render_type_conversion_details(analysis)

    if any([
        analysis["cell_diffs"], analysis["rows_removed"],
    ]):
        st.divider()

    # ── 9. Column Impact Dashboard ──
    render_column_impact_dashboard(analysis)

    st.divider()

    # ── 10. Transformation Timeline ──
    render_transformation_timeline(analysis)

    st.divider()

    # ── Raw Data View (replaces old diff view) ──
    render_section("📋 Raw Data View", "")
    view_mode = st.radio(
        "View",
        ["✅ Cleaned", "📋 Original"],
        horizontal=True,
        key="view_toggle",
    )
    if view_mode == "📋 Original":
        st.dataframe(df_original, use_container_width=True)
    else:
        st.dataframe(df_cleaned, use_container_width=True)

    # ── Operations Detail (collapsed) ──
    with st.expander("📊 Operation Details (technical)", expanded=False):
        if not op_results:
            st.info("No operations were run.")
        else:
            for entry in op_results:
                op_name = _DISPLAY_NAMES.get(entry["op"], entry["op"])
                result = entry.get("result", {})
                if "error" in result:
                    st.error(f"⚠️ {op_name} — {result['error']}")
                    continue
                parts = []
                for k, v in result.items():
                    if isinstance(v, dict) and v:
                        parts.append(f"{len(v)} errors")
                    elif isinstance(v, list) and v:
                        parts.append(f"{len(v)} items")
                    elif isinstance(v, (int, float)) and v:
                        label = k.replace("_", " ")
                        parts.append(f"{int(v)} {label}")
                summary = ", ".join(parts) if parts else "No changes"
                st.markdown(f"✅ **{op_name}** — {summary}")

    st.divider()

    st.subheader("Download your results")

    orig_diag = st.session_state.get("orig_diagnosis_for_report")
    if orig_diag is None:
        orig_diag = st.session_state["diagnosis"]
    issue_rows = [d for d in orig_diag if d["status"] != "clean"]
    report_filename = f"{base_name}_issues_report.csv"
    report_csv = b""
    if issue_rows:
        report_df = pd.DataFrame([{
            "Column": d["column_name"],
            "Status": d["status"],
            "Missing %": d["missing_pct"],
            "Duplicates": d["duplicate_values"],
            "Issues": "; ".join(d["issues_found"]),
        } for d in issue_rows])
        report_csv = report_df.to_csv(index=False).encode("utf-8")

    if orig_ext.lower() in ("xlsx", "xls"):
        buf = BytesIO()
        df_cleaned.to_excel(buf, index=False, engine="openpyxl")
        file_bytes = buf.getvalue()
        dl_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        dl_ext = orig_ext
    else:
        file_bytes = df_cleaned.to_csv(index=False).encode("utf-8-sig")
        dl_mime = "text/csv"
        dl_ext = "csv"

    dl_filename = f"{base_name}_cleaned.{dl_ext}"

    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(dl_filename, file_bytes)
        zf.writestr(report_filename, report_csv)
    zip_data = zip_buf.getvalue()

    dl1, dl2, dl3 = st.columns(3)

    with dl1:
        st.markdown(
            f'<div class="_ds-dl-card">'
            f'<span class="icon">📄</span>'
            f'<h4>Cleaned file</h4>'
            f'<p>{dl_ext.upper()} · {n_rows_after:,} rows · {get_size_str(len(file_bytes))}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download cleaned file", file_bytes, dl_filename, dl_mime,
            key="dl_cleaned", use_container_width=True,
        )

    with dl2:
        if issue_rows:
            st.markdown(
                f'<div class="_ds-dl-card">'
                f'<span class="icon">📊</span>'
                f'<h4>Issues report</h4>'
                f'<p>{len(issue_rows)} columns with issues · {get_size_str(len(report_csv))}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download issues report", report_csv, report_filename, "text/csv",
                key="dl_report", use_container_width=True,
            )
        else:
            st.markdown(
                f'<div class="_ds-dl-card" style="opacity:0.7">'
                f'<span class="icon">📊</span>'
                f'<h4>Issues report</h4>'
                f'<p>No issues found</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇️ Download issues report", report_csv, report_filename, "text/csv",
                key="dl_report", use_container_width=True, disabled=True,
            )

    with dl3:
        st.markdown(
            f'<div class="_ds-dl-card">'
            f'<span class="icon">📦</span>'
            f'<h4>Full package</h4>'
            f'<p>Cleaned file + report · {get_size_str(len(zip_data))}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download ZIP", zip_data, f"{base_name}_sanitized_package.zip", "application/zip",
            key="dl_zip", use_container_width=True,
        )

    st.divider()

    # Differentiate bottom actions through label and placement (PROBLEM 21)
    st.caption("Start over will clear your file and all cleaning settings.")
    c_left, c_right = st.columns(2)
    with c_left:
        if st.button("← Clean again", use_container_width=True, key="btn_clean_again_bottom"):
            st.session_state["current_step"] = 2
            st.rerun()
    with c_right:
        if st.button("↺ Start over", use_container_width=True, key="btn_start_over_bottom"):
            start_over()


# ── Global Chrome / Shell Injection ──
current_step = st.session_state["current_step"]
inject_design_system()

# Render shell header and stepper (from ui/shell.py)
_render_header(current_step)
render_stepper(current_step)

# Render step titles and step content
if current_step == 0:
    render_step_upload()
elif current_step == 1:
    st.markdown(page_title("Data diagnostics report", "A column-by-column look at what needs cleaning."), unsafe_allow_html=True)
    render_step_report()
elif current_step == 2:
    st.markdown(page_title("Review & Apply Fixes", "Review detected issues, preview changes, and apply fixes confidently."), unsafe_allow_html=True)
    render_step_clean()
elif current_step == 3:
    st.markdown(page_title("Cleaning results", "Review the changes and download your cleaned data."), unsafe_allow_html=True)
    render_step_results()
