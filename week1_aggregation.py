import os
import glob
import pandas as pd

# ==========================================
# 1. SET UP FILE PATHS
# ==========================================
# Get lists of all Sold and Listing CSV files from Jan 2024 onwards
sold_files = sorted(glob.glob("CRMLSSold2024*.csv"))
listing_files = sorted(glob.glob("CRMLSListing2024*.csv"))

print(f"Found {len(sold_files)} Sold files.")
print(f"Found {len(listing_files)} Listing files.\n")


# ==========================================
# 2. AGGREGATE SOLD TRANSACTIONS
# ==========================================
print("--- PROCESSING SOLD TRANSACTIONS ---")
sold_dfs = []
total_individual_sold_rows = 0

for file in sold_files:
    df = pd.read_csv(file, low_memory=False)
    row_count = len(df)
    total_individual_sold_rows += row_count
    # Row count before concatenation (per individual file)
    print(f"File: {file} | Row count: {row_count}")
    sold_dfs.append(df)

# Concatenate all sold DataFrames
sold_combined = pd.concat(sold_dfs, ignore_index=True)

# Row counts before and after concatenation
print(f"\nSum of individual Sold file rows: {total_individual_sold_rows}")
print(f"Total rows AFTER concatenation: {len(sold_combined)}")

# Row count BEFORE filtering for PropertyType == 'Residential'
rows_before_filter_sold = len(sold_combined)
print(f"Rows before Residential filter: {rows_before_filter_sold}")

# Filter for Residential properties
sold_residential = sold_combined[sold_combined['PropertyType'] == 'Residential'].copy()

# Row count AFTER filtering for PropertyType == 'Residential'
rows_after_filter_sold = len(sold_residential)
print(f"Rows after Residential filter: {rows_after_filter_sold}")
print(f"Removed {rows_before_filter_sold - rows_after_filter_sold} non-residential rows.")

# Export to CSV
sold_residential.to_csv("combined_sold_residential.csv", index=False)
print("Saved: combined_sold_residential.csv\n")


# ==========================================
# 3. AGGREGATE LISTINGS TRANSACTIONS
# ==========================================
print("--- PROCESSING LISTINGS TRANSACTIONS ---")
listing_dfs = []
total_individual_listing_rows = 0

for file in listing_files:
    df = pd.read_csv(file, low_memory=False)
    row_count = len(df)
    total_individual_listing_rows += row_count
    # Row count before concatenation (per individual file)
    print(f"File: {file} | Row count: {row_count}")
    listing_dfs.append(df)

# Concatenate all listing DataFrames
listing_combined = pd.concat(listing_dfs, ignore_index=True)

# Row counts before and after concatenation
print(f"\nSum of individual Listing file rows: {total_individual_listing_rows}")
print(f"Total rows AFTER concatenation: {len(listing_combined)}")

# Row count BEFORE filtering for PropertyType == 'Residential'
rows_before_filter_listing = len(listing_combined)
print(f"Rows before Residential filter: {rows_before_filter_listing}")

# Filter for Residential properties
listing_residential = listing_combined[listing_combined['PropertyType'] == 'Residential'].copy()

# Row count AFTER filtering for PropertyType == 'Residential'
rows_after_filter_listing = len(listing_residential)
print(f"Rows after Residential filter: {rows_after_filter_listing}")
print(f"Removed {rows_before_filter_listing - rows_after_filter_listing} non-residential rows.")

# Export to CSV
listing_residential.to_csv("combined_listings_residential.csv", index=False)
print("Saved: combined_listings_residential.csv\n")

print("Processing complete!")