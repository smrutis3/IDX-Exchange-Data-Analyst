"""
Week 6 - Feature Engineering and Market Metrics
IDX Exchange MLS Analytics Internship

Takes the Weeks 4-5 cleaned datasets and engineers the market metrics that power the
Tableau dashboards, then summarizes them by segment.

Metrics created
  price_ratio                   ClosePrice / ListPrice            (final list price: negotiation at the end)
  close_to_original_list_ratio  ClosePrice / OriginalListPrice    (includes the full price-reduction history)
  price_per_sqft                ClosePrice / LivingArea
  days_on_market                DaysOnMarket (raw field, negatives -> null)
  close_year / close_month / close_yrmo   derived from CloseDate
  listing_to_contract_days      PurchaseContractDate - ListingContractDate
  contract_to_close_days        CloseDate - PurchaseContractDate

Rules
  - Rows are never dropped here. A metric is set to null (not imputed) when its inputs are
    invalid, using the Week 4-5 rules: price <= 0, LivingArea <= 0, DaysOnMarket < 0, or a
    date pair in the wrong order. Extreme-but-valid values are left for Week 7 (IQR).
  - Listings holds every MlsStatus. Closed-sale metrics (prices, ratios, PPSF, close date
    fields, contract-to-close) are only computed for MlsStatus == 'Closed'.
    listing_to_contract_days and days_on_market need no close, so they use any row with the inputs.
  - Segment tables use Closed sales only and require a minimum number of sales per segment.

Input : csv/sold_cleaned.csv, csv/listings_cleaned.csv
Output: csv/sold_featured.csv, csv/listings_featured.csv, csv/segment_*.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "csv"
pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_rows", 200)

DATE_COLS = ["CloseDate", "PurchaseContractDate", "ListingContractDate", "ContractStatusChangeDate"]
MIN_SALES = 100          # minimum closed sales for a segment to be reported
TOP_OFFICES = 25         # offices shown in the competitive tables
NEW_COLS = ["price_ratio", "close_to_original_list_ratio", "price_per_sqft", "days_on_market",
            "close_year", "close_month", "close_yrmo", "listing_to_contract_days", "contract_to_close_days"]


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def safe_ratio(num, den):
    """num/den where both are positive; otherwise null."""
    ok = (num > 0) & (den > 0)
    return (num / den).where(ok)


def engineer(df, name):
    banner(f"FEATURE ENGINEERING - {name}")
    n = len(df)
    closed = df["MlsStatus"].eq("Closed")
    print(f"rows={n:,}  closed={closed.sum():,}")

    # Price metrics (closed sales only)
    df["price_ratio"] = safe_ratio(df["ClosePrice"], df["ListPrice"]).where(closed)
    df["close_to_original_list_ratio"] = safe_ratio(df["ClosePrice"], df["OriginalListPrice"]).where(closed)
    df["price_per_sqft"] = safe_ratio(df["ClosePrice"], df["LivingArea"]).where(closed)

    # Days on market: raw field, negative values are invalid
    df["days_on_market"] = df["DaysOnMarket"].where(df["DaysOnMarket"] >= 0)

    # Time keys from CloseDate (null for rows that have not closed)
    cd = df["CloseDate"].where(closed)
    df["close_year"] = cd.dt.year.astype("Int64")
    df["close_month"] = cd.dt.month.astype("Int64")
    df["close_yrmo"] = cd.dt.strftime("%Y-%m")

    # Timeline durations; an out-of-order pair is null rather than a negative duration
    l2c = (df["PurchaseContractDate"] - df["ListingContractDate"]).dt.days
    c2c = (df["CloseDate"] - df["PurchaseContractDate"]).dt.days
    df["listing_to_contract_days"] = l2c.where(l2c >= 0)
    df["contract_to_close_days"] = c2c.where((c2c >= 0) & closed)

    print("\nNon-null counts and what was nulled (inputs present but invalid):")
    rows = []
    for c in NEW_COLS:
        rows.append({"metric": c, "non_null": int(df[c].notna().sum()),
                     "pct_of_rows": round(100 * df[c].notna().mean(), 1)})
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"  listing_to_contract_days nulled for wrong order: {int((l2c < 0).sum()):,}")
    print(f"  contract_to_close_days   nulled for wrong order: {int(((c2c < 0) & closed).sum()):,}")

    print("\nDistribution of engineered metrics (closed sales):")
    dist = df.loc[closed, [c for c in NEW_COLS if df[c].dtype.kind in "fi" and c not in
                           ("close_year", "close_month")]].describe(percentiles=[.01, .5, .99]).T
    print(dist.round(3).to_string())
    print("  (extremes such as price_per_sqft or ratios far from 1 are handled in Week 7)")
    return df


def sample_table(df, name):
    banner(f"SAMPLE OUTPUT - {name} (first 8 closed rows with all metrics populated)")
    cols = ["ListingKey", "OriginalListPrice", "ListPrice", "ClosePrice", "LivingArea"] + NEW_COLS
    ok = df["MlsStatus"].eq("Closed") & df[NEW_COLS].notna().all(axis=1)
    print(df.loc[ok, cols].head(8).round(3).to_string(index=False))


def summarize(df, by, min_n=MIN_SALES, top=None):
    """Segment summary on closed sales."""
    d = df[df["MlsStatus"].eq("Closed") & df["ClosePrice"].gt(0)]
    g = d.groupby(by, dropna=False)
    out = pd.DataFrame({
        "sales": g.size(),
        "median_close_price": g["ClosePrice"].median(),
        "mean_close_price": g["ClosePrice"].mean().round(0),
        "median_price_per_sqft": g["price_per_sqft"].median(),
        "median_days_on_market": g["days_on_market"].median(),
        "median_price_ratio": g["price_ratio"].median(),
        "median_close_to_orig_list": g["close_to_original_list_ratio"].median(),
        "pct_sold_over_list": g["price_ratio"].apply(lambda s: (s.dropna() > 1).mean() * 100),
        "median_listing_to_contract_days": g["listing_to_contract_days"].median(),
        "median_contract_to_close_days": g["contract_to_close_days"].median(),
    })
    out = out[out["sales"] >= min_n].sort_values("sales", ascending=False)
    if top:
        out = out.head(top)
    return out.round(3)


def segments(df, label):
    banner(f"SEGMENT ANALYSIS - {label} (closed sales; segments with >= {MIN_SALES} sales)")
    specs = {
        "propertytype": ("PropertyType", None),
        "propertysubtype": ("PropertySubType", None),
        "county": ("CountyOrParish", None),
        "mlsareamajor": ("MLSAreaMajor", 40),
        "listoffice": ("ListOfficeName", TOP_OFFICES),
        "buyeroffice": ("BuyerOfficeName", TOP_OFFICES),
        "year_month": ("close_yrmo", None),
    }
    for key, (col, top) in specs.items():
        t = summarize(df, col, top=top)
        path = DATA / f"segment_{label}_{key}.csv"
        t.to_csv(path)
        title = f"By {col}" + (f" (top {top} by sales)" if top else "")
        print(f"\n{title}  [{len(t)} segments] -> {path.name}")
        if key in ("year_month", "mlsareamajor"):
            print(t.head(12).to_string())
        else:
            print(t.to_string())


def main():
    results = {}
    for name, label in (("Sold", "sold"), ("Listings", "listings")):
        df = pd.read_csv(DATA / f"{label}_cleaned.csv", parse_dates=DATE_COLS, low_memory=False)
        df = engineer(df, name)
        sample_table(df, name)
        out = DATA / f"{label}_featured.csv"
        df.to_csv(out, index=False)
        print(f"\nSaved {out.name}: {len(df):,} rows x {df.shape[1]} cols")
        results[label] = df

    segments(results["sold"], "sold")
    segments(results["listings"], "listings")

    banner("SANITY CHECKS")
    s = results["sold"]
    assert (s["price_per_sqft"].dropna() > 0).all()
    assert (s["days_on_market"].dropna() >= 0).all()
    assert (s["listing_to_contract_days"].dropna() >= 0).all()
    assert (s["contract_to_close_days"].dropna() >= 0).all()
    l = results["listings"]
    assert l.loc[l["MlsStatus"] != "Closed", ["price_ratio", "price_per_sqft", "close_yrmo"]].isna().all().all()
    print("OK: metrics are positive / non-negative; non-closed listings have no closed-sale metrics.")


if __name__ == "__main__":
    main()
