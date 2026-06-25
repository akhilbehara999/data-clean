-- queries.sql
-- Analytical SQL Queries for Bluestock Mutual Fund

-- ==========================================
-- MANDATORY QUERIES
-- ==========================================

-- 1. Top 5 funds by AUM
-- Business Purpose: Identify the largest mutual funds by assets under management.
SELECT
    f.amfi_code,
    f.scheme_name,
    p.aum_crore
FROM dim_fund f
JOIN fact_performance p ON f.amfi_code = p.amfi_code
ORDER BY p.aum_crore DESC
LIMIT 5;

-- 2. Average NAV per month
-- Business Purpose: Track the overall valuation trend of funds across different months.
SELECT
    d.year,
    d.month,
    f.amfi_code,
    f.scheme_name,
    AVG(n.nav) AS avg_monthly_nav
FROM fact_nav n
JOIN dim_date d ON n.date_id = d.date_id
JOIN dim_fund f ON n.amfi_code = f.amfi_code
GROUP BY d.year, d.month, f.amfi_code, f.scheme_name
ORDER BY f.amfi_code, d.year, d.month;

-- 3. SIP YoY growth
-- Business Purpose: Understand how the volume and value of Systematic Investment Plans are growing year over year.
-- Note: Derived from fact_transactions for SIP types.
WITH yearly_sip AS (
    SELECT
        d.year,
        SUM(t.amount_inr) AS total_sip_amount,
        COUNT(t.transaction_id) AS sip_count
    FROM fact_transactions t
    JOIN dim_date d ON t.transaction_date = d.date_id
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
)
SELECT
    y1.year,
    y1.total_sip_amount,
    y1.sip_count,
    y2.total_sip_amount AS prev_year_amount,
    ((y1.total_sip_amount - y2.total_sip_amount) / y2.total_sip_amount) * 100 AS yoy_growth_pct
FROM yearly_sip y1
LEFT JOIN yearly_sip y2 ON y1.year = y2.year + 1
ORDER BY y1.year;

-- 4. Transactions by state
-- Business Purpose: Determine geographic distribution of investor activities to target regional marketing.
SELECT
    state,
    transaction_type,
    COUNT(transaction_id) AS total_transactions,
    SUM(amount_inr) AS total_amount
FROM fact_transactions
GROUP BY state, transaction_type
ORDER BY state, total_amount DESC;

-- 5. Funds with expense_ratio < 1%
-- Business Purpose: Highlight low-cost mutual fund options for cost-conscious investors.
SELECT
    f.amfi_code,
    f.scheme_name,
    f.fund_house,
    p.expense_ratio_pct
FROM dim_fund f
JOIN fact_performance p ON f.amfi_code = p.amfi_code
WHERE p.expense_ratio_pct < 1.0
ORDER BY p.expense_ratio_pct ASC;

-- ==========================================
-- ADDITIONAL BUSINESS ANALYTICS QUERIES
-- ==========================================

-- 6. Average Transaction Amount by Age Group and Gender
-- Business Purpose: Understand investor demographics to tailor financial products.
SELECT
    age_group,
    gender,
    transaction_type,
    AVG(amount_inr) AS avg_transaction_amount
FROM fact_transactions
GROUP BY age_group, gender, transaction_type
ORDER BY age_group, gender, transaction_type;

-- 7. Fund Performance vs Benchmark (Alpha Generation)
-- Business Purpose: Identify which funds are beating their benchmarks over a 3-year period (Alpha > 0).
SELECT
    f.scheme_name,
    f.category,
    p.return_3yr_pct,
    p.benchmark_3yr_pct,
    p.alpha
FROM fact_performance p
JOIN dim_fund f ON p.amfi_code = f.amfi_code
WHERE p.alpha > 0
ORDER BY p.alpha DESC;

-- 8. Risk-Adjusted Return Analysis (Top Sharpe Ratios)
-- Business Purpose: Identify the best funds in terms of risk-adjusted returns (Sharpe Ratio).
SELECT
    f.scheme_name,
    f.risk_category,
    p.sharpe_ratio,
    p.sortino_ratio,
    p.std_dev_ann_pct
FROM fact_performance p
JOIN dim_fund f ON p.amfi_code = f.amfi_code
ORDER BY p.sharpe_ratio DESC
LIMIT 10;

-- 9. Monthly AUM Trend per Fund House
-- Business Purpose: Track the growth trajectory of assets managed by different fund houses over time.
SELECT
    d.year,
    d.month,
    fh.fund_house_name,
    SUM(a.aum_crore) AS total_aum_crore
FROM fact_aum a
JOIN dim_date d ON a.date_id = d.date_id
JOIN dim_fund_house fh ON a.fund_house_id = fh.fund_house_id
GROUP BY d.year, d.month, fh.fund_house_name
ORDER BY fh.fund_house_name, d.year, d.month;

-- 10. Investor KYC Status Distribution by City Tier
-- Business Purpose: Assess KYC compliance levels across different city tiers (T30 vs B30) to focus on operational bottlenecks.
SELECT
    city_tier,
    kyc_status,
    COUNT(DISTINCT investor_id) AS unique_investors,
    COUNT(transaction_id) AS total_transactions
FROM fact_transactions
GROUP BY city_tier, kyc_status
ORDER BY city_tier, kyc_status;
