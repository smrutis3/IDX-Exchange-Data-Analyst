import pandas as pd
import numpy as np

# ==========================================
# 1. LOAD WEEK 1 RESIDENTIAL DATASETS
# ==========================================
print("--- 1. LOADING COMBINED RESIDENTIAL DATASETS ---")
sold = pd.read_csv("combined_sold_residential.csv", low_memory=False)
listings = pd.read_csv("combined_listings_residential.csv", low_memory=False)

print(f"Sold Dataset Shape: {sold.shape}")
print(f"Listings Dataset Shape: {listings.shape}\n")


# ==========================================
# 2. MISSING VALUE ANALYSIS (>90% NULL REPORT)
# ==========================================
def analyze_missing_values(df, dataset_name):
    print(f"--- 2. MISSING VALUE ANALYSIS: {dataset_name.upper()} ---")
    total_rows = len(df)
    null_counts = df.isnull().sum()
    null_pcts = (null_counts / total_rows) * 100
    
    missing_df = pd.DataFrame({
        'Null Count': null_counts,
        'Null Percentage (%)': null_pcts.round(2)
    })
    
    # Flag columns with >90% missing values
    high_missing = missing_df[missing_df['Null Percentage (%)'] > 90.0]
    
    print(f"Total Columns Analyzed: {len(df.columns)}")
    print(f"Columns with >90% Missing Values: {len(high_missing)}")
    if not high_missing.empty:
        print("\nColumns flagged with >90% nulls:")
        print(high_missing)
    else:
        print("No columns found with >90% missing values.")
    print("\n" + "="*50 + "\n")

analyze_missing_values(sold, "Sold Transactions")
analyze_missing_values(listings, "Listings Transactions")


# ==========================================
# 3. NUMERIC DISTRIBUTION SUMMARY
# ==========================================
print("--- 3. NUMERIC DISTRIBUTION SUMMARY ---")

def generate_numeric_summary(df, cols, dataset_name):
    print(f"[{dataset_name}] Distribution Summary for Key Numeric Fields:")
    summary_data = []
    
    for col in cols:
        if col in df.columns:
            # Coerce non-numeric values to NaN safely
            s = pd.to_numeric(df[col], errors='coerce').dropna()
            stats = {
                'Field': col,
                'Min': s.min(),
                '25%': s.quantile(0.25),
                'Median (50%)': s.median(),
                'Mean': s.mean(),
                '75%': s.quantile(0.75),
                'Max': s.max()
            }
            summary_data.append(stats)
        else:
            print(f"Warning: Column '{col}' not found in {dataset_name}.")
            
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    print("\n")

# Target fields specified in the internship handbook
target_fields = ['ClosePrice', 'LivingArea', 'DaysOnMarket']

generate_numeric_summary(sold, target_fields, "Sold Dataset")


# ==========================================
# 4. FETCH FRED MORTGAGE RATE DATA
# ==========================================
print("--- 4. FETCHING FRED 30-YEAR MORTGAGE RATE DATA ---")
fred_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
mortgage = pd.read_csv(fred_url, parse_dates=['observation_date'])
mortgage.columns = ['date', 'rate_30yr_fixed']

print(f"Fetched {len(mortgage)} weekly rate observations from FRED.")
print(mortgage.head(), "\n")


# ==========================================
# 5. RESAMPLE WEEKLY RATES TO MONTHLY AVERAGES
# ==========================================
print("--- 5. RESAMPLING MORTGAGE RATES TO MONTHLY AVERAGES ---")
mortgage['year_month'] = mortgage['date'].dt.to_period('M')
mortgage_monthly = (
    mortgage.groupby('year_month')['rate_30yr_fixed']
    .mean()
    .reset_index()
)

print("Sample Monthly Mortgage Averages:")
print(mortgage_monthly.tail(12).to_string(index=False), "\n")


# ==========================================
# 6. CREATE JOIN KEYS & MERGE DATASETS
# ==========================================
print("--- 6. MERGING MORTGAGE RATES ONTO MLS DATASETS ---")

# Sold dataset key off CloseDate
sold['CloseDate'] = pd.to_datetime(sold['CloseDate'], errors='coerce')
sold['year_month'] = sold['CloseDate'].dt.to_period('M')

# Listings dataset key off Listing ContractDate (or ListingContractDate)
listing_date_col = 'Listing ContractDate' if 'Listing ContractDate' in listings.columns else 'ListingContractDate'
listings[listing_date_col] = pd.to_datetime(listings[listing_date_col], errors='coerce')
listings['year_month'] = listings[listing_date_col].dt.to_period('M')

# Perform Left Merges
sold_enriched = sold.merge(mortgage_monthly, on='year_month', how='left')
listings_enriched = listings.merge(mortgage_monthly, on='year_month', how='left')


# ==========================================
# 7. VALIDATE MERGE COMPLETENESS
# ==========================================
print("--- 7. MERGE VALIDATION CHECK ---")
null_rates_sold = sold_enriched['rate_30yr_fixed'].isnull().sum()
null_rates_listings = listings_enriched['rate_30yr_fixed'].isnull().sum()

print(f"Unmatched/Null Mortgage Rates in Sold Dataset: {null_rates_sold}")
print(f"Unmatched/Null Mortgage Rates in Listings Dataset: {null_rates_listings}")

if null_rates_sold == 0 and null_rates_listings == 0:
    print("SUCCESS: All records successfully enriched with 30-year mortgage rates!\n")
else:
    print("WARNING: Some records failed to match a mortgage rate period.\n")


# Preview Enriched Data
print("Enriched Sold Dataset Sample:")
print(sold_enriched[['CloseDate', 'year_month', 'ClosePrice', 'rate_30yr_fixed']].head(), "\n")


# ==========================================
# 8. SAVE ENRICHED DATASETS
# ==========================================
print("--- 8. SAVING ENRICHED DATASETS ---")
sold_enriched.to_csv("sold_enriched.csv", index=False)
listings_enriched.to_csv("listings_enriched.csv", index=False)

print("Saved: sold_enriched.csv")
print("Saved: listings_enriched.csv")
print("\nWeeks 2-3 Processing Complete!")