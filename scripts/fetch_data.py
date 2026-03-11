# ============================================================
# Nigeria Macro Economic Tracker — Data Pipeline
# fetch_data.py
# ============================================================
# PURPOSE: Pull live data from CBN, World Bank, and Yahoo Finance
# OUTPUT:  Two CSV files saved to data/processed/
#          - macro_indicators.csv  (all 7 indicators)
#          - stress_index.csv      (composite score — built in Phase 3)
# ============================================================

# --- IMPORTS ---
# requests: sends HTTP calls to APIs and websites
import requests

# pandas: stores and manipulates data as tables (DataFrames)
import pandas as pd

# datetime: handles dates and timestamps
from datetime import datetime, timedelta

# os: lets us work with file paths and folders
import os

# time: lets us pause between API calls (prevents rate limiting)
import time

# ============================================================
# CONFIGURATION — edit these values if paths change
# ============================================================

# Get the root folder of the project (one level up from scripts/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define output paths
RAW_DIR = os.path.join(ROOT_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "processed")

# Today's date — used for timestamping files
TODAY = datetime.today().strftime('%Y-%m-%d')

print(f"Pipeline started: {TODAY}")
print(f"Raw data folder: {RAW_DIR}")
print(f"Processed data folder: {PROCESSED_DIR}")


# ============================================================
# FUNCTION 1: World Bank API — GDP Growth Rate
# ============================================================
# IN:  nothing (URL is built inside the function)
# OUT: pandas DataFrame with columns [date, value, indicator]
#      OR None if the request fails
# ============================================================

def fetch_worldbank(indicator_code, indicator_name):
    """
    Fetches annual data for Nigeria from the World Bank API.
    
    indicator_code: the World Bank code e.g. 'NY.GDP.MKTP.KD.ZG'
    indicator_name: a human-readable label e.g. 'GDP Growth Rate (%)'
    """
    
    print(f"\nFetching {indicator_name} from World Bank...")
    
    # Build the API URL
    # per_page=30 gives us 30 years of data — enough for our dashboard
    url = (
        f"https://api.worldbank.org/v2/country/NG"
        f"/indicator/{indicator_code}"
        f"?format=json&per_page=30"
    )
    
    # --- STEP 1: Make the API call ---
    try:
        # requests.get() sends a GET request to the URL
        # timeout=10 means: if no response in 10 seconds, stop trying
        response = requests.get(url, timeout=10)
        
        # status_code 200 means success
        # anything else (404, 500 etc) means something went wrong
        response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        # If anything goes wrong with the network call, print the error
        # and return None so the rest of the pipeline keeps running
        print(f"  ERROR fetching {indicator_name}: {e}")
        return None
    
    # --- STEP 2: Parse the JSON response ---
    # The World Bank returns a list with 2 items:
    # [0] = metadata (page info)
    # [1] = the actual data records
    data = response.json()
    records = data[1]
    
    # --- STEP 3: Check we actually got data ---
    if not records:
        print(f"  WARNING: No records returned for {indicator_name}")
        return None
    
    # --- STEP 4: Build a clean DataFrame ---
    rows = []
    for record in records:
        # Skip records where value is None (not published yet)
        if record['value'] is None:
            continue
        rows.append({
            'date': record['date'],        # Year as string e.g. '2024'
            'value': record['value'],      # The numeric value
            'indicator': indicator_name    # Human readable label
        })
    
    # Convert our list of rows into a pandas DataFrame
    df = pd.DataFrame(rows)
    
    # Convert date column from string to integer year
    df['date'] = pd.to_numeric(df['date'])
    
    # Sort oldest to newest
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"  SUCCESS: {len(df)} records retrieved")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Latest value: {df['value'].iloc[-1]:.2f}")
    
    return df


# ============================================================
# FUNCTION 2: Yahoo Finance — Brent Crude Oil Price
# ============================================================
# IN:  nothing
# OUT: pandas DataFrame with columns [date, value, indicator]
#      OR None if the request fails
#
# Brent Crude ticker on Yahoo Finance: BZ=F
# We pull weekly data and calculate the weekly average price
# ============================================================

def fetch_brent_crude():
    """
    Fetches Brent Crude Oil weekly price data from Yahoo Finance.
    Returns weekly average prices for the last 3 years.
    """
    
    print(f"\nFetching Brent Crude Oil Price from Yahoo Finance...")
    
    # Import yfinance inside the function
    # This is a safe pattern — if yfinance fails to import,
    # only this function fails, not the whole script
    try:
        import yfinance as yf
    except ImportError:
        print("  ERROR: yfinance not installed. Run: pip install yfinance")
        return None
    
    try:
        # --- STEP 1: Define date range ---
        # We want 3 years of history
        end_date = datetime.today()
        start_date = end_date - timedelta(days=3*365)
        
        # Format dates as strings (yfinance expects 'YYYY-MM-DD')
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # --- STEP 2: Download the data ---
        # BZ=F is the Yahoo Finance ticker for Brent Crude Futures
        # interval='1wk' gives us one row per week
        ticker = yf.Ticker("BZ=F")
        raw_df = ticker.history(
            start=start_str,
            end=end_str,
            interval="1wk"   # weekly data
        )
        
        # --- STEP 3: Check we got data ---
        if raw_df.empty:
            print("  WARNING: No data returned from Yahoo Finance")
            return None
        
        # --- STEP 4: Clean and structure the data ---
        # yfinance returns: Open, High, Low, Close, Volume columns
        # We want the weekly average = mean of High and Low
        raw_df['weekly_avg'] = (raw_df['High'] + raw_df['Low']) / 2
        
        # Reset index so date becomes a regular column
        raw_df = raw_df.reset_index()
        
        # Build our standard output DataFrame
        df = pd.DataFrame({
            # Convert to date only (remove time component)
            'date': pd.to_datetime(raw_df['Date']).dt.date,
            'value': raw_df['weekly_avg'].round(2),
            'indicator': 'Brent Crude Price (USD/barrel)'
        })
        
        # Drop any rows with missing values
        df = df.dropna()
        
        print(f"  SUCCESS: {len(df)} weekly records retrieved")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Latest value: ${df['value'].iloc[-1]:.2f}/barrel")
        
        return df
        
    except Exception as e:
        print(f"  ERROR fetching Brent Crude: {e}")
        return None

        # ============================================================
# FUNCTION 3: CBN API — NGN/USD Exchange Rate
# ============================================================
# IN:  nothing
# OUT: pandas DataFrame with columns [date, value, indicator]
#      OR None if the request fails
#
# Source: CBN hidden API endpoint discovered via browser DevTools
# We filter for "US DOLLAR" and use the centralrate column
# We then calculate weekly averages for our dashboard
# ============================================================

def fetch_cbn_fx():
    """
    Fetches NGN/USD exchange rate data from the CBN API.
    Returns weekly average central rates.
    """
    
    print(f"\nFetching NGN/USD Exchange Rate from CBN...")
    
    # The CBN API endpoint we discovered in browser DevTools
    url = "https://www.cbn.gov.ng/api/GetAllExchangeRates?format=json"
    
    try:
        # --- STEP 1: Call the API ---
        # Some websites block automated requests
        # Adding a 'User-Agent' header makes our request look like a browser
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        print(f"  ERROR fetching CBN FX data: {e}")
        return None
    
    try:
        # --- STEP 2: Parse JSON ---
        all_records = response.json()
        
        # --- STEP 3: Filter for US DOLLAR only ---
        usd_records = [
            r for r in all_records
            if r.get('currency', '').upper() == 'US DOLLAR'
        ]
        
        if not usd_records:
            print("  WARNING: No US DOLLAR records found in CBN data")
            return None
        
        print(f"  Found {len(usd_records)} USD records")
        
        # --- STEP 4: Build DataFrame ---
        df = pd.DataFrame(usd_records)
        
        # Convert date string to datetime
        # CBN format is 'YYYY-MM-DD' which pandas reads directly
        df['ratedate'] = pd.to_datetime(df['ratedate'])
        
        # Convert rate strings to numbers
        # They come as strings like "1375.6925" — we need floats
        df['centralrate'] = pd.to_numeric(df['centralrate'], errors='coerce')
        
        # --- STEP 5: Data quality check ---
        # Drop rows where rate is missing or zero
        df = df.dropna(subset=['centralrate'])
        df = df[df['centralrate'] > 0]
        
        # --- STEP 6: Calculate weekly averages ---
        # Set date as index for resampling
        df = df.set_index('ratedate')
        
        # resample('W') groups data by calendar week
        # .mean() calculates the average rate for each week
        weekly_df = df['centralrate'].resample('W').mean()
        
        # Reset index to make date a regular column again
        weekly_df = weekly_df.reset_index()
        
        # --- STEP 7: Build standard output format ---
        result_df = pd.DataFrame({
            'date': weekly_df['ratedate'].dt.date,
            'value': weekly_df['centralrate'].round(4),
            'indicator': 'NGN/USD Exchange Rate'
        })
        
        # Drop any weeks with no data
        result_df = result_df.dropna()
        
        # Sort oldest to newest
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        print(f"  SUCCESS: {len(result_df)} weekly records")
        print(f"  Date range: {result_df['date'].min()} to {result_df['date'].max()}")
        print(f"  Latest rate: ₦{result_df['value'].iloc[-1]:,.2f} per USD")
        
        return result_df
        
    except Exception as e:
        print(f"  ERROR processing CBN FX data: {e}")
        return None
    

    # ============================================================
# FUNCTION 4: CBN API — External Reserves
# ============================================================
# IN:  nothing
# OUT: pandas DataFrame with columns [date, value, indicator]
#      OR None if the request fails
#
# Source: CBN hidden API endpoint
# Value: Gross reserves converted from raw USD to USD billions
# Date format: MM/DD/YYYY (different from FX endpoint)
# ============================================================

def fetch_cbn_reserves():
    """
    Fetches Nigeria external reserves data from the CBN API.
    Returns weekly average gross reserves in USD billions.
    """
    
    print(f"\nFetching External Reserves from CBN...")
    
    url = "https://www.cbn.gov.ng/api/GetAllReserves?format=json"
    
    try:
        # --- STEP 1: Call the API ---
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        print(f"  ERROR fetching CBN Reserves data: {e}")
        return None
    
    try:
        # --- STEP 2: Parse JSON ---
        all_records = response.json()
        print(f"  Found {len(all_records)} reserve records")
        
        # --- STEP 3: Build DataFrame ---
        df = pd.DataFrame(all_records)
        
        # --- STEP 4: Convert date ---
        # IMPORTANT: CBN reserves uses MM/DD/YYYY format
        # We must tell pandas this explicitly using format parameter
        df['moveDate'] = pd.to_datetime(
            df['moveDate'],
            format='%m/%d/%Y',   # MM/DD/YYYY
            errors='coerce'       # invalid dates become NaT
        )
        
        # --- STEP 5: Convert gross reserves to number ---
        # Values come as strings like "49988795924.34"
        # We convert to billions by dividing by 1,000,000,000
        df['gross'] = pd.to_numeric(df['gross'], errors='coerce')
        df['gross_billions'] = df['gross'] / 1_000_000_000
        
        # --- STEP 6: Data quality checks ---
        # Drop rows with missing dates or zero/negative reserves
        df = df.dropna(subset=['moveDate', 'gross'])
        df = df[df['gross'] > 0]
        
        # --- STEP 7: Calculate weekly averages ---
        df = df.set_index('moveDate')
        weekly_df = df['gross_billions'].resample('W').mean()
        weekly_df = weekly_df.reset_index()
        
        # --- STEP 8: Build standard output format ---
        result_df = pd.DataFrame({
            'date': weekly_df['moveDate'].dt.date,
            'value': weekly_df['gross_billions'].round(2),
            'indicator': 'External Reserves (USD Billion)'
        })
        
        # Drop empty weeks and sort
        result_df = result_df.dropna()
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        # --- DATA QUALITY: Remove future dates ---
        # Any date beyond today is impossible — filter it out
        today = datetime.today().date()
        before_filter = len(result_df)
        result_df = result_df[result_df['date'] <= today]
        after_filter = len(result_df)
        
        if before_filter != after_filter:
            print(f"  WARNING: Removed {before_filter - after_filter} future-dated records")
        
        print(f"  SUCCESS: {len(result_df)} weekly records")
        print(f"  Date range: {result_df['date'].min()} to {result_df['date'].max()}")
        print(f"  Latest value: ${result_df['value'].iloc[-1]:.2f} billion")
        
        return result_df
        
    except Exception as e:
        print(f"  ERROR processing CBN Reserves data: {e}")
        return None


        # ============================================================
# FUNCTION 5: CBN API — Nigeria Inflation Rate
# ============================================================
# IN:  nothing
# OUT: pandas DataFrame with columns [date, value, indicator]
#      OR None if the request fails
#
# Source: CBN hidden API endpoint
# Value: allItemsYearOn = headline CPI year-on-year %
# Date: constructed from separate tyear and tmonth fields
# ============================================================

