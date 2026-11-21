"""
Weeks 8-10 prep - Lean Tableau exports
IDX Exchange MLS Analytics Internship

The Week 7 flagged files are 380-400 MB with 100+ columns. Tableau only needs the fields behind the
handbook's required dashboards, so this script writes trimmed CSVs. It changes no data: every row of
the Week 7 flagged files is kept, and the full files remain the audit trail.

Handbook dashboards these exports feed
  market_analysis.twbx      monthly median close price, average days on market, average
                            close-to-original-list ratio, new listings, closed sales
                            (filter: city, county, zip code, PropertySubType)
  competitive_analysis.twbx top 100 listing agents and offices by sales volume and units;
                            zip-code heat maps of median close price and homes sold
                            (filter: month, city, county, zip code, PropertySubType)

Columns kept, grouped by use
  time        close_yrmo / list_yrmo (YYYY-MM), CloseDate or ListingContractDate
  geography   city_clean, CountyOrParish, zip5, mls_area_clean, school_district, Latitude, Longitude
  property    PropertySubType, LivingArea, BedroomsTotal, BathroomsTotalInteger, YearBuilt
  prices      ClosePrice, ListPrice, OriginalListPrice
  metrics     price_per_sqft, close_to_original_list_ratio, days_on_market, listing_to_contract_days,
              contract_to_close_days
  competitive list_agent_clean, list_office_clean, buyer_office_clean
  economic    rate_30yr_fixed
  quality     include_in_analysis, price_outlier_flag, timeline_extreme_flag, bad_coordinates_flag,
              duplicate_listingkey_flag

Dropped on purpose: price_ratio (identical to close_to_original_list_ratio), DaysOnMarket (use
days_on_market, the same field with invalid negatives nulled), year/month (Tableau derives them from
the date), PropertyType and StateOrProvince (constant or near-constant), school/agent/office columns not
used by a required dashboard, and the per-field outlier flags (consolidated below). Original agent,
office and area name columns stay in the upstream files.

How to use the quality flags in Tableau (full guidance in tableau/README_tableau.txt)
  include_in_analysis   False = business-rule invalid or IQR outlier (Week 7 tiered filter). Use as a data
                        source filter for "typical market" metrics: median/average price, DOM, ratios.
  price_outlier_flag    True = above the global ClosePrice IQR fence ($2.39M). Do not filter on it for
                        county or zip price charts - it removes 30% of San Mateo - use medians instead.
  timeline_extreme_flag True = listing-to-contract or contract-to-close above 365 days. Exclude only on
                        charts of those two timeline metrics.
  bad_coordinates_flag  True = missing / zero / positive-longitude / out-of-box coordinates. Exclude on
                        maps only.
  Counts such as "closed sales" and "new listings" should use ALL rows (no include_in_analysis filter)
  unless the whole dashboard is meant to show the filtered market.

Input : csv/sold_flagged.csv, csv/listings_flagged.csv
Output: tableau/tableau_sold.csv, tableau/tableau_listings.csv, tableau/README_tableau.txt
        tableau/data_dictionary.csv
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "csv"
OUT = ROOT / "tableau"
OUT.mkdir(exist_ok=True)
pd.set_option("display.width", 200, "display.max_columns", 50, "display.max_rows", 100)

GEO = ["city_clean", "CountyOrParish", "zip5", "mls_area_clean", "school_district", "Latitude", "Longitude"]
PROPERTY = ["PropertySubType", "LivingArea", "BedroomsTotal", "BathroomsTotalInteger", "YearBuilt"]
PRICES = ["ClosePrice", "ListPrice", "OriginalListPrice"]
METRICS = ["price_per_sqft", "close_to_original_list_ratio", "days_on_market",
           "listing_to_contract_days", "contract_to_close_days"]

SOLD_COLS = (["ListingKey", "CloseDate", "close_yrmo", "ListingContractDate"] + GEO + PROPERTY + PRICES + METRICS
             + ["list_agent_clean", "list_office_clean", "buyer_office_clean", "rate_30yr_fixed"])
LISTING_COLS = (["ListingKey", "ListingContractDate", "list_yrmo", "MlsStatus", "CloseDate"] + GEO + PROPERTY
                + ["ListPrice", "OriginalListPrice", "days_on_market", "list_office_clean", "list_agent_clean",
                   "rate_30yr_fixed"])
ROUND = {"price_per_sqft": 2, "close_to_original_list_ratio": 4, "rate_30yr_fixed": 4, "Latitude": 6, "Longitude": 6}


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def quality_flags(df):
    return pd.DataFrame({
        "include_in_analysis": ~df["exclude_from_analysis"].astype(bool),
        "price_outlier_flag": df["closeprice_outlier_flag"].astype(bool),
        "timeline_extreme_flag": df["timeline_extreme_flag"].astype(bool),
        "bad_coordinates_flag": df["geo_invalid_flag"].astype(bool),
        "duplicate_listingkey_flag": df["duplicate_listingkey_flag"].astype(bool),
    })


def export(name, cols, out_name, date_cols):
    banner(f"EXPORT - {name.upper()}")
    full = pd.read_csv(DATA / f"{name}_flagged.csv", low_memory=False, dtype={"zip5": "string"},
                       parse_dates=date_cols)
    n, size_in = len(full), (DATA / f"{name}_flagged.csv").stat().st_size
    if name == "listings":
        full["list_yrmo"] = full["ListingContractDate"].dt.strftime("%Y-%m")
    keep = [c for c in cols if c in full.columns]
    missing = sorted(set(cols) - set(keep))
    assert not missing, f"columns missing from the flagged file: {missing}"
    out = pd.concat([full[keep], quality_flags(full)], axis=1)
    for c, d in ROUND.items():
        if c in out.columns:
            out[c] = out[c].round(d)
    for c in date_cols:
        if c in out.columns:
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    for c in ["BedroomsTotal", "BathroomsTotalInteger", "YearBuilt"]:
        out[c] = out[c].astype("Int64")

    # checks
    assert len(out) == n, "row count changed"
    assert out["ListingKey"].notna().all()
    analysis = pd.read_csv(DATA / f"{name}_analysis.csv", usecols=["ListingKey"], low_memory=False)
    assert int(out["include_in_analysis"].sum()) == len(analysis), "include_in_analysis != Week 7 analysis rows"
    key = "close_yrmo" if name == "sold" else "list_yrmo"
    assert out[key].notna().sum() > 0

    path = OUT / out_name
    out.to_csv(path, index=False)
    size_out = path.stat().st_size
    print(f"rows: {n:,}   columns: {full.shape[1]} -> {out.shape[1]}")
    print(f"file size: {size_in / 1e6:,.0f} MB -> {size_out / 1e6:,.0f} MB  ({1 - size_out / size_in:.0%} smaller)")
    print(f"include_in_analysis rows: {int(out['include_in_analysis'].sum()):,} (matches {name}_analysis.csv)")
    print("\nNull counts of key dashboard fields (nulls are expected where noted):")
    keys = [key, "city_clean", "CountyOrParish", "zip5", "PropertySubType", "list_agent_clean", "list_office_clean"]
    if name == "sold":
        keys += ["ClosePrice", "close_to_original_list_ratio", "days_on_market"]
    print(out[[k for k in keys if k in out.columns]].isna().sum().to_frame("nulls").T.to_string())
    print(f"'Unknown' city: {(out['city_clean'] == 'Unknown').sum():,}   'Unknown' zip: "
          f"{(out['zip5'] == 'Unknown').sum():,}   'Unknown' subtype: {(out['PropertySubType'] == 'Unknown').sum():,}")
    return out


def reconcile(sold, listings):
    """Tie the exports back to the Week 6 monthly table so Tableau totals can be checked."""
    banner("RECONCILIATION with csv/monthly_market_activity.csv")
    m = pd.read_csv(DATA / "monthly_market_activity.csv", index_col="year_month")
    closed = sold.groupby("close_yrmo").size()
    new = listings.groupby("list_yrmo")["ListingKey"].nunique()
    d1 = (closed.reindex(m.index) - m["closed_sales"]).abs().max()
    d2 = (new.reindex(m.index) - m["new_listings"]).abs().max()
    print(f"max monthly difference, closed sales: {d1}   new listings (distinct ListingKey): {d2}")
    assert d1 == 0 and d2 == 0, "exports do not tie to monthly_market_activity.csv"
    print("OK: tableau exports reproduce the monthly closed-sales and new-listing counts exactly.")


DICT = [
    ("include_in_analysis", "bool", "False = business-rule invalid or IQR outlier (Week 7 tiered filter)"),
    ("price_outlier_flag", "bool", "ClosePrice above the global 1.5xIQR fence; do not use for county/zip price views"),
    ("timeline_extreme_flag", "bool", "listing-to-contract or contract-to-close > 365 days"),
    ("bad_coordinates_flag", "bool", "missing, zero, positive-longitude or out-of-box coordinates"),
    ("duplicate_listingkey_flag", "bool", "ListingKey appears on more than one row (kept, not removed)"),
    ("close_yrmo", "text YYYY-MM", "month of CloseDate (closed sales)"),
    ("list_yrmo", "text YYYY-MM", "month of ListingContractDate (new listings)"),
    ("city_clean", "text", "City with case variants merged; 'Unknown' if missing"),
    ("zip5", "text", "5-digit ZIP; 'Unknown' if not a valid ZIP. Set as a Tableau Geographic Role > ZIP Code"),
    ("mls_area_clean", "text", "MLSAreaMajor with 'Not Defined' folded into 'Unknown' (about 24% Unknown)"),
    ("school_district", "text", "CDE 2025-26 Unified or Elementary district; 'Unknown' without usable coordinates"),
    ("price_per_sqft", "float", "ClosePrice / LivingArea (closed sales only)"),
    ("close_to_original_list_ratio", "float", "ClosePrice / OriginalListPrice (handbook Price Ratio; closed sales only)"),
    ("days_on_market", "number", "DaysOnMarket with negative values set to null"),
    ("listing_to_contract_days", "number", "PurchaseContractDate - ListingContractDate"),
    ("contract_to_close_days", "number", "CloseDate - PurchaseContractDate"),
    ("list_agent_clean", "text", "ListAgentFullName with case variants merged; matched by name (no agent ID in the data)"),
    ("list_office_clean", "text", "ListOfficeName normalized; 'Non-member / Out of Area' and 'Unknown' are placeholders"),
    ("buyer_office_clean", "text", "BuyerOfficeName normalized; same placeholders"),
    ("rate_30yr_fixed", "float", "monthly average 30-year fixed rate (FRED MORTGAGE30US)"),
]

GUIDE = """TABLEAU NOTES (generated by week8_tableau_export.py)

