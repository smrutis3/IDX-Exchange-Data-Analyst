# IDX Exchange - MLS Analytics Internship

Code, progress, and findings for the **IDX Exchange 12-Week Data Analyst Internship** (MLS Analytics & Tableau Dashboard Program).

**Data:** monthly CRMLS (California Regional MLS) Listing and Sold files, January 2024 - April 2026, produced from the CoreLogic Trestle API. The data is confidential MLS transaction data, so **no data files are committed to this repo** - only code and aggregate findings.

**Pipeline:** `week1_aggregation.py` -> `week2_3_validation_enrichment.py` -> `week4_5_cleaning.py` -> `week6_feature_engineering.py` -> `week7_outliers.py` -> *(Tableau)*

---

## Roadmap

- [x] **Week 1:** Monthly dataset aggregation & Residential filtering
- [x] **Weeks 2-3:** Dataset structuring, validation, EDA & FRED mortgage rate enrichment
- [x] **Weeks 4-5:** Data cleaning, transformation & quality flags
- [x] **Week 6:** Feature engineering, housing market metrics & school-district join
- [x] **Week 7:** Outlier detection (IQR) & quality flags
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
- **45,263 sold rows** have coordinates imputed upstream (`latfilled` / `lonfilled` = True). Only the 108,157 rows from the `_filled` monthly exports carry this flag (it is null elsewhere), so that is about 42% of the rows where it is recorded and 11% of all Sold rows.
- Roughly **1.2% of sold rows** (4,897) have at least one data-quality flag (excluding the duplicate-key flag), and 586 sold rows and 276 listing rows share a `ListingKey` with another row.
- Date-order violations (510 sold, 530 listings) mostly involve the purchase contract date, so contract-timeline metrics in Week 6 need to account for them.

**Carried forward**
- Week 6 must filter the Listings dataset by `MlsStatus` before any closed-sale or supply metric.
- Week 7 decides how to treat flagged rows and repeated `ListingKey`s when building the filtered analysis dataset.

---

## Week 6 - Feature Engineering and Market Metrics

**Objective:** engineer the market indicators that power the Tableau dashboards, then summarize them by segment.

**Script:** `week6_feature_engineering.py` (input: the Weeks 4-5 cleaned datasets)

### Engineered metrics

| Column | Formula | Purpose |
|---|---|---|
| `price_ratio` | `ClosePrice / OriginalListPrice` | Negotiation strength (handbook formula) |
| `close_to_original_list_ratio` | `ClosePrice / OriginalListPrice` | Captures the full price-reduction history |
| `price_per_sqft` | `ClosePrice / LivingArea` | Normalizes price across home sizes |
| `days_on_market` | `DaysOnMarket` (negatives -> null) | Time-to-sell |
| `close_year`, `close_month`, `close_yrmo` | Derived from `CloseDate` | Time-series analysis |
| `listing_to_contract_days` | `PurchaseContractDate - ListingContractDate` | Time from listing to accepted offer |
| `contract_to_close_days` | `CloseDate - PurchaseContractDate` | Escrow / closing period |

### Design decisions
- **Price Ratio follows the handbook.** The handbook defines Price Ratio and Close-to-Original-List Ratio with the same formula (`ClosePrice / OriginalListPrice`), so the two columns are identical. `% sold over list` in the segment tables is measured against the final `ListPrice`, consistent with the Weeks 2-3 EDA.
- **No rows dropped, nothing imputed.** A metric is null when its inputs are invalid (price or area <= 0, negative days on market, or dates in the wrong order), using the Weeks 4-5 rules. Extreme-but-valid values are left for Week 7.
- **Listings is filtered by `MlsStatus`.** Closed-sale metrics (ratios, price per sq ft, close date fields, contract-to-close) are computed only for `Closed` listings (137,676 of 547,162 rows), as flagged in Weeks 4-5. Segment tables use closed sales only.
- **Medians lead the summaries** because the means are distorted by extreme values (see below).

### Coverage (Sold, 414,091 rows)

