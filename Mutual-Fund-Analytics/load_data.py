import pandas as pd
from sqlalchemy import create_engine
import sqlite3
import os

def load_data():
    print("=== Loading Data into SQLite ===")

    # Initialize DB
    db_path = 'bluestock_mf.db'
    if os.path.exists(db_path):
        os.remove(db_path)

    # We will use sqlite3 to execute schema first, then sqlalchemy to load
    conn = sqlite3.connect(db_path)
    with open('schema.sql', 'r') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.close()

    engine = create_engine(f'sqlite:///{db_path}')

    # 1. Load dim_fund
    df_fund = pd.read_csv('data/processed/fund_master_clean.csv')
    df_fund.to_sql('dim_fund', con=engine, if_exists='append', index=False)

    # 2. Extract and load dim_date
    # We need a unified date range across all tables with date columns
    df_nav = pd.read_csv('data/processed/nav_history_clean.csv')
    df_tx = pd.read_csv('data/processed/investor_transactions_clean.csv')
    df_aum = pd.read_csv('data/processed/aum_by_fund_house_clean.csv')

    all_dates = pd.concat([
        df_nav['date'],
        df_tx['transaction_date'],
        df_aum['date']
    ]).dropna().unique()

    df_dates = pd.DataFrame({'date_id': pd.to_datetime(all_dates)})
    df_dates['year'] = df_dates['date_id'].dt.year
    df_dates['month'] = df_dates['date_id'].dt.month
    df_dates['day'] = df_dates['date_id'].dt.day
    df_dates['quarter'] = df_dates['date_id'].dt.quarter
    df_dates['day_of_week'] = df_dates['date_id'].dt.dayofweek
    df_dates['is_weekend'] = df_dates['day_of_week'].isin([5, 6])

    # Format date_id as string (YYYY-MM-DD) since SQLite handles dates as text
    df_dates['date_id'] = df_dates['date_id'].dt.strftime('%Y-%m-%d')
    df_dates.to_sql('dim_date', con=engine, if_exists='append', index=False)

    # 3. Build and load dim_fund_house
    # Extract unique fund houses from AUM and Fund Master
    fund_houses_aum = df_aum['fund_house'].unique()
    fund_houses_fund = df_fund['fund_house'].unique()
    all_fund_houses = list(set(fund_houses_aum).union(set(fund_houses_fund)))

    df_fh = pd.DataFrame({'fund_house_name': all_fund_houses})
    df_fh['fund_house_id'] = range(1, len(df_fh) + 1)
    df_fh.to_sql('dim_fund_house', con=engine, if_exists='append', index=False)

    # Create mapping dict for AUM load
    fh_map = dict(zip(df_fh['fund_house_name'], df_fh['fund_house_id']))

    # 4. Load fact_nav
    df_nav['date_id'] = pd.to_datetime(df_nav['date']).dt.strftime('%Y-%m-%d')
    df_nav = df_nav[['amfi_code', 'date_id', 'nav']]
    df_nav.to_sql('fact_nav', con=engine, if_exists='append', index=False)

    # 5. Load fact_transactions
    df_tx['transaction_date'] = pd.to_datetime(df_tx['transaction_date']).dt.strftime('%Y-%m-%d')
    # Since transaction_id is AUTOINCREMENT, we can drop it from df and let SQL handle it
    # We will just insert the rest of the columns
    df_tx.to_sql('fact_transactions', con=engine, if_exists='append', index=False)

    # 6. Load fact_performance
    df_perf = pd.read_csv('data/processed/scheme_performance_clean.csv')
    df_perf_fact = df_perf[['amfi_code', 'return_1yr_pct', 'return_3yr_pct', 'return_5yr_pct',
                            'benchmark_3yr_pct', 'alpha', 'beta', 'sharpe_ratio', 'sortino_ratio',
                            'std_dev_ann_pct', 'max_drawdown_pct', 'aum_crore', 'expense_ratio_pct',
                            'morningstar_rating', 'risk_grade', 'expense_ratio_anomaly_flag']]
    df_perf_fact.to_sql('fact_performance', con=engine, if_exists='append', index=False)

    # 7. Load fact_aum
    df_aum['date_id'] = pd.to_datetime(df_aum['date']).dt.strftime('%Y-%m-%d')
    df_aum['fund_house_id'] = df_aum['fund_house'].map(fh_map)
    df_aum_fact = df_aum[['date_id', 'fund_house_id', 'aum_lakh_crore', 'aum_crore', 'num_schemes']]
    df_aum_fact.to_sql('fact_aum', con=engine, if_exists='append', index=False)

    print("=== Data Load Verification ===")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tables = ['dim_fund', 'dim_date', 'dim_fund_house', 'fact_nav', 'fact_transactions', 'fact_performance', 'fact_aum']

    # Source row counts vs loaded
    counts = {
        'dim_fund': len(df_fund),
        'dim_date': len(df_dates),
        'dim_fund_house': len(df_fh),
        'fact_nav': len(df_nav),
        'fact_transactions': len(df_tx),
        'fact_performance': len(df_perf_fact),
        'fact_aum': len(df_aum_fact)
    }

    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        db_count = cur.fetchone()[0]
        source_count = counts[table]
        match = "MATCH" if db_count == source_count else "MISMATCH"
        print(f"{table}: Source {source_count} rows | DB {db_count} rows -> {match}")

    conn.close()

if __name__ == "__main__":
    load_data()
