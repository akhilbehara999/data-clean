"""Application shell: shared header, visual stepper, and page-chrome wrapper.

Rendered consistently at the top of every page so the four-step wizard
(Upload → Report → Clean → Results) always reads as one connected product.
"""
from __future__ import annotations

import streamlit as st

from ui.theme import C, R, TOKENS, inject_design_system, page_title

# Ordered step metadata. ``key`` matches the navigation order in app.py.
STEPS = [
    {"key": "upload",  "label": "Upload",   "icon": "1"},
    {"key": "report",  "label": "Diagnose", "icon": "2"},
    {"key": "clean",   "label": "Clean",    "icon": "3"},
    {"key": "results", "label": "Report",   "icon": "4"},
]


def _stepper_css() -> str:
    c, sh = C, TOKENS["shadow"]
    return f"""
<style>
/* ── App header ─────────────────────────────────────────────── */
.ds-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0 18px 0;
    border-bottom: 1px solid {c['border']};
    margin-bottom: 24px;
}}
.ds-header .ds-brand {{ display: flex; align-items: center; gap: 14px; }}
.ds-header .ds-logo {{
    width: 42px; height: 42px;
    border-radius: {R['md']};
    background: linear-gradient(135deg, {c['brand']} 0%, {c['brand_hover']} 100%);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.25rem;
    box-shadow: {sh['sm']};
    flex-shrink: 0;
}}
.ds-header .ds-wordmark {{
    font-size: 1.2rem;
    font-weight: 700;
    color: {c['text_strong']};
    letter-spacing: -0.02em;
    line-height: 1.1;
}}
.ds-header .ds-tagline {{
    font-size: 0.82rem;
    color: {c['text_muted']};
    line-height: 1.2;
    font-weight: 500;
}}
.ds-header .ds-step-label {{
    font-size: 0.8rem;
    font-weight: 500;
    color: {c['text_muted']};
    text-align: right;
    line-height: 1.3;
}}
.ds-header .ds-step-label strong {{ color: {c['brand']}; font-weight: 600; }}

/* ── Stepper Button Grid overrides ── */
div[data-testid="stHorizontalBlock"]:first-of-type {{
    gap: 12px !important;
    margin-bottom: 28px !important;
}}
div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="stColumn"] {{
    padding-left: 0 !important;
    padding-right: 0 !important;
}}
div[data-testid="stHorizontalBlock"]:first-of-type button {{
    border-radius: 14px !important;
    border: 1.5px solid {c['border']} !important;
    padding: 10px 14px !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    color: {c['text']} !important;
    background: {c['surface']} !important;
    box-shadow: {sh['xs']} !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    height: 52px !important;
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
/* Hover state */
div[data-testid="stHorizontalBlock"]:first-of-type button:hover:not(:disabled) {{
    border-color: {c['brand_border']} !important;
    color: {c['brand']} !important;
    background: {c['brand_softer']} !important;
    box-shadow: {sh['sm']} !important;
    transform: translateY(-1.5px) !important;
}}
/* Active State */
div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"] {{
    background: {c['brand_soft']} !important;
    border: 2px solid {c['brand']} !important;
    color: {c['brand']} !important;
    font-weight: 600 !important;
    box-shadow: 0 0 0 3px rgba(108, 76, 241, 0.12) !important;
}}
div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"]:hover {{
    background: {c['brand_soft']} !important;
    border-color: {c['brand']} !important;
    color: {c['brand']} !important;
    transform: none !important;
}}
/* Disabled steps */
div[data-testid="stHorizontalBlock"]:first-of-type button:disabled {{
    border-color: {c['border']} !important;
    background: {c['surface_alt']} !important;
    color: {c['text_subtle']} !important;
    opacity: 0.6 !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}}

/* narrow screens: adjust labels */
@media (max-width: 640px) {{
    div[data-testid="stHorizontalBlock"]:first-of-type button {{
        font-size: 0.8rem !important;
        padding: 6px !important;
    }}
}}
</style>
"""


def _render_header(current_step: int) -> None:
    """Render the slim app header with wordmark + current-step label."""
    step = STEPS[current_step]
    
    st.markdown(_stepper_css(), unsafe_allow_html=True)
    
    # 2-column layout: brand logo & details on left, step label on right
    col_brand, col_step = st.columns([8.2, 1.8])
    
    with col_brand:
        st.markdown(
            f"""
            <div class="ds-brand">
                <div class="ds-logo">✨</div>
                <div>
                    <div class="ds-wordmark">Data Sanitizer</div>
                    <div class="ds-tagline">Clean. Analyze. Transform. <span style="font-weight:400; color:{C['text_muted']}; margin-left: 8px; border-left: 1px solid {C['border']}; padding-left: 8px;">Professional data cleaning and quality analysis.</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
    with col_step:
        st.markdown(
            f"""
            <div class="ds-step-label" style="margin-top: 6px;">
                Step <strong>{current_step + 1}</strong> of {len(STEPS)}<br>
                <strong style="color: {C['brand']};">{step["label"]}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
    st.markdown(f"<div style='border-bottom: 1px solid {C['border']}; margin-bottom: 24px; margin-top: 12px;'></div>", unsafe_allow_html=True)


def render_stepper(current_step: int) -> None:
    """Render the horizontal 4-node progress stepper.

    ``current_step`` is 0-indexed (0 = Upload … 3 = Results).
    Completed/previous/available steps are clickable to navigate backward and forward.
    """
    has_orig = st.session_state.get("df_original") is not None
    has_clean = st.session_state.get("df_cleaned") is not None

    # Calculate step eligibility
    eligible = {
        0: True,      # Upload is always eligible
        1: has_orig,  # Report eligible if original file is loaded
        2: has_orig,  # Clean is eligible if original file is loaded
        3: has_clean, # Results eligible if cleaned file exists
    }

    steps_metadata = [
        {"name": "Upload",   "icon": "📤", "val": 0},
        {"name": "Diagnose", "icon": "📊", "val": 1},
        {"name": "Clean",    "icon": "🧼", "val": 2},
        {"name": "Report",   "icon": "✨", "val": 3},
    ]
    cols = st.columns(4)
    for i, step in enumerate(steps_metadata):
        val = step["val"]
        name = step["name"]
        icon = step["icon"]

        # Formulate premium dynamic labels
        if val < current_step:
            label = f"✅ {name}"
        elif val == current_step:
            label = f"{icon} {name}"
        else:
            label = f"⚪ {name}"

        with cols[i]:
            if val == current_step:
                # Current step: highlighted primary button, clicking does nothing
                st.button(label, key=f"stepper_{i}", type="primary", use_container_width=True)
            elif eligible.get(val, False):
                # Eligible step: clickable secondary button to navigate
                if st.button(label, key=f"stepper_{i}", type="secondary", use_container_width=True):
                    st.session_state["current_step"] = val
                    st.rerun()
            else:
                # Ineligible step: disabled secondary button
                st.button(label, key=f"stepper_{i}", type="secondary", use_container_width=True, disabled=True)


def page_chrome(step: int, title: str, subtitle: str = "") -> None:
    """Inject theme, then render header + stepper + page title.

    Call at the top of each page so every screen shares the same chrome.
    """
    inject_design_system()
    _render_header(step)
    render_stepper(step)
    if title:
        st.markdown(page_title(title, subtitle), unsafe_allow_html=True)
