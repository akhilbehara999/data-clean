import pandas as pd
import os

def baseline_clean():
    print("=== Baseline Cleaning Remaining Datasets ===")
    files = [
        ('01_fund_master.csv', 'fund_master_clean.csv'),
        ('03_aum_by_fund_house.csv', 'aum_by_fund_house_clean.csv'),
        ('04_monthly_sip_inflows.csv', 'monthly_sip_inflows_clean.csv'),
        ('05_category_inflows.csv', 'category_inflows_clean.csv'),
        ('06_industry_folio_count.csv', 'industry_folio_count_clean.csv'),
        ('09_portfolio_holdings.csv', 'portfolio_holdings_clean.csv'),
        ('10_benchmark_indices.csv', 'benchmark_indices_clean.csv')
    ]

    for raw_name, clean_name in files:
        raw_path = os.path.join('data/raw', raw_name)
        clean_path = os.path.join('data/processed', clean_name)

        if not os.path.exists(raw_path):
            print(f"File {raw_path} not found.")
            continue

        df = pd.read_csv(raw_path)
        initial_rows = len(df)

        # Identify date columns and parse
        for col in df.columns:
            if 'date' in col.lower() or 'month' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='ignore')
                except Exception:
                    pass

        # Remove duplicates
        df = df.drop_duplicates()
        final_rows = len(df)

        df.to_csv(clean_path, index=False)
        print(f"Processed {raw_name}: {initial_rows} rows -> {final_rows} rows")

if __name__ == "__main__":
    baseline_clean()
