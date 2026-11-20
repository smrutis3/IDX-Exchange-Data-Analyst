"""
Week 7 - Outlier Detection and Data Quality (IQR)
IDX Exchange MLS Analytics Internship

Handbook: apply IQR filtering to key numeric fields (ClosePrice, LivingArea, DaysOnMarket); the Week 7
text also names price per square foot and the close-to-list ratio. Add outlier FLAG columns rather
than deleting records, save a full flagged dataset AND a clean filtered dataset, and compare dataset
size and medians before and after. Tiered approach: flag first, apply business rules (ClosePrice <= 0
is always invalid), and use percentiles alongside IQR.

Method (handbook formula, applied globally to each field)
    Q1, Q3 = 25th / 75th percentile;  IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR;  upper = Q3 + 1.5 * IQR;  outlier = value < lower or value > upper
  - Bounds are computed on rows that pass the business rules (a $0 price or a negative DOM would
    otherwise drag Q1 down). Null values are never flagged: a missing value cannot be judged.
  - Percentiles (p1, p99) are printed beside every bound to show how much of the tail IQR cuts.

Fields checked
    ClosePrice, LivingArea, days_on_market        (handbook deliverable)
    price_per_sqft, close_to_original_list_ratio  (named in the Week 7 text)
  days_on_market is DaysOnMarket with negatives already set to null in Week 6.

Rules
  - Rows are never deleted from the flagged dataset. `exclude_from_analysis` marks the rows left out of
    the filtered dataset (tiered, so legitimate high-end and slow sales are not wiped out):
      tier 1  business-rule invalid rows (ClosePrice/ListPrice/LivingArea <= 0, DaysOnMarket < 0,
              negative bedrooms/bathrooms)                                   -> always excluded
      tier 2  1.5 x IQR outlier on ClosePrice, LivingArea or days_on_market  -> excluded (handbook fields)
      tier 3  price_per_sqft and close_to_original_list_ratio: flagged at 1.5 x IQR but excluded only when
              EXTREME (3 x IQR, `*_extreme_flag`). A 1.5 x fence on these cuts normal sales (a ratio below
              0.855 is a real discount); the 3 x fence still removes the source errors
              (ratios in the millions, $1M+ per sq ft).
  - Date-order and coordinate flags from Weeks 4-5 do NOT exclude a row: they do not affect these
    price/size/time metrics, and dropping them would remove homes from the zip/map dashboards.
  - Repeated ListingKeys are kept (each has a different CloseDate, so it is not a safe duplicate).
  - Sold and Listings are each judged on their own distribution. Closed-sale fields are null for
    non-closed Listings rows, so those rows are never flagged on them.

Input : csv/sold_featured.csv, csv/listings_featured.csv
Output: csv/sold_flagged.csv,    csv/listings_flagged.csv     (every row, with outlier flag columns)
        csv/sold_analysis.csv,   csv/listings_analysis.csv    (filtered analysis datasets)
        csv/outlier_bounds_{sold,listings}.csv, csv/outlier_before_after_{sold,listings}.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "csv"
pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_rows", 200)

# column -> flag name
FIELDS = {
    "ClosePrice": "closeprice_outlier_flag",
    "LivingArea": "livingarea_outlier_flag",
    "days_on_market": "dom_outlier_flag",
    "price_per_sqft": "ppsf_outlier_flag",
    "close_to_original_list_ratio": "close_to_list_outlier_flag",
}
EXTREME_K = 3.0   # IQR multiplier for the exclusion fence on price_per_sqft / close_to_original_list_ratio
EXTREME = {"price_per_sqft": "ppsf_extreme_flag", "close_to_original_list_ratio": "close_to_list_extreme_flag"}
EXCLUDE_FLAGS = ["closeprice_outlier_flag", "livingarea_outlier_flag", "dom_outlier_flag"] + list(EXTREME.values())
COMPARE = ["ClosePrice", "LivingArea", "days_on_market", "price_per_sqft", "close_to_original_list_ratio"]


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def iqr_bounds(s):
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return q1, q3, iqr, q1 - 1.5 * iqr, q3 + 1.5 * iqr


def flag_outliers(df, name):
    banner(f"IQR OUTLIER FLAGS - {name.upper()}")
    # Business rules (always invalid) from Weeks 4-5
    business = df["any_invalid_numeric_flag"].astype(bool)
    print(f"rows={len(df):,}   business-rule invalid (any_invalid_numeric_flag): {business.sum():,}")
    valid = df[~business]

    rows = []
    for col, flag in FIELDS.items():
        s = pd.to_numeric(valid[col], errors="coerce").dropna()
        s = s[s > 0] if col != "days_on_market" else s       # a ratio/price/area must be positive
        q1, q3, iqr, lo, hi = iqr_bounds(s)
        x = pd.to_numeric(df[col], errors="coerce")
        df[flag] = ((x < lo) | (x > hi)) & ~business         # NaN compares False -> never flagged
        n_lo, n_hi = int(((x < lo) & ~business).sum()), int(((x > hi) & ~business).sum())
        rows.append({"field": col, "n_used": len(s), "Q1": q1, "Q3": q3, "IQR": iqr, "lower": lo, "upper": hi,
                     "p1": s.quantile(.01), "p99": s.quantile(.99), "max": s.max(),
                     "below_lower": n_lo, "above_upper": n_hi, "flagged": n_lo + n_hi,
                     "flagged_pct": round(100 * (n_lo + n_hi) / max(len(s), 1), 2)})
    for col, flag in EXTREME.items():            # tier 3: extreme fence
        s = pd.to_numeric(valid[col], errors="coerce").dropna()
        s = s[s > 0]
        _, _, _, lo, hi = iqr_bounds(s)
        q1, q3 = s.quantile(.25), s.quantile(.75)
        lo, hi = q1 - EXTREME_K * (q3 - q1), q3 + EXTREME_K * (q3 - q1)
        x = pd.to_numeric(df[col], errors="coerce")
        df[flag] = ((x < lo) | (x > hi)) & ~business
        rows.append({"field": f"{col} (extreme, {EXTREME_K:g}xIQR)", "n_used": len(s), "Q1": q1, "Q3": q3,
                     "IQR": q3 - q1, "lower": lo, "upper": hi, "p1": s.quantile(.01), "p99": s.quantile(.99),
                     "max": s.max(), "below_lower": int(((x < lo) & ~business).sum()),
                     "above_upper": int(((x > hi) & ~business).sum()), "flagged": int(df[flag].sum()),
                     "flagged_pct": round(100 * df[flag].sum() / max(len(s), 1), 2)})
    bounds = pd.DataFrame(rows).set_index("field")
    print("\nIQR bounds, with percentiles for context (handbook: use percentiles alongside IQR):")
    print(bounds.round(3).to_string())

    flags = list(FIELDS.values())
    df["any_outlier_flag"] = df[flags].any(axis=1)                       # any 1.5 x IQR flag (informational)
    df["exclude_from_analysis"] = business | df[EXCLUDE_FLAGS].any(axis=1)
    print("\nRows flagged per rule:")
    print(df[flags + list(EXTREME.values()) + ["any_outlier_flag"]].sum().to_frame("flagged").to_string())
    print(f"\nExcluded from analysis (tier 1 business rules, tier 2 IQR on price/area/DOM, "
          f"tier 3 extreme ppsf/ratio): {df['exclude_from_analysis'].sum():,} "
          f"of {len(df):,} ({df['exclude_from_analysis'].mean():.1%})")
    return df, bounds


def subtype_sensitivity(df):
    """Not the method - a check on how much a single global ClosePrice range favours cheap subtypes/areas."""
    banner("SENSITIVITY CHECK (not applied): global vs. per-group IQR on ClosePrice")
    d = df[~df["any_invalid_numeric_flag"].astype(bool) & df["ClosePrice"].gt(0)]
    for by in ("PropertySubType", "CountyOrParish"):
        def per_group(x):
            _, _, _, lo, hi = iqr_bounds(x)
            return int(((x < lo) | (x > hi)).sum())
        per = d.groupby(by)["ClosePrice"].apply(per_group).sum()
        glob = d["closeprice_outlier_flag"].sum()
        print(f"  global IQR flags {glob:,} ClosePrice outliers; per-{by} IQR would flag {per:,}")
    cty = d.groupby("CountyOrParish").agg(n=("ClosePrice", "size"), flagged=("closeprice_outlier_flag", "sum"))
    cty["pct_flagged"] = (cty["flagged"] / cty["n"] * 100).round(1)
    print("\nShare of each county's sales flagged as ClosePrice outliers by the GLOBAL rule "
          "(top 8 counties by % flagged, >= 500 sales):")
    print(cty[cty["n"] >= 500].sort_values("pct_flagged", ascending=False).head(8).to_string())


def before_after(full, kept, name):
    banner(f"BEFORE vs. AFTER FILTERING - {name.upper()}")
    rows = [{"metric": "rows", "before": len(full), "after": len(kept),
             "change_pct": round(100 * (len(kept) - len(full)) / len(full), 2)}]
    for c in COMPARE:
        b, a = full[c].median(), kept[c].median()
        rows.append({"metric": f"median {c}", "before": b, "after": a,
                     "change_pct": round(100 * (a - b) / b, 2) if b else np.nan})
    for c in ("ClosePrice", "price_per_sqft"):
        b, a = full[c].mean(), kept[c].mean()
        rows.append({"metric": f"mean {c}", "before": b, "after": a, "change_pct": round(100 * (a - b) / b, 2)})
    out = pd.DataFrame(rows).set_index("metric")
    print(out.round(3).to_string())
    print(f"\nMax ClosePrice: {full['ClosePrice'].max():,.0f} -> {kept['ClosePrice'].max():,.0f};  "
          f"max LivingArea: {full['LivingArea'].max():,.0f} -> {kept['LivingArea'].max():,.0f};  "
          f"max days_on_market: {full['days_on_market'].max():,.0f} -> {kept['days_on_market'].max():,.0f}")
    return out


def main():
    for name in ("sold", "listings"):
        df = pd.read_csv(DATA / f"{name}_featured.csv", low_memory=False)
        n = len(df)
        df, bounds = flag_outliers(df, name)
        if name == "sold":
            subtype_sensitivity(df)
        kept = df[~df["exclude_from_analysis"]]
        cmp = before_after(df, kept, name)

        assert len(df) == n, "flagged dataset must keep every row"
        assert len(kept) + df["exclude_from_analysis"].sum() == n
        assert (kept["ClosePrice"].dropna() > 0).all() and (kept["LivingArea"].dropna() > 0).all()
        assert (kept["DaysOnMarket"].dropna() >= 0).all()

        df.to_csv(DATA / f"{name}_flagged.csv", index=False)
        kept.to_csv(DATA / f"{name}_analysis.csv", index=False)
        bounds.round(4).to_csv(DATA / f"outlier_bounds_{name}.csv")
        cmp.round(4).to_csv(DATA / f"outlier_before_after_{name}.csv")
        print(f"\nSaved {name}_flagged.csv ({n:,} rows x {df.shape[1]} cols) and "
              f"{name}_analysis.csv ({len(kept):,} rows)")
    print("\nWeek 7 complete.")


if __name__ == "__main__":
    main()
