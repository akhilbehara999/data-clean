"""Design system for the Data Sanitizer.

Single source of truth for the application's visual language: color tokens,
typography, radii, spacing, and a global CSS layer injected into Streamlit.

All custom HTML elsewhere in the app should reference the ``.ds-*`` utility
classes defined here rather than hardcoding hex values.
"""
from __future__ import annotations

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Design tokens
# ─────────────────────────────────────────────────────────────────────────────
TOKENS = {
    "color": {
        # Brand (indigo/violet gradient palette)
        "brand": "#6C4CF1",
        "brand_hover": "#8B5CF6",
        "brand_active": "#A855F7",
        "brand_soft": "#F3F0FF",
        "brand_softer": "#F8F6FF",
        "brand_border": "#E0D7FF",
        # Status
        "success": "#10B981",
        "success_soft": "#ECFDF5",
        "success_border": "#A7F3D0",
        "warning": "#F59E0B",
        "warning_soft": "#FFFBEB",
        "warning_border": "#FDE68A",
        "danger": "#EF4444",
        "danger_soft": "#FEF2F2",
        "danger_border": "#FECACA",
        # Slate text ramp
        "text_strong": "#0F172A",
        "text": "#334155",
        "text_muted": "#64748B",
        "text_subtle": "#94A3B8",
        # Surfaces & lines
        "bg": "#F8FAFC",      # Very light gray background
        "surface": "#FFFFFF", # Pure white cards
        "surface_alt": "#F1F5F9",
        "border": "#E2E8F0",
        "border_strong": "#CBD5E1",
    },
    "radius": {"sm": "8px", "md": "12px", "lg": "16px", "xl": "24px", "pill": "999px"},
    "shadow": {
        "xs": "0 1px 2px 0 rgba(15, 23, 42, 0.05)",
        "sm": "0 4px 6px -1px rgba(15, 23, 42, 0.05), 0 2px 4px -1px rgba(15, 23, 42, 0.025)",
        "md": "0 10px 15px -3px rgba(108, 76, 241, 0.08), 0 4px 6px -2px rgba(108, 76, 241, 0.04)",
        "ring": "0 0 0 3px rgba(108, 76, 241, 0.15)",
    },
    "space": {"2": "2px", "4": "4px", "8": "8px", "12": "12px", "16": "16px",
              "20": "20px", "24": "24px", "32": "32px", "40": "40px"},
    "font": {
        "sans": 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
                'Helvetica, Arial, sans-serif',
        "mono": '"JetBrains Mono", ui-monospace, SFMono-Regular, "SF Mono", '
                'Menlo, Consolas, monospace',
    },
}

C = TOKENS["color"]   # color shorthand
R = TOKENS["radius"]  # radius shorthand


def status_tone(status: str) -> str:
    """Map a diagnostics status to a tone name used by badges/labels."""
    return {
        "clean": "success",
        "attention": "warning",
        "critical": "danger",
    }.get(status, "neutral")


# ─────────────────────────────────────────────────────────────────────────────
# Global CSS layer
# ─────────────────────────────────────────────────────────────────────────────
def _build_css() -> str:
    c, r, sh, f = C, R, TOKENS["shadow"], TOKENS["font"]
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
/* ── Base typography ───────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: {f['sans']};
    color: {c['text']};
}}
h1, h2, h3, h4, h5, h6 {{
    font-family: {f['sans']};
    color: {c['text_strong']};
    letter-spacing: -0.015em;
    font-weight: 600;
}}
h1 {{ letter-spacing: -0.025em; font-weight: 700; }}
code, pre, .stCode, [data-testid="stCodeBlock"] {{
    font-family: {f['mono']} !important;
}}
.stApp {{ background-color: {c['bg']}; }}

/* ── Sidebar ────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {c['surface']} 0%, {c['surface_alt']} 100%);
    border-right: 1px solid {c['border']};
}}
section[data-testid="stSidebar"] .stMarkdown h2 {{
    font-size: 1.05rem;
    margin-bottom: 2px;
    color: {c['text_strong']};
}}
section[data-testid="stSidebar"] .stCode {{
    font-size: 0.75rem !important;
    border-radius: {r['md']};
    background: {c['bg']} !important;
    border: 1px solid {c['border']} !important;
}}
/* Session log code block */
section[data-testid="stSidebar"] [data-testid="stCode"] {{
    border-radius: {r['md']};
}}

