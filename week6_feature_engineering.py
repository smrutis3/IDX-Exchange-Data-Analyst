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
  - Segment tables use Closed sales only and require a minimum number of sales per segment
    (the year_month table is the exception: every month is kept, in chronological order).
  - Office names are normalized into list_office_clean / buyer_office_clean (spelling, case,
    punctuation and legal-suffix variants of the same brokerage are merged; placeholders such
    as 'NONMEMBER MRML' and nulls are labelled, not ranked). The original columns are untouched
    and the full old -> new mapping is saved for review.

Input : csv/sold_cleaned.csv, csv/listings_cleaned.csv
Output: csv/sold_featured.csv, csv/listings_featured.csv, csv/segment_*.csv, csv/office_name_mapping.csv
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "csv"
pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_rows", 200)

DATE_COLS = ["CloseDate", "PurchaseContractDate", "ListingContractDate", "ContractStatusChangeDate"]
MIN_SALES = 100          # minimum closed sales for a segment to be reported
TOP_OFFICES = 100        # offices shown in the competitive tables (handbook: top 100)
NEW_COLS = ["price_ratio", "close_to_original_list_ratio", "price_per_sqft", "days_on_market",
            "close_year", "close_month", "close_yrmo", "listing_to_contract_days", "contract_to_close_days"]


# --- Office name normalization -------------------------------------------------------------
NONMEMBER = "Non-member / Out of Area"
UNKNOWN = "Unknown"
PLACEHOLDER_KEYS = {"none mrml", "none", "n/a", "na"}
PLACEHOLDER_RE = re.compile(r"non[- ]?member|out of area")   # NONMEMBER MRML, Non-Member Office, ...
LEGAL_SUFFIX = re.compile(r"\s+(inc|incorporated|llc|corp|corporation|co|lp)$")
# Same company under a different registered/brand name (confirmed brand renames only).
KEY_ALIASES = {"redfin corporation": "redfin", "real broker": "real brokerage technologies"}


def office_key(name):
    """Grouping key: case, punctuation, whitespace and legal suffix are ignored."""
    if pd.isna(name):
        return None
    k = re.sub(r"[.,'\u2019]", "", str(name).casefold().replace("&", " and "))
    k = re.sub(r"\s+", " ", k).strip()
    k = LEGAL_SUFFIX.sub("", k)
    return KEY_ALIASES.get(k, k)


def build_office_map(*series):
    """Map every raw office name to one clean label (the most common spelling in its group)."""
    counts = pd.concat([s.value_counts() for s in series]).groupby(level=0).sum()
    m = pd.DataFrame({"raw_name": counts.index, "records": counts.values})
    m["key"] = m["raw_name"].map(office_key)
    best = m.sort_values("records", ascending=False).drop_duplicates("key").set_index("key")["raw_name"]
    m["clean_name"] = m["key"].map(best)
    is_placeholder = m["key"].isin(PLACEHOLDER_KEYS) | m["key"].str.contains(PLACEHOLDER_RE, na=False)
    m.loc[is_placeholder, "clean_name"] = NONMEMBER
    return m.sort_values(["clean_name", "records"], ascending=[True, False])


def apply_office_map(s, m):
    lookup = m.set_index("raw_name")["clean_name"]
    return s.map(lookup).fillna(UNKNOWN)


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def safe_ratio(num, den):
    """num/den where both are positive; otherwise null."""
    ok = (num > 0) & (den > 0)
    return (num / den).where(ok)


def engineer(df, name, office_map):
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

    # Normalized office names for the competitive analysis (originals kept)
    df["list_office_clean"] = apply_office_map(df["ListOfficeName"], office_map)
    df["buyer_office_clean"] = apply_office_map(df["BuyerOfficeName"], office_map)

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


def summarize(df, by, min_n=MIN_SALES, top=None, exclude=(), by_index=False):
    """Segment summary on closed sales. by_index=True sorts by segment (e.g. chronologically)."""
    d = df[df["MlsStatus"].eq("Closed") & df["ClosePrice"].gt(0)]
    d = d[~d[by].isin(exclude)]
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
    out = out[out["sales"] >= min_n]
    out = out.sort_index() if by_index else out.sort_values("sales", ascending=False)
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
        "listoffice": ("list_office_clean", TOP_OFFICES),
        "buyeroffice": ("buyer_office_clean", TOP_OFFICES),
        "year_month": ("close_yrmo", None),
    }
    for key, (col, top) in specs.items():
        if key == "year_month":      # full monthly series, chronological, no minimum
            t = summarize(df, col, min_n=1, by_index=True)
        else:
            # offices: placeholders are not brokerages, so they are not ranked
            t = summarize(df, col, top=top, exclude=(NONMEMBER, UNKNOWN) if "office" in col else ())
        path = DATA / f"segment_{label}_{key}.csv"
        t.to_csv(path)
        title = f"By {col}" + (f" (top {top} by sales)" if top else "")
        print(f"\n{title}  [{len(t)} segments] -> {path.name}")
        if key == "mlsareamajor":
            print(t.head(12).to_string())
        elif "office" in key:
            print(t.head(25).to_string())
        else:
            print(t.to_string())


def main():
    results = {}
    raw = {label: pd.read_csv(DATA / f"{label}_cleaned.csv", parse_dates=DATE_COLS, low_memory=False)
           for label in ("sold", "listings")}
    office_map = build_office_map(*[raw[k][c] for k in raw for c in ("ListOfficeName", "BuyerOfficeName")])
    office_map.to_csv(DATA / "office_name_mapping.csv", index=False)
    banner("OFFICE NAME NORMALIZATION")
    print(f"raw distinct names: {len(office_map):,} -> clean distinct names: {office_map['clean_name'].nunique():,}"
          f"  -> office_name_mapping.csv")
    multi = office_map.groupby("clean_name").filter(lambda g: len(g) > 1).sort_values("records", ascending=False)
    print("Largest merged groups (raw spelling -> clean name):")
    print(multi.head(30)[["raw_name", "records", "clean_name"]].to_string(index=False))

    for name, label in (("Sold", "sold"), ("Listings", "listings")):
        df = engineer(raw[label], name, office_map)
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
    ym = pd.read_csv(DATA / "segment_sold_year_month.csv")["close_yrmo"]
    assert ym.is_monotonic_increasing, "year_month segment must be chronological"
    assert len(ym) == len(pd.period_range(ym.iloc[0], ym.iloc[-1], freq="M")), "year_month has gaps"
    assert not (s["list_office_clean"].isna() | s["buyer_office_clean"].isna()).any()
    l = results["listings"]
    assert l.loc[l["MlsStatus"] != "Closed", ["price_ratio", "price_per_sqft", "close_yrmo"]].isna().all().all()
    print("OK: metrics are positive / non-negative; non-closed listings have no closed-sale metrics.")


if __name__ == "__main__":
    main()
