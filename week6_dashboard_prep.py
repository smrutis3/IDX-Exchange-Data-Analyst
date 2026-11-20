"""
Week 6 (cont.) - Dashboard Prep: ZIP, City, Agent cleanup and monthly activity table
IDX Exchange MLS Analytics Internship

Handbook (Weeks 8-10): dashboards must be filterable by city, county and zip code; competitive
dashboards need the top 100 listing agents and offices by sales volume and units; the market
dashboard needs monthly new listings and closed sales. This script prepares those fields.
Original columns are never overwritten - clean versions are added next to them.

Columns added
  zip5              5-digit ZIP ('94563-4211' -> '94563'); anything that is not a 5-digit ZIP -> 'Unknown'
  city_clean        City with spelling-case variants merged ('Marina del Rey' / 'Marina Del Rey')
  list_agent_clean  ListAgentFullName with case / punctuation / spacing variants merged

Caveat on agents: the extract has no listing-agent ID, so agents are matched by normalized NAME.
Two different agents with the identical name would be merged; this is rare and is reported below.

Input : csv/sold_featured.csv, csv/listings_featured.csv (after week6_feature_engineering.py and
        week6_school_districts.py)
Output: csv/sold_featured.csv, csv/listings_featured.csv (columns added in place; re-runnable)
        csv/agent_name_mapping.csv, csv/city_name_mapping.csv
        csv/segment_{sold,listings}_listagent.csv   (top 100 listing agents)
        csv/segment_{sold,listings}_zip.csv         (ZIP summary)
        csv/monthly_market_activity.csv             (new listings vs. closed sales by month)
"""
import re
from pathlib import Path

import pandas as pd

from week6_feature_engineering import summarize

DATA = Path(__file__).resolve().parent / "csv"
TOP_AGENTS = 100
NEW_COLS = ["zip5", "city_clean", "list_agent_clean"]
UNKNOWN = "Unknown"
pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_rows", 200)


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def to_zip5(s):
    """First 5 digits of a ZIP / ZIP+4; anything else is not a usable ZIP."""
    z = s.astype("string").str.strip().str.extract(r"^(\d{5})(?:-\d{1,4})?$")[0]
    return z.fillna(UNKNOWN).astype(object)


def most_common_spelling(raw, key):
    """Map every raw value to the most common spelling in its key group; a mixed-case spelling
    beats an ALL-CAPS / all-lower one so 'RANDY ANDERSON' becomes 'Randy Anderson' when available."""
    counts = raw.value_counts()
    m = pd.DataFrame({"raw": counts.index, "n": counts.values})
    m["key"] = m["raw"].map(key)
    m["is_mixed"] = m["raw"].map(lambda v: v != v.upper() and v != v.lower())
    best = (m.sort_values(["is_mixed", "n"], ascending=False).drop_duplicates("key")
             .set_index("key")["raw"])
    m["clean"] = m["key"].map(best)
    # names that only exist in ALL CAPS / all lower get title case ('LESLIE OLIVO' -> 'Leslie Olivo')
    shout = m["clean"].map(lambda v: v == v.upper() or v == v.lower())
    m.loc[shout, "clean"] = m.loc[shout, "clean"].str.title()
    return m


def city_key(v):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9() ]", "", v.casefold())).strip()


def agent_key(v):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", v.casefold())).strip()


def build_maps(frames):
    city = pd.concat([f["City"].dropna() for f in frames])
    agent = pd.concat([f["ListAgentFullName"].dropna() for f in frames])
    cm = most_common_spelling(city, city_key)
    am = most_common_spelling(agent, agent_key)
    cm[cm["raw"] != cm["clean"]].to_csv(DATA / "city_name_mapping.csv", index=False)
    am[am["raw"] != am["clean"]].sort_values("n", ascending=False).to_csv(DATA / "agent_name_mapping.csv", index=False)
    banner("NAME NORMALIZATION")
    print(f"City:  {len(cm):,} distinct -> {cm['clean'].nunique():,}   (changed: {(cm['raw'] != cm['clean']).sum()})")
    print(cm[cm["raw"] != cm["clean"]].sort_values("n", ascending=False).head(10)[["raw", "n", "clean"]]
          .to_string(index=False))
    print(f"\nAgent: {len(am):,} distinct -> {am['clean'].nunique():,}   (changed: {(am['raw'] != am['clean']).sum():,})")
    print(am[am["raw"] != am["clean"]].sort_values("n", ascending=False).head(10)[["raw", "n", "clean"]]
          .to_string(index=False))
    return cm.set_index("raw")["clean"], am.set_index("raw")["clean"]