Files
  tableau_sold.csv      one row per closed Residential sale (Jan 2024 - Apr 2026). Use for closed sales,
                        median close price, days on market, close-to-original-list ratio, price per
                        sq ft, agents, offices and the zip heat maps.
  tableau_listings.csv  one row per Residential listing. Use for NEW LISTINGS by list_yrmo.
                        (Closed-sale metrics come from tableau_sold.csv, not from this file.)
  Both are CSV on purpose - Tableau reads CSV faster than Excel. Create a Tableau extract (.hyper)
  once, then save the workbook as .twbx so the data travels with it.

Setup
  - Set zip5 to Geographic Role > ZIP Code/Postcode. 'Unknown' will show as unmatched; filter it out.
  - New listings by month: COUNTD([ListingKey]) on tableau_listings.csv by list_yrmo.
  - Closed sales by month: COUNT of rows in tableau_sold.csv by close_yrmo.
  - Median close price: MEDIAN([ClosePrice]); average DOM: AVG([days_on_market]);
    average ratio: AVG([close_to_original_list_ratio]).

Which rows to use
  - Typical-market averages and medians: filter include_in_analysis = True.
  - Counts (closed sales, new listings, top agents/offices by units): use all rows.
  - Top 100 offices/agents: exclude list_office_clean in ('Non-member / Out of Area', 'Unknown') and
    list_agent_clean = 'Unknown'. Rank by SUM(ClosePrice) for volume and COUNT for units.
  - County/zip price comparisons: do not filter on price_outlier_flag (it removes 30% of San Mateo
    sales); use medians.
  - Timeline charts only: exclude timeline_extreme_flag = True.
  - Latitude/Longitude point maps only: exclude bad_coordinates_flag = True (zip-code maps use
    zip5 and do not need it).

