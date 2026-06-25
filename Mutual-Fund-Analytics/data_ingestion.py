import pandas as pd
import os
import glob
import logging
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(message)s')

def identify_column(df: pd.DataFrame, possible_names: List[str]) -> str:
    """Helper to dynamically identify the name of a specific logical column."""
    for col in df.columns:
        if col.lower() in possible_names:
            return col
    return None

def find_primary_keys(df: pd.DataFrame) -> List[str]:
    """Basic heuristic to find potential primary/join keys."""
    keys = []
    # common id names
    for col in df.columns:
        lower_col = col.lower()
        if "code" in lower_col or "id" in lower_col or "date" in lower_col or "month" in lower_col or "house" in lower_col or "category" in lower_col:
            keys.append(col)
    return keys

def process_and_analyze_datasets(csv_files: List[str]):
    datasets = {}
    report_lines = []

    report_lines.append("1. Dataset Inventory & 2. Schema Summary")
    report_lines.append("=========================================")
    report_lines.append(f"{'Dataset Name':<30} | {'Rows':<8} | {'Cols':<6} | {'Size (KB)':<10} | {'Missing %':<10} | {'Potential Keys'}")
    report_lines.append("-" * 110)

    for f in csv_files:
        filename = os.path.basename(f)
        try:
            df = pd.read_csv(f)
            datasets[filename] = df

            logging.info(f"\n--- Processing {filename} ---")
            logging.info(f"Shape: {df.shape}")
            logging.info(f"\nDtypes:\n{df.dtypes}")
            logging.info(f"\nFirst 5 rows:\n{df.head()}")

            missing = df.isnull().sum()
            logging.info(f"\nMissing values:\n{missing}")

            duplicates = df.duplicated().sum()
            logging.info(f"\nDuplicate rows: {duplicates}")

            logging.info(f"\nDescriptive statistics:\n{df.describe(include='all')}")

            # Inventory report additions
            rows = len(df)
            cols = len(df.columns)
            size_kb = os.path.getsize(f) / 1024
            missing_pct = (df.isnull().sum().sum() / df.size) * 100 if df.size > 0 else 0

            keys = find_primary_keys(df)
            keys_str = ", ".join(keys) if keys else "None"

            report_lines.append(f"{filename:<30} | {rows:<8} | {cols:<6} | {size_kb:<10.2f} | {missing_pct:<10.2f} | {keys_str}")

            # Explicitly append schema types for the final report as requested
            report_lines.append(f"\n  [Schema for {filename}]")
            for col, dtype in zip(df.columns, df.dtypes):
                report_lines.append(f"   - {col}: {dtype}")
            report_lines.append("-" * 110)

        except Exception as e:
            logging.error(f"Error reading {filename}: {e}")

    # Relationships map
    report_lines.append("\nDataset Relationships Mapping")
    report_lines.append("=============================")
    report_lines.append("Based on column names, the datasets connect via common keys:")

    # Simple mapping of identical column names across datasets
    col_to_datasets = {}
    for name, df in datasets.items():
        for col in df.columns:
            if col not in col_to_datasets:
                col_to_datasets[col] = []
            col_to_datasets[col].append(name)

    for col, dsets in col_to_datasets.items():
        if len(dsets) > 1 and ("code" in col.lower() or "id" in col.lower() or "date" in col.lower() or "month" in col.lower() or "house" in col.lower() or "category" in col.lower()):
            report_lines.append(f"- `{col}` joins: {', '.join(dsets)}")

    return datasets, report_lines

def analyze_fund_master(datasets: Dict[str, pd.DataFrame]):
    report_lines = []

    fund_master_key = next((k for k in datasets.keys() if 'fund_master' in k.lower()), None)
    if not fund_master_key:
        return []

    df = datasets[fund_master_key]
    logging.info("\n--- Fund Master Analysis ---")

    amfi_col = identify_column(df, ['amfi_code', 'scheme_code', 'code'])
    fh_col = identify_column(df, ['fund_house', 'amc'])
    cat_col = identify_column(df, ['category', 'scheme_category'])
    subcat_col = identify_column(df, ['sub_category'])
    risk_col = identify_column(df, ['risk_category', 'risk_grade', 'risk'])

    if amfi_col:
        total_schemes = df[amfi_col].nunique()
        logging.info(f"Total schemes: {total_schemes}")
        logging.info(f"AMFI Scheme Code Structure: Type: {df[amfi_col].dtype}, Min length: {df[amfi_col].astype(str).str.len().min()}, Max length: {df[amfi_col].astype(str).str.len().max()}")
        invalid_codes = df[df[amfi_col].isnull()]
        if len(invalid_codes) > 0:
            logging.info(f"Invalid or missing scheme codes found: {len(invalid_codes)}")

    if fh_col:
        logging.info(f"Unique Fund Houses: {df[fh_col].nunique()}")
        logging.info(f"List: {df[fh_col].unique()}")

    if cat_col:
        logging.info(f"Categories: {df[cat_col].unique()}")

    if subcat_col:
        logging.info(f"Sub-categories: {df[subcat_col].unique()}")

    if risk_col:
        logging.info(f"Risk Grades:\n{df[risk_col].value_counts()}")

    return report_lines