/* Buttons: consistent radius, refined weight */
.stButton > button, .stDownloadButton > button {{
    border-radius: {r['md']};
    font-weight: 500;
    transition: all 0.15s ease;
    border: 1px solid {c['border']};
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: {c['border_strong']};
}}
/* ── Primary buttons → indigo gradient ────────────────────── */
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"],
.stButton > button[data-testid="baseButton-primary"],
[data-testid="stBaseButton-primary"] {{
    background: linear-gradient(135deg, {c['brand']} 0%, {c['brand_hover']} 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: {r['md']} !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(79,70,229,0.28) !important;
    transition: all 0.18s ease !important;
}}
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {{
    background: linear-gradient(135deg, {c['brand_hover']} 0%, {c['brand_active']} 100%) !important;
    box-shadow: 0 6px 20px rgba(79,70,229,0.38) !important;
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"]:active,
button[data-testid="baseButton-primary"]:active,
[data-testid="stBaseButton-primary"]:active {{
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(79,70,229,0.25) !important;
}}

/* ── Download buttons → indigo, full-width ──────────────────── */
[data-testid="stDownloadButton"] > button,
[data-testid="stBaseButton-secondary"].stDownloadButton,
.stDownloadButton > button {{
    background: linear-gradient(135deg, {c['brand']} 0%, {c['brand_hover']} 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: {r['md']} !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(79,70,229,0.25) !important;
    transition: all 0.18s ease !important;
    width: 100%;
}}
[data-testid="stDownloadButton"] > button:hover,
.stDownloadButton > button:hover {{
    background: linear-gradient(135deg, {c['brand_hover']} 0%, {c['brand_active']} 100%) !important;
    box-shadow: 0 6px 20px rgba(79,70,229,0.35) !important;
    transform: translateY(-1px);
}}
[data-testid="stDownloadButton"] > button:active,
.stDownloadButton > button:active {{
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(79,70,229,0.2) !important;
}}

/* Hide sidebar completely */
[data-testid="collapsedControl"],
section[data-testid="stSidebar"] {{
    display: none !important;
    visibility: hidden !important;
}}

/* Sliders → indigo */
[data-baseweb="slider"] [role="thumb"],
[data-baseweb="slider"] [class*="track"] {{
    /* base-web slider accent handled via :checked fallback below */
}}

/* Inputs: focus ring */
.stTextInput > div > div > input:focus,
.stSelectbox [aria-expanded="true"] {{
    border-color: {c['brand']} !important;
    box-shadow: {sh['ring']} !important;
}}

/* ── st.metric → premium card ──────────────────────────────── */
div[data-testid="metric-container"],
[data-testid="stMetric"] {{
    background: linear-gradient(135deg, {c['bg']} 0%, {c['surface']} 100%);
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    padding: 20px 24px;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 4px 16px rgba(79,70,229,0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}}
div[data-testid="metric-container"]::before,
[data-testid="stMetric"]::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, {c['brand']}, #818CF8);
    border-radius: {r['lg']} {r['lg']} 0 0;
}}
div[data-testid="metric-container"]:hover,
[data-testid="stMetric"]:hover {{
    transform: translateY(-3px);
    box-shadow: 0 10px 20px rgba(15,23,42,0.05), 0 20px 32px rgba(79,70,229,0.10);
    border-color: {c['border_strong']};
}}
[data-testid="stMetric"] label {{
    color: #475569 !important;
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}}
[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    color: {c['text_strong']} !important;
    font-size: 1.65rem !important;
    font-weight: 700;
    letter-spacing: -0.025em;
    line-height: 1.1;
}}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {{
    font-size: 0.8rem !important;
    font-weight: 500;
    margin-top: 4px;
}}

/* ── Dataframes: refined borders ───────────────────────────── */
.stDataFrame, [data-testid="stDataFrame"] {{
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    overflow: hidden;
}}
.stDataFrame [data-testid="stDataFrameResizable"] {{
    border-radius: {r['lg']} !important;
}}

/* ── Expanders ──────────────────────────────────────────────── */
details[data-testid="stExpander"] {{
    border: 1px solid {c['border']} !important;
    border-radius: {r['lg']} !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04);
    margin-bottom: 8px;
    overflow: hidden;
    transition: box-shadow 0.15s ease;
}}
details[data-testid="stExpander"]:hover {{
    box-shadow: 0 2px 8px rgba(15,23,42,0.07);
    border-color: {c['border_strong']} !important;
}}
details[data-testid="stExpander"] summary {{
    font-weight: 500;
    color: {c['text_strong']};
    padding: 14px 16px;
    background: {c['surface']};
}}
details[data-testid="stExpander"][open] summary {{
    border-bottom: 1px solid {c['border']};
    background: {c['bg']};
}}
details[data-testid="stExpander"] > div {{
    padding: 4px 0;
}}

/* ── Dividers ──────────────────────────────────────────────── */
hr {{
    border-color: {c['border']} !important;
    margin: 24px 0 !important;
}}

/* ─────────────────────────────────────────────────────────────
   Design-system utility classes (.ds-*)
   ─────────────────────────────────────────────────────────── */
.ds-page-title {{
    font-size: 2rem;
    font-weight: 700;
    color: {c['text_strong']};
    letter-spacing: -0.03em;
    margin: 0 0 4px 0;
}}
.ds-page-sub {{
    color: {c['text_muted']};
    font-size: 0.8rem;
    font-weight: 400;
    margin: 0 0 4px 0;
}}

/* Card */
.ds-card {{
    background-color: {c['bg']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    padding: 20px;
    box-shadow: {sh['xs']};
}}
.ds-card-soft {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    padding: 20px;
}}

/* Badge / chip */
.ds-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: {r['pill']};
    line-height: 1.4;
    white-space: nowrap;
    border: 1px solid transparent;
}}
.ds-badge-success {{ color: {c['success']}; background: {c['success_soft']}; border-color: {c['success_border']}; }}
.ds-badge-warning {{ color: {c['warning']}; background: {c['warning_soft']}; border-color: {c['warning_border']}; }}
.ds-badge-danger  {{ color: {c['danger']};  background: {c['danger_soft']};  border-color: {c['danger_border']}; }}
.ds-badge-brand   {{ color: {c['brand']};   background: {c['brand_soft']};   border-color: {c['brand_border']}; }}
.ds-badge-neutral {{ color: {c['text_muted']}; background: {c['surface_alt']}; border-color: {c['border']}; }}

