import pandas as pd
import os
import json

def clean_investor_transactions():
    print("=== Cleaning Investor Transactions ===")
    df = pd.read_csv('data/raw/08_investor_transactions.csv')
    initial_rows = len(df)

    # 1. Parse date
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    invalid_dates = df['transaction_date'].isna().sum()

    # 2. Standardize transaction_type
    # "SIP", "Lumpsum", "Redemption"
    mapping = {
        'sip': 'SIP', 'systematic investment plan': 'SIP', 's i p': 'SIP',
        'lumpsum': 'Lumpsum', 'lump sum': 'Lumpsum', 'one time': 'Lumpsum',
        'redemption': 'Redemption', 'redeem': 'Redemption', 'withdrawal': 'Redemption'
    }

    def standardize_tx(val):
        if pd.isna(val): return val
        v = str(val).strip().lower()
        return mapping.get(v, str(val).strip().capitalize())

    df['transaction_type'] = df['transaction_type'].apply(standardize_tx)

    valid_tx_types = ['SIP', 'Lumpsum', 'Redemption']
    df['transaction_type'] = df['transaction_type'].apply(lambda x: x if x in valid_tx_types else x) # The user requires only standard ones. If not, what do we do? We should probably keep track.

    # 3. Validate amount > 0
    df['amount_inr'] = pd.to_numeric(df['amount_inr'], errors='coerce')
    invalid_amounts = df[(df['amount_inr'].isna()) | (df['amount_inr'] <= 0)]
    invalid_amount_count = len(invalid_amounts)

    # 4. KYC Status Enum ['Verified', 'Pending']
    valid_kyc = ['Verified', 'Pending']
    invalid_kyc = df[~df['kyc_status'].isin(valid_kyc)]
    invalid_kyc_count = len(invalid_kyc)

    # Clean up df for the final dataset - drop invalid rows
    df = df.dropna(subset=['transaction_date'])
    df = df[df['amount_inr'] > 0]
    df = df[df['kyc_status'].isin(valid_kyc)]
    df = df[df['transaction_type'].isin(valid_tx_types)]

    final_rows = len(df)

    report = {
        "Dataset": "investor_transactions",
        "Rows before cleaning": initial_rows,
        "Rows after cleaning": final_rows,
        "Invalid transaction amounts": int(invalid_amount_count),
        "Invalid dates": int(invalid_dates),
        "Invalid KYC statuses": int(invalid_kyc_count),
        "Standardization mappings applied": mapping
    }

    print(json.dumps(report, indent=2))

    df.to_csv('data/processed/investor_transactions_clean.csv', index=False)
    return report

if __name__ == "__main__":
    clean_investor_transactions()
