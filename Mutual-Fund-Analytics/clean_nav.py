import pandas as pd
import numpy as np
import os

def clean_nav_history():
    print("=== Cleaning NAV History ===")
    df = pd.read_csv('data/raw/02_nav_history.csv')
    initial_rows = len(df)

    # Track missing NAVs initially
    missing_nav_initially = df['nav'].isna().sum()

    # 1. Parse date
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # 2. Sort records
    df = df.sort_values(['amfi_code', 'date'])

    # 3. Remove duplicates
    duplicate_rows = df.duplicated().sum()
    df = df.drop_duplicates()

    # 4. Forward-fill missing NAV values within each fund (do NOT generate synthetic date rows)
    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
    df['nav'] = df.groupby('amfi_code')['nav'].ffill()

    missing_nav_after_ffill = df['nav'].isna().sum()

    # 5. Validate: NAV must be greater than 0
    invalid_navs = df[df['nav'] <= 0]
    invalid_nav_count = len(invalid_navs)
    df = df[df['nav'] > 0] # Removing invalid NAVs as part of cleaning or just flagging? Usually we remove or impute. The prompt says "Validate... Create anomaly report". I'll drop them from the cleaned dataset.

    final_rows = len(df)

    # Anomaly report
    report = {
        "Dataset": "nav_history",
        "Rows before cleaning": initial_rows,
        "Rows after cleaning": final_rows,
        "Duplicates removed": int(duplicate_rows),
        "Null values handled": int(missing_nav_initially - missing_nav_after_ffill),
        "Missing NAV (after ffill)": int(missing_nav_after_ffill),
        "Invalid NAV values (<=0)": int(invalid_nav_count)
    }

    print(f"Duplicates removed: {duplicate_rows}")
    print(f"Missing NAVs forward-filled: {missing_nav_initially - missing_nav_after_ffill}")
    print(f"Remaining Missing NAVs: {missing_nav_after_ffill}")
    print(f"Invalid NAV values (<=0): {invalid_nav_count}")

    os.makedirs('data/processed', exist_ok=True)
    df.to_csv('data/processed/nav_history_clean.csv', index=False)

    return report

if __name__ == "__main__":
    clean_nav_history()