/* Chip (operation pill) */
.ds-chip {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.8rem;
    font-weight: 500;
    padding: 5px 11px;
    border-radius: {r['pill']};
    color: {c['brand']};
    background: {c['brand_soft']};
    border: 1px solid {c['brand_border']};
    margin: 0 4px 6px 0;
}}
.ds-chip-arrow {{
    color: {c['text_subtle']};
    font-weight: 700;
    margin: 0 2px;
    align-self: center;
}}

/* Section header */
.ds-section {{
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {c['text_muted']};
    margin: 0 0 10px 0;
}}
.ds-card-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: {c['text_strong']};
}}
.ds-metadata {{
    font-size: 0.8rem;
    font-weight: 400;
    color: {c['text_muted']};
}}

/* Empty state */
.ds-empty {{
    text-align: center;
    padding: 48px 24px;
    border: 1px solid {c['border']};
    border-radius: {r['xl']};
    background-color: {c['surface']};
}}
.ds-empty .ds-empty-icon {{
    font-size: 2.6rem;
    margin-bottom: 8px;
    line-height: 1;
}}
.ds-empty .ds-empty-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: {c['text_strong']};
    margin-bottom: 4px;
}}
.ds-empty .ds-empty-hint {{
    font-size: 0.9rem;
    color: {c['text_muted']};
}}

/* Drop zone */
.ds-dropzone {{
    text-align: center;
    padding: 36px 32px;
    border: 2px dashed {c['brand']};
    border-radius: {r['xl']};
    background: {c['surface']};
    margin-bottom: 12px;
}}
.ds-dropzone .ds-dropzone-icon {{
    font-size: 2.2rem;
    margin-bottom: 8px;
    color: {c['brand']};
    display: block;
}}
.ds-dropzone .ds-dropzone-title {{
    font-size: 1.1rem;
    font-weight: 600;
    color: {c['text_strong']};
    margin-bottom: 4px;
}}
.ds-dropzone .ds-dropzone-hint {{
    font-size: 0.85rem;
    color: {c['text_muted']};
}}
.ds-formats {{
    display: flex;
    gap: 6px;
    justify-content: center;
    margin-top: 10px;
}}
.ds-format {{
    font-family: {f['mono']};
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: {r['sm']};
    color: {c['text_muted']};
    background: {c['bg']};
    border: 1px solid {c['border']};
}}

/* ── File Uploader Styling ── */
[data-testid="stFileUploader"] section {{
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}}
[data-testid="stFileUploader"] section > div {{
    border: 2px dashed {c['brand_border']} !important;
    border-radius: {r['xl']} !important;
    background: {c['surface']} !important;
    padding: 44px 32px !important;
    box-shadow: {sh['sm']} !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}}
[data-testid="stFileUploader"] section > div:hover {{
    border-color: {c['brand_hover']} !important;
    background: {c['brand_softer']} !important;
    box-shadow: {sh['md']} !important;
    transform: translateY(-2px) !important;
}}
/* Browse button alignment inside Streamlit uploader */
[data-testid="stFileUploader"] section button {{
    display: none !important;
}}
[data-testid="stFileUploader"] section button:hover {{
    display: none !important;
}}
[data-testid="stFileUploader"] [data-testid="stMarkdownContainer"] p {{
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: {c['text_strong']} !important;
}}
[data-testid="stFileUploader"] section > div > div > small {{
    font-size: 0.82rem !important;
    color: {c['text_muted']} !important;
}}

