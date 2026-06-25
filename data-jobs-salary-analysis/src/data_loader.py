"""
Data loading and cleaning module for the Jobs in Data analysis project.
Handles CSV ingestion, type casting, feature engineering, and data validation.
"""

import pandas as pd
import numpy as np
import os


def load_raw_data(filepath: str = None) -> pd.DataFrame:
    """Load the raw CSV dataset."""
    if filepath is None:
        # Try common paths
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobs_in_data.csv"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs_in_data.csv"),
            "data/jobs_in_data.csv",
            "jobs_in_data.csv",
        ]
        for path in candidates:
            if os.path.exists(path):
                filepath = path
                break
        if filepath is None:
            raise FileNotFoundError("Could not find jobs_in_data.csv. Please provide the filepath.")
    
    df = pd.read_csv(filepath)
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and preprocess the dataset."""
    df = df.copy()
    
    # --- Remove exact duplicates ---
    df = df.drop_duplicates()
    
    # --- Fix dtypes ---
    df["work_year"] = df["work_year"].astype(int)
    df["salary"] = pd.to_numeric(df["salary"], errors="coerce")
    df["salary_in_usd"] = pd.to_numeric(df["salary_in_usd"], errors="coerce")
    
    # --- Drop rows with null salary ---
    df = df.dropna(subset=["salary_in_usd"])
    
    # --- Standardize text columns ---
    text_cols = ["job_title", "job_category", "salary_currency", "employee_residence",
                 "experience_level", "employment_type", "work_setting", "company_location", "company_size"]
    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
    
    return df.reset_index(drop=True)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features for analysis and modeling."""
    df = df.copy()
    
    # --- Experience level numeric rank ---
    exp_map = {"Entry-level": 1, "Mid-level": 2, "Senior": 3, "Executive": 4}
    df["experience_rank"] = df["experience_level"].map(exp_map).fillna(0).astype(int)
    
    # --- Salary bands ---
    df["salary_band"] = pd.cut(
        df["salary_in_usd"],
        bins=[0, 50000, 100000, 150000, 200000, 300000, float("inf")],
        labels=["<50K", "50K-100K", "100K-150K", "150K-200K", "200K-300K", "300K+"],
    )
    
    # --- Company size full label ---
    size_map = {"S": "Small", "M": "Medium", "L": "Large"}
    df["company_size_label"] = df["company_size"].map(size_map).fillna("Unknown")
    
    # --- Geographic grouping (top countries vs "Other") ---
    top_countries = df["company_location"].value_counts().head(10).index.tolist()
    df["country_group"] = df["company_location"].apply(
        lambda x: x if x in top_countries else "Other"
    )
    
    # --- Is US ---
    df["is_us"] = (df["company_location"] == "United States").astype(int)
    
    # --- Year as string for grouping ---
    df["work_year_str"] = df["work_year"].astype(str)
    
    return df


def get_clean_data(filepath: str = None) -> pd.DataFrame:
    """One-call pipeline: load → clean → engineer features."""
    df = load_raw_data(filepath)
    df = clean_data(df)
    df = engineer_features(df)
    return df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Generate key summary statistics for KPI cards."""
    return {
        "total_jobs": len(df),
        "unique_titles": df["job_title"].nunique(),
        "unique_categories": df["job_category"].nunique(),
        "unique_countries": df["company_location"].nunique(),
        "avg_salary_usd": round(df["salary_in_usd"].mean(), 2),
        "median_salary_usd": round(df["salary_in_usd"].median(), 2),
        "min_salary_usd": round(df["salary_in_usd"].min(), 2),
        "max_salary_usd": round(df["salary_in_usd"].max(), 2),
        "most_common_title": df["job_title"].mode().iloc[0] if len(df) > 0 else "N/A",
        "most_common_category": df["job_category"].mode().iloc[0] if len(df) > 0 else "N/A",
        "pct_remote": round((df["work_setting"] == "Remote").mean() * 100, 1),
        "pct_senior": round((df["experience_level"] == "Senior").mean() * 100, 1),
        "year_range": f"{df['work_year'].min()}-{df['work_year'].max()}",
    }


if __name__ == "__main__":
    df = get_clean_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    stats = get_summary_stats(df)
    for k, v in stats.items():
        print(f"  {k}: {v}")