def analyze_datasets(datasets: Dict[str, pd.DataFrame]):
    report_lines = []
    report_lines.append("\n3. Data Quality Assessment")
    report_lines.append("==========================")

    report_lines.append("\n4. Missing Values Analysis")
    report_lines.append("==========================")
    for name, df in datasets.items():
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if not missing.empty:
            report_lines.append(f"- {name}:")
            for col, val in missing.items():
                report_lines.append(f"  - {col}: {val} missing values")
        else:
            report_lines.append(f"- {name}: No missing values")

    report_lines.append("\n5. Duplicate Analysis")
    report_lines.append("=====================")
    for name, df in datasets.items():
        dupes = df.duplicated().sum()
        if dupes > 0:
            report_lines.append(f"- {name}: {dupes} duplicate rows")
        else:
            report_lines.append(f"- {name}: No duplicate rows")

    return report_lines

def amfi_code_validation(datasets: Dict[str, pd.DataFrame]):
    report_lines = []
    report_lines.append("\n6. AMFI Code Validation Results")
    report_lines.append("===============================")

    master_key = next((k for k in datasets.keys() if 'fund_master' in k.lower()), None)
    if not master_key:
        return []

    master_df = datasets[master_key]
    amfi_col = identify_column(master_df, ['amfi_code', 'scheme_code', 'code'])

    if amfi_col:
        master_codes = set(master_df[amfi_col].unique())
        report_lines.append(f"- Total unique AMFI codes in fund_master: {len(master_codes)}")

        for name, df in datasets.items():
            if name != master_key:
                df_amfi_col = identify_column(df, ['amfi_code', 'scheme_code', 'code'])
                if df_amfi_col:
                    codes = set(df[df_amfi_col].unique())
                    missing_in_master = codes - master_codes
                    missing_in_df = master_codes - codes
                    if missing_in_master:
                        report_lines.append(f"  - WARNING: {len(missing_in_master)} AMFI codes in {name} are NOT in fund_master.")
                    else:
                        report_lines.append(f"  - SUCCESS: All AMFI codes in {name} exist in fund_master.")
    else:
        report_lines.append("- fund_master missing an AMFI code column.")

    return report_lines

def nav_history_validation(datasets: Dict[str, pd.DataFrame]):
    report_lines = []
    report_lines.append("\n7. NAV History Validation Results")
    report_lines.append("=================================")

    master_key = next((k for k in datasets.keys() if 'fund_master' in k.lower()), None)
    nav_key = next((k for k in datasets.keys() if 'nav_history' in k.lower()), None)

    if master_key and nav_key:
        master_df = datasets[master_key]
        nav_df = datasets[nav_key]

        master_amfi_col = identify_column(master_df, ['amfi_code', 'scheme_code', 'code'])
        nav_amfi_col = identify_column(nav_df, ['amfi_code', 'scheme_code', 'code'])

        if master_amfi_col and nav_amfi_col:
            master_codes = set(master_df[master_amfi_col].unique())
            nav_codes = set(nav_df[nav_amfi_col].unique())

            missing_in_nav = master_codes - nav_codes
            orphan_in_nav = nav_codes - master_codes

            if missing_in_nav:
                report_lines.append(f"- WARNING: {len(missing_in_nav)} scheme codes from fund_master missing in nav_history: {missing_in_nav}")
            else:
                report_lines.append("- SUCCESS: All scheme codes in fund_master have NAV history.")

            if orphan_in_nav:
                report_lines.append(f"- WARNING: {len(orphan_in_nav)} orphan scheme codes found in nav_history (not in fund_master).")
            else:
                report_lines.append("- SUCCESS: No orphan scheme codes in nav_history.")

            nav_val_col = identify_column(nav_df, ['nav', 'net_asset_value'])
            if nav_val_col:
                missing_navs = nav_df[nav_val_col].isnull().sum()
                if missing_navs > 0:
                    report_lines.append(f"- WARNING: Found {missing_navs} missing NAV values in nav_history.")
                else:
                    report_lines.append("- SUCCESS: No missing NAV values.")

            date_col = identify_column(nav_df, ['date', 'nav_date'])
            if date_col:
                try:
                    nav_df[date_col] = pd.to_datetime(nav_df[date_col])
                    report_lines.append(f"- NAV History Date Range: {nav_df[date_col].min().date()} to {nav_df[date_col].max().date()}")
                except Exception as e:
                    report_lines.append(f"- WARNING: Date inconsistencies found: {e}")

    return report_lines

