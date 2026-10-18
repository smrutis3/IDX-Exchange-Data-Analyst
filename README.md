# IDX Exchange - MLS Analytics Internship

Code, progress, and findings for the **IDX Exchange 12-Week Data Analyst Internship** (MLS Analytics & Tableau Dashboard Program).

**Data:** monthly CRMLS (California Regional MLS) Listing and Sold files, January 2024 - April 2026, produced from the CoreLogic Trestle API. The data is confidential MLS transaction data, so **no data files are committed to this repo** - only code and aggregate findings.

**Pipeline:** `week1_aggregation.py` -> `week2_3_validation_enrichment.py` -> `week4_5_cleaning.py` -> *(Week 6+ feature engineering, outliers, Tableau)*

---

## Roadmap

- [x] **Week 1:** Monthly dataset aggregation & Residential filtering
- [x] **Weeks 2-3:** Dataset structuring, validation, EDA & FRED mortgage rate enrichment
- [x] **Weeks 4-5:** Data cleaning, transformation & quality flags
- [ ] **Week 6:** Feature engineering & housing market metrics
- [ ] **Week 7:** Outlier detection (IQR) & quality flags
- [ ] **Weeks 8-10:** Tableau dashboards (market & competitive analysis)
- [ ] **Weeks 11-12:** Market intelligence report & final presentation

---

## Week 1 - Monthly Dataset Aggregation

**Objective:** combine every monthly file from January 2024 through the latest available month into one Sold and one Listings dataset, then keep `PropertyType == 'Residential'` only.

**Script:** `week1_aggregation.py`

**What it does**
- Discovers `CRMLSSoldYYYYMM` / `CRMLSListingYYYYMM` files by month, not by a hardcoded year.
- Uses the `_filled` version of a sold month when both versions exist, so no month is counted twice.
- Fails loudly if any month between the first and last is missing, and asserts that rows after concatenation equal the sum of the monthly files.

**Row counts**

| Dataset | Months covered | Rows before concat (sum of files) | Rows after concat | Rows after Residential filter |
|---|---|---|---|---|
| Sold | 28 (2024-01 -> 2026-04) | 615,931 | 615,931 | 414,139 |
| Listings | 28 (2024-01 -> 2026-04) | 860,898 | 860,898 | 547,162 |

**Findings**
- Residential is **67.2%** of sold records and **63.6%** of listing records. The rest is mostly ResidentialLease (about 21-23%), then Land, ResidentialIncome, ManufacturedInPark, CommercialSale, CommercialLease and BusinessOpportunity.
- Sold `CloseDate` spans 2024-01-01 -> 2026-04-30. Listing `ListingContractDate` spans 2024-01-01 -> 2026-04-30. Neither has null dates.
- January 2026 listings is unusually small (1,721 rows vs. roughly 20,000 in a typical month), so that month's raw file may be incomplete.

---

## Weeks 2-3 - Structuring, Validation, EDA & Mortgage Rate Enrichment

**Objective:** audit structure and missing data, review numeric distributions, answer baseline EDA questions, then enrich both datasets with the monthly 30-year fixed mortgage rate from FRED.

**Script:** `week2_3_validation_enrichment.py`

### Dataset structure and missing values

| | Sold | Listings |
|---|---|---|
| Rows | 414,139 | 547,162 |
| Columns | 84 | 84 |
| Columns > 90% null | 15 | 13 |
| Columns kept after drop | 69 | 71 |

- Columns over 90% null that were **dropped** (none are core fields): `AboveGradeFinishedArea`, `CoveredSpaces`, `TaxAnnualAmount`, `TaxYear`, `ElementarySchoolDistrict`, `MiddleOrJuniorSchoolDistrict`, `FireplacesTotal`, `BusinessType`, `BelowGradeFinishedArea`, `BuilderName`, `LotSizeDimensions`, `BuildingAreaTotal`, `CoBuyerAgentFirstName`, plus `WaterfrontYN` and `BasementYN` in sold.
- Core fields (prices, areas, dates, coordinates, geography, agents/offices) are always kept even when partly missing.
- Fields were split into **market-analysis fields** and **metadata fields** (IDs, system names, agent MLS IDs, AORs) in the missing-value report.

### Numeric distributions (Sold)

| Field | Min | Median | Mean | 95th pct | 99th pct | Max |
|---|---|---|---|---|---|---|
| ClosePrice | $0 | $823,000 | $1,188,411 | $2,850,000 | $5,560,660 | $989,500,000 |
| LivingArea (sq ft) | 0 | 1,642 | 1,904 | 3,559 | 5,282 | 17,021,321 |
| DaysOnMarket | -288 | 18 | 37.4 | 132 | 231 | 12,430 |

