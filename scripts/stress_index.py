# ============================================================
# Nigeria Economic Stress Index Calculator
# stress_index.py
# ============================================================
# PURPOSE: Takes the macro_indicators.csv produced by
#          fetch_data.py and calculates a composite stress
#          score (0-100) for each time period where we have
#          sufficient data across all indicators.
#
# OUTPUT:  data/processed/stress_index.csv
#
# METHODOLOGY:
#   1. For each indicator, normalise to 0-1 scale (min-max)
#   2. Invert indicators where high value = low stress
#   3. Apply weights and sum to composite score
#   4. Multiply by 100 for 0-100 scale
#   5. Assign GREEN/AMBER/RED band
# ============================================================

import pandas as pd
import numpy as np
import os
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

# File paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "processed")
INPUT_FILE = os.path.join(PROCESSED_DIR, "macro_indicators.csv")
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "stress_index.csv")

# ============================================================
# INDEX WEIGHTS
# These must sum to 1.0 (100%)
# ============================================================
WEIGHTS = {
    'NGN/USD Exchange Rate':          0.25,  # FX depreciation
    'Inflation Rate YoY (%)':         0.25,  # Inflation deviation
    'Brent Crude Price (USD/barrel)': 0.20,  # Oil price (inverted)
    'External Reserves (USD Billion)':0.15,  # Reserves (inverted)
    'Monetary Policy Rate (%)':       0.10,  # MPR level
    'Remittance Inflows (USD)':       0.05,  # Remittances (inverted)
}

# ============================================================
# INVERSION FLAGS
# True = high value means LOW stress (we invert the score)
# False = high value means HIGH stress (no inversion)
# ============================================================
INVERT = {
    'NGN/USD Exchange Rate':           False, # High rate = weak Naira = stress
    'Inflation Rate YoY (%)':          False, # High inflation = stress
    'Brent Crude Price (USD/barrel)':  True,  # High oil = good for Nigeria
    'External Reserves (USD Billion)': True,  # High reserves = safety
    'Monetary Policy Rate (%)':        False, # High MPR = tightening = stress
    'Remittance Inflows (USD)':        True,  # High remittances = good
}

# ============================================================
# HISTORICAL MIN/MAX FOR NORMALISATION
# These are the bounds we use to normalise each indicator.
# We use historical observed values, not theoretical limits.
# This means a new all-time high would score 1.0 (maximum stress)
# ============================================================
BOUNDS = {
    'NGN/USD Exchange Rate':           {'min': 85,    'max': 1650},
    'Inflation Rate YoY (%)':          {'min': 3,     'max': 35},
    'Brent Crude Price (USD/barrel)':  {'min': 20,    'max': 130},
    'External Reserves (USD Billion)': {'min': 20,    'max': 65},
    'Monetary Policy Rate (%)':        {'min': 6,     'max': 27},
    'Remittance Inflows (USD)':        {'min': 2e9,   'max': 22e9},
}


# ============================================================
# FUNCTION 1: Normalise A Single Value
# ============================================================
# IN:  value (float), indicator name (string)
# OUT: normalised score between 0 and 1
# ============================================================

def normalise(value, indicator_name):
    """
    Applies min-max normalisation to a single value.
    
    Formula: (value - min) / (max - min)
    
    If value is below min, returns 0 (floor)
    If value is above max, returns 1 (ceiling)
    This prevents extreme outliers from distorting the index.
    """
    
    bounds = BOUNDS[indicator_name]
    min_val = bounds['min']
    max_val = bounds['max']
    
    # Apply min-max formula
    normalised = (value - min_val) / (max_val - min_val)
    
    # Clip to 0-1 range
    # If a value exceeds our historical bounds, we cap it
    # rather than letting it push the score above 1.0
    normalised = max(0.0, min(1.0, normalised))
    
    # Invert if needed
    if INVERT[indicator_name]:
        normalised = 1.0 - normalised
    
    return normalised


# ============================================================
# FUNCTION 2: Classify Score Into Band
# ============================================================
# IN:  score (float 0-100)
# OUT: band string "GREEN", "AMBER", or "RED"
# ============================================================

def classify_band(score):
    """
    Assigns a stress band based on the composite score.
    GREEN:  0-33  = Low stress
    AMBER: 34-66  = Elevated stress
    RED:   67-100 = High stress / crisis
    """
    if score <= 33:
        return "GREEN"
    elif score <= 66:
        return "AMBER"
    else:
        return "RED"
    

# ============================================================
# FUNCTION 3: Calculate Stress Index
# ============================================================
# IN:  path to macro_indicators.csv
# OUT: saves stress_index.csv and returns DataFrame
# ============================================================