/* Hero (upload) */
.ds-hero {{
    text-align: center;
    padding: 24px 0 32px 0;
}}
.ds-hero h1 {{
    font-size: 2.5rem;
    font-weight: 700;
    color: {c['text_strong']};
    letter-spacing: -0.03em;
    margin: 0 0 10px 0;
    line-height: 1.15;
}}
.ds-hero p {{
    color: {c['text_muted']};
    font-size: 1.15rem;
    margin: 0 auto;
    max-width: 600px;
    line-height: 1.5;
}}

/* Trust Cards Grid */
.ds-trust-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-top: 32px;
    margin-bottom: 12px;
}}
.ds-trust-card {{
    background: {c['surface']} !important;
    border: 1px solid {c['border']} !important;
    border-radius: {r['lg']} !important;
    padding: 24px 20px !important;
    text-align: center !important;
    box-shadow: {sh['xs']} !important;
    transition: all 0.2s ease !important;
}}
.ds-trust-card:hover {{
    border-color: {c['brand_border']} !important;
    box-shadow: {sh['sm']} !important;
    transform: translateY(-2px) !important;
}}
.ds-trust-card .icon {{
    font-size: 1.75rem !important;
    margin-bottom: 8px !important;
    display: inline-block !important;
}}
.ds-trust-card h4 {{
    margin: 0 0 6px 0 !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: {c['text_strong']} !important;
}}
.ds-trust-card p {{
    margin: 0 !important;
    font-size: 0.8rem !important;
    color: {c['text_muted']} !important;
    line-height: 1.4 !important;
}}

/* Circular Health Score Card */
.ds-health-card {{
    background: {c['surface']} !important;
    border: 1px solid {c['border']} !important;
    border-radius: {r['lg']} !important;
    padding: 24px !important;
    text-align: center !important;
    box-shadow: {sh['sm']} !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
    height: 100% !important;
}}
.ds-health-ring-wrap {{
    display: flex !important;
    justify-content: center !important;
    margin: 18px 0 !important;
}}
.ds-health-ring {{
    position: relative !important;
    width: 120px !important;
    height: 120px !important;
    border-radius: 50% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
.ds-health-ring::after {{
    content: attr(data-score) !important;
    position: absolute !important;
    width: 100px !important;
    height: 100px !important;
    background: {c['surface']} !important;
    border-radius: 50% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-weight: 700 !important;
    font-size: 1.5rem !important;
    color: {c['text_strong']} !important;
}}

/* ── Upgraded stToggle label (PROBLEM 11) ── */
[data-testid="stToggle"] label {{
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    color: #334155 !important;
}}

/* ── Upgraded columns internal padding normalization (PROBLEM 16) ── */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    padding-left: 0 !important;
    padding-right: 12px !important;
}}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
    padding-right: 0 !important;
    padding-left: 12px !important;
}}

/* ── Upgraded Radio selection override (PROBLEM 19) ── */
[data-testid="stRadio"] [role="radio"][aria-checked="true"] + div {{
    color: #4F46E5 !important;
}}
[data-testid="stRadio"] label [data-testid="stWidgetLabel"] {{
    font-weight: 500 !important;
}}
[data-baseweb="radio"] [role="radio"] div:first-child {{
    border-color: #4F46E5 !important;
    background-color: #4F46E5 !important;
}}

/* ── Upgraded Download cards CSS (PROBLEM 20) ── */
._ds-dl-card {{
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 24px 20px 16px 20px;
    text-align: center;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    box-shadow: 0 1px 3px rgba(15,23,42,0.05);
    margin-bottom: 8px;
}}
._ds-dl-card:hover {{
    border-color: #C7D2FE;
    box-shadow: 0 4px 16px rgba(79,70,229,0.10);
}}
._ds-dl-card .icon {{
    font-size: 2rem;
    margin-bottom: 8px;
    display: block;
}}
._ds-dl-card h4 {{
    margin: 0 0 4px 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #0F172A;
}}
._ds-dl-card p {{
    margin: 0 0 0 0;
    font-size: 0.8rem;
    color: #64748B;
}}

