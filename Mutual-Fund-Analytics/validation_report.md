# Validation Report - Day 2 Tasks

## Files Created
1. `data/processed/nav_history_clean.csv`
2. `data/processed/investor_transactions_clean.csv`
3. `data/processed/scheme_performance_clean.csv`
4. `data/processed/fund_master_clean.csv`
5. `data/processed/aum_by_fund_house_clean.csv`
6. `data/processed/monthly_sip_inflows_clean.csv`
7. `data/processed/category_inflows_clean.csv`
8. `data/processed/industry_folio_count_clean.csv`
9. `data/processed/portfolio_holdings_clean.csv`
10. `data/processed/benchmark_indices_clean.csv`
11. `bluestock_mf.db` (SQLite Database)
12. `schema.sql` (Star Schema Design)
13. `queries.sql` (Analytical SQL Queries)
14. `data_dictionary.md` (Metadata and Schema definition)
15. Processing scripts (`clean_nav.py`, `clean_transactions.py`, `clean_performance.py`, `clean_baseline.py`, `load_data.py`)

## Data Quality Summary

**1. nav_history.csv**
- Rows before cleaning: 46,000
- Rows after cleaning: 46,000
- Duplicates removed: 0
- Null values handled: 0 (No missing NAVs existed initially to forward fill)
- Validation issues found: 0 (No invalid NAVs <= 0 found)

**2. investor_transactions.csv**
- Rows before cleaning: 32,778
- Rows after cleaning: 32,778
- Standardization: `transaction_type` was standardized to `SIP`, `Lumpsum`, or `Redemption`.
- Validation issues found:
  - Invalid transaction amounts: 0
  - Invalid dates: 0
  - Invalid KYC statuses: 0

**3. scheme_performance.csv**
- Rows before cleaning: 40
- Rows after cleaning: 40
- Return anomalies flagged: None (No values > 1000% or < -100%)
- Invalid expense ratios flagged: 0 (All values strictly between 0.1% and 2.5%)
- A new column `expense_ratio_anomaly_flag` was added to preserve row structure while explicitly marking anomalous states.

**4. Baseline datasets**
All 7 other datasets successfully parsed dates, checked for duplicates, and retained their original row counts.

## Database Validation
- Load Success Confirmation: **PASSED**. The `load_data.py` script verified that exactly 100% of rows from processed CSVs mapped directly to the corresponding dimension or fact tables in `bluestock_mf.db`.
- Database Row Counts:
  - `dim_fund`: 40 rows
  - `dim_date`: 1,297 rows
  - `dim_fund_house`: 10 rows
  - `fact_nav`: 46,000 rows
  - `fact_transactions`: 32,778 rows
  - `fact_performance`: 40 rows
  - `fact_aum`: 90 rows

## Risks / Assumptions
- **Assumption 1**: Forward-filling NAV data applies to existing rows. Synthetic records mapping to non-trading dates were *not* generated. This limits analytical continuity across weekends/holidays but avoids inflating database size needlessly per human request.
- **Assumption 2**: Expense ratio ranges assume that inputs are in valid float percentage form (e.g. `1.54` not `0.0154`).
- **Assumption 3**: KYC Status values other than "Verified" and "Pending" would be discarded, but the data only contained these two statuses.
- **Risk 1**: Analytical metrics on SIP YoY growth depend on the specific transaction sample available. They may appear incomplete for partial years in `investor_transactions`.
- **Assumption 4**: A surrogate `dim_fund_house` approach was adopted to link `fact_aum` efficiently since it is aggregated at the fund house level rather than the scheme level.