"""
Visualization functions for the Jobs in Data project.
Generates both Matplotlib/Seaborn (for notebook) and Plotly (for dashboard) charts.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ──────────────────────────────────────────────
# Theme Setup
# ──────────────────────────────────────────────

# Matplotlib/Seaborn dark theme
PALETTE = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#06b6d4", "#22d3ee",
           "#10b981", "#34d399", "#f59e0b", "#f97316", "#ef4444", "#ec4899"]

def setup_matplotlib_theme():
    """Configure a premium dark theme for matplotlib."""
    plt.rcParams.update({
        "figure.facecolor": "#0f0f1a",
        "axes.facecolor": "#1a1a2e",
        "axes.edgecolor": "#2d2d44",
        "axes.labelcolor": "#e2e8f0",
        "text.color": "#e2e8f0",
        "xtick.color": "#94a3b8",
        "ytick.color": "#94a3b8",
        "grid.color": "#2d2d44",
        "grid.alpha": 0.5,
        "figure.figsize": (12, 6),
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "legend.facecolor": "#1a1a2e",
        "legend.edgecolor": "#2d2d44",
    })
    sns.set_palette(PALETTE)


# ──────────────────────────────────────────────
# Plotly Theme (for Streamlit)
# ──────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,15,26,0.8)",
    font=dict(family="Inter, sans-serif", color="#e2e8f0"),
    title_font=dict(size=18, color="#e2e8f0"),
    margin=dict(l=40, r=40, t=60, b=40),
    colorway=PALETTE,
)


def apply_plotly_theme(fig):
    """Apply the premium dark theme to a Plotly figure."""
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_xaxes(gridcolor="#2d2d44", gridwidth=0.5)
    fig.update_yaxes(gridcolor="#2d2d44", gridwidth=0.5)
    return fig


# ──────────────────────────────────────────────
# Matplotlib Charts (for Notebook)
# ──────────────────────────────────────────────

def plot_category_distribution(df: pd.DataFrame):
    """Bar chart of job count by category."""
    setup_matplotlib_theme()
    counts = df["job_category"].value_counts()
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color=PALETTE[:len(counts)], edgecolor="none")
    ax.set_xlabel("Number of Jobs")
    ax.set_title("Job Distribution by Category")
    ax.grid(axis="x", alpha=0.3)
    for bar, val in zip(bars, counts.values[::-1]):
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
                f"{val:,}", va="center", fontsize=10, color="#94a3b8")
    plt.tight_layout()
    return fig


def plot_yearly_trends(df: pd.DataFrame):
    """Line chart of job count and avg salary by year."""
    setup_matplotlib_theme()
    yearly = df.groupby("work_year").agg(
        count=("salary_in_usd", "count"),
        avg_salary=("salary_in_usd", "mean")
    )
    
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(yearly.index, yearly["count"], color="#6366f1", alpha=0.7, label="Job Count", width=0.4)
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Job Count", color="#6366f1")
    ax1.tick_params(axis="y", labelcolor="#6366f1")
    
    ax2 = ax1.twinx()
    ax2.plot(yearly.index, yearly["avg_salary"], color="#22d3ee", marker="o", linewidth=2.5, label="Avg Salary (USD)")
    ax2.set_ylabel("Average Salary (USD)", color="#22d3ee")
    ax2.tick_params(axis="y", labelcolor="#22d3ee")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    
    fig.suptitle("Year-over-Year: Job Count & Average Salary", fontsize=14, fontweight="bold", y=1.02)
    fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.95))
    plt.tight_layout()
    return fig


def plot_salary_distribution(df: pd.DataFrame):
    """Histogram + KDE of salary distribution."""
    setup_matplotlib_theme()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.hist(df["salary_in_usd"], bins=60, color="#6366f1", alpha=0.6, edgecolor="none", density=True)
    df["salary_in_usd"].plot.kde(ax=ax, color="#22d3ee", linewidth=2.5)
    ax.set_xlabel("Salary (USD)")
    ax.set_ylabel("Density")
    ax.set_title("Salary Distribution (USD)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.axvline(df["salary_in_usd"].median(), color="#f59e0b", linestyle="--", linewidth=1.5, label=f"Median: ${df['salary_in_usd'].median():,.0f}")
    ax.legend()
    plt.tight_layout()
    return fig


def plot_salary_by_category(df: pd.DataFrame):
    """Box plot of salary by job category."""
    setup_matplotlib_theme()
    order = df.groupby("job_category")["salary_in_usd"].median().sort_values(ascending=False).index
    fig, ax = plt.subplots(figsize=(14, 7))
    bp = sns.boxplot(data=df, y="job_category", x="salary_in_usd", order=order,
                     palette=PALETTE, fliersize=2, linewidth=1.2, ax=ax)
    ax.set_xlabel("Salary (USD)")
    ax.set_ylabel("")
    ax.set_title("Salary Distribution by Job Category")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    return fig


def plot_salary_by_experience(df: pd.DataFrame):
    """Violin plot of salary by experience level."""
    setup_matplotlib_theme()
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.violinplot(data=df, x="experience_level", y="salary_in_usd", order=order,
                   palette=PALETTE[:4], inner="box", ax=ax)
    ax.set_ylabel("Salary (USD)")
    ax.set_xlabel("Experience Level")
    ax.set_title("Salary Distribution by Experience Level")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    return fig


def plot_top_titles(df: pd.DataFrame, n: int = 15):
    """Horizontal bar chart of top-paying job titles."""
    setup_matplotlib_theme()
    agg = df.groupby("job_title")["salary_in_usd"].agg(["median", "count"])
    agg = agg[agg["count"] >= 5].sort_values("median", ascending=True).tail(n)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(agg.index, agg["median"], color=PALETTE[0], edgecolor="none")
    ax.set_xlabel("Median Salary (USD)")
    ax.set_title(f"Top {n} Highest-Paying Job Titles (min 5 listings)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    for bar, val in zip(bars, agg["median"]):
        ax.text(bar.get_width() + 1000, bar.get_y() + bar.get_height()/2,
                f"${val:,.0f}", va="center", fontsize=9, color="#94a3b8")
    plt.tight_layout()
    return fig


def plot_work_setting_comparison(df: pd.DataFrame):
    """Grouped bar chart comparing salaries across work settings."""
    setup_matplotlib_theme()
    agg = df.groupby("work_setting")["salary_in_usd"].agg(["mean", "median"]).sort_values("median", ascending=False)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(agg))
    w = 0.35
    ax.bar(x - w/2, agg["mean"], w, label="Mean", color="#6366f1")
    ax.bar(x + w/2, agg["median"], w, label="Median", color="#22d3ee")
    ax.set_xticks(x)
    ax.set_xticklabels(agg.index)
    ax.set_ylabel("Salary (USD)")
    ax.set_title("Salary by Work Setting")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend()
    plt.tight_layout()
    return fig


def plot_country_salaries(df: pd.DataFrame, top_n: int = 15):
    """Bar chart of average salary by top countries."""
    setup_matplotlib_theme()
    top = df["company_location"].value_counts().head(top_n).index
    subset = df[df["company_location"].isin(top)]
    agg = subset.groupby("company_location")["salary_in_usd"].median().sort_values(ascending=True)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = [PALETTE[0] if c != "United States" else "#f59e0b" for c in agg.index]
    ax.barh(agg.index, agg.values, color=colors, edgecolor="none")
    ax.set_xlabel("Median Salary (USD)")
    ax.set_title(f"Median Salary by Country (Top {top_n} by Job Count)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    plt.tight_layout()
    return fig


def plot_experience_growth_by_category(df: pd.DataFrame):
    """Line chart showing salary growth across experience levels per category."""
    setup_matplotlib_theme()
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    top_cats = df["job_category"].value_counts().head(6).index
    subset = df[df["job_category"].isin(top_cats)]
    
    pivot = subset.pivot_table(values="salary_in_usd", index="experience_level",
                                columns="job_category", aggfunc="median")
    pivot = pivot.reindex(order)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, col in enumerate(pivot.columns):
        ax.plot(pivot.index, pivot[col], marker="o", linewidth=2.5, label=col, color=PALETTE[i % len(PALETTE)])
    ax.set_xlabel("Experience Level")
    ax.set_ylabel("Median Salary (USD)")
    ax.set_title("Career Progression: Salary Growth by Category")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    plt.tight_layout()
    return fig


def plot_employment_type_pie(df: pd.DataFrame):
    """Pie/donut chart of employment type distribution."""
    setup_matplotlib_theme()
    counts = df["employment_type"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        counts, labels=counts.index, autopct="%1.1f%%",
        colors=PALETTE[:len(counts)], pctdistance=0.85,
        wedgeprops=dict(width=0.4, edgecolor="#0f0f1a")
    )
    for t in autotexts:
        t.set_fontsize(10)
        t.set_color("#e2e8f0")
    ax.set_title("Employment Type Distribution")
    plt.tight_layout()
    return fig


def plot_company_size_distribution(df: pd.DataFrame):
    """Bar chart of company size distribution."""
    setup_matplotlib_theme()
    counts = df["company_size_label"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(counts.index, counts.values, color=PALETTE[:3], edgecolor="none")
    ax.set_ylabel("Number of Jobs")
    ax.set_title("Company Size Distribution")
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 30,
                f"{val:,}", ha="center", fontsize=11, color="#e2e8f0")
    plt.tight_layout()
    return fig


def plot_feature_importance(importance_df: pd.DataFrame):
    """Horizontal bar chart of feature importance."""
    setup_matplotlib_theme()
    fig, ax = plt.subplots(figsize=(8, 5))
    imp = importance_df.sort_values("Importance", ascending=True)
    ax.barh(imp["Feature"], imp["Importance"], color="#6366f1", edgecolor="none")
    ax.set_xlabel("Importance")
    ax.set_title("Feature Importance for Salary Prediction")
    plt.tight_layout()
    return fig


# ──────────────────────────────────────────────
# Plotly Charts (for Streamlit Dashboard)
# ──────────────────────────────────────────────

def plotly_category_bar(df: pd.DataFrame):
    """Interactive bar chart of jobs by category."""
    counts = df["job_category"].value_counts().reset_index()
    counts.columns = ["Category", "Count"]
    fig = px.bar(counts, x="Count", y="Category", orientation="h",
                 color="Count", color_continuous_scale="Viridis",
                 title="Job Distribution by Category")
    fig.update_layout(showlegend=False, yaxis=dict(autorange="reversed"))
    return apply_plotly_theme(fig)


def plotly_salary_histogram(df: pd.DataFrame):
    """Interactive salary distribution."""
    fig = px.histogram(df, x="salary_in_usd", nbins=50, 
                       title="Salary Distribution (USD)",
                       labels={"salary_in_usd": "Salary (USD)"},
                       color_discrete_sequence=["#6366f1"])
    fig.add_vline(x=df["salary_in_usd"].median(), line_dash="dash",
                  line_color="#f59e0b", annotation_text=f"Median: ${df['salary_in_usd'].median():,.0f}")
    return apply_plotly_theme(fig)


def plotly_salary_box(df: pd.DataFrame, group_col: str = "job_category", title: str = "Salary by Category"):
    """Interactive box plot."""
    order = df.groupby(group_col)["salary_in_usd"].median().sort_values(ascending=False).index.tolist()
    fig = px.box(df, x="salary_in_usd", y=group_col, color=group_col,
                 category_orders={group_col: order},
                 title=title, labels={"salary_in_usd": "Salary (USD)"})
    fig.update_layout(showlegend=False)
    return apply_plotly_theme(fig)


def plotly_yearly_trend(df: pd.DataFrame):
    """Interactive year-over-year trend."""
    yearly = df.groupby("work_year").agg(
        count=("salary_in_usd", "count"),
        avg_salary=("salary_in_usd", "mean"),
        median_salary=("salary_in_usd", "median"),
    ).reset_index()
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=yearly["work_year"], y=yearly["count"], name="Job Count",
                         marker_color="#6366f1", opacity=0.7), secondary_y=False)
    fig.add_trace(go.Scatter(x=yearly["work_year"], y=yearly["avg_salary"], name="Avg Salary",
                             line=dict(color="#22d3ee", width=3), mode="lines+markers"), secondary_y=True)
    fig.update_yaxes(title_text="Job Count", secondary_y=False)
    fig.update_yaxes(title_text="Average Salary (USD)", secondary_y=True)
    fig.update_layout(title="Year-over-Year: Job Count & Average Salary")
    return apply_plotly_theme(fig)


def plotly_experience_violin(df: pd.DataFrame):
    """Interactive violin plot by experience level."""
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    fig = px.violin(df, x="experience_level", y="salary_in_usd", color="experience_level",
                    category_orders={"experience_level": order}, box=True, points=False,
                    title="Salary Distribution by Experience Level",
                    labels={"salary_in_usd": "Salary (USD)", "experience_level": "Experience Level"})
    fig.update_layout(showlegend=False)
    return apply_plotly_theme(fig)


def plotly_country_bar(df: pd.DataFrame, top_n: int = 15):
    """Interactive country salary comparison."""
    top = df["company_location"].value_counts().head(top_n).index
    subset = df[df["company_location"].isin(top)]
    agg = subset.groupby("company_location")["salary_in_usd"].agg(["median", "count"]).reset_index()
    agg.columns = ["Country", "Median Salary", "Job Count"]
    agg = agg.sort_values("Median Salary", ascending=True)
    
    fig = px.bar(agg, x="Median Salary", y="Country", orientation="h",
                 color="Median Salary", color_continuous_scale="Viridis",
                 hover_data=["Job Count"],
                 title=f"Median Salary by Country (Top {top_n})")
    fig.update_layout(showlegend=False)
    return apply_plotly_theme(fig)


def plotly_work_setting_sunburst(df: pd.DataFrame):
    """Sunburst chart: work setting × experience level."""
    fig = px.sunburst(df, path=["work_setting", "experience_level"], values="salary_in_usd",
                       title="Work Setting & Experience Level (by Total Salary Volume)",
                       color_discrete_sequence=PALETTE)
    return apply_plotly_theme(fig)


def plotly_career_progression(df: pd.DataFrame):
    """Line chart of salary growth across experience levels by category."""
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    top_cats = df["job_category"].value_counts().head(6).index
    subset = df[df["job_category"].isin(top_cats)]
    
    pivot = subset.pivot_table(values="salary_in_usd", index="experience_level",
                                columns="job_category", aggfunc="median").reindex(order).reset_index()
    pivot_melted = pivot.melt(id_vars="experience_level", var_name="Category", value_name="Median Salary")
    
    fig = px.line(pivot_melted, x="experience_level", y="Median Salary", color="Category",
                  markers=True, title="Career Progression: Salary by Experience & Category",
                  labels={"experience_level": "Experience Level", "Median Salary": "Median Salary (USD)"})
    fig.update_traces(line=dict(width=3))
    return apply_plotly_theme(fig)


def plotly_feature_importance(importance_df: pd.DataFrame):
    """Interactive feature importance chart."""
    imp = importance_df.sort_values("Importance", ascending=True)
    fig = px.bar(imp, x="Importance", y="Feature", orientation="h",
                 title="Feature Importance for Salary Prediction",
                 color="Importance", color_continuous_scale="Viridis")
    fig.update_layout(showlegend=False)
    return apply_plotly_theme(fig)


def plotly_heatmap_category_experience(df: pd.DataFrame):
    """Heatmap of median salary by category × experience."""
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    pivot = df.pivot_table(values="salary_in_usd", index="job_category",
                            columns="experience_level", aggfunc="median")
    cols = [c for c in order if c in pivot.columns]
    pivot = pivot[cols]
    
    fig = px.imshow(pivot, text_auto="$,.0f", aspect="auto",
                    color_continuous_scale="Viridis",
                    title="Median Salary Heatmap: Category × Experience Level",
                    labels=dict(x="Experience Level", y="Job Category", color="Median Salary"))
    return apply_plotly_theme(fig)
