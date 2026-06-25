-- schema.sql
-- Star Schema Design for Bluestock Mutual Fund Analytics

-- ==========================================
-- DIMENSION TABLES
-- ==========================================

-- dim_fund: Contains static and slowly changing attributes of mutual fund schemes
CREATE TABLE dim_fund (
    amfi_code INTEGER PRIMARY KEY,
    fund_house TEXT NOT NULL,
    scheme_name TEXT NOT NULL,
    category TEXT,
    sub_category TEXT,
    plan TEXT,
    launch_date DATE,
    benchmark TEXT,
    expense_ratio_pct REAL,
    exit_load_pct REAL,
    min_sip_amount INTEGER,
    min_lumpsum_amount INTEGER,
    fund_manager TEXT,
    risk_category TEXT,
    sebi_category_code TEXT
);

-- dim_date: Contains date dimensions for analytical grouping
CREATE TABLE dim_date (
    date_id DATE PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

-- dim_fund_house: Surrogate key dimension for fund houses (used for fact_aum)
CREATE TABLE dim_fund_house (
    fund_house_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_house_name TEXT NOT NULL UNIQUE
);

-- ==========================================
-- FACT TABLES
-- ==========================================

-- fact_nav: Daily Net Asset Value (NAV) per scheme
CREATE TABLE fact_nav (
    amfi_code INTEGER NOT NULL,
    date_id DATE NOT NULL,
    nav REAL NOT NULL,
    PRIMARY KEY (amfi_code, date_id),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code),
    FOREIGN KEY (date_id) REFERENCES dim_date (date_id)
);

-- fact_transactions: Individual investor transactions
CREATE TABLE fact_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    amfi_code INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    amount_inr REAL NOT NULL,
    state TEXT,
    city TEXT,
    city_tier TEXT,
    age_group TEXT,
    gender TEXT,
    annual_income_lakh REAL,
    payment_mode TEXT,
    kyc_status TEXT,
    FOREIGN KEY (transaction_date) REFERENCES dim_date (date_id),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code)
);

-- fact_performance: Scheme performance and risk metrics (grain: amfi_code, single snapshot)
CREATE TABLE fact_performance (
    amfi_code INTEGER PRIMARY KEY,
    return_1yr_pct REAL,
    return_3yr_pct REAL,
    return_5yr_pct REAL,
    benchmark_3yr_pct REAL,
    alpha REAL,
    beta REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    std_dev_ann_pct REAL,
    max_drawdown_pct REAL,
    aum_crore REAL,
    expense_ratio_pct REAL,
    morningstar_rating INTEGER,
    risk_grade TEXT,
    expense_ratio_anomaly_flag BOOLEAN,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund (amfi_code)
);

-- fact_aum: Monthly AUM metrics per fund house
CREATE TABLE fact_aum (
    date_id DATE NOT NULL,
    fund_house_id INTEGER NOT NULL,
    aum_lakh_crore REAL NOT NULL,
    aum_crore REAL NOT NULL,
    num_schemes INTEGER NOT NULL,
    PRIMARY KEY (date_id, fund_house_id),
    FOREIGN KEY (date_id) REFERENCES dim_date (date_id),
    FOREIGN KEY (fund_house_id) REFERENCES dim_fund_house (fund_house_id)
);

-- ==========================================
-- INDEXES
-- ==========================================
CREATE INDEX idx_fact_nav_date ON fact_nav(date_id);
CREATE INDEX idx_fact_transactions_date ON fact_transactions(transaction_date);
CREATE INDEX idx_fact_transactions_amfi ON fact_transactions(amfi_code);
CREATE INDEX idx_fact_aum_fund_house ON fact_aum(fund_house_id);
CREATE INDEX idx_dim_fund_fund_house ON dim_fund(fund_house);
