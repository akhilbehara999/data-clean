import argparse
import pandas as pd
import sys

def recommend(risk_appetite):
    # Load data
    try:
        fm_df = pd.read_csv('data/processed/fund_master_clean.csv')
        perf_df = pd.read_csv('data/processed/scheme_performance_clean.csv')
    except FileNotFoundError:
        print("Error: Could not find processed datasets.")
        sys.exit(1)

    merged = perf_df.merge(fm_df[['amfi_code', 'risk_category']], on='amfi_code', how='inner')

    # Map input to risk grades
    risk_mapping = {
        'low': ['Low', 'Low to Moderate'],
        'moderate': ['Moderate', 'Moderately High'],
        'high': ['High', 'Very High']
    }

    appetite = risk_appetite.lower()
    if appetite not in risk_mapping:
        print("Invalid risk appetite. Choose from: Low, Moderate, High.")
        sys.exit(1)

    allowed_risks = risk_mapping[appetite]

    # Filter by risk
    filtered = merged[merged['risk_category'].isin(allowed_risks)].copy()

    if filtered.empty:
        print(f"No funds found for risk appetite: {risk_appetite}")
        return

    # Rank by: 1. Sharpe Ratio DESC, 2. Return (1yr) DESC, 3. Expense Ratio ASC
    # We will compute a simple recommendation score based on normalized ranks to be safe,
    # but the exact instruction says "Rank by: 1. Sharpe... 2. Return... 3. Expense"
    # which implies a sort order. Let's sort by those exact columns.

    # We use return_1yr_pct for 'Return'
    # Sort order: Sharpe (descending), Return 1Y (descending), Expense (ascending)
    filtered = filtered.sort_values(
        by=['sharpe_ratio', 'return_1yr_pct', 'expense_ratio_pct'],
        ascending=[False, False, True]
    )

    # Take top 3
    top_3 = filtered.head(3).copy()

    # Calculate a simple "Recommendation Score" out of 10 for illustration
    # Since they are the top 3, we can assign 10, 9, 8 or base it on percentiles.
    # We'll use a relative score based on Sharpe ratio in the filtered set.
    max_sharpe = filtered['sharpe_ratio'].max()
    top_3['Recommendation Score'] = (top_3['sharpe_ratio'] / max_sharpe * 10).round(1)

    # Output Table
    output = top_3[['scheme_name', 'risk_category', 'sharpe_ratio', 'return_1yr_pct', 'expense_ratio_pct', 'Recommendation Score']]
    output.columns = ['Fund Name', 'Risk Grade', 'Sharpe Ratio', 'Return', 'Expense Ratio', 'Recommendation Score']

    print(f"\nTop 3 Fund Recommendations for {risk_appetite.capitalize()} Risk Appetite:\n")
    print(output.to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rule-Based Fund Recommender")
    parser.add_argument('risk_appetite', choices=['Low', 'Moderate', 'High', 'low', 'moderate', 'high'],
                        help="Your risk appetite: Low, Moderate, or High")

    args = parser.parse_args()
    recommend(args.risk_appetite)
