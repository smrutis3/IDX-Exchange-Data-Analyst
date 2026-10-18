"""
Week 1 - Monthly Dataset Aggregation
IDX Exchange MLS Analytics Internship

Concatenates every monthly CRMLS file (January 2024 -> latest month available)
into one Listings dataset and one Sold dataset, filters both to
PropertyType == 'Residential', and saves them as new CSVs.

Input : csv/CRMLSListingYYYYMM.csv, csv/CRMLSSoldYYYYMM[_filled].csv
Output: csv/combined_listings_residential.csv, csv/combined_sold_residential.csv

Notes
- Files are discovered with a regex on the YYYYMM token (not a hardcoded year),
  so every month present on disk is picked up.
- Some sold months were re-exported as CRMLSSoldYYYYMM_filled.csv. If a month
  has both a plain and a _filled file, the _filled one is used so a month is
  never counted twice.
- A contiguity check fails loudly if any month between the first and last is
  missing, so a partial aggregation can't pass silently.
"""
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "csv"
START = "202401"  # January 2024


def find_monthly_files(prefix):
    """Return {YYYYMM: Path} for files like <prefix>YYYYMM[_filled].csv, >= START."""
    pattern = re.compile(rf"^{prefix}(\d{{6}})(_filled)?\.csv$")
    found = {}
    for path in sorted(DATA_DIR.glob(f"{prefix}*.csv")):
        m = pattern.match(path.name)
        if not m or m.group(1) < START:
            continue
        month, filled = m.group(1), bool(m.group(2))
        # prefer the _filled version when both exist for the same month
        if month not in found or filled:
            found[month] = path
    return dict(sorted(found.items()))


def check_contiguous(months, label):
    first, last = months[0], months[-1]
    expected = [p.strftime("%Y%m") for p in pd.period_range(first, last, freq="M")]
    missing = [m for m in expected if m not in months]
    assert not missing, f"{label}: missing months {missing}"
    print(f"{label}: {len(months)} contiguous months ({first} -> {last})")


def aggregate(prefix, label, out_name):
    print(f"\n{'=' * 60}\n{label.upper()}\n{'=' * 60}")
    files = find_monthly_files(prefix)
    check_contiguous(list(files), label)

    frames, per_file_total = [], 0
    for month, path in files.items():
        df = pd.read_csv(path, low_memory=False)
        per_file_total += len(df)
        print(f"  {path.name:<36} rows: {len(df):>8,}")
        frames.append(df)

    # Row count BEFORE concatenation = sum of the individual monthly files
    print(f"\nRows before concatenation (sum of {len(frames)} files): {per_file_total:,}")

    combined = pd.concat(frames, ignore_index=True)
    # Row count AFTER concatenation - must equal the sum above
    print(f"Rows after concatenation: {len(combined):,}")
    assert len(combined) == per_file_total, "concat lost or gained rows"

    # Row count BEFORE the Residential filter
    print(f"\nPropertyType values: {combined['PropertyType'].value_counts(dropna=False).to_dict()}")
    print(f"Rows before Residential filter: {len(combined):,}")
    residential = combined[combined["PropertyType"] == "Residential"].copy()
    # Row count AFTER the Residential filter
    print(f"Rows after Residential filter:  {len(residential):,}")
    print(f"Removed non-Residential rows:   {len(combined) - len(residential):,}")

    out_path = DATA_DIR / out_name
    residential.to_csv(out_path, index=False)
    print(f"Saved -> {out_path.name} ({residential.shape[0]:,} rows x {residential.shape[1]} cols)")
    return residential


if __name__ == "__main__":
    sold = aggregate("CRMLSSold", "Sold", "combined_sold_residential.csv")
    listings = aggregate("CRMLSListing", "Listings", "combined_listings_residential.csv")
    print("\nWeek 1 aggregation complete.")