The mean sits well above the median for price and area: a small number of extreme values drive the skew. These are flagged here and handled in Week 7.

### EDA answers (Sold)

| Question | Answer |
|---|---|
| Median / mean close price | $823,000 / $1,188,411 |
| Median days on market | 18 days; 62.9% of homes sold within 30 days |
| Sold above / below / at list price | 40.1% / 42.6% / 17.4% |
| Listing date after close date | 63 records |
| Purchase contract date after close date | 240 records |
| Listing date after purchase contract date | 270 records |

**Days on market distribution**

| DOM | <=0 | 1-7 | 8-30 | 31-60 | 61-90 | 91-180 | 180+ |
|---|---|---|---|---|---|---|---|
| Share of sales | 4.0% | 20.4% | 38.5% | 17.6% | 8.7% | 8.6% | 2.1% |

**Highest median close price by county** (counties with >= 200 sales)

| County | Median close price | Sales |
|---|---|---|
| San Mateo | $1,700,000 | 7,273 |
| Santa Clara | $1,600,000 | 18,426 |
| Santa Cruz | $1,200,000 | 3,001 |
| San Francisco | $1,198,950 | 956 |
| Orange | $1,175,000 | 46,603 |
| Alameda | $1,133,000 | 19,541 |
| Monterey | $910,000 | 3,986 |
| Los Angeles | $900,000 | 102,913 |
| San Diego | $899,000 | 51,202 |
| Ventura | $869,000 | 12,882 |

### FRED mortgage rate enrichment
1. Fetches `MORTGAGE30US` (weekly, Freddie Mac) from FRED with no API key.
2. Resamples weekly rates to monthly averages.
3. Builds a `year_month` key - `CloseDate` for Sold, `ListingContractDate` for Listings - and left-merges the monthly rate.
4. **Validation:** both merged datasets have **0 null `rate_30yr_fixed` values**, and the row count is unchanged by the merge.

Monthly average 30-year fixed rate, selected months: 2024-01 **6.64%**, 2024-05 **7.06%** (the peak through April 2026), 2024-09 **6.18%**, 2025-01 **6.96%**, 2025-12 **6.19%**, 2026-04 **6.33%**.

**Data quality issues carried forward to Weeks 4-5**
- Impossible values: `ClosePrice` of 0, `LivingArea` of 0 and up to 17 million sq ft, negative `DaysOnMarket`, and homes listed with 45 bedrooms or 175 bathrooms.
- The raw listing files contain duplicated column headers (e.g. `CloseDate.1`).
- Sold files contain `latfilled` / `lonfilled` columns from the `_filled` exports.
- The Listings dataset contains all statuses (Active, Pending, Closed, etc.), not just closed sales.

---

## Weeks 4-5 - Data Cleaning and Preparation

**Objective:** produce analysis-ready datasets. Following the handbook's tiered approach, questionable records are **flagged, not deleted**; only exact duplicate rows and redundant columns are removed.

**Script:** `week4_5_cleaning.py` (input: the Weeks 2-3 enriched datasets)

### Before / after

| | Sold | Listings |
|---|---|---|
| Rows before -> after | 414,139 -> 414,091 | 547,162 -> 547,162 |
| Exact duplicate rows removed | 48 | 0 |
| Columns before -> after | 71 -> 84 | 73 -> 77 |
| Columns removed | 4 | 13 |
| Flag columns added | 17 | 17 |

### Transformations and why

| Step | Decision | Reason |
|---|---|---|
| Date fields | `CloseDate`, `PurchaseContractDate`, `ListingContractDate`, `ContractStatusChangeDate` converted to datetime | Needed for date logic and time series; no values failed to parse |
| Numeric fields | Coerced to numeric; bedrooms, bathrooms and year built stored as nullable integers | Guarantees correct types for calculations |
| Duplicate-header columns | 11 listing columns (`*.1`) dropped | Verified identical to the originals; one raw row was misaligned, and the original column's value was kept |
| `ListAgentEmail` | Dropped | Personal contact data, not needed for market analytics |
| `OriginatingSystemName` / `SubName` | Dropped (sold) | System metadata, ~89% null |
| `ListingKeyNumeric` | Dropped | 1:1 duplicate of `ListingKey` |
| Text fields | Whitespace stripped, blanks -> null | Consistent grouping and null counts |
| Segmentation fields | Missing `PropertySubType`, `City`, `MLSAreaMajor`, `PostalCode` -> `Unknown` | Group-bys keep these rows instead of silently dropping them |
| Prices, areas, beds, baths | **Not imputed** | A fabricated price would bias every downstream metric; missing stays null |
| Exact duplicate rows | Removed | Same record exported twice |
| Repeated `ListingKey` | Kept and flagged (`duplicate_listingkey_flag`) | Likely relistings or re-exports; deduplication is a Week 7 decision |