/* ── Issue Cards Redesign ── */
.ds-issue-card {{
    background: {c['surface']} !important;
    border: 1px solid {c['border']} !important;
    border-radius: {r['lg']} !important;
    padding: 18px 20px !important;
    margin-bottom: 12px !important;
    box-shadow: {sh['xs']} !important;
    display: flex !important;
    align-items: flex-start !important;
    gap: 16px !important;
    transition: all 0.2s ease !important;
}}
.ds-issue-card:hover {{
    border-color: {c['brand_border']} !important;
    box-shadow: {sh['sm']} !important;
    transform: translateY(-1px) !important;
}}
.ds-issue-card .issue-icon {{
    font-size: 1.5rem !important;
    padding: 8px !important;
    border-radius: {r['md']} !important;
    background: {c['bg']} !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
.ds-issue-card .issue-content {{
    flex: 1 !important;
}}
.ds-issue-card h5 {{
    margin: 0 0 4px 0 !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: {c['text_strong']} !important;
}}
.ds-issue-card p {{
    margin: 0 !important;
    font-size: 0.82rem !important;
    color: {c['text_muted']} !important;
    line-height: 1.45 !important;
}}

/* ── Review & Apply Fixes Page ───────────────────────── */
.ds-fix-summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}}
.ds-fix-summary-card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    padding: 18px 20px;
    text-align: center;
    box-shadow: {sh['xs']};
    transition: all 0.2s ease;
}}
.ds-fix-summary-card:hover {{
    transform: translateY(-2px);
    box-shadow: {sh['sm']};
}}
.ds-fix-summary-value {{
    font-size: 2rem;
    font-weight: 800;
    color: {c['text_strong']};
    line-height: 1.1;
    margin-bottom: 4px;
}}
.ds-fix-summary-label {{
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: {c['text_muted']};
}}

/* ── Quality Journey ──────────────────────────────────── */
.ds-quality-journey {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 24px;
    padding: 20px 24px;
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    box-shadow: {sh['xs']};
    margin-bottom: 24px;
}}
.ds-qj-score {{
    text-align: center;
    padding: 12px 28px;
    border-radius: {r['md']};
    min-width: 140px;
}}
.ds-qj-score--before {{
    background: {c['danger_soft']};
    border: 1px solid {c['danger_border']};
}}
.ds-qj-score--after {{
    background: {c['success_soft']};
    border: 1px solid {c['success_border']};
}}
.ds-qj-value {{
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1;
}}
.ds-qj-label {{
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 6px;
}}
.ds-qj-arrow {{
    font-size: 1.6rem;
    font-weight: 700;
    color: {c['brand']};
}}

/* ── Fix Card (Issue-Based) ────────────────────────────── */
.ds-fix-card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    margin-bottom: 16px;
    box-shadow: {sh['xs']};
    transition: all 0.2s ease;
    overflow: hidden;
}}
.ds-fix-card:hover {{
    box-shadow: {sh['sm']};
    border-color: {c['border_strong']};
}}
.ds-fix-card--critical {{ border-left: 4px solid {c['danger']}; }}
.ds-fix-card--warning {{ border-left: 4px solid {c['warning']}; }}
.ds-fix-card--info {{ border-left: 4px solid {c['brand']}; }}
.ds-fix-card-header {{
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 20px;
    background: {c['bg']};
    border-bottom: 1px solid {c['border']};
}}
.ds-fix-card-icon {{
    width: 40px;
    height: 40px;
    border-radius: {r['md']};
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    background: {c['surface']};
    border: 1px solid {c['border']};
    flex-shrink: 0;
}}
.ds-fix-card-title-area {{ flex: 1; min-width: 0; }}
.ds-fix-card-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: {c['text_strong']};
    margin: 0 0 2px 0;
}}
.ds-fix-card-subtitle {{
    font-size: 0.78rem;
    color: {c['text_muted']};
    margin: 0;
}}
.ds-fix-card-body {{ padding: 16px 20px; }}
.ds-fix-card-desc {{
    font-size: 0.85rem;
    color: {c['text']};
    line-height: 1.5;
    margin-bottom: 12px;
}}
.ds-fix-card-meta {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 12px;
    font-size: 0.78rem;
    color: {c['text_muted']};
}}
.ds-fix-card-meta strong {{ color: {c['text']}; }}
.ds-fix-card-action {{
    font-size: 0.82rem;
    color: #065F46;
    background: {c['success_soft']};
    border: 1px solid {c['success_border']};
    border-radius: {r['md']};
    padding: 10px 14px;
    margin-bottom: 12px;
}}
.ds-fix-card-actions {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 20px;
    border-top: 1px solid {c['border']};
    background: {c['bg']};
}}

