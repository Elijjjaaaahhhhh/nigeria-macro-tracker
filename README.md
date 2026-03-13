# Nigeria Macro Economic Tracker

A live, automated dashboard tracking Nigeria's macroeconomic 
health across 7 key indicators with a composite Economic 
Stress Index (0-100).

## Live Dashboard
[View on Microsoft Fabric](https://app.powerbi.com/links/6r1cIiVavp?ctid=72ca12ad-1c5b-400e-a56e-de2f46920121&pbi_source=linkShare)

## Current Reading
- Stress Score: 51.73 — AMBER
- Last Updated: March 2026

## Indicators Tracked
1. NGN/USD Exchange Rate (CBN)
2. Inflation Rate YoY (CBN)
3. Monetary Policy Rate (CBN)
4. Brent Crude Price (Yahoo Finance)
5. External Reserves (CBN)
6. GDP Growth Rate (World Bank)
7. Remittance Inflows (World Bank)

## Tech Stack
- Python 3.14 — data pipeline
- GitHub Actions — weekly automation
- Power BI — dashboard
- Microsoft Fabric — cloud publishing

## Methodology
The Economic Stress Index uses min-max normalisation 
with fixed historical bounds, weighted composite scoring, 
and three stress bands: GREEN (0-33), AMBER (34-66), 
RED (67-100).

## Project Structure
nigeria-macro-tracker/
├── data/
│   ├── raw/          # dated backup CSVs
│   └── processed/    # clean CSVs for Power BI
├── scripts/
│   ├── fetch_data.py
│   └── stress_index.py
├── .github/workflows/
│   └── update_data.yml
└── dashboard/
    └── nigeria-macro-tracker.pbix
