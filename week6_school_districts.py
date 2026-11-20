"""
Week 6 (cont.) - School District Enrichment
IDX Exchange MLS Analytics Internship

Handbook: "Add school districts using the properties' latitude and longitude values."

Spatial join of each property's coordinates to the California Department of Education
School District Areas 2025-26 boundary file (data.ca.gov / gis.data.ca.gov). The boundary file has
three district types that overlap: Unified (K-12), Elementary (K-8) and High (9-12). A home in an
Elementary district also sits inside a High School district, so two columns are produced.

Columns added
  school_district         Unified district, or the Elementary district when there is no Unified one
  school_district_type    'Unified' / 'Elementary'
  school_district_cds     CDS code of school_district (join key to CDE enrollment / test-score data)
  high_school_district    High School district (equals the Unified district for Unified areas)
  school_district_source  polygon | nearest_1km | no_valid_coordinates | unmatched

Rules
  - Only rows with usable coordinates (geo_invalid_flag == False from Weeks 4-5) are joined.
    Rows with missing/invalid coordinates get 'Unknown' - coordinates are never guessed.
  - Points that fall just outside every polygon (shoreline, simplified boundaries) are assigned to the
    nearest district only if it is within 1 km; the source column records that this happened.
  - Rows are never dropped or duplicated; the row count must be identical before and after.

Setup : run with the project virtualenv (geopandas is not installed in the base environment):
        .venv/bin/python week6_school_districts.py
Input : csv/sold_featured.csv, csv/listings_featured.csv (Week 6 output)
        geo/raw_download/sd/DistrictAreas2526.shp  (CDE boundary file, shapefile download)
Output: csv/sold_featured.csv, csv/listings_featured.csv (school columns added in place)
        csv/segment_{sold,listings}_schooldistrict.csv
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "csv"
SHP = ROOT / "geo" / "raw_download" / "sd" / "DistrictAreas2526.shp"
NEAREST_M = 1000        # max distance for the nearest-district fallback
MIN_SALES = 100
SCHOOL_COLS = ["school_district", "school_district_type", "school_district_cds",
               "high_school_district", "school_district_source"]
pd.set_option("display.width", 220, "display.max_columns", 40, "display.max_rows", 200)


def banner(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def load_districts():
    banner("BOUNDARY FILE")
    g = gpd.read_file(SHP)
    keep = ["CDSCode", "DistrictNa", "DistrictTy", "CountyName", "geometry"]
    g = g[keep].rename(columns={"DistrictNa": "district", "DistrictTy": "dtype", "CDSCode": "cds"})
    g["geometry"] = g.geometry.make_valid()       # a few polygons have self-intersections
    g = g.to_crs(4326)
    print(f"{len(g)} districts: {g['dtype'].value_counts().to_dict()}   CRS -> EPSG:4326")
    return g


def lookup_for_points(pts, districts):
    """pts: DataFrame with unique lat/lon. Returns one row per point with the school columns."""
    gp = gpd.GeoDataFrame(pts.copy(), geometry=gpd.points_from_xy(pts["lon"], pts["lat"]), crs=4326)
    hit = gpd.sjoin(gp, districts, how="left", predicate="intersects").drop(columns="index_right")
    # polygon area in a metric CRS, so overlaps resolve to the smallest (most specific) polygon
    area = districts.to_crs(3310).geometry.area
    hit["area"] = hit["cds"].map(districts.assign(area=area.values).drop_duplicates("cds").set_index("cds")["area"])
    hit = hit.sort_values("area")

    primary = (hit[hit["dtype"].isin(["Unified", "Elementary"])]
               .drop_duplicates(["lat", "lon"]).set_index(["lat", "lon"])[["district", "dtype", "cds"]])
    high = (hit[hit["dtype"].isin(["High"])]
            .drop_duplicates(["lat", "lon"]).set_index(["lat", "lon"])["district"])
    out = pts.set_index(["lat", "lon"]).join(primary).join(high.rename("high_district"))
    out = out.rename(columns={"district": "school_district", "dtype": "school_district_type",
                              "cds": "school_district_cds"})
    out["school_district_source"] = np.where(out["school_district"].notna(), "polygon", "unmatched")

    # nearest-district fallback (primary types only), metric CRS
    miss = out[out["school_district"].isna()].reset_index()
    if len(miss):
        mp = gpd.GeoDataFrame(miss[["lat", "lon"]], geometry=gpd.points_from_xy(miss["lon"], miss["lat"]),
                              crs=4326).to_crs(3310)
        prim = districts[districts["dtype"].isin(["Unified", "Elementary"])].to_crs(3310)
        near = gpd.sjoin_nearest(mp, prim, how="left", max_distance=NEAREST_M).drop_duplicates(["lat", "lon"])
        near = near.dropna(subset=["district"]).set_index(["lat", "lon"])
        idx = near.index
        out.loc[idx, "school_district"] = near["district"]
        out.loc[idx, "school_district_type"] = near["dtype"]
        out.loc[idx, "school_district_cds"] = near["cds"]
        out.loc[idx, "school_district_source"] = "nearest_1km"
        # high school district for those points: nearest High polygon too
        hp = districts[districts["dtype"] == "High"].to_crs(3310)
        nh = gpd.sjoin_nearest(mp.set_index(["lat", "lon"]).loc[idx].reset_index(), hp, how="left",
                               max_distance=NEAREST_M).drop_duplicates(["lat", "lon"]).set_index(["lat", "lon"])
        out.loc[idx, "high_district"] = nh["district"].reindex(idx).values

    # Unified districts cover grades 9-12 themselves
    uni = out["school_district_type"].eq("Unified")
    out.loc[uni, "high_district"] = out.loc[uni, "school_district"]
    return out.rename(columns={"high_district": "high_school_district"})


def enrich(df, label, districts):
    banner(f"SCHOOL DISTRICT JOIN - {label.upper()}")
    n = len(df)
    df = df.drop(columns=[c for c in SCHOOL_COLS if c in df.columns])
    usable = ~df["geo_invalid_flag"].astype(bool) & df["Latitude"].notna() & df["Longitude"].notna()
    keys = pd.DataFrame({"lat": df.loc[usable, "Latitude"].round(6), "lon": df.loc[usable, "Longitude"].round(6)})
    uniq = keys.drop_duplicates().reset_index(drop=True)
    print(f"rows={n:,}  usable coordinates={usable.sum():,}  unique points to join={len(uniq):,}")

    lk = lookup_for_points(uniq, districts)
    joined = keys.join(lk, on=["lat", "lon"])
    joined.index = keys.index
    for c in ["school_district", "school_district_type", "school_district_cds", "high_school_district",
              "school_district_source"]:
        df[c] = joined[c].reindex(df.index)
    df.loc[~usable, "school_district_source"] = "no_valid_coordinates"
    df["school_district_source"] = df["school_district_source"].fillna("unmatched")
    for c in ["school_district", "high_school_district"]:
        df[c] = df[c].fillna("Unknown")

    assert len(df) == n, "row count changed"
    src = df["school_district_source"].value_counts()
    print("\nMatch source:")
    print(pd.DataFrame({"rows": src, "pct": (src / n * 100).round(2)}).to_string())
    m = df["school_district"].ne("Unknown")
    print(f"\nRows with a school district: {m.sum():,} ({m.mean():.1%});  distinct districts: "
          f"{df.loc[m, 'school_district'].nunique()}")
    print("District type of matched rows:", df.loc[m, "school_district_type"].value_counts().to_dict())
    return df


def county_check(df, districts):
    """Sanity check: the matched district's county should usually equal CountyOrParish."""
    banner("SANITY CHECK - district county vs. listing county")
    cty = districts.drop_duplicates("cds").set_index("cds")["CountyName"]
    m = df["school_district_cds"].notna()
    dc = df.loc[m, "school_district_cds"].map(cty).str.casefold()
    lc = df.loc[m, "CountyOrParish"].astype(str).str.casefold()
    agree = (dc == lc).mean()
    print(f"matched rows whose district county == CountyOrParish: {agree:.1%} "
          "(districts can span a county line, so 100% is not expected)")
    return agree