Known data caveats to put on the dashboards
  - New-listing counts are low in Nov-Dec 2024, Jun-Dec 2025 and especially Jan 2026 because the raw
    listing extracts are smaller in those months (about 26K rows vs. about 40K; Jan 2026 has 2.6K).
    This is an extract problem, not a market drop.
  - Agents are matched by name only; the data has no listing-agent ID.
  - Files are confidential MLS data - do not publish them. Publish only the dashboards you are allowed to share.
"""


def main():
    sold = export("sold", SOLD_COLS, "tableau_sold.csv", ["CloseDate", "ListingContractDate"])
    listings = export("listings", LISTING_COLS, "tableau_listings.csv", ["ListingContractDate", "CloseDate"])
    reconcile(sold, listings)
    cols = []
    for df, f in ((sold, "tableau_sold.csv"), (listings, "tableau_listings.csv")):
        cols += [(f, c, str(df[c].dtype)) for c in df.columns]
    desc = {k: (t, d) for k, t, d in DICT}
    dd = pd.DataFrame(cols, columns=["file", "column", "pandas_dtype"])
    dd["meaning"] = dd["column"].map(lambda c: desc.get(c, ("", ""))[1])
    dd.to_csv(OUT / "data_dictionary.csv", index=False)
    (OUT / "README_tableau.txt").write_text(GUIDE)
    banner("DONE")
    print("Wrote tableau/tableau_sold.csv, tableau_listings.csv, data_dictionary.csv, README_tableau.txt")


if __name__ == "__main__":
    main()