def add_columns(df, label, city_map, agent_map):
    banner(f"ADD COLUMNS - {label.upper()}")
    n = len(df)
    df = df.drop(columns=[c for c in NEW_COLS if c in df.columns])
    df["zip5"] = to_zip5(df["PostalCode"])
    df["city_clean"] = df["City"].map(city_map).fillna(df["City"]).fillna(UNKNOWN)
    df["list_agent_clean"] = df["ListAgentFullName"].map(agent_map).fillna(UNKNOWN)
    assert len(df) == n
    bad = df["PostalCode"].notna() & df["zip5"].eq(UNKNOWN) & df["PostalCode"].ne(UNKNOWN)
    print(f"zip5: {(df['zip5'] != UNKNOWN).sum():,} valid; {bad.sum()} unusable PostalCode values -> Unknown "
          f"(e.g. {df.loc[bad, 'PostalCode'].head(5).tolist()})")
    non_ca = (df["zip5"] != UNKNOWN) & ~df["zip5"].str.startswith("9")
    print(f"      {non_ca.sum()} valid-format ZIPs do not start with 9 (out-of-state properties; kept as is)")
    print(f"city_clean: {df['City'].nunique():,} -> {df['city_clean'].nunique():,} distinct;  "
          f"Unknown: {(df['city_clean'] == UNKNOWN).sum():,}")
    print(f"list_agent_clean: {df['ListAgentFullName'].nunique():,} -> {df['list_agent_clean'].nunique():,} "
          f"distinct;  Unknown: {(df['list_agent_clean'] == UNKNOWN).sum():,}")
    return df


def agent_name_collision_check(df):
    """How many agent names appear under several different list offices (possible different people)?"""
    d = df[df["list_agent_clean"] != UNKNOWN]
    g = d.groupby("list_agent_clean")["list_office_clean"].nunique()
    big = d["list_agent_clean"].value_counts().head(TOP_AGENTS).index
    print(f"\nAgent-name collision check: {int((g > 1).sum()):,} of {len(g):,} agent names list under "
          f">1 office (normal when agents change brokerage); in the top {TOP_AGENTS}: {int((g.loc[big] > 1).sum())}")


def segments(df, label):
    banner(f"SEGMENTS - {label.upper()} (closed sales)")
    t = summarize(df, "list_agent_clean", min_n=1, top=TOP_AGENTS, exclude=(UNKNOWN,))
    t.to_csv(DATA / f"segment_{label}_listagent.csv")
    print(f"\nTop {TOP_AGENTS} listing agents by units -> segment_{label}_listagent.csv")
    print(t.head(10)[["sales", "sales_volume", "median_close_price", "median_days_on_market"]].to_string())
    z = summarize(df, "zip5", exclude=(UNKNOWN,))
    z.to_csv(DATA / f"segment_{label}_zip.csv")
    print(f"\nZIP summary (>= 100 sales): {len(z)} zip codes -> segment_{label}_zip.csv")
    print(z.head(5)[["sales", "median_close_price", "median_price_per_sqft"]].to_string())


def monthly_activity(sold, listings):
    """New listings (Listings file, by ListingContractDate) vs. closed sales (Sold file, by CloseDate)."""
    banner("MONTHLY MARKET ACTIVITY - new listings vs. closed sales")
    ld = pd.to_datetime(listings["ListingContractDate"], errors="coerce")
    new = (listings.assign(ym=ld.dt.strftime("%Y-%m")).dropna(subset=["ym"])
           .groupby("ym").agg(new_listings=("ListingKey", "nunique"),
                              new_listing_rows=("ListingKey", "size"),
                              median_list_price=("ListPrice", "median"),
                              median_original_list_price=("OriginalListPrice", "median")))
    cd = pd.to_datetime(sold["CloseDate"], errors="coerce")
    closed = sold[sold["MlsStatus"].eq("Closed")]
    sales = (closed.assign(ym=cd.loc[closed.index].dt.strftime("%Y-%m")).dropna(subset=["ym"])
             .groupby("ym").agg(closed_sales=("ListingKey", "size"), sales_volume=("ClosePrice", "sum"),
                                median_close_price=("ClosePrice", "median"),
                                median_days_on_market=("days_on_market", "median"),
                                median_close_to_orig_list=("close_to_original_list_ratio", "median")))
    out = new.join(sales, how="outer").sort_index()
    out.index.name = "year_month"
    out["sales_to_new_listings_ratio"] = (out["closed_sales"] / out["new_listings"]).round(3)
    out = out.loc["2024-01":"2026-04"]
    assert len(out) == len(pd.period_range("2024-01", "2026-04", freq="M")), "months missing"
    out.round(3).to_csv(DATA / "monthly_market_activity.csv")
    print(out[["new_listings", "new_listing_rows", "closed_sales", "sales_to_new_listings_ratio",
               "median_close_price", "median_days_on_market"]].to_string())
    print("\n-> monthly_market_activity.csv  (new_listings counts distinct ListingKey; "
          "new_listing_rows is the raw row count)")


def main():
    raw = {k: pd.read_csv(DATA / f"{k}_featured.csv", low_memory=False, dtype={"PostalCode": "string"})
           for k in ("sold", "listings")}
    city_map, agent_map = build_maps(list(raw.values()))
    out = {}
    for label, df in raw.items():
        out[label] = add_columns(df, label, city_map, agent_map)
    agent_name_collision_check(out["sold"])
    for label, df in out.items():
        segments(df, label)
        df.to_csv(DATA / f"{label}_featured.csv", index=False)
        print(f"\nSaved {label}_featured.csv: {len(df):,} rows x {df.shape[1]} cols")
    monthly_activity(out["sold"], out["listings"])


if __name__ == "__main__":
    main()