/* Severity & Confidence Pills */
.ds-severity-pill {{
    display: inline-flex;
    align-items: center;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: {r['pill']};
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
}}
.ds-severity-pill--critical {{ color: #DC2626; background: #FEF2F2; border: 1px solid #FECACA; }}
.ds-severity-pill--warning {{ color: #D97706; background: #FFFBEB; border: 1px solid #FDE68A; }}
.ds-severity-pill--info {{ color: #2563EB; background: #EFF6FF; border: 1px solid #BFDBFE; }}
.ds-confidence-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: {r['pill']};
    border: 1px solid {c['border']};
    background: {c['surface']};
    color: {c['text_muted']};
}}
.ds-confidence-badge--high {{ color: #059669; background: #ECFDF5; border-color: #A7F3D0; }}
.ds-confidence-badge--medium {{ color: #D97706; background: #FFFBEB; border-color: #FDE68A; }}
.ds-confidence-badge--low {{ color: #DC2626; background: #FEF2F2; border-color: #FECACA; }}

/* Cleaning Plan */
.ds-cleaning-plan {{
    background: {c['brand_soft']};
    border: 1px solid {c['brand_border']};
    border-left: 4px solid {c['brand']};
    border-radius: {r['lg']};
    padding: 18px 22px;
    margin-bottom: 24px;
}}
.ds-cleaning-plan h4 {{
    margin: 0 0 10px 0;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {c['brand']};
}}
.ds-cleaning-plan ul {{
    margin: 0;
    padding-left: 20px;
    font-size: 0.85rem;
    color: #4338CA;
    line-height: 1.75;
}}
.ds-cleaning-plan li {{ margin-bottom: 2px; }}
.ds-cleaning-plan li strong {{ color: {c['text_strong']}; }}

/* Preview Table */
.ds-preview-wrap {{
    border: 1px solid {c['border']};
    border-radius: {r['md']};
    overflow: hidden;
    margin: 10px 0;
}}
.ds-preview-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
.ds-preview-table th {{
    background: {c['surface_alt']};
    color: {c['text_muted']};
    font-weight: 600;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 14px;
    text-align: left;
    border-bottom: 2px solid {c['border']};
}}
.ds-preview-table td {{
    padding: 8px 14px;
    border-bottom: 1px solid {c['border']};
    color: {c['text']};
}}
.ds-preview-table tr:last-child td {{ border-bottom: none; }}
.ds-prev-before {{
    color: {c['danger']}; background: {c['danger_soft']};
    text-decoration: line-through; padding: 2px 8px;
    border-radius: 4px; font-family: {f['mono']}; font-size: 0.78rem;
}}
.ds-prev-after {{
    color: {c['success']}; background: {c['success_soft']};
    font-weight: 500; padding: 2px 8px;
    border-radius: 4px; font-family: {f['mono']}; font-size: 0.78rem;
}}
.ds-prev-arrow {{ color: {c['text_subtle']}; padding: 0 8px; font-weight: 700; }}

/* Empty state for no fixes */
.ds-fix-empty {{
    text-align: center; padding: 48px 24px;
    border: 2px dashed {c['border']}; border-radius: {r['xl']};
    background: {c['surface']};
}}
.ds-fix-empty-icon {{ font-size: 2.5rem; margin-bottom: 12px; }}
.ds-fix-empty-title {{ font-size: 1.1rem; font-weight: 600; color: {c['text_strong']}; margin-bottom: 6px; }}
.ds-fix-empty-hint {{ font-size: 0.85rem; color: {c['text_muted']}; }}

/* ── What Changed? Experience ───────────────────────────── */
.ds-changed-hero {{
    background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 50%, #FDF2F8 100%);
    border: 1px solid {c['brand_border']};
    border-radius: {r['xl']};
    padding: 28px 32px;
    margin-bottom: 28px;
    text-align: center;
}}
.ds-changed-hero h2 {{ margin: 0 0 6px 0; font-size: 1.6rem; font-weight: 700; color: {c['text_strong']}; letter-spacing: -0.02em; }}
.ds-changed-hero p {{ margin: 0; font-size: 0.88rem; color: {c['text_muted']}; }}

.ds-change-overview {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
}}
.ds-change-overview-card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    padding: 18px 16px;
    text-align: center;
    box-shadow: {sh['xs']};
    transition: all 0.2s ease;
}}
.ds-change-overview-card:hover {{ transform: translateY(-2px); box-shadow: {sh['sm']}; border-color: {c['brand_border']}; }}
.ds-change-overview-icon {{ font-size: 1.5rem; margin-bottom: 6px; display: block; }}
.ds-change-overview-value {{ font-size: 1.8rem; font-weight: 800; color: {c['text_strong']}; line-height: 1.1; }}
.ds-change-overview-label {{ font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: {c['text_muted']}; margin-top: 4px; }}

.ds-change-category {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r['lg']};
    margin-bottom: 12px;
    overflow: hidden;
    box-shadow: {sh['xs']};
    transition: border-color 0.15s ease;
}}
.ds-change-category:hover {{ border-color: {c['border_strong']}; }}
.ds-change-category-header {{
    display: flex; align-items: center; gap: 12px;
    padding: 14px 18px; background: {c['bg']};
    border-bottom: 1px solid {c['border']};
}}
.ds-change-category-icon {{ font-size: 1.3rem; width: 36px; height: 36px; border-radius: {r['md']}; background: {c['surface']}; border: 1px solid {c['border']}; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.ds-change-category-title {{ flex: 1; font-weight: 600; color: {c['text_strong']}; font-size: 0.92rem; }}
.ds-change-category-count {{ font-size: 0.78rem; font-weight: 600; color: {c['brand']}; background: {c['brand_soft']}; border: 1px solid {c['brand_border']}; padding: 3px 10px; border-radius: {r['pill']}; white-space: nowrap; }}
.ds-change-category-body {{ padding: 16px 18px; }}

.ds-diff-inline {{
    display: inline-flex; align-items: center; gap: 6px;
    font-family: {f['mono']}; font-size: 0.8rem;
    padding: 3px 8px; border-radius: 6px;
}}
.ds-diff-inline-before {{ color: {c['danger']}; background: {c['danger_soft']}; text-decoration: line-through; }}
.ds-diff-inline-after {{ color: {c['success']}; background: {c['success_soft']}; font-weight: 600; }}
.ds-diff-inline-arrow {{ color: {c['text_subtle']}; font-weight: 700; text-decoration: none; }}

.ds-diff-table {{
    width: 100%; border-collapse: collapse;
    font-size: 0.84rem; font-family: {f['sans']};
}}
.ds-diff-table th {{
    background: {c['surface_alt']}; color: {c['text_muted']};
    font-weight: 600; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.05em; padding: 10px 14px; text-align: left;
    border-bottom: 2px solid {c['border']};
}}
.ds-diff-table td {{
    padding: 10px 14px; border-bottom: 1px solid {c['border']};
    color: {c['text']}; vertical-align: middle;
}}
.ds-diff-table tr:hover td {{ background: {c['bg']}; }}
.ds-diff-table .ds-cell-before {{
    color: {c['danger']}; background: {c['danger_soft']};
    text-decoration: line-through; padding: 2px 8px;
    border-radius: 4px; font-family: {f['mono']}; font-size: 0.8rem;
}}
.ds-diff-table .ds-cell-after {{
    color: {c['success']}; background: {c['success_soft']};
    font-weight: 500; padding: 2px 8px;
    border-radius: 4px; font-family: {f['mono']}; font-size: 0.8rem;
}}
.ds-diff-table .ds-cell-arrow {{ color: {c['text_subtle']}; font-weight: 700; padding: 0 6px; }}
.ds-diff-table .ds-cell-removed {{
    color: {c['text_subtle']}; background: {c['surface_alt']};
    text-decoration: line-through; font-style: italic; padding: 2px 8px;
    border-radius: 4px;
}}
.ds-diff-table .ds-cell-added {{
    color: {c['success']}; background: {c['success_soft']};
    font-weight: 500; padding: 2px 8px; border-radius: 4px;
}}
.ds-diff-table .ds-cell-null {{
    color: {c['text_subtle']}; font-style: italic; opacity: 0.7;
}}
.ds-diff-table .ds-cell-type-before {{
    font-family: {f['mono']}; font-size: 0.75rem; color: {c['danger']};
    background: {c['danger_soft']}; padding: 2px 6px; border-radius: 4px;
}}
.ds-diff-table .ds-cell-type-after {{
    font-family: {f['mono']}; font-size: 0.75rem; color: {c['success']};
    background: {c['success_soft']}; padding: 2px 6px; border-radius: 4px;
}}

.ds-change-sample-info {{
    font-size: 0.78rem; color: {c['text_muted']}; text-align: center;
    padding: 8px 12px; background: {c['bg']}; border-radius: {r['md']};
    border: 1px dashed {c['border']}; margin-top: 12px;
}}

.ds-change-timeline {{
    border-left: 3px solid {c['brand_border']};
    margin-left: 12px; padding-left: 24px;
}}
.ds-change-timeline-item {{
    position: relative; padding-bottom: 16px;
}}
.ds-change-timeline-item::before {{
    content: '';
    position: absolute; left: -31px; top: 4px;
    width: 12px; height: 12px; border-radius: 50%;
    background: {c['brand']}; border: 2px solid {c['surface']};
    box-shadow: 0 0 0 2px {c['brand_border']};
}}
.ds-change-timeline-step {{ font-weight: 600; color: {c['text_strong']}; font-size: 0.88rem; }}
.ds-change-timeline-detail {{ font-size: 0.82rem; color: {c['text_muted']}; margin-top: 2px; }}

.ds-column-impact-row {{
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0;
}}
.ds-column-impact-name {{
    font-family: {f['mono']}; font-size: 0.82rem; font-weight: 500;
    color: {c['text_strong']}; min-width: 120px;
}}
.ds-column-impact-bar {{
    flex: 1; height: 8px; background: {c['surface_alt']};
    border-radius: {r['pill']}; overflow: hidden;
}}
.ds-column-impact-fill {{
    height: 100%; border-radius: {r['pill']};
    background: linear-gradient(90deg, {c['brand']}, #818CF8);
    transition: width 0.5s ease;
}}
.ds-column-impact-count {{
    font-size: 0.78rem; font-weight: 600; color: {c['text_muted']};
    min-width: 50px; text-align: right;
}}
.ds-column-impact-types {{
    font-size: 0.72rem; color: {c['text_subtle']};
    min-width: 100px;
}}

.ds-trust-banner {{
    display: flex; align-items: center; justify-content: center; gap: 24px;
    padding: 14px 20px; background: {c['success_soft']};
    border: 1px solid {c['success_border']}; border-radius: {r['lg']};
    margin-bottom: 20px;
    font-size: 0.82rem; color: #065F46; font-weight: 500;
}}
.ds-trust-badge {{ display: inline-flex; align-items: center; gap: 6px; }}

/* Responsive */
@media (max-width: 768px) {{
    .ds-fix-summary {{ grid-template-columns: repeat(2, 1fr); }}
    .ds-quality-journey {{ flex-direction: column; gap: 12px; }}
    .ds-change-overview {{ grid-template-columns: repeat(2, 1fr); }}
    .ds-column-impact-row {{ flex-wrap: wrap; }}
    .ds-column-impact-bar {{ min-width: 100%; order: 3; }}
}}

/* ── Selection Cards ── */
.selection-card {{
    border: 1px solid {c['border']} !important;
    border-radius: {r['md']} !important;
    padding: 14px 12px !important;
    background: {c['surface']} !important;
    transition: all 0.2s ease !important;
    text-align: center !important;
    margin-bottom: 8px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: space-between !important;
    height: 165px !important;
    box-shadow: {sh['xs']} !important;
}}
.selection-card:hover {{
    border-color: {c['border_strong']} !important;
    box-shadow: {sh['sm']} !important;
}}
.selection-card.selected {{
    border-color: {c['brand']} !important;
    background: {c['brand_soft']} !important;
    box-shadow: 0 0 0 2px {c['brand_border']} !important;
}}
.selection-card-title {{
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    color: {c['text_strong']} !important;
}}
.selection-card-example {{
    font-size: 0.75rem !important;
    margin-top: 8px !important;
    padding: 6px 8px !important;
    background: {c['surface_alt']} !important;
    border-radius: 6px !important;
    border: 1px solid {c['border']} !important;
}}
</style>
"""


def inject_design_system() -> None:
    """Inject the global design-system stylesheet. Call at the top of every page."""
    st.markdown(_build_css(), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Markup helpers (return HTML strings; callers use st.markdown)
# ─────────────────────────────────────────────────────────────────────────────
def badge(text: str, tone: str = "neutral") -> str:
    """Return an HTML badge span. ``tone`` ∈ success/warning/danger/brand/neutral."""
    return f'<span class="ds-badge ds-badge-{tone}">{text}</span>'


def chip(text: str, icon: str = "") -> str:
    """Return an HTML chip span (operation pill)."""
    inner = f"{icon} {text}" if icon else text
    return f'<span class="ds-chip">{inner}</span>'


def chip_arrow() -> str:
    """Connector arrow between pipeline chips."""
    return '<span class="ds-chip-arrow">→</span>'


def empty_state(icon: str, title: str, hint: str) -> str:
    """Return an HTML empty-state block."""
    return (
        f'<div class="ds-empty">'
        f'<div class="ds-empty-icon">{icon}</div>'
        f'<div class="ds-empty-title">{title}</div>'
        f'<div class="ds-empty-hint">{hint}</div>'
        f'</div>'
    )


def dropzone(icon: str, title: str, hint: str) -> str:
    """Return an HTML drop-zone block."""
    return (
        f'<div class="ds-dropzone">'
        f'<div class="ds-dropzone-icon">{icon}</div>'
        f'<div class="ds-dropzone-title">{title}</div>'
        f'<div class="ds-dropzone-hint">{hint}</div>'
        f'<div class="ds-formats">'
        f'<span class="ds-format">CSV</span>'
        f'<span class="ds-format">XLSX</span>'
        f'<span class="ds-format">XLS</span>'
        f'</div>'
        f'</div>'
    )


def page_title(title: str, subtitle: str = "") -> str:
    """Return an HTML page title + subtitle block."""
    sub = f'<p class="ds-page-sub">{subtitle}</p>' if subtitle else ""
    return f'<div class="ds-page-title">{title}</div>{sub}'
