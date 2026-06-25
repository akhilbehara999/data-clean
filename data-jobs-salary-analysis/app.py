"""
Jobs in Data — Interactive Salary Analysis Dashboard
Built with Streamlit • Portfolio Project

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.data_loader import get_clean_data, get_summary_stats
from src.analysis import (
    salary_by_group, top_n_titles, bottom_n_titles, yearly_trends,
    remote_premium, experience_salary_growth, category_experience_matrix,
    country_analysis, test_remote_vs_inperson, anova_experience_salary,
    prepare_features, train_models, get_feature_importance, predict_salary
)
from src.visualizations import (
    plotly_category_bar, plotly_salary_histogram, plotly_salary_box,
    plotly_yearly_trend, plotly_experience_violin, plotly_country_bar,
    plotly_work_setting_sunburst, plotly_career_progression,
    plotly_feature_importance, plotly_heatmap_category_experience
)

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Jobs in Data — Salary Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────

st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Dark theme overrides */
    .stApp > header {
        background-color: transparent;
    }
    
    /* KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2d2d44;
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.15);
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #22d3ee);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 8px 0;
    }
    .kpi-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 500;
    }
    .kpi-icon {
        font-size: 1.5rem;
        margin-bottom: 4px;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.4rem;
        font-weight: 700;
        color: #e2e8f0;
        margin: 2rem 0 1rem 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #6366f1;
        display: inline-block;
    }
    
    /* Insight boxes */
    .insight-box {
        background: linear-gradient(135deg, #1e1e38 0%, #1a1a2e 100%);
        border-left: 4px solid #6366f1;
        border-radius: 0 12px 12px 0;
        padding: 16px 20px;
        margin: 12px 0;
        color: #cbd5e1;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }
    
    /* Sidebar */
    .css-1d391kg, [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #64748b;
        font-size: 0.8rem;
        padding: 2rem 0 1rem 0;
        border-top: 1px solid #2d2d44;
        margin-top: 3rem;
    }
    
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Prediction result */
    .prediction-result {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 2px solid #6366f1;
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        margin: 20px 0;
    }
    .prediction-value {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #22d3ee);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Load Data (cached)
# ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_data():
    return get_clean_data()

@st.cache_data(ttl=3600)
def load_stats(df):
    return get_summary_stats(df)

@st.cache_resource
def load_model(df):
    X, y, encoders, feature_names = prepare_features(df)
    results, models, splits = train_models(X, y)
    best_name = max(results, key=lambda k: results[k]["test_r2"])
    best_model = models[best_name]
    importance = get_feature_importance(best_model, feature_names)
    return best_model, encoders, feature_names, results, importance, best_name

df = load_data()
stats = load_stats(df)


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 Jobs in Data")
    st.markdown("**Salary & Market Analysis**")
    st.markdown("---")
    
    st.markdown("### 🔍 Filters")
    
    # Year filter
    years = sorted(df["work_year"].unique())
    selected_years = st.multiselect("📅 Work Year", years, default=years)
    
    # Category filter
    categories = sorted(df["job_category"].unique())
    selected_categories = st.multiselect("📁 Job Category", categories, default=categories)
    
    # Experience filter
    exp_levels = ["Entry-level", "Mid-level", "Senior", "Executive"]
    selected_exp = st.multiselect("🎯 Experience Level", exp_levels, default=exp_levels)
    
    # Work setting filter
    settings = sorted(df["work_setting"].unique())
    selected_settings = st.multiselect("🏢 Work Setting", settings, default=settings)
    
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align:center; color:#64748b; font-size:0.8rem;'>
        Dataset: <strong>{stats['total_jobs']:,}</strong> records<br>
        {stats['year_range']}<br><br>
        Built with ❤️ using Streamlit
    </div>
    """, unsafe_allow_html=True)


# Apply filters
df_filtered = df[
    (df["work_year"].isin(selected_years)) &
    (df["job_category"].isin(selected_categories)) &
    (df["experience_level"].isin(selected_exp)) &
    (df["work_setting"].isin(selected_settings))
]


