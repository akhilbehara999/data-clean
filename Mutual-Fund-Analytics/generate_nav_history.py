import pandas as pd
import glob
import os

all_files = glob.glob('data/raw/nav_*.csv')
df_list = []
for file in all_files:
    df_list.append(pd.read_csv(file))

combined_df = pd.concat(df_list, ignore_index=True)
combined_df.to_csv('data/raw/nav_history.csv', index=False)
