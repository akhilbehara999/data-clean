import requests
import pandas as pd
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_nav_data(scheme_code, scheme_name):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    logging.info(f"Fetching data for {scheme_name} ({scheme_code}) from {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Check if 'data' key exists in the response
        if 'data' in data and data['data']:
            df = pd.DataFrame(data['data'])

            # Add scheme code and name to the dataframe for identification
            df['scheme_code'] = scheme_code
            df['scheme_name'] = scheme_name

            filename = f"data/raw/nav_{scheme_code}.csv"
            df.to_csv(filename, index=False)
            logging.info(f"Successfully saved data for {scheme_name} to {filename}")
            return True
        else:
            logging.warning(f"No data found for {scheme_name} ({scheme_code})")
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data for {scheme_name} ({scheme_code}): {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error processing data for {scheme_name} ({scheme_code}): {e}")
        return False

def main():
    schemes = {
        "125497": "HDFC Top 100 Direct",
        "119551": "SBI Bluechip",
        "120503": "ICICI Bluechip",
        "118632": "Nippon Large Cap",
        "119092": "Axis Bluechip",
        "120841": "Kotak Bluechip"
    }

    # Ensure output directory exists
    os.makedirs("data/raw", exist_ok=True)

    for code, name in schemes.items():
        fetch_nav_data(code, name)

if __name__ == "__main__":
    main()