### Data type confirmation
All four date fields are `datetime64[ns]`; `ClosePrice`, `ListPrice`, `OriginalListPrice`, `LivingArea`, `Latitude`, `Longitude` are `float64`; `DaysOnMarket` is `int64`; `BedroomsTotal`, `BathroomsTotalInteger`, `YearBuilt` are nullable `Int64`.

### Invalid numeric value flags (rows kept)

| Flag | Rule | Sold | Listings |
|---|---|---|---|
| `invalid_closeprice_flag` | `ClosePrice <= 0` | 1 | 0 |
| `invalid_listprice_flag` | `ListPrice <= 0` | 0 | 0 |
| `invalid_livingarea_flag` | `LivingArea <= 0` | 150 | 360 |
| `invalid_dom_flag` | `DaysOnMarket < 0` | 48 | 27 |
| `invalid_bedrooms_flag` | negative bedrooms | 0 | 0 |
| `invalid_bathrooms_flag` | negative bathrooms | 0 | 0 |
| `any_invalid_numeric_flag` | any of the above | 199 | 387 |

### Date consistency flags
Expected order: `ListingContractDate` <= `PurchaseContractDate` <= `CloseDate`.

| Flag | Meaning | Sold | Listings |
|---|---|---|---|
| `listing_after_close_flag` | Listing date after close date | 63 | 73 |
| `purchase_after_close_flag` | Purchase contract after close date | 240 | 262 |
| `negative_timeline_flag` | Any order violation among the three dates | 510 | 530 |

### Geographic data quality summary

| Flag | Rule | Sold | Sold % | Listings | Listings % |
|---|---|---|---|---|---|
| `geo_missing_flag` | Latitude or Longitude is null | 4,108 | 0.99% | 80,247 | 14.67% |
| `geo_zero_flag` | Latitude or Longitude equals 0 (sentinel null) | 27 | 0.01% | 64 | 0.01% |
| `geo_positive_lon_flag` | Longitude > 0 (California should be negative) | 31 | 0.01% | 73 | 0.01% |
| `geo_out_of_state_flag` | Outside the California bounding box (lat 32.5-42.0, lon -124.5 to -114.1) | 34 | 0.01% | 175 | 0.03% |
| `geo_state_mismatch_flag` | `StateOrProvince` is not CA | 29 | 0.01% | 155 | 0.03% |
| `geo_invalid_flag` | Any of the coordinate flags above (excludes state mismatch) | 4,200 | 1.01% | 80,559 | 14.72% |

### Findings
- **About 1% of sold records have unusable coordinates**, almost all of them missing. Listings have far more missing coordinates (14.7%) because they include active and pending homes that are newer or incomplete in the MLS.
- Several invalid coordinates are recognizable errors, such as positive longitudes with a dropped minus sign, and `0,0` or `1,2` placeholders.
- Many "out of box" coordinates are legitimate out-of-state properties that the MLS labels "Outside Area".
- **45,263 sold rows (about 11%)** have coordinates that were imputed upstream (`latfilled` / `lonfilled` = True).
- Roughly **1.2% of sold rows** (4,897) have at least one data-quality flag (excluding the duplicate-key flag), and 586 sold rows and 276 listing rows share a `ListingKey` with another row.
- Date-order violations (510 sold, 530 listings) mostly involve the purchase contract date, so contract-timeline metrics in Week 6 need to account for them.

**Carried forward**
- Week 6 must filter the Listings dataset by `MlsStatus` before any closed-sale or supply metric.
- Week 7 decides how to treat flagged rows and repeated `ListingKey`s when building the filtered analysis dataset.

---

## How to Run

Place the monthly CRMLS CSVs in a local `csv/` folder (not tracked), then from the repo root:

```bash
python week1_aggregation.py                # -> combined_sold_residential.csv, combined_listings_residential.csv
python week2_3_validation_enrichment.py    # -> *_filtered.csv, *_with_rates.csv, missing-value and numeric summaries, plots/
python week4_5_cleaning.py                 # -> sold_cleaned.csv, listings_cleaned.csv
```

Requires Python 3 with `pandas`, `numpy`, and `matplotlib`. The Weeks 2-3 script needs internet access to fetch the FRED series. All generated CSVs, plots and run logs stay local because the underlying data is confidential.