| Metric | Non-null | Median |
|---|---|---|
| `price_ratio` | 413,323 | 0.996 |
| `close_to_original_list_ratio` | 413,323 | 0.996 |
| `price_per_sqft` | 413,702 | $537 |
| `days_on_market` | 414,043 | 18 days |
| `listing_to_contract_days` | 413,626 | 25 days |
| `contract_to_close_days` | 413,657 | 29 days |

Out-of-order dates left 270 null `listing_to_contract_days` and 240 null `contract_to_close_days` in Sold. These match the Weeks 4-5 flag counts.

### Segment analysis (Sold, closed sales, segments with >= 100 sales)

Tables are saved as `segment_<sold|listings>_<propertytype|propertysubtype|county|mlsareamajor|listoffice|buyeroffice|year_month>.csv`. Each reports sales, median and mean close price, median price per sq ft, median days on market, median price ratios, % sold over list, and median listing-to-contract and contract-to-close days.

**By PropertySubType (selected)**

| Subtype | Sales | Median price | Median $/sq ft | Median DOM |
|---|---|---|---|---|
| Single Family Residence | 309,729 | $893,224 | $533 | 17 |
| Condominium | 68,512 | $628,000 | $565 | 24 |
| Townhouse | 24,296 | $805,000 | $562 | 17 |
| Manufactured On Land | 5,343 | $324,000 | $226 | 30 |
| Duplex | 2,253 | $915,000 | $544 | 22 |

**By county (selected)**

| County | Sales | Median price | Median $/sq ft | Median DOM | % sold over list |
|---|---|---|---|---|---|
| Santa Clara | 18,425 | $1,600,000 | $966 | 10 | 63.1% |
| Alameda | 19,541 | $1,133,000 | $701 | 14 | 62.5% |
| San Mateo | 7,271 | $1,700,000 | $1,051 | 12 | 57.3% |
| Los Angeles | 102,893 | $900,000 | $608 | 19 | 42.3% |
| Riverside | 57,383 | $600,000 | $321 | 30 | 31.3% |
| Lake | 1,789 | $310,000 | $213 | 52 | 15.5% |

County medians match the Weeks 2-3 results, confirming the pipeline is consistent.

**Competitive view (top list offices by sales):** Compass (29,101 sales, median $1.35M, 14 days), Coldwell Banker Realty (18,693, $1.195M, 16 days), Keller Williams Realty (8,120, $870K, 15 days). The top 25 list and buyer offices are in the office segment files.

### Findings
- The Bay Area (Santa Clara, Alameda, San Mateo) is the tightest market: 57-63% of sales close above list in 10-14 days. Rural and inland counties (Lake, Mendocino) sell slowly (50+ days) and rarely above list.
- Condos sell at a higher price per sq ft than single-family homes but take longer to sell (24 vs. 17 days).
- Extremes remain in the engineered fields: `close_to_original_list_ratio` reaches 9.1 million, `price_per_sqft` reaches $1.16M, and `contract_to_close_days` reaches 36,629. These come from source data errors and are the main targets for Week 7 IQR handling.
- Sacramento (886 sales) and Placer (200) are thinly represented in the dataset, so county comparisons for them should be read with caution.

### School districts

**Script:** `week6_school_districts.py` (run after `week6_feature_engineering.py`; needs `geopandas`, installed in a local `.venv`)

Each property's latitude/longitude is spatially joined to the California Department of Education **School District Areas 2025-26** boundary file (data.ca.gov). The file has three overlapping district types (Unified, Elementary, High), so two columns are produced: `school_district` (Unified, or Elementary when there is no Unified district) and `high_school_district`, plus `school_district_type`, `school_district_cds` and `school_district_source`.

| | Sold | Listings |
|---|---|---|
| Rows with a school district | 409,881 (99.0%) | 466,586 (85.3%) |
| Matched inside a district polygon | 409,772 | 466,445 |
| Matched to the nearest district within 1 km | 109 | 141 |
| Unmatched (out-of-state coordinates) | 10 | 17 |
| No usable coordinates -> `Unknown` | 4,200 | 80,559 |

