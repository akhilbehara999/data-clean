# Advanced Analytics Validation Report

## Coverage Summary
*   **Funds analyzed:** 40
*   **Investors analyzed:** 5000
*   **Funds eligible for VaR/CVaR:** 40
*   **Funds eligible for Rolling Sharpe:** 40
*   **Investors eligible for SIP continuity:** 1362
*   **Equity funds eligible for HHI:** 34

## Metric Validation

### Sample VaR and CVaR Calculation
For fund AMFI code 101207 (ABSL Small Cap Fund - Regular - Growth):
- VaR95: -0.02602 (meaning there is a 5% chance of daily returns falling below -2.6%)
- CVaR95: -0.03246 (meaning the average loss on those worst 5% days is -3.24%)

### Sample Rolling Sharpe Calculation
Formula used: `rolling_mean(return, 90) / rolling_std(return, 90) * sqrt(252)`
The rolling mean over a 90-day window is computed, divided by the 90-day standard deviation, and annualized by multiplying by `sqrt(252)`. Data points with 0 standard deviation are handled safely (replaced with NaN). Funds with insufficient observations are automatically skipped. The output plot `rolling_sharpe_chart.png` includes 5 representative funds based on specific criteria.

### Sample Cohort Assignment
Investors are grouped by the year of their earliest transaction date.
For example, if an investor's first recorded transaction is in `2024`, their cohort is `2024`.
Cohort details (Number of investors, Average SIP amount, Total Invested, etc.) are computed and displayed within the notebook analysis.

### SIP Continuity Calculation
For investors with `>= 6` SIP transactions, consecutive gaps are computed.
Average Gap `<= 35 days` -> Healthy
Average Gap `> 35 days` -> At-Risk
Results are evaluated and visualized directly in the `Advanced_Analytics.ipynb`.

### Sample Recommendation Logic Output
```bash
$ python recommender.py Low
Top 3 Fund Recommendations for Low Risk Appetite:
                               Fund Name Risk Grade  Sharpe Ratio  Return  Expense Ratio  Recommendation Score
ICICI Pru Liquid Fund - Regular - Growth        Low          7.68    8.89           0.74                  10.0
    Kotak Liquid Fund - Regular - Growth        Low          6.18    4.26           0.60                   8.0
     ABSL Liquid Fund - Regular - Growth        Low          5.14    6.18           0.79                   6.7

$ python recommender.py Moderate
Top 3 Fund Recommendations for Moderate Risk Appetite:
                                    Fund Name Risk Grade  Sharpe Ratio  Return  Expense Ratio  Recommendation Score
Mirae Asset Large Cap Fund - Regular - Growth   Moderate          1.06   15.12           1.46                  10.0
    HDFC Top 100 Fund - Regular Plan - Growth   Moderate          1.06   10.94           1.55                  10.0
    ICICI Pru Bluechip Fund - Direct - Growth   Moderate          1.03   14.12           0.80                   9.7

$ python recommender.py High
Top 3 Fund Recommendations for High Risk Appetite:
                                    Fund Name Risk Grade  Sharpe Ratio  Return  Expense Ratio  Recommendation Score
Kotak Emerging Equity Fund - Regular - Growth       High          0.96   17.12           1.56                  10.0
     ICICI Pru Midcap Fund - Regular - Growth       High          0.95   14.02           1.36                   9.9
   SBI Small Cap Fund - Regular Plan - Growth  Very High          0.94   24.56           1.43                   9.8
```

### Sample HHI Calculation
For an equity fund, HHI (Herfindahl-Hirschman Index) is computed as the sum of squared weights (in decimal form).
Example: If a fund has holdings with weights 18.22%, 13.94%, etc., the HHI is `(0.1822)^2 + (0.1394)^2 + ...`
If HHI < 0.10, it's Diversified. If between 0.10 and 0.18, it's Moderate. If > 0.18, it's Concentrated.
Sample calculation yields valid classification categories which are tabulated in the Jupyter notebook.
