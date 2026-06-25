import pandas as pd
import glob
import os

files = glob.glob('data/processed/*.csv')
for f in files:
    df = pd.read_csv(f)
    print(f"--- {f} ---")
    print(f"Row count: {len(df)}")
    print(f"Column count: {len(df.columns)}")
    print(f"Columns: {', '.join(df.columns)}")
    if 'date' in df.columns:
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Missing %:\n{(df.isnull().sum() / len(df) * 100).to_dict()}")
    print("\n")
