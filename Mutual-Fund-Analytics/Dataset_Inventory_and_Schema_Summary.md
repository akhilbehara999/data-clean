# Dataset Inventory and Schema Summary

## 1. Dataset Inventory

| Dataset Name | Row Count | Column Count | Date Range | Missing % |
|---|---|---|---|---|
| `nav_history_clean.csv` | 46000 | 3 | 2022-01-03 to 2026-05-29 | 0.0% |
| `benchmark_indices_clean.csv` | 8050 | 3 | 2022-01-03 to 2026-05-29 | 0.0% |
| `fund_master_clean.csv` | 40 | 15 | N/A | 0.0% |
| `scheme_performance_clean.csv` | 40 | 20 | N/A | 0.0% |
| `investor_transactions_clean.csv` | 32778 | 13 | N/A | 0.0% |
| `portfolio_holdings_clean.csv` | 322 | 8 | N/A | 0.0% |
| `aum_by_fund_house_clean.csv` | 90 | 5 | 2022-03-31 to 2025-12-31 | 0.0% |
| `monthly_sip_inflows_clean.csv` | 48 | 6 | N/A | `yoy_growth_pct` (25.0%) |
| `category_inflows_clean.csv` | 144 | 3 | N/A | 0.0% |
| `industry_folio_count_clean.csv` | 21 | 6 | N/A | 0.0% |

## 2. Detected Columns & Candidate Keys

*   **Fund NAV History**
    *   **File:** `nav_history_clean.csv`
    *   **Candidate Keys:** `(amfi_code, date)`
    *   **Detected NAV Columns:** `nav`
*   **Benchmarks**
    *   **File:** `benchmark_indices_clean.csv`
    *   **Candidate Keys:** `(index_name, date)`
    *   **Detected Benchmark Columns:** `index_name`, `close_value`
*   **Fund Metadata**
    *   **File:** `fund_master_clean.csv`
    *   **Candidate Keys:** `amfi_code`
    *   **Detected Expense Ratio Columns:** `expense_ratio_pct`

## 3. Required Input Verification

| Required Input | Status | Dataset Mapping |
|---|---|---|
| Fund NAV history | **Available** | `nav_history_clean.csv` |
| Nifty 50 benchmark data | **Available** | `benchmark_indices_clean.csv` (filter `index_name == 'NIFTY50'`) |
| Nifty 100 benchmark data | **Available** | `benchmark_indices_clean.csv` (filter `index_name == 'NIFTY100'`) |
| Expense ratio data | **Available** | `fund_master_clean.csv` (column `expense_ratio_pct`) |
| Fund metadata | **Available** | `fund_master_clean.csv` |
