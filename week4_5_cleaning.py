"""
Weeks 4-5 - Data Cleaning and Preparation
IDX Exchange MLS Analytics Internship

Takes the Weeks 2-3 enriched datasets and produces analysis-ready cleaned datasets.
Principle (handbook, Week 7): FLAG questionable records rather than silently deleting them.
Only exact duplicate rows and structurally redundant columns are removed here; every
other problem becomes a boolean flag column so later weeks can filter explicitly.

Input : csv/sold_with_rates.csv, csv/listings_with_rates.csv
Output: csv/sold_cleaned.csv, csv/listings_cleaned.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "csv"
pd.set_option("display.width", 200, "display.max_columns", 40, "display.max_rows", 200)

DATE_COLS = ["CloseDate", "PurchaseContractDate", "ListingContractDate", "ContractStatusChangeDate"]
NUMERIC_COLS = ["ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea", "LotSizeAcres", "LotSizeArea",
                "LotSizeSquareFeet", "BedroomsTotal", "BathroomsTotalInteger", "DaysOnMarket", "YearBuilt",
                "Latitude", "Longitude", "ParkingTotal", "GarageSpaces", "Stories", "MainLevelBedrooms",
                "AssociationFee", "BuyerAgencyCompensation", "rate_30yr_fixed"]
# Segmentation fields: a missing value becomes an explicit 'Unknown' bucket so group-bys don't drop rows
FILL_UNKNOWN = ["PropertySubType", "CountyOrParish", "City", "MLSAreaMajor", "ListOfficeName", "PostalCode"]
# Columns removed as unnecessary (reason printed at runtime)
DROP_REASONS = {
    "ListAgentEmail": "personal contact data, not needed for market analytics",
    "OriginatingSystemName": "system metadata, ~89% null",
    "OriginatingSystemSubName": "system metadata, ~89% null",
}
# California bounding box (generous): lat 32.5-42.0, lon -124.5 to -114.1
CA_LAT, CA_LON = (32.5, 42.0), (-124.5, -114.1)


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def clean(df, name):
    banner(f"CLEANING - {name.upper()}")
    log = {"rows_start": len(df), "cols_start": df.shape[1]}
    print(f"[start] rows={len(df):,} cols={df.shape[1]}")

    # ---- 1. Duplicate-header columns (listings extraction selected some fields twice -> 'X.1') ----
    dup_cols = [c for c in df.columns if c.endswith(".1") and c[:-2] in df.columns]
    for c in dup_cols:
        diff = ~((df[c] == df[c[:-2]]) | (df[c].isna() & df[c[:-2]].isna()))
        assert diff.sum() <= 5, f"{c} differs from {c[:-2]} in {diff.sum()} rows"
        if diff.sum():   # a handful of malformed raw rows; the original column is kept
            print(f"    note: {c} differs from {c[:-2]} in {diff.sum()} row(s), original kept: "
                  f"{df.loc[diff, [c[:-2], c]].to_dict('records')}")
    if dup_cols:
        df = df.drop(columns=dup_cols)
    print(f"[1] Dropped {len(dup_cols)} duplicate-header columns (identical to originals except noted rows): {dup_cols}")

    # ---- 2. Unnecessary / redundant columns ----
    drops = {c: r for c, r in DROP_REASONS.items() if c in df.columns}
    if "ListingKeyNumeric" in df.columns:
        if df.groupby("ListingKey")["ListingKeyNumeric"].nunique().max() == 1 and \
           df.groupby("ListingKeyNumeric")["ListingKey"].nunique().max() == 1:
            drops["ListingKeyNumeric"] = "1:1 duplicate of ListingKey"
    df = df.drop(columns=list(drops))
    for c, r in drops.items():
        print(f"[2] Dropped {c}: {r}")

    # ---- 3. Standardize text: strip whitespace, empty -> NaN ----
    obj = df.select_dtypes(include="object").columns
    for c in obj:
        t = df[c].astype("string").str.strip()          # object cols can hold mixed types
        df[c] = t.mask(t == "").astype(object).where(t.notna(), np.nan)
    print(f"[3] Stripped whitespace and converted blanks to NaN in {len(obj)} text columns")

    # ---- 4. Dates -> datetime64 ----
    print("[4] Date conversion (nulls before -> after; increase = unparseable values):")
    for c in DATE_COLS:
        before = df[c].isna().sum()
        df[c] = pd.to_datetime(df[c], errors="coerce")
        print(f"    {c:<26} {before:>8,} -> {df[c].isna().sum():>8,}   dtype={df[c].dtype}")

    # ---- 5. Numeric typing ----
    print("[5] Numeric coercion (new NaNs introduced):")
    for c in [c for c in NUMERIC_COLS if c in df.columns]:
        before = df[c].isna().sum()
        df[c] = pd.to_numeric(df[c], errors="coerce")
        if df[c].isna().sum() != before:
            print(f"    {c}: +{df[c].isna().sum() - before:,} NaN")
    for c in ["BedroomsTotal", "BathroomsTotalInteger", "YearBuilt"]:
        df[c] = df[c].astype("Int64")                       # whole-number fields, nullable int
    for c in ["latfilled", "lonfilled"]:
        if c in df.columns:                                  # True where lat/lon were imputed upstream
            df[c] = df[c].map({"True": True, "False": False, True: True, False: False}).astype("boolean")
    print("    Done. BedroomsTotal/BathroomsTotalInteger/YearBuilt -> Int64; latfilled/lonfilled -> boolean")

    # ---- 6. Exact duplicate rows removed; repeated ListingKey flagged ----
    n = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"[6] Removed {n - len(df):,} exact duplicate rows ({n:,} -> {len(df):,})")
    df["duplicate_listingkey_flag"] = df["ListingKey"].duplicated(keep=False)
    print(f"    Rows sharing a ListingKey (kept, flagged): {df['duplicate_listingkey_flag'].sum():,}")

    # ---- 7. Missing values ----
    for c in [c for c in FILL_UNKNOWN if c in df.columns]:
        k = df[c].isna().sum()
        if k:
            df[c] = df[c].fillna("Unknown")
            print(f"[7] {c}: {k:,} missing -> 'Unknown'")
    print("[7] Price/size/bed/bath fields are NOT imputed (a fabricated price would bias every metric); "
          "missing values stay NaN.")

    # ---- 8. Invalid numeric values -> flags ----
    f = pd.DataFrame(index=df.index)
    f["invalid_closeprice_flag"] = df["ClosePrice"] <= 0                       # NaN compares False
    f["invalid_listprice_flag"] = df["ListPrice"] <= 0
    f["invalid_livingarea_flag"] = df["LivingArea"] <= 0
    f["invalid_dom_flag"] = df["DaysOnMarket"] < 0
    f["invalid_bedrooms_flag"] = (df["BedroomsTotal"] < 0).fillna(False).astype(bool)
    f["invalid_bathrooms_flag"] = (df["BathroomsTotalInteger"] < 0).fillna(False).astype(bool)
    f["any_invalid_numeric_flag"] = f.any(axis=1)
    df = pd.concat([df, f.astype(bool)], axis=1)
    print("[8] Invalid numeric flags (rows kept):")
    print(f.sum().to_frame("count").to_string())

    # ---- 9. Date consistency flags ----
    L, P, C = df["ListingContractDate"], df["PurchaseContractDate"], df["CloseDate"]
    df["listing_after_close_flag"] = L > C
    df["purchase_after_close_flag"] = P > C
    df["negative_timeline_flag"] = (L > P) | (L > C) | (P > C)           # any order violation
    print("[9] Date consistency flags (L=ListingContract <= P=PurchaseContract <= C=Close):")
    print(df[["listing_after_close_flag", "purchase_after_close_flag", "negative_timeline_flag"]]
          .sum().to_frame("count").to_string())

    # ---- 10. Geographic flags ----
    lat, lon = df["Latitude"], df["Longitude"]
    df["geo_missing_flag"] = lat.isna() | lon.isna()
    df["geo_zero_flag"] = (lat == 0) | (lon == 0)
    df["geo_positive_lon_flag"] = lon > 0
    present = ~df["geo_missing_flag"] & ~df["geo_zero_flag"] & ~df["geo_positive_lon_flag"]
    df["geo_out_of_state_flag"] = present & ~(lat.between(*CA_LAT) & lon.between(*CA_LON))
    df["geo_state_mismatch_flag"] = df["StateOrProvince"].notna() & (df["StateOrProvince"] != "CA")
    df["geo_invalid_flag"] = (df["geo_missing_flag"] | df["geo_zero_flag"]
                              | df["geo_positive_lon_flag"] | df["geo_out_of_state_flag"])
    geo = df[["geo_missing_flag", "geo_zero_flag", "geo_positive_lon_flag", "geo_out_of_state_flag",
              "geo_state_mismatch_flag", "geo_invalid_flag"]].sum().to_frame("count")
    geo["pct"] = (geo["count"] / len(df) * 100).round(2)
    print("[10] Geographic data quality summary:")
    print(geo.to_string())
    bad = df[df["geo_invalid_flag"] & ~df["geo_missing_flag"]]
    if len(bad):
        print("     Sample invalid (non-missing) coordinate records:")
        print(bad[["ListingKey", "City", "StateOrProvince", "Latitude", "Longitude"]].head(8).to_string(index=False))
    print("     Coordinates imputed upstream (latfilled/lonfilled == True):",
          int(df["latfilled"].fillna(False).sum()) if "latfilled" in df else "n/a")

    # ---- Summary ----
    banner(f"SUMMARY - {name.upper()}")
    print(f"Rows   : {log['rows_start']:,} -> {len(df):,}  (removed {log['rows_start'] - len(df):,} exact duplicates)")
    print(f"Columns: {log['cols_start']} -> {df.shape[1]}  "
          f"(removed {len(dup_cols) + len(drops)}, added {df.shape[1] - (log['cols_start'] - len(dup_cols) - len(drops))} flags)")
    print("\nData type confirmation:")
    chk = DATE_COLS + ["ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea", "DaysOnMarket",
                       "BedroomsTotal", "BathroomsTotalInteger", "YearBuilt", "Latitude", "Longitude"]
    print(df[chk].dtypes.astype(str).to_frame("dtype").to_string())
    flags = [c for c in df.columns if c.endswith("_flag")]
    print(f"\nRows with at least one flag: {df[flags].any(axis=1).sum():,} of {len(df):,}")
    return df


if __name__ == "__main__":
    for name in ("sold", "listings"):
        raw = pd.read_csv(DATA / f"{name}_with_rates.csv", low_memory=False)
        out = clean(raw, name)
        out.to_csv(DATA / f"{name}_cleaned.csv", index=False)
        print(f"\nSaved csv/{name}_cleaned.csv  ({out.shape[0]:,} rows x {out.shape[1]} cols)")
    print("\nWeeks 4-5 complete.")