def fetch_cbn_inflation():
    """
    Fetches Nigeria monthly inflation rate from the CBN API.
    Returns headline CPI year-on-year percentage.
    """
    
    print(f"\nFetching Inflation Rate from CBN...")
    
    url = "https://www.cbn.gov.ng/api/GetAllInflationRates"
    
    try:
        # --- STEP 1: Call the API ---
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        print(f"  ERROR fetching CBN Inflation data: {e}")
        return None
    
    try:
        # --- STEP 2: Parse JSON ---
        all_records = response.json()
        print(f"  Found {len(all_records)} inflation records")
        
        # --- STEP 3: Build DataFrame ---
        df = pd.DataFrame(all_records)
        
        # --- STEP 4: Construct date from tyear and tmonth ---
        # We have separate year (2022) and month (3) columns
        # We combine them into a proper date: 2022-03-01
        # day=1 means the first of each month
        df['date'] = pd.to_datetime(
            df['tyear'].astype(str) + '-' +
            df['tmonth'].astype(str).str.zfill(2) + '-01',
            format='%Y-%m-%d',
            errors='coerce'
        )
        
        # --- STEP 5: Convert inflation rate to number ---
        # allItemsYearOn = headline CPI year-on-year %
        df['allItemsYearOn'] = pd.to_numeric(
            df['allItemsYearOn'],
            errors='coerce'
        )
        
        # --- STEP 6: Data quality checks ---
        df = df.dropna(subset=['date', 'allItemsYearOn'])
        df = df[df['allItemsYearOn'] > 0]
        
        # Remove future dates
        today = datetime.today().date()
        df_filtered = df[df['date'].dt.date <= today]
        removed = len(df) - len(df_filtered)
        if removed > 0:
            print(f"  WARNING: Removed {removed} future-dated records")
        df = df_filtered
        
        # --- STEP 7: Build standard output format ---
        result_df = pd.DataFrame({
            'date': df['date'].dt.date,
            'value': df['allItemsYearOn'],
            'indicator': 'Inflation Rate YoY (%)'
        })
        
        # Sort oldest to newest
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        print(f"  SUCCESS: {len(result_df)} monthly records")
        print(f"  Date range: {result_df['date'].min()} to {result_df['date'].max()}")
        print(f"  Latest value: {result_df['value'].iloc[-1]:.2f}%")
        
        return result_df
        
    except Exception as e:
        print(f"  ERROR processing CBN Inflation data: {e}")
        return None




    # ============================================================
# FUNCTION 6: CBN API — Monetary Policy Rate (MPR)
# ============================================================
# IN:  nothing
# OUT: pandas DataFrame with columns [date, value, indicator]
#      OR None if the request fails
#
# Source: CBN hidden API — GetAllMoneyMarketIndicators
# Value: mpr field = Monetary Policy Rate %
# Date: constructed from tyear + tmonth (same as inflation)
# ============================================================

def fetch_cbn_mpr():
    """
    Fetches Nigeria Monetary Policy Rate history from CBN API.
    Returns monthly MPR values.
    """
    
    print(f"\nFetching Monetary Policy Rate from CBN...")
    
    url = "https://www.cbn.gov.ng/api/GetAllMoneyMarketIndicators"
    
    try:
        # --- STEP 1: Call the API ---
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        print(f"  ERROR fetching CBN MPR data: {e}")
        return None
    
    try:
        # --- STEP 2: Parse JSON ---
        all_records = response.json()
        print(f"  Found {len(all_records)} money market records")
        
        # --- STEP 3: Build DataFrame ---
        df = pd.DataFrame(all_records)
        
        # --- STEP 4: Construct date from tyear and tmonth ---
        # Same pattern as inflation function
        df['date'] = pd.to_datetime(
            df['tyear'].astype(str) + '-' +
            df['tmonth'].astype(str).str.zfill(2) + '-01',
            format='%Y-%m-%d',
            errors='coerce'
        )
        
        # --- STEP 5: Convert MPR to number ---
        # mpr comes as string e.g. "14.00"
        # empty strings "" become NaN via errors='coerce'
        df['mpr'] = pd.to_numeric(df['mpr'], errors='coerce')
        
        # --- STEP 6: Data quality checks ---
        # Drop rows where MPR is missing
        df = df.dropna(subset=['date', 'mpr'])
        df = df[df['mpr'] > 0]
        
        # Remove future dates
        today = datetime.today().date()
        df_filtered = df[df['date'].dt.date <= today]
        removed = len(df) - len(df_filtered)
        if removed > 0:
            print(f"  WARNING: Removed {removed} future-dated records")
        df = df_filtered
        
        # --- STEP 7: Build standard output format ---
        result_df = pd.DataFrame({
            'date': df['date'].dt.date,
            'value': df['mpr'],
            'indicator': 'Monetary Policy Rate (%)'
        })
        
        # Sort oldest to newest
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        print(f"  SUCCESS: {len(result_df)} monthly records")
        print(f"  Date range: {result_df['date'].min()} to {result_df['date'].max()}")
        print(f"  Latest MPR: {result_df['value'].iloc[-1]:.2f}%")
        
        return result_df
        
    except Exception as e:
        print(f"  ERROR processing CBN MPR data: {e}")
        return None


        # ============================================================