# ──────────────────────────────────────────────
# Main Content — Tabs
# ──────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["🏠 Overview", "💰 Salary Explorer", "🌍 Geographic View", "🤖 Salary Predictor"])


# ═══════════════════════════════════════════════
# TAB 1: OVERVIEW
# ═══════════════════════════════════════════════

with tab1:
    st.markdown("# 📊 Jobs in Data — Market Overview")
    st.markdown("*Comprehensive analysis of **9,000+** data industry job listings across the globe.*")
    st.markdown("")
    
    # KPI Row
    filtered_stats = get_summary_stats(df_filtered) if len(df_filtered) > 0 else stats
    
    k1, k2, k3, k4, k5 = st.columns(5)
    
    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">📋</div>
            <div class="kpi-value">{filtered_stats['total_jobs']:,}</div>
            <div class="kpi-label">Total Jobs</div>
        </div>
        """, unsafe_allow_html=True)
    
    with k2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">💰</div>
            <div class="kpi-value">${filtered_stats['avg_salary_usd']:,.0f}</div>
            <div class="kpi-label">Avg Salary</div>
        </div>
        """, unsafe_allow_html=True)
    
    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">📊</div>
            <div class="kpi-value">${filtered_stats['median_salary_usd']:,.0f}</div>
            <div class="kpi-label">Median Salary</div>
        </div>
        """, unsafe_allow_html=True)
    
    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">🏠</div>
            <div class="kpi-value">{filtered_stats['pct_remote']}%</div>
            <div class="kpi-label">Remote Jobs</div>
        </div>
        """, unsafe_allow_html=True)
    
    with k5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">🌍</div>
            <div class="kpi-value">{filtered_stats['unique_countries']}</div>
            <div class="kpi-label">Countries</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Charts Row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(plotly_yearly_trend(df_filtered), use_container_width=True)
    
    with col2:
        st.plotly_chart(plotly_category_bar(df_filtered), use_container_width=True)
    
    # Charts Row 2
    col3, col4 = st.columns(2)
    
    with col3:
        st.plotly_chart(plotly_salary_histogram(df_filtered), use_container_width=True)
    
    with col4:
        # Employment type & work setting
        emp_counts = df_filtered["employment_type"].value_counts().reset_index()
        emp_counts.columns = ["Type", "Count"]
        from src.visualizations import apply_plotly_theme, PALETTE
        import plotly.express as px
        fig_emp = px.pie(emp_counts, values="Count", names="Type", hole=0.4,
                         title="Employment Type", color_discrete_sequence=PALETTE)
        st.plotly_chart(apply_plotly_theme(fig_emp), use_container_width=True)
    
    # Key Insights
    st.markdown('<div class="section-header">🔑 Key Insights</div>', unsafe_allow_html=True)
    
    top_cat = df_filtered.groupby("job_category")["salary_in_usd"].median().idxmax() if len(df_filtered) > 0 else "N/A"
    top_cat_salary = df_filtered.groupby("job_category")["salary_in_usd"].median().max() if len(df_filtered) > 0 else 0
    
    st.markdown(f"""
    <div class="insight-box">
        📈 <strong>Highest-paying category:</strong> {top_cat} with a median salary of <strong>${top_cat_salary:,.0f}</strong>
    </div>
    """, unsafe_allow_html=True)
    
    if len(df_filtered) > 0:
        senior_premium = df_filtered[df_filtered["experience_level"] == "Senior"]["salary_in_usd"].median()
        entry_salary = df_filtered[df_filtered["experience_level"] == "Entry-level"]["salary_in_usd"].median()
        if pd.notna(senior_premium) and pd.notna(entry_salary) and entry_salary > 0:
            growth = ((senior_premium - entry_salary) / entry_salary) * 100
            st.markdown(f"""
            <div class="insight-box">
                🚀 <strong>Senior Premium:</strong> Senior-level roles earn <strong>{growth:.0f}%</strong> more than entry-level 
                (${entry_salary:,.0f} → ${senior_premium:,.0f})
            </div>
            """, unsafe_allow_html=True)
        
        pct_ft = (df_filtered["employment_type"] == "Full-time").mean() * 100
        st.markdown(f"""
        <div class="insight-box">
            💼 <strong>{pct_ft:.1f}%</strong> of all positions are full-time roles, underscoring the industry's preference for permanent employment
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# TAB 2: SALARY EXPLORER
# ═══════════════════════════════════════════════

with tab2:
    st.markdown("# 💰 Salary Explorer")
    st.markdown("*Deep dive into salary distributions across roles, categories, and experience levels.*")
    st.markdown("")
    
    # Salary by category
    st.plotly_chart(plotly_salary_box(df_filtered, "job_category", "Salary Distribution by Job Category"), 
                    use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(plotly_experience_violin(df_filtered), use_container_width=True)
    
    with col2:
        st.plotly_chart(plotly_heatmap_category_experience(df_filtered), use_container_width=True)
    
    # Top & Bottom titles
    st.markdown('<div class="section-header">🏆 Highest & Lowest Paying Titles</div>', unsafe_allow_html=True)
    
    col_top, col_bot = st.columns(2)
    
    with col_top:
        st.markdown("**🔝 Top 10 Highest-Paying Titles** *(min 5 listings)*")
        top = top_n_titles(df_filtered, 10)
        if len(top) > 0:
            display_top = top[["Median", "Mean", "Count"]].copy()
            display_top["Median"] = display_top["Median"].apply(lambda x: f"${x:,.0f}")
            display_top["Mean"] = display_top["Mean"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(display_top, use_container_width=True)
        else:
            st.info("Not enough data with current filters")
    
    with col_bot:
        st.markdown("**🔻 Bottom 10 Lowest-Paying Titles** *(min 5 listings)*")
        bottom = bottom_n_titles(df_filtered, 10)
        if len(bottom) > 0:
            display_bot = bottom[["Median", "Mean", "Count"]].copy()
            display_bot["Median"] = display_bot["Median"].apply(lambda x: f"${x:,.0f}")
            display_bot["Mean"] = display_bot["Mean"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(display_bot, use_container_width=True)
        else:
            st.info("Not enough data with current filters")
    
    # Career progression
    st.markdown("")
    st.plotly_chart(plotly_career_progression(df_filtered), use_container_width=True)
    
    # Statistical test
    st.markdown('<div class="section-header">📊 Statistical Tests</div>', unsafe_allow_html=True)
    
    col_t1, col_t2 = st.columns(2)
    
    with col_t1:
        anova = anova_experience_salary(df_filtered)
        sig = "✅ Yes" if anova.get("significant_at_005") else "❌ No"
        st.markdown(f"""
        <div class="insight-box">
            <strong>ANOVA Test — Experience Level Effect on Salary</strong><br>
            F-statistic: {anova.get('f_statistic', 'N/A')} &nbsp;|&nbsp; p-value: {anova.get('p_value', 'N/A')}<br>
            Significant at α=0.05? {sig}
        </div>
        """, unsafe_allow_html=True)
    
    with col_t2:
        remote_test = test_remote_vs_inperson(df_filtered)
        if "error" not in remote_test:
            sig2 = "✅ Yes" if remote_test.get("significant_at_005") else "❌ No"
            st.markdown(f"""
            <div class="insight-box">
                <strong>T-Test — Remote vs In-Person Salary</strong><br>
                Remote mean: ${remote_test['remote_mean']:,.0f} &nbsp;|&nbsp; In-person mean: ${remote_test['inperson_mean']:,.0f}<br>
                Difference: ${remote_test['difference']:,.0f} &nbsp;|&nbsp; p-value: {remote_test['p_value']}<br>
                Significant at α=0.05? {sig2}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Not enough data for remote vs in-person comparison")


# ═══════════════════════════════════════════════
# TAB 3: GEOGRAPHIC VIEW
# ═══════════════════════════════════════════════

with tab3:
    st.markdown("# 🌍 Geographic Analysis")
    st.markdown("*How do salaries and job availability vary by location?*")
    st.markdown("")
    
    st.plotly_chart(plotly_country_bar(df_filtered, 15), use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Work setting comparison
        ws_agg = df_filtered.groupby("work_setting")["salary_in_usd"].agg(["median", "mean", "count"]).reset_index()
        ws_agg.columns = ["Work Setting", "Median", "Mean", "Count"]
        ws_agg = ws_agg.sort_values("Median", ascending=False)
        
        import plotly.graph_objects as go
        fig_ws = go.Figure()
        fig_ws.add_trace(go.Bar(x=ws_agg["Work Setting"], y=ws_agg["Mean"], name="Mean", marker_color="#6366f1"))
        fig_ws.add_trace(go.Bar(x=ws_agg["Work Setting"], y=ws_agg["Median"], name="Median", marker_color="#22d3ee"))
        fig_ws.update_layout(title="Salary by Work Setting", barmode="group", yaxis_title="Salary (USD)")
        st.plotly_chart(apply_plotly_theme(fig_ws), use_container_width=True)
    
    with col2:
        st.plotly_chart(plotly_work_setting_sunburst(df_filtered), use_container_width=True)
    
    # US vs non-US
    st.markdown('<div class="section-header">🇺🇸 US vs International</div>', unsafe_allow_html=True)
    
    col_us1, col_us2 = st.columns(2)
    
    us_data = df_filtered[df_filtered["is_us"] == 1]
    non_us_data = df_filtered[df_filtered["is_us"] == 0]
    
    with col_us1:
        us_med = us_data["salary_in_usd"].median() if len(us_data) > 0 else 0
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">🇺🇸</div>
            <div class="kpi-value">${us_med:,.0f}</div>
            <div class="kpi-label">US Median Salary ({len(us_data):,} jobs)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_us2:
        non_us_med = non_us_data["salary_in_usd"].median() if len(non_us_data) > 0 else 0
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon">🌍</div>
            <div class="kpi-value">${non_us_med:,.0f}</div>
            <div class="kpi-label">International Median ({len(non_us_data):,} jobs)</div>
        </div>
        """, unsafe_allow_html=True)
    
    if us_med > 0 and non_us_med > 0:
        gap = ((us_med - non_us_med) / non_us_med) * 100
        st.markdown(f"""
        <div class="insight-box">
            💡 US-based roles pay <strong>{gap:.0f}%</strong> more than international roles on a median basis. 
            This reflects higher cost of living and the concentration of major tech companies in the US.
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# TAB 4: SALARY PREDICTOR
# ═══════════════════════════════════════════════

with tab4:
    st.markdown("# 🤖 Salary Predictor")
    st.markdown("*Machine learning model trained on the dataset to estimate salary based on your inputs.*")
    st.markdown("")
    
    # Train model
    with st.spinner("Training models... ⚡"):
        best_model, encoders, feature_names, model_results, importance, best_name = load_model(df)
    
    # Model performance
    st.markdown('<div class="section-header">📈 Model Performance</div>', unsafe_allow_html=True)
    
    perf_cols = st.columns(len(model_results))
    for i, (name, res) in enumerate(model_results.items()):
        with perf_cols[i]:
            is_best = " 🏆" if name == best_name else ""
            st.markdown(f"""
            <div class="kpi-card">
                <div style="font-size:1rem; font-weight:600; color:#e2e8f0; margin-bottom:8px;">{name}{is_best}</div>
                <div style="color:#94a3b8; font-size:0.85rem;">
                    Test R²: <strong style="color:#6366f1">{res['test_r2']}</strong><br>
                    CV R²: <strong style="color:#22d3ee">{res['cv_r2_mean']} ± {res['cv_r2_std']}</strong><br>
                    MAE: <strong style="color:#f59e0b">${res['mae']:,.0f}</strong><br>
                    RMSE: <strong>${res['rmse']:,.0f}</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Feature importance
    if len(importance) > 0:
        st.plotly_chart(plotly_feature_importance(importance), use_container_width=True)
    
    st.markdown("---")
    
    # Prediction Form
    st.markdown('<div class="section-header">🎯 Predict Your Salary</div>', unsafe_allow_html=True)
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        pred_category = st.selectbox("Job Category", sorted(df["job_category"].unique()), key="pred_cat")
        pred_exp = st.selectbox("Experience Level", ["Entry-level", "Mid-level", "Senior", "Executive"], key="pred_exp")
    
    with col_f2:
        pred_setting = st.selectbox("Work Setting", sorted(df["work_setting"].unique()), key="pred_setting")
        pred_emp = st.selectbox("Employment Type", sorted(df["employment_type"].unique()), key="pred_emp")
    
    with col_f3:
        pred_size = st.selectbox("Company Size", ["S", "M", "L"], format_func=lambda x: {"S": "Small", "M": "Medium", "L": "Large"}[x], key="pred_size")
        pred_country = st.selectbox("Country Group", sorted(df["country_group"].unique()), key="pred_country")
    
    if st.button("🔮 Predict Salary", type="primary", use_container_width=True):
        input_dict = {
            "job_category": pred_category,
            "experience_level": pred_exp,
            "work_setting": pred_setting,
            "employment_type": pred_emp,
            "company_size": pred_size,
            "country_group": pred_country,
        }
        
        predicted = predict_salary(best_model, encoders, feature_names, input_dict)
        
        # Get comparable actual salaries for confidence range
        mask = (df["job_category"] == pred_category) & (df["experience_level"] == pred_exp)
        comparable = df[mask]["salary_in_usd"]
        
        st.markdown(f"""
        <div class="prediction-result">
            <div style="color:#94a3b8; font-size:1rem; margin-bottom:8px;">Estimated Annual Salary</div>
            <div class="prediction-value">${predicted:,.0f}</div>
            <div style="color:#64748b; font-size:0.85rem; margin-top:12px;">
                Using: {best_name} (R² = {model_results[best_name]['test_r2']})
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if len(comparable) >= 5:
            q25, q75 = comparable.quantile([0.25, 0.75])
            st.markdown(f"""
            <div class="insight-box">
                📊 <strong>Market Context:</strong> For {pred_exp} {pred_category} roles, 
                actual salaries range from <strong>${q25:,.0f}</strong> (25th percentile) 
                to <strong>${q75:,.0f}</strong> (75th percentile) with a median of 
                <strong>${comparable.median():,.0f}</strong> (based on {len(comparable)} records)
            </div>
            """, unsafe_allow_html=True)
    
    # Model caveats
    st.markdown("")
    with st.expander("⚠️ Model Limitations & Caveats"):
        st.markdown("""
        **Important notes about this prediction model:**
        
        1. **R² Score**: The model achieves a moderate R² score, which is expected for salary prediction 
           with limited features. Salary depends on many factors not captured here (specific company, 
           negotiation skills, exact location within a country, education, etc.)
        
        2. **Feature limitations**: The model uses categorical groupings (job category, country group) 
           rather than fine-grained features. A "Data Scientist" at a FAANG company vs a startup 
           will have very different salaries.
        
        3. **Data bias**: The dataset skews heavily toward US-based, full-time positions. 
           Predictions for underrepresented groups may be less reliable.
        
        4. **No temporal adjustment**: The model doesn't account for inflation or market changes 
           across the years in the dataset.
        
        5. **Use as directional guidance**: Treat predictions as ballpark estimates, not exact figures. 
           Always reference actual job postings and market data for salary negotiations.
        """)


# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────

st.markdown("""
<div class="footer">
    <strong>Jobs in Data — Salary & Market Analysis</strong><br>
    Built with Python, Streamlit & Plotly | Data Analysis Portfolio Project<br>
    © 2024 | <a href="https://github.com/akhilbehara999/data-jobs-salary-analysis" style="color:#6366f1;">View on GitHub</a>
</div>
""", unsafe_allow_html=True)
