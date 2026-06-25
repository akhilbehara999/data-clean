"""
Analysis functions for the Jobs in Data project.
Contains statistical analysis, aggregations, and predictive modeling utilities.
"""

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error


# ──────────────────────────────────────────────
# Aggregation Helpers
# ──────────────────────────────────────────────

def salary_by_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Compute salary statistics grouped by a column."""
    agg = df.groupby(group_col)["salary_in_usd"].agg(
        ["mean", "median", "min", "max", "std", "count"]
    ).round(2).sort_values("median", ascending=False)
    agg.columns = ["Mean", "Median", "Min", "Max", "Std", "Count"]
    return agg


def top_n_titles(df: pd.DataFrame, n: int = 10, by: str = "median") -> pd.DataFrame:
    """Get top N job titles by salary metric."""
    agg = salary_by_group(df, "job_title")
    # Only include titles with at least 5 data points
    agg = agg[agg["Count"] >= 5]
    return agg.sort_values(by.capitalize(), ascending=False).head(n)


def bottom_n_titles(df: pd.DataFrame, n: int = 10, by: str = "median") -> pd.DataFrame:
    """Get bottom N job titles by salary metric."""
    agg = salary_by_group(df, "job_title")
    agg = agg[agg["Count"] >= 5]
    return agg.sort_values(by.capitalize(), ascending=True).head(n)


def yearly_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Job count and average salary by year."""
    return df.groupby("work_year").agg(
        job_count=("salary_in_usd", "count"),
        avg_salary=("salary_in_usd", "mean"),
        median_salary=("salary_in_usd", "median"),
    ).round(2)


def remote_premium(df: pd.DataFrame) -> pd.DataFrame:
    """Compare salaries across work settings."""
    return salary_by_group(df, "work_setting")


def experience_salary_growth(df: pd.DataFrame) -> pd.DataFrame:
    """Salary stats by experience level, ordered by seniority."""
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    agg = salary_by_group(df, "experience_level")
    agg = agg.reindex([x for x in order if x in agg.index])
    return agg


def category_experience_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot table: median salary by category × experience level."""
    order = ["Entry-level", "Mid-level", "Senior", "Executive"]
    pivot = df.pivot_table(
        values="salary_in_usd",
        index="job_category",
        columns="experience_level",
        aggfunc="median",
    )
    cols = [c for c in order if c in pivot.columns]
    return pivot[cols].round(0)


def country_analysis(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """Top N countries by job count with salary stats."""
    top_countries = df["company_location"].value_counts().head(top_n).index
    subset = df[df["company_location"].isin(top_countries)]
    return salary_by_group(subset, "company_location")


# ──────────────────────────────────────────────
# Statistical Tests
# ──────────────────────────────────────────────

def test_remote_vs_inperson(df: pd.DataFrame) -> dict:
    """T-test: is there a statistically significant salary difference between remote and in-person?"""
    remote = df[df["work_setting"] == "Remote"]["salary_in_usd"]
    inperson = df[df["work_setting"] == "In-person"]["salary_in_usd"]
    
    if len(remote) < 2 or len(inperson) < 2:
        return {"error": "Not enough data for test"}
    
    t_stat, p_value = stats.ttest_ind(remote, inperson, equal_var=False)
    return {
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_value, 6),
        "significant_at_005": p_value < 0.05,
        "remote_mean": round(remote.mean(), 2),
        "inperson_mean": round(inperson.mean(), 2),
        "difference": round(remote.mean() - inperson.mean(), 2),
    }


def anova_experience_salary(df: pd.DataFrame) -> dict:
    """ANOVA: do experience levels have significantly different salaries?"""
    groups = [g["salary_in_usd"].values for _, g in df.groupby("experience_level")]
    f_stat, p_value = stats.f_oneway(*groups)
    return {
        "f_statistic": round(f_stat, 4),
        "p_value": round(p_value, 6),
        "significant_at_005": p_value < 0.05,
    }


# ──────────────────────────────────────────────
# Predictive Modeling
# ──────────────────────────────────────────────

def prepare_features(df: pd.DataFrame) -> tuple:
    """Prepare features for salary prediction."""
    feature_cols = ["job_category", "experience_level", "employment_type",
                    "work_setting", "company_size", "country_group"]
    
    df_model = df[feature_cols + ["salary_in_usd"]].dropna().copy()
    
    # Label encode categoricals
    encoders = {}
    for col in feature_cols:
        le = LabelEncoder()
        df_model[col + "_enc"] = le.fit_transform(df_model[col].astype(str))
        encoders[col] = le
    
    enc_cols = [c + "_enc" for c in feature_cols]
    X = df_model[enc_cols].values
    y = df_model["salary_in_usd"].values
    
    return X, y, encoders, enc_cols


def train_models(X, y, test_size=0.2, random_state=42):
    """Train multiple models and return results."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=200, max_depth=10, min_samples_leaf=5,
            random_state=random_state, n_jobs=-1
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            min_samples_leaf=5, random_state=random_state
        ),
    }
    
    results = {}
    trained_models = {}
    
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)
        
        # Cross-validation
        cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2")
        
        results[name] = {
            "train_r2": round(r2_score(y_train, y_pred_train), 4),
            "test_r2": round(r2_score(y_test, y_pred_test), 4),
            "cv_r2_mean": round(cv_scores.mean(), 4),
            "cv_r2_std": round(cv_scores.std(), 4),
            "mae": round(mean_absolute_error(y_test, y_pred_test), 2),
            "rmse": round(np.sqrt(mean_squared_error(y_test, y_pred_test)), 2),
        }
        trained_models[name] = model
    
    return results, trained_models, (X_train, X_test, y_train, y_test)


def get_feature_importance(model, feature_names: list) -> pd.DataFrame:
    """Extract feature importance from tree-based models."""
    if hasattr(model, "feature_importances_"):
        imp = pd.DataFrame({
            "Feature": [f.replace("_enc", "") for f in feature_names],
            "Importance": model.feature_importances_
        }).sort_values("Importance", ascending=False)
        return imp
    return pd.DataFrame()


def predict_salary(model, encoders, feature_cols, input_dict: dict) -> float:
    """Predict salary for a single input."""
    encoded = []
    for col in feature_cols:
        col_clean = col.replace("_enc", "")
        le = encoders[col_clean]
        val = input_dict.get(col_clean, "Unknown")
        if val in le.classes_:
            encoded.append(le.transform([val])[0])
        else:
            encoded.append(0)
    
    prediction = model.predict([encoded])[0]
    return max(prediction, 0)  # No negative salaries