# FUNCTION 7: Save All Indicators To CSV
# ============================================================
# IN:  list of DataFrames (one per indicator)
# OUT: saves two files:
#      - data/processed/macro_indicators.csv (all 7 combined)
#      - data/raw/macro_indicators_raw_YYYY-MM-DD.csv (dated backup)
# ============================================================

def save_indicators(dataframes):
    """
    Combines all indicator DataFrames and saves to CSV.
    dataframes: list of pandas DataFrames to combine
    """
    
    print(f"\nSaving data to CSV...")
    
    # --- STEP 1: Remove any None values from the list ---
    # If a source failed, its DataFrame will be None
    # We skip those and save whatever succeeded
    valid_dfs = [df for df in dataframes if df is not None]
    
    if not valid_dfs:
        print("  ERROR: No data to save — all sources failed")
        return False
    
    print(f"  Combining {len(valid_dfs)} indicator datasets...")
    
    # --- STEP 2: Combine all DataFrames into one master table ---
    # pd.concat stacks DataFrames on top of each other vertically
    master_df = pd.concat(valid_dfs, ignore_index=True)
    
    # --- STEP 3: Clean up the combined DataFrame ---
    # Convert date column to string for clean CSV output
    master_df['date'] = master_df['date'].astype(str)
    
    # Round all values to 4 decimal places
    master_df['value'] = pd.to_numeric(
        master_df['value'], errors='coerce'
    ).round(4)
    
    # Sort by indicator name and then by date
    master_df = master_df.sort_values(
        ['indicator', 'date']
    ).reset_index(drop=True)
    
    # --- STEP 4: Save processed file ---
    # This is the file Power BI will connect to
    processed_path = os.path.join(
        PROCESSED_DIR, 'macro_indicators.csv'
    )
    master_df.to_csv(processed_path, index=False)
    print(f"  Saved processed file: {processed_path}")
    
    # --- STEP 5: Save dated raw backup ---
    # We keep a dated copy every time the pipeline runs
    # This gives us a history of every data pull
    raw_path = os.path.join(
        RAW_DIR, f'macro_indicators_raw_{TODAY}.csv'
    )
    master_df.to_csv(raw_path, index=False)
    print(f"  Saved raw backup: {raw_path}")
    
    # --- STEP 6: Print summary ---
    print(f"\n  SUMMARY:")
    print(f"  Total rows: {len(master_df):,}")
    print(f"  Indicators: {master_df['indicator'].nunique()}")
    for indicator in master_df['indicator'].unique():
        count = len(master_df[master_df['indicator'] == indicator])
        print(f"    - {indicator}: {count} records")
    
    return True




# ============================================================
# MAIN PIPELINE — runs when script is executed directly
# ============================================================

if __name__ == "__main__":
    
    print("\n" + "="*50)
    print("FETCHING ALL 7 INDICATORS")
    print("="*50)
    
    # --- Fetch all sources ---
    gdp_df = fetch_worldbank(
        indicator_code="NY.GDP.MKTP.KD.ZG",
        indicator_name="GDP Growth Rate (%)"
    )
    time.sleep(1)
    
    remittance_df = fetch_worldbank(
        indicator_code="BX.TRF.PWKR.CD.DT",
        indicator_name="Remittance Inflows (USD)"
    )
    time.sleep(1)
    
    brent_df = fetch_brent_crude()
    time.sleep(1)
    
    fx_df = fetch_cbn_fx()
    time.sleep(1)
    
    reserves_df = fetch_cbn_reserves()
    time.sleep(1)
    
    inflation_df = fetch_cbn_inflation()
    time.sleep(1)
    
    mpr_df = fetch_cbn_mpr()
    
    print("\n" + "="*50)
    print("SAVING DATA")
    print("="*50)
    
    # --- Combine and save all DataFrames ---
    all_dataframes = [
        gdp_df,
        remittance_df,
        brent_df,
        fx_df,
        reserves_df,
        inflation_df,
        mpr_df
    ]
    
    success = save_indicators(all_dataframes)
    
    if success:
        print("\n" + "="*50)
        print("PIPELINE COMPLETE ✓")
        print("="*50)
    else:
        print("\nPIPELINE FAILED — check errors above")
