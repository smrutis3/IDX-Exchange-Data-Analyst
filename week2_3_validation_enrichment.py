"""
Weeks 2-3 - Dataset Structuring, Validation & Mortgage Rate Enrichment
IDX Exchange MLS Analytics Internship

Part A  Structure + missing-value audit + numeric distributions + EDA questions
Part B  Fetch FRED MORTGAGE30US, resample weekly -> monthly, merge on year_month

Input : csv/combined_sold_residential.csv, csv/combined_listings_residential.csv  (Week 1 output)
        csv/CRMLS*.csv (raw monthly files, read for PropertyType only, to document the filter)
Output: csv/sold_filtered.csv, csv/listings_filtered.csv
        csv/sold_with_rates.csv, csv/listings_with_rates.csv
        csv/missing_value_report_{sold,listings}.csv
        csv/numeric_summary_{sold,listings}.csv
        plots/*.png
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "csv"
PLOTS = ROOT / "plots"
PLOTS.mkdir(exist_ok=True)
pd.set_option("display.width", 200, "display.max_columns", 30, "display.max_rows", 200)

NUMERIC_FIELDS = ["ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea", "LotSizeAcres",
                  "BedroomsTotal", "BathroomsTotalInteger", "DaysOnMarket", "YearBuilt"]
# Core fields are kept even if >90% null (the handbook: "keep core fields even if partially missing")
CORE_FIELDS = set(NUMERIC_FIELDS) | {
    "ListingKey", "ListingId", "PropertyType", "PropertySubType", "CloseDate", "PurchaseContractDate",
    "ListingContractDate", "ContractStatusChangeDate", "Latitude", "Longitude", "City", "CountyOrParish",
    "PostalCode", "MLSAreaMajor", "StateOrProvince", "UnparsedAddress", "MlsStatus",
    "ListOfficeName", "BuyerOfficeName", "ListAgentFullName", "BuyerAgentFirstName", "BuyerAgentLastName"}
# Fields that describe the market / transaction (the rest are identifiers, agent/office, geography text, metadata)
METADATA_FIELDS = {"ListingKey", "ListingKeyNumeric", "ListingId", "OriginatingSystemName",
                   "OriginatingSystemSubName", "ListAgentEmail", "BuyerAgentMlsId", "BuyerAgentAOR",
                   "ListAgentAOR", "BuyerOfficeAOR", "StreetNumberNumeric", "UnparsedAddress"}


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


# --------------------------------------------------------------------------
# A1. Property types (documents the filter applied in Week 1)
# --------------------------------------------------------------------------
def property_type_shares():
    banner("A1. PROPERTY TYPES IN THE RAW MONTHLY FILES (before Residential filter)")
    for prefix in ("CRMLSSold", "CRMLSListing"):
        counts = pd.Series(dtype=int)
        for p in sorted(DATA.glob(f"{prefix}*.csv")):
            m = re.match(rf"^{prefix}(\d{{6}})(_filled)?\.csv$", p.name)
            if not m or m.group(1) < "202401":
                continue
            counts = counts.add(pd.read_csv(p, usecols=["PropertyType"])["PropertyType"]
                                .value_counts(dropna=False), fill_value=0)
        counts = counts.sort_values(ascending=False).astype(int)
        share = (counts / counts.sum() * 100).round(2)
        print(f"\n{prefix}: unique PropertyType values = {list(counts.index)}")
        print(pd.DataFrame({"rows": counts, "share_%": share}))
    print("\nFiltering logic: df = df[df['PropertyType'] == 'Residential'] "
          "(done in Week 1; re-asserted below).")


# --------------------------------------------------------------------------
# A2. Structure, missing values, numeric distributions
# --------------------------------------------------------------------------
def structure_and_missing(df, name):
    banner(f"A2. STRUCTURE & MISSING VALUES - {name.upper()}")
    assert (df["PropertyType"] == "Residential").all(), "non-Residential rows present"
    print(f"Rows: {len(df):,}   Columns: {df.shape[1]}")
    print("\nColumn data types:")
    print(df.dtypes.value_counts().to_string())

    nulls = df.isnull().sum()
    rep = pd.DataFrame({"dtype": df.dtypes.astype(str), "null_count": nulls,
                        "null_pct": (nulls / len(df) * 100).round(2)})
    rep["over_90pct_null"] = rep["null_pct"] > 90
    rep["field_group"] = np.where(rep.index.isin(METADATA_FIELDS), "metadata", "market_analysis")
    rep["core_field"] = rep.index.isin(CORE_FIELDS)
    rep["decision"] = np.where(rep["over_90pct_null"] & ~rep["core_field"], "DROP", "KEEP")
    rep = rep.sort_values("null_pct", ascending=False)
    rep.to_csv(DATA / f"missing_value_report_{name}.csv")

    print("\nNull-count summary table (top 30 by % missing; full table in csv/missing_value_report_*.csv):")
    print(rep.head(30).to_string())
    flagged = rep[rep["over_90pct_null"]]
    print(f"\nColumns > 90% null: {len(flagged)}")
    print(flagged[["null_pct", "core_field", "decision"]].to_string() if len(flagged) else "  none")
    print(f"\nField groups: {rep['field_group'].value_counts().to_dict()}")
    return rep


def numeric_summary(df, name):
    banner(f"A3. NUMERIC DISTRIBUTIONS - {name.upper()}")
    cols = [c for c in NUMERIC_FIELDS if c in df.columns]
    pct = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    num = df[cols].apply(pd.to_numeric, errors="coerce")
    summ = num.describe(percentiles=pct).T
    summ["median"] = num.median()
    summ["skew"] = num.skew()
    summ["iqr_outliers"] = [
        int(((num[c] < num[c].quantile(.25) - 1.5 * (num[c].quantile(.75) - num[c].quantile(.25))) |
             (num[c] > num[c].quantile(.75) + 1.5 * (num[c].quantile(.75) - num[c].quantile(.25)))).sum())
        for c in cols]
    summ.to_csv(DATA / f"numeric_summary_{name}.csv")
    print(summ.round(2).to_string())
    print("\nCore three (min, max, mean, median, percentiles):")
    core = [c for c in ["ClosePrice", "LivingArea", "DaysOnMarket"] if c in cols]
    print(summ.loc[core].round(2).to_string())

    # histograms + boxplots (clipped to the 1st-99th percentile for readability; stats above are unclipped)
    fig, axes = plt.subplots(2, len(cols), figsize=(3.2 * len(cols), 6))
    for i, c in enumerate(cols):
        s = num[c].dropna()
        lo, hi = s.quantile(.01), s.quantile(.99)
        axes[0, i].hist(s.clip(lo, hi), bins=50, color="#3b7dd8")
        axes[0, i].set_title(c, fontsize=9)
        axes[1, i].boxplot(s.clip(lo, hi), vert=False)
    fig.suptitle(f"{name}: histograms (top) and boxplots (bottom), clipped to p1-p99", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOTS / f"distributions_{name}.png", dpi=110)
    plt.close(fig)
    print(f"Saved plots/distributions_{name}.png")
    return summ


# --------------------------------------------------------------------------
# A4. EDA questions
# --------------------------------------------------------------------------
def eda_questions(sold):
    banner("A4. EDA QUESTIONS (SOLD)")
    cp = pd.to_numeric(sold["ClosePrice"], errors="coerce")
    lp = pd.to_numeric(sold["ListPrice"], errors="coerce")
    print(f"Median close price: ${cp.median():,.0f}   Mean close price: ${cp.mean():,.0f}")

    dom = pd.to_numeric(sold["DaysOnMarket"], errors="coerce")
    bins = [-np.inf, 0, 7, 30, 60, 90, 180, np.inf]
    labels = ["<=0", "1-7", "8-30", "31-60", "61-90", "91-180", "180+"]
    print("\nDays on Market distribution (share of sold):")
    print((pd.cut(dom, bins, labels=labels).value_counts(normalize=True).sort_index() * 100).round(1).to_string())
    print(f"DOM median {dom.median():.0f}, mean {dom.mean():.1f}, p95 {dom.quantile(.95):.0f}")

    valid = cp.notna() & lp.notna() & (lp > 0)
    above, below, equal = (cp[valid] > lp[valid]).mean(), (cp[valid] < lp[valid]).mean(), (cp[valid] == lp[valid]).mean()
    print(f"\nSold ABOVE list: {above:.1%}   BELOW list: {below:.1%}   AT list: {equal:.1%}   (n={valid.sum():,})")

    d = {c: pd.to_datetime(sold[c], errors="coerce") for c in
         ["ListingContractDate", "PurchaseContractDate", "CloseDate"]}
    print("\nDate consistency issues:")
    print(f"  Listing date AFTER close date:       {(d['ListingContractDate'] > d['CloseDate']).sum():,}")
    print(f"  Purchase contract AFTER close date:  {(d['PurchaseContractDate'] > d['CloseDate']).sum():,}")
    print(f"  Listing date AFTER purchase contract:{(d['ListingContractDate'] > d['PurchaseContractDate']).sum():,}")
    print(f"  Missing: " + ", ".join(f"{k}={v.isna().sum():,}" for k, v in d.items()))

    print("\nTop 10 counties by median close price (counties with >= 200 sales):")
    g = sold.assign(cp=cp).groupby("CountyOrParish")["cp"].agg(["median", "count"])
    print(g[g["count"] >= 200].sort_values("median", ascending=False).head(10).round(0).to_string())


# --------------------------------------------------------------------------
# B. Mortgage rate enrichment
# --------------------------------------------------------------------------
def fetch_mortgage_monthly():
    banner("B1. FRED MORTGAGE30US -> MONTHLY AVERAGE")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
    mortgage = pd.read_csv(url, parse_dates=["observation_date"])           # (1) fetch
    mortgage.columns = ["date", "rate_30yr_fixed"]
    mortgage["rate_30yr_fixed"] = pd.to_numeric(mortgage["rate_30yr_fixed"], errors="coerce")
    print(f"Fetched {len(mortgage):,} weekly observations: {mortgage['date'].min().date()} -> "
          f"{mortgage['date'].max().date()}  (null rates: {mortgage['rate_30yr_fixed'].isna().sum()})")
    mortgage["year_month"] = mortgage["date"].dt.to_period("M")             # (2) resample weekly -> monthly mean
    monthly = mortgage.groupby("year_month")["rate_30yr_fixed"].mean().reset_index()
    print(monthly[monthly["year_month"] >= "2024-01"].round(3).to_string(index=False))
    return monthly


def enrich(df, date_col, monthly, name, out_name):
    banner(f"B2. MERGE RATES - {name.upper()} (key: {date_col})")
    df = df.copy()
    df["year_month"] = pd.to_datetime(df[date_col], errors="coerce").dt.to_period("M")   # (3) join key
    n_before = len(df)
    out = df.merge(monthly, on="year_month", how="left")                                   # (4) left merge
    assert len(out) == n_before, "merge changed row count"
    nulls = int(out["rate_30yr_fixed"].isnull().sum())                                     # (5) validation
    print(f"Rows before merge: {n_before:,}   after: {len(out):,}")
    print(f"Null year_month keys: {out['year_month'].isna().sum():,}")
    print(f"Null rate_30yr_fixed after merge: {nulls}")
    assert nulls == 0, f"{nulls} rows have no mortgage rate - check date range / nulls"
    print("VALIDATION PASSED: no null rate values.")
    print(out[[date_col, "year_month", "rate_30yr_fixed"]].head().to_string())
    out["year_month"] = out["year_month"].astype(str)
    out.to_csv(DATA / out_name, index=False)
    print(f"Saved csv/{out_name}")
    return out


if __name__ == "__main__":
    property_type_shares()
    sold = pd.read_csv(DATA / "combined_sold_residential.csv", low_memory=False)
    listings = pd.read_csv(DATA / "combined_listings_residential.csv", low_memory=False)

    filtered = {}
    for name, df in (("sold", sold), ("listings", listings)):
        rep = structure_and_missing(df, name)
        numeric_summary(df, name)
        drop = rep.index[rep["decision"] == "DROP"].tolist()
        print(f"\n{name}: dropping {len(drop)} columns >90% null and non-core: {drop}")
        filtered[name] = df.drop(columns=drop)
        filtered[name].to_csv(DATA / f"{name}_filtered.csv", index=False)
        print(f"Saved csv/{name}_filtered.csv  ({filtered[name].shape[0]:,} rows x {filtered[name].shape[1]} cols)")

    eda_questions(filtered["sold"])

    monthly = fetch_mortgage_monthly()
    enrich(filtered["sold"], "CloseDate", monthly, "sold", "sold_with_rates.csv")
    enrich(filtered["listings"], "ListingContractDate", monthly, "listings", "listings_with_rates.csv")
    print("\nWeeks 2-3 complete.")