- Coordinates are never guessed: rows with missing or invalid coordinates (the Weeks 4-5 `geo_invalid_flag`) are labelled `Unknown`.
- **Check:** for 99.7% of matched rows the district's county equals `CountyOrParish`.
- 735 distinct districts appear in Sold; 341 have >= 100 sales and are summarized in `segment_sold_schooldistrict.csv`.
- Largest: Los Angeles Unified (42,121 sales, median $980,000), San Diego Unified (14,949, $930,000), Capistrano Unified (8,605, $1,350,000, the priciest of the large districts).

### Dashboard prep (ZIP, city, agents, monthly activity)

**Script:** `week6_dashboard_prep.py` (run after the school-district script). The Weeks 8-10 dashboards must filter by city, county and zip code, rank the top 100 listing agents and offices by sales volume and units, and show monthly new listings vs. closed sales. Original columns are never overwritten; clean versions are added next to them.

| Column / table | What it does |
|---|---|
| `zip5` | 5-digit ZIP. 2,130 Sold rows had ZIP+4 (`94563-4211`); values that are not a 5-digit ZIP (e.g. `907013`, `0`) become `Unknown` (4 Sold, 18 Listings). |
| `city_clean` | Merges case variants (`Marina del Rey` / `Marina Del Rey`, `Corona del Mar`, `Playa del Rey`, `Cardiff by the Sea`, `McFarland`). Neighborhood names such as `Mission Hills (San Fernando)` are real and left alone. |
| `list_agent_clean` | Merges case/spacing variants of `ListAgentFullName` (`RANDY ANDERSON` -> `Randy Anderson`): 77,942 -> 76,907 distinct names in Sold. |
| `segment_*_listagent.csv` | Top 100 listing agents with units and total sales volume. |
| `segment_*_zip.csv` | Summary per ZIP (811 ZIPs with >= 100 sales in Sold). |
| `monthly_market_activity.csv` | Per month: distinct new listings (by `ListingContractDate`), closed sales (Sold, by `CloseDate`), sales volume, medians, and the sales-to-new-listings ratio. |

- Office and agent segment tables now include `sales_volume` (total dollars closed) alongside units.
- **Agent matching is by name.** The extract has no listing-agent ID, so two different agents with the same name would be merged. Of the 100 top agent names, 22 list under more than one office, which is common when agents change brokerage but cannot be separated here.
- **New-listing counts look incomplete in several months.** The raw `CRMLSListing` files fall from about 40,000 rows in May 2025 to about 26,000 from June 2025 on, and January 2026 has only 2,606 rows (1,721 residential new listings vs. about 20,000 normal). Nov-Dec 2024 are also low. The "new listings" dashboard will show artificial dips in those months unless the extracts are re-pulled; flag this to the program team.

---

## Week 7 - Outlier Detection (IQR) and Data Quality

**Objective:** flag extreme values instead of deleting them, and produce a separate filtered analysis dataset.

**Script:** `week7_outliers.py` (input: the Week 6 featured datasets)

**Method (handbook formula):** `Q1`, `Q3`, `IQR = Q3 - Q1`, outlier if outside `Q1 - 1.5*IQR` .. `Q3 + 1.5*IQR`, applied globally per field. Bounds are computed on rows that pass the business rules, so a $0 price or negative days on market cannot drag Q1 down. Percentiles (p1, p99) are printed beside every bound.

**Tiers**

| Tier | Rule | Result |
|---|---|---|
| 1 | Business rules (`ClosePrice`/`ListPrice`/`LivingArea` <= 0, `DaysOnMarket` < 0, negative beds/baths) | Always excluded |
| 2 | 1.5 x IQR on `ClosePrice`, `LivingArea`, `days_on_market` (handbook fields) | Excluded |
| 3 | `price_per_sqft` and `close_to_original_list_ratio`: flagged at 1.5 x IQR, excluded only when extreme (3 x IQR) | Excluded if extreme |

Tier 3 is a judgment call. At 1.5 x IQR the ratio fence is 0.855-1.118, which would discard real discounts and bidding wars; the 3 x fence (0.756-1.217) still removes source errors such as ratios in the millions and $1M+ per sq ft.