def school_segment(df, label):
    d = df[df["MlsStatus"].eq("Closed") & df["ClosePrice"].gt(0) & df["school_district"].ne("Unknown")]
    g = d.groupby("school_district")
    out = pd.DataFrame({
        "sales": g.size(),
        "median_close_price": g["ClosePrice"].median(),
        "median_price_per_sqft": g["price_per_sqft"].median(),
        "median_days_on_market": g["days_on_market"].median(),
        "median_close_to_orig_list": g["close_to_original_list_ratio"].median(),
    })
    out = out[out["sales"] >= MIN_SALES].sort_values("sales", ascending=False).round(3)
    path = DATA / f"segment_{label}_schooldistrict.csv"
    out.to_csv(path)
    print(f"\nBy school_district (>= {MIN_SALES} sales) [{len(out)} districts] -> {path.name}")
    print(out.head(15).to_string())


def main():
    districts = load_districts()
    for label in ("sold", "listings"):
        path = DATA / f"{label}_featured.csv"
        df = pd.read_csv(path, low_memory=False)
        df = enrich(df, label, districts)
        county_check(df, districts)
        school_segment(df, label)
        df.to_csv(path, index=False)
        print(f"\nSaved {path.name}: {len(df):,} rows x {df.shape[1]} cols")


if __name__ == "__main__":
    main()