def cross_dataset_integrity(datasets: Dict[str, pd.DataFrame]):
    report_lines = []
    report_lines.append("\n8. Cross-Dataset Integrity Checks")
    report_lines.append("=================================")

    master_key = next((k for k in datasets.keys() if 'fund_master' in k.lower()), None)
    aum_key = next((k for k in datasets.keys() if 'aum_by_fund_house' in k.lower()), None)
    txn_key = next((k for k in datasets.keys() if 'investor_transactions' in k.lower()), None)

    # Check Fund House
    if master_key and aum_key:
        master_df = datasets[master_key]
        aum_df = datasets[aum_key]
        master_fh = identify_column(master_df, ['fund_house', 'amc'])
        aum_fh = identify_column(aum_df, ['fund_house', 'amc'])
        if master_fh and aum_fh:
            mfh = set(master_df[master_fh].unique())
            afh = set(aum_df[aum_fh].unique())
            missing_aum = mfh - afh
            if missing_aum:
                report_lines.append(f"- WARNING: Fund houses in fund_master missing AUM data: {missing_aum}")
            else:
                report_lines.append("- SUCCESS: All fund houses in fund_master have corresponding AUM data.")

    # Check Investor Transactions against AMFI Code
    if master_key and txn_key:
        master_df = datasets[master_key]
        txn_df = datasets[txn_key]
        master_amfi = identify_column(master_df, ['amfi_code', 'scheme_code', 'code'])
        txn_amfi = identify_column(txn_df, ['amfi_code', 'scheme_code', 'code'])
        if master_amfi and txn_amfi:
            master_codes = set(master_df[master_amfi].unique())
            txn_codes = set(txn_df[txn_amfi].unique())
            orphan_txns = txn_codes - master_codes
            if orphan_txns:
                report_lines.append(f"- WARNING: {len(orphan_txns)} AMFI codes in transactions not found in fund_master.")
            else:
                report_lines.append("- SUCCESS: All AMFI codes in investor transactions are valid.")

    return report_lines

def anomalies_and_recommendations(datasets: Dict[str, pd.DataFrame]):
    report_lines = []
    report_lines.append("\n9. Anomalies and Recommendations")
    report_lines.append("================================")

    # Detect dynamically some anomalies
    anomalies_found = False
    for name, df in datasets.items():
        dupes = df.duplicated().sum()
        if dupes > 0:
            report_lines.append(f"- Anomaly: {name} contains {dupes} duplicate rows.")
            anomalies_found = True

        missing = df.isnull().sum()
        if missing.sum() > 0:
            report_lines.append(f"- Anomaly: {name} contains missing values in columns: {', '.join(missing[missing > 0].index.tolist())}.")
            anomalies_found = True

    if not anomalies_found:
        report_lines.append("- No obvious anomalies (duplicates, missing values) found besides what is stated in section 4 & 5.")

    report_lines.append("- Recommendation: Impute or handle missing metrics (like YoY growth) appropriately during transformations.")
    report_lines.append("- Recommendation: Set up automated validation checks to flag orphan AMFI codes and missing NAV dates upon data load.")
    return report_lines

def execution_summary(datasets: Dict[str, pd.DataFrame]):
    report_lines = []
    report_lines.append("\n10. Execution Summary")
    report_lines.append("=====================")
    total_rows = sum(len(df) for df in datasets.values())
    report_lines.append(f"- Total datasets processed: {len(datasets)}")
    report_lines.append(f"- Total rows processed across all datasets: {total_rows}")
    report_lines.append("- Data ingestion validation completed successfully.")
    return report_lines

def main():
    csv_files = sorted(glob.glob('data/raw/*.csv'))

    if not csv_files:
        logging.warning("No CSV files found in data/raw/")
        return

    datasets, report_lines = process_and_analyze_datasets(csv_files)

    # Fund master specific requested logs
    analyze_fund_master(datasets)

    # Generate the rest of the report
    report_lines.extend(analyze_datasets(datasets))
    report_lines.extend(amfi_code_validation(datasets))
    report_lines.extend(nav_history_validation(datasets))
    report_lines.extend(cross_dataset_integrity(datasets))
    report_lines.extend(anomalies_and_recommendations(datasets))
    report_lines.extend(execution_summary(datasets))

    os.makedirs("reports", exist_ok=True)
    report_path = "reports/data_quality_summary.txt"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))

    logging.info(f"\nReport generated and saved to {report_path}")

if __name__ == '__main__':
    main()