def calculate_stress_index():
    """
    Main function. Loads indicator data, normalises each
    indicator, applies weights, and outputs stress scores.
    """
    
    print("Loading indicator data...")
    
    # --- STEP 1: Load the master CSV ---
    df = pd.read_csv(INPUT_FILE)
    print(f"  Loaded {len(df):,} rows across {df['indicator'].nunique()} indicators")
    
    # --- STEP 2: Pivot the data ---
    # Currently our data is in LONG format:
    #   date | value | indicator
    #   2024 | 4.06  | GDP Growth Rate (%)
    #   2024 | 15.10 | Inflation Rate YoY (%)
    #
    # We need WIDE format for the index calculation:
    #   date | GDP Growth | Inflation | FX Rate | ...
    #
    # pivot_table does this transformation
    # Handle mixed date formats
    # Annual data comes as integer years e.g. 1996, 2024
    # Monthly/weekly data comes as YYYY-MM-DD strings
    # We convert annual years to Jan 1st of that year
    def parse_date(val):
        val = str(val).strip()
        # If it looks like a plain year e.g. "2024"
        if len(val) == 4 and val.isdigit():
            return pd.Timestamp(f"{val}-01-01")
        # Otherwise parse normally
        return pd.to_datetime(val, errors='coerce')
    
    df['date'] = df['date'].apply(parse_date)    
    pivot = df.pivot_table(
        index='date',
        columns='indicator',
        values='value',
        aggfunc='mean'  # if duplicate dates exist, average them
    )
    
    print(f"  Pivoted to wide format: {len(pivot)} dates × {len(pivot.columns)} indicators")
    
    # --- STEP 3: Resample to monthly ---
    # Different indicators have different frequencies
    # (daily FX, monthly inflation, annual GDP)
    # We resample everything to monthly using forward-fill
    # Forward-fill means: carry the last known value forward
    pivot_monthly = pivot.resample('MS').mean()
    
    # Forward fill to handle indicators updated less frequently
    # e.g. GDP is annual — we carry that value forward each month
    pivot_monthly = pivot_monthly.ffill()
    
    print(f"  Resampled to monthly: {len(pivot_monthly)} months")
    
    # --- STEP 4: Calculate normalised scores ---
    print("\nCalculating normalised scores...")
    
    # Only calculate index for indicators we have weights for
    index_indicators = list(WEIGHTS.keys())
    
    # Store normalised scores in a new DataFrame
    scores = pd.DataFrame(index=pivot_monthly.index)
    
    for indicator in index_indicators:
        if indicator not in pivot_monthly.columns:
            print(f"  WARNING: {indicator} not found in data — skipping")
            continue
        
        # Apply normalisation to every value in this column
        scores[indicator] = pivot_monthly[indicator].apply(
            lambda x: normalise(x, indicator) if pd.notna(x) else np.nan
        )
        
        latest_raw = pivot_monthly[indicator].iloc[-1]
        latest_norm = scores[indicator].iloc[-1]
        print(f"  {indicator[:35]:<35} raw: {latest_raw:>10.2f}  normalised: {latest_norm:.3f}")
    
    # --- STEP 5: Calculate weighted composite score ---
    print("\nCalculating composite stress score...")
    
    scores['stress_score'] = 0.0
    
    for indicator, weight in WEIGHTS.items():
        if indicator in scores.columns:
            scores['stress_score'] += scores[indicator] * weight
    
    # Multiply by 100 for 0-100 scale
    scores['stress_score'] = (scores['stress_score'] * 100).round(2)
    
    # --- STEP 6: Assign bands ---
    scores['stress_band'] = scores['stress_score'].apply(classify_band)
    
    # --- STEP 7: Add component contributions ---
    # This shows how much each indicator contributed to the score
    # Useful for the decomposition chart on Page 5
    for indicator, weight in WEIGHTS.items():
        if indicator in scores.columns:
            col_name = f"contrib_{indicator[:20]}"
            scores[col_name] = (scores[indicator] * weight * 100).round(2)
    
    # --- STEP 8: Remove rows with insufficient data ---
    # Only check indicators that actually exist in scores
    available_indicators = [i for i in index_indicators if i in scores.columns]
    valid_indicator_count = scores[available_indicators].notna().sum(axis=1)
    min_required = max(4, len(available_indicators) - 1)
    before = len(scores)
    scores = scores[valid_indicator_count >= min_required]
    after = len(scores)
    
    if before != after:
        print(f"  Removed {before - after} months with insufficient data")
    
    # --- STEP 9: Save output ---
    scores = scores.reset_index()
    scores.to_csv(OUTPUT_FILE, index=False)
    
    print(f"\nSaved stress index to: {OUTPUT_FILE}")
    print(f"Total months calculated: {len(scores)}")
    print(f"Earliest stress date: {scores['date'].min()}")
    print(f"\nLatest stress reading:")
    latest = scores.iloc[-1]
    print(f"  Date:   {latest['date']}")
    print(f"  Score:  {latest['stress_score']}")
    print(f"  Band:   {latest['stress_band']}")
    
    return scores


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("="*50)
    print("NIGERIA ECONOMIC STRESS INDEX CALCULATOR")
    print("="*50)
    
    results = calculate_stress_index()
    
    print("\n--- Last 6 Months ---")
    display_cols = ['date', 'stress_score', 'stress_band']
    print(results[display_cols].tail(6).to_string(index=False))
    
    print("\n" + "="*50)
    print("STRESS INDEX COMPLETE ✓")
    print("="*50)
