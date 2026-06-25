<div align="center">

# 📊 Jobs in Data — Salary & Market Analysis

**A comprehensive data analysis of 9,000+ data industry job listings, uncovering salary trends, geographic patterns, and career progression insights.**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)

[**🚀 Live Demo**](https://data-jobs-salary-analysis-zrjymrqkcvgo53tpxwq9uh.streamlit.app/) 

</div>

---

## 🎯 Project Overview

This project analyzes a dataset of **9,356 data industry job listings** to answer key questions about the modern data job market:

- 💰 **How much do data professionals earn** across different roles and experience levels?
- 🌍 **How do salaries vary globally**, and what's the US premium?
- 📈 **What's the career salary progression** from entry-level to executive?
- 🏠 **Does remote work pay more or less** than in-person roles?
- 🤖 **Can we predict salary** based on role, experience, and location?

## 📊 Key Findings

> **🔥 ML/AI roles command the highest salaries** — Machine Learning Engineers and AI Specialists earn 20-40% more than the industry median

> **📈 The Senior jump is the biggest career milestone** — Senior-level professionals earn 50-80% more than entry-level across all categories

> **🇺🇸 US dominance is clear** — US-based roles pay significantly more than international counterparts, even for the same job titles

> **🏠 Remote work is competitive** — Remote positions offer salaries comparable to in-person roles, with statistical testing to back it up

> **📊 Data Engineering leads in volume** — More job listings than any other category, reflecting high industry demand

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.9+** | Core language |
| **Pandas & NumPy** | Data manipulation & analysis |
| **Matplotlib & Seaborn** | Static visualizations (notebook) |
| **Plotly** | Interactive visualizations (dashboard) |
| **Scikit-learn** | Machine learning models |
| **Streamlit** | Interactive web dashboard |
| **SciPy** | Statistical hypothesis testing |

---

## 📁 Project Structure

```
data-jobs-salary-analysis/
├── 📁 data/
│   └── jobs_in_data.csv              # Raw dataset (9,356 records)
├── 📁 notebooks/
│   └── analysis.ipynb                # Full EDA notebook (8 sections)
├── 📁 src/
│   ├── __init__.py
│   ├── data_loader.py                # Data loading & feature engineering
│   ├── analysis.py                   # Statistical analysis & ML models
│   └── visualizations.py             # Chart generation (MPL + Plotly)
├── 📁 assets/
│   └── banner.png                    # Project banner
├── 📁 .streamlit/
│   └── config.toml                   # Dashboard theme config
├── app.py                            # Streamlit dashboard (4 tabs)
├── requirements.txt                  # Python dependencies
├── README.md
├── LICENSE
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/akhilbehara999/data-jobs-salary-analysis.git
cd data-jobs-salary-analysis

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Dashboard

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

### Run the Notebook

```bash
jupyter notebook notebooks/analysis.ipynb
```

---

## 📊 Dashboard Features

The interactive Streamlit dashboard has **4 tabs**:

| Tab | Features |
|---|---|
| 🏠 **Overview** | KPI cards, job trends, category distribution, employment type breakdown |
| 💰 **Salary Explorer** | Box plots, violin plots, heatmaps, top/bottom titles, statistical tests |
| 🌍 **Geographic View** | Country salary comparison, US vs international, work setting analysis |
| 🤖 **Salary Predictor** | ML model performance, feature importance, interactive salary prediction |

**Sidebar Filters:** Filter all visualizations by year, job category, experience level, and work setting.

---

## 🔬 Analysis Methodology

### Exploratory Data Analysis
- Distribution analysis with histograms and KDE plots
- Group comparisons using box plots and violin plots
- Cross-tabulation heatmaps for multi-dimensional analysis

### Statistical Testing
- **ANOVA** — Testing whether experience levels have significantly different salary distributions
- **Welch's t-test** — Comparing remote vs in-person salary means

### Predictive Modeling
- **Models trained:** Linear Regression, Random Forest, Gradient Boosting
- **Evaluation:** R², MAE, RMSE with 5-fold cross-validation
- **Honest assessment:** Model limitations are clearly documented (R² ~0.3-0.5 is expected given feature constraints)

---

## 📈 Dataset Details

| Feature | Description |
|---|---|
| `work_year` | Year of the job listing (2020-2024) |
| `job_title` | Specific role title (100+ unique titles) |
| `job_category` | Broad category (8 categories) |
| `salary_in_usd` | Annual salary normalized to USD |
| `experience_level` | Entry-level, Mid-level, Senior, Executive |
| `employment_type` | Full-time, Part-time, Contract, Freelance |
| `work_setting` | Remote, In-person, Hybrid |
| `company_location` | Company HQ country (70+ countries) |
| `company_size` | Small, Medium, Large |

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Open an issue for bugs or feature requests
- Submit a pull request with improvements
- Star the repo if you find it useful ⭐

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ as a Data Analysis Portfolio Project**

*If you found this useful, consider giving it a ⭐!*

</div>
