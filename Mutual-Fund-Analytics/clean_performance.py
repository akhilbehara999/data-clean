import pandas as pd
import json

def clean_scheme_performance():
    print("=== Cleaning Scheme Performance ===")
    df = pd.read_csv('data/raw/07_scheme_performance.csv')
    initial_rows = len(df)

    # 1. Validate all return columns are numeric
    return_cols = ['return_1yr_pct', 'return_3yr_pct', 'return_5yr_pct', 'benchmark_3yr_pct']
    for col in return_cols:
        if col in df.columns:
            # Remove any '%' signs if present and convert to numeric
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace('%', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. Flag extreme outliers/anomalies (e.g. > 1000% or < -100%)
    outliers = []
    for col in return_cols:
        if col in df.columns:
            col_outliers = df[(df[col] > 1000) | (df[col] < -100)]
            if not col_outliers.empty:
                outliers.append(f"{col} has {len(col_outliers)} outliers")

    # 3. Validate expense_ratio
    df['expense_ratio_pct'] = pd.to_numeric(df['expense_ratio_pct'], errors='coerce')
    invalid_expense = df[(df['expense_ratio_pct'] < 0.1) | (df['expense_ratio_pct'] > 2.5)]
    invalid_expense_count = len(invalid_expense)

    df['is_valid_expense_ratio'] = (df['expense_ratio_pct'] >= 0.1) & (df['expense_ratio_pct'] <= 2.5)
    # We can flag them by keeping the column or removing rows.
    # Instruction: "Flag values outside range." We will keep them but flag via a boolean column, or drop them?
    # Usually "Flag" means adding a column. I'll add 'expense_ratio_anomaly_flag'
    df['expense_ratio_anomaly_flag'] = ~df['is_valid_expense_ratio']
    df = df.drop(columns=['is_valid_expense_ratio'])

    final_rows = len(df)

    report = {
        "Dataset": "scheme_performance",
        "Rows before cleaning": initial_rows,
        "Rows after cleaning": final_rows,
        "Return outliers flagged": outliers,
        "Invalid expense ratios flagged": int(invalid_expense_count)
    }

    print(json.dumps(report, indent=2))
    df.to_csv('data/processed/scheme_performance_clean.csv', index=False)

if __name__ == "__main__":
    clean_scheme_performance()