**Outputs:** `*_flagged.csv` (every row, with `closeprice_outlier_flag`, `livingarea_outlier_flag`, `dom_outlier_flag`, `ppsf_outlier_flag`, `close_to_list_outlier_flag`, the two `*_extreme_flag` columns, `any_outlier_flag`, `exclude_from_analysis`) and `*_analysis.csv` (rows with `exclude_from_analysis == False`). Bounds and before/after tables are saved as `outlier_bounds_*.csv` and `outlier_before_after_*.csv`.

### Sold: IQR bounds and flags

| Field | Lower | Upper | p99 | Flagged |
|---|---|---|---|---|
| `ClosePrice` | -512,500 | 2,387,500 | 5,550,000 | 30,695 (7.4%) |
| `LivingArea` | -208 | 3,676 | 5,282 | 18,203 (4.4%) |
| `days_on_market` | -52 | 108 | 231 | 31,785 (7.7%) |
| `price_per_sqft` (1.5x / 3x) | -177 / -723 | 1,278 / 1,824 | 1,887 | 17,452 / 4,754 |
| `close_to_original_list_ratio` (1.5x / 3x) | 0.855 / 0.756 | 1.118 / 1.217 | 1.281 | 39,128 / 11,740 |

### Dataset size and medians before and after filtering

| | Sold before | Sold after | Listings before | Listings after |
|---|---|---|---|---|
| Rows | 414,091 | 340,522 (-17.8%) | 547,162 | 464,673 (-15.1%) |
| Median `ClosePrice` | $822,540 | $780,000 | $850,000 | $818,000 |
| Median `LivingArea` | 1,642 | 1,572 | 1,670 | 1,613 |
| Median days on market | 18 | 16 | 10 | 9 |
| Median price per sq ft | $537 | $524 | $562 | $551 |
| Mean `ClosePrice` | $1,188,390 | $892,611 | $1,203,602 | $935,187 |
| Max `ClosePrice` | $989.5M | $2.39M | $820M | $2.48M |

### Findings and caveats
- The mean close price falls 25% after filtering while the median moves 5%: a few extreme records, not the typical home, were distorting the averages.
- **A global price fence is not neutral.** It flags 30% of San Mateo and 24% of Santa Clara sales as price outliers (vs. 7% in San Diego), because genuinely expensive markets sit above $2.39M. A per-subtype or per-county IQR flags about the same number of rows overall (29,928 / 30,373) but redistributes them. The handbook method is global, so that is what the filtered dataset uses; for county-level price dashboards, use `*_flagged.csv` and filter on the flags deliberately, or use medians.
- The 108-day DOM fence also removes legitimate slow sales, so median DOM in the filtered data (16) is lower than the raw median (18).
- Date-order and coordinate flags from Weeks 4-5 do not exclude a row; they do not affect these metrics, and excluding them would remove homes from the zip-code and map dashboards.
- Repeated `ListingKey`s (586 Sold rows) are kept: every pair has a different `CloseDate`, so none can be dropped as a safe duplicate.

---

## How to Run

Place the monthly CRMLS CSVs in a local `csv/` folder (not tracked), then from the repo root:

```bash
python week1_aggregation.py                # -> combined_sold_residential.csv, combined_listings_residential.csv
python week2_3_validation_enrichment.py    # -> *_filtered.csv, *_with_rates.csv, missing-value and numeric summaries, plots/
python week4_5_cleaning.py                 # -> sold_cleaned.csv, listings_cleaned.csv
python week6_feature_engineering.py        # -> sold_featured.csv, listings_featured.csv, segment_*.csv
.venv/bin/python week6_school_districts.py # -> adds school district columns to the featured files (needs geopandas)
python week6_dashboard_prep.py             # -> zip5, city_clean, list_agent_clean, segment_*_listagent/zip.csv, monthly_market_activity.csv
python week7_outliers.py                   # -> sold/listings_flagged.csv (all rows + outlier flags), *_analysis.csv (filtered)
```

Requires Python 3 with `pandas`, `numpy`, and `matplotlib`. The Weeks 2-3 script needs internet access to fetch the FRED series. All generated CSVs, plots and run logs stay local because the underlying data is confidential.
