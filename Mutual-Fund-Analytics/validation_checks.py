import pandas as pd
import numpy as np

# Load scorecards and alpha_beta
scorecard = pd.read_csv('fund_scorecard.csv')
alpha_beta = pd.read_csv('alpha_beta.csv')

print("--- Validation Checks ---")

# 1. Scorecard validations
print("\nScorecard Bounds Check:")
print(f"Final Score Range: {scorecard['Final Score'].min()} to {scorecard['Final Score'].max()} (Expected 0 to 100)")
assert (scorecard['Final Score'] >= 0).all() and (scorecard['Final Score'] <= 100).all(), "Scores out of bounds"

print("\nScorecard Ranking Check:")
print(f"Ranks unique: {scorecard['Overall Rank'].nunique() == len(scorecard)}")
print(f"Sorted correctly: {scorecard['Final Score'].is_monotonic_decreasing}")
assert scorecard['Final Score'].is_monotonic_decreasing, "Not sorted by final score"

# 2. Alpha Beta Validations
print("\nAlpha/Beta Data Types and Missing:")
print(alpha_beta.info())
print("\nAlpha bounds sample:", alpha_beta['Alpha'].describe())
print("Beta bounds sample:", alpha_beta['Beta'].describe())

print("\nAll validation checks passed successfully.")
