# Tableau Dashboard Specs - Weeks 8-10

Specs for the two workbooks the handbook requires, built on the exports in `tableau/` (see `week8_tableau_export.py`). Dashboards cover January 2024 through April 2026, the latest month available.

| Workbook | Required dashboards | Required filters |
|---|---|---|
| `market_analysis.twbx` | Monthly median close price; average days on market; average close-to-original-list ratio; new listings; closed sales; **plus one of your own design** | city, county or zip code, and PropertySubType |
| `competitive_analysis.twbx` | Top 100 listing agents (sales volume and units); top 100 listing offices (sales volume and units); zip heat map of median close price; zip heat map of homes sold; **plus one of your own design** | offices: city, county, zip, PropertySubType. Heat maps: **month**, city, county, zip, PropertySubType |

> **Read this before publishing:** the handbook asks for Tableau Public, and it also says the MLS data is confidential and must not be distributed. A published Tableau Public workbook contains its data extract, so row-level data (ListingKey, coordinates, agent names) would become public. Ask your mentor how to publish. The safe fallback is an aggregated extract; see "Publishing" at the end.

---

## 0. Data setup (both workbooks)

**Files:** `tableau/tableau_sold.csv` (closed sales) and `tableau/tableau_listings.csv` (new listings).

**Connecting.** Use one data source so that one filter control drives every sheet:
1. Connect to `tableau_sold.csv`, then drag `tableau_listings.csv` onto the canvas and choose **Union** (not join). Tableau adds a `Table Name` field and aligns same-named columns (`city_clean`, `CountyOrParish`, `zip5`, `PropertySubType`, price and metric columns).
2. Create an **extract** (.hyper). Save the workbook as `.twbx`.
3. Set `zip5` to **Geographic Role > ZIP Code/Postcode**. Set `Latitude` and `Longitude` to their geographic roles.

**Shared calculated fields**

| Name | Formula | Use |
|---|---|---|
| `Is Sold` | `CONTAINS([Table Name], 'sold')` | separates the two files |
| `Event Month` | `IF [Is Sold] THEN DATETRUNC('month',[CloseDate]) ELSE DATETRUNC('month',[ListingContractDate]) END` | one month axis for sales and new listings |
| `Basis` (parameter) | string list: `Typical market (filtered)`, `All sales` | default `Typical market (filtered)` |
| `Use for Metrics` | `[include_in_analysis] OR [Basis] = 'All sales'` | filter for price, DOM and ratio charts |
| `Closed Sale` | `IF [Is Sold] THEN 1 END` | counts |
| `New Listing Key` | `IF NOT [Is Sold] THEN [ListingKey] END` | for COUNTD |

**Global filters** (show as dashboard filter controls, **Apply to Worksheets > All Using This Data Source**): `city_clean`, `CountyOrParish`, `zip5`, `PropertySubType`. Add `Event Month` (range) on the heat-map sheets. Remove `Unknown` from `zip5` and `city_clean` through a data-source filter only on map sheets; keep it elsewhere so counts tie to the CSV.

**Which rows to use** (from `tableau/README_tableau.txt`)

| Chart type | Rows |
|---|---|
| Median / average price, days on market, ratio | `Use for Metrics` = True (typical market; the Week 7 tiered filter) |
| Counts: closed sales, new listings, agent and office units | all rows (no flag filter) |
| County / zip price comparisons | do **not** filter on `price_outlier_flag`; use medians |
| Charts of listing-to-contract or contract-to-close | exclude `timeline_extreme_flag` = True |
| Latitude/Longitude point maps | exclude `bad_coordinates_flag` = True (zip-code maps use `zip5` and do not need it) |

The `Basis` parameter lets a viewer compare the typical-market view against all sales. It matters: the filtered median close price is $780,000 against $822,540 for all rows, because the filter removes sales above $2.39M.

---

## 1. `market_analysis.twbx`

### 1.1 Monthly median close price
- **Sheet:** line chart. Columns `Event Month` (month), rows `MEDIAN([ClosePrice])`.
- **Filters:** `Is Sold` = True; `Use for Metrics` = True.
- **Add:** a reference line for the overall median; tooltip with `COUNT([ListingKey])` (sales that month).
- **Expect (typical market):** about $718K in Jan 2024, rising to about $805K by Jun 2024, then flat at roughly $775-800K. With `Basis` = All sales the same months read about $749K to $856K, so the filtered view runs about 5% lower.

### 1.2 Average days on market
- **Sheet:** line or bar. Rows `AVG([days_on_market])` by `Event Month`.
- **Filters:** `Is Sold` = True; `Use for Metrics` = True.
- **Note on the tooltip:** the filtered data excludes days on market above 108, so the average reads lower than the raw average. Also show `MEDIAN([days_on_market])` as a second line, since days on market is skewed.

### 1.3 Average close-to-original-list ratio
- **Sheet:** line chart. Rows `AVG([close_to_original_list_ratio])` by `Event Month`. Set the axis to roughly 0.95-1.05, with a reference line at 1.0 (sold at original list price).
- **Filters:** `Is Sold` = True; `Use for Metrics` = True.
- **Expect (typical market):** about 1.01 in Apr-Jun 2024, then 0.98-0.99 from late 2024 onward (lowest about 0.98 in Sep 2025 and Jan 2026), recovering to about 0.995 by Mar-Apr 2026.

### 1.4 New listings
- **Sheet:** bar chart. Rows `COUNTD([New Listing Key])` by `Event Month`.
- **Filters:** none besides the global ones. Use all rows.
- **Annotation (required):** the raw listing extracts are smaller in Nov-Dec 2024 (25K and 19K rows), Jun-Dec 2025 (about 26K) and especially Jan 2026 (2.6K rows; about 1,700 residential new listings against about 20,000 in a normal month). Add a footnote: "Low months reflect smaller data extracts, not a market decline." Shade those months.

### 1.5 Closed sales
- **Sheet:** bar chart. Rows `SUM([Closed Sale])` by `Event Month`.
- **Filters:** none besides the global ones. Use all rows.
- **Expect:** about 11K in Jan 2024, 18.5K in May 2024, about 10K in Jan 2026.

### 1.6 Own design: "Rates and market activity"
- **Purpose:** link the FRED mortgage rate to activity, using `rate_30yr_fixed`.
- **Sheet:** dual axis by `Event Month`. Left axis `SUM([Closed Sale])` as bars; right axis `AVG([rate_30yr_fixed])` as a line (about 6.0-7.1%). Add `MEDIAN([ClosePrice])` as a third panel below.
- **Add:** a small "sales per new listing" line, `SUM([Closed Sale]) / COUNTD([New Listing Key])`, with the same extract-gap footnote as 1.4 (the ratio spikes to 5.9 in Jan 2026 purely because new listings are missing).
- **Takeaway:** peak rates (7.06% in May 2024) coincide with peak volume, so rates alone do not explain sales.

### Market dashboard layout
One page per required chart, plus an overview page with the five charts in a 2 x 3 grid, the four global filters across the top, and the `Basis` parameter toggle. Limit all date axes to Jan 2024-Apr 2026.

---

## 2. `competitive_analysis.twbx`

Use `tableau_sold.csv` only (all competitive metrics are closed-sale based).

### 2.1 Top 100 listing agents
- **Sheet:** horizontal bar or table. Rows `list_agent_clean`. Measures `SUM([ClosePrice])` (sales volume) and `COUNT([ListingKey])` (units), plus `MEDIAN([ClosePrice])`.
- **Filters:** `list_agent_clean` not `Unknown`. **Top filter** on `list_agent_clean`: Top 100 by `SUM([ClosePrice])`. Provide a parameter to switch the ranking between volume and units: `Rank By` (`Volume` / `Units`) and `Rank Value = IF [Rank By]='Volume' THEN SUM([ClosePrice]) ELSE COUNT([ListingKey]) END`; top filter by `Rank Value`.
- **Important:** right-click `city_clean`, `CountyOrParish`, `zip5` and `PropertySubType` filters and choose **Add to Context**. Otherwise the Top 100 is calculated over the whole market and then filtered, which leaves fewer than 100 agents.
- **Caveat on the dashboard:** agents are matched by name only (the data has no agent ID), so two agents with the same name would be combined.

### 2.2 Top 100 listing offices
- **Sheet:** same structure on `list_office_clean`.
- **Filters:** exclude `Non-member / Out of Area` and `Unknown` from the ranking (they are placeholders, not brokerages); the same top-100 filter and context filters as 2.1.
- **Required filters:** city, county, zip, PropertySubType.
- **Expect:** Compass first (about 31K sales Sold-wide), then Coldwell Banker Realty, eXp Realty of California Inc, Keller Williams Realty, Real Broker.

### 2.3 Zip heat map: median close price
- **Sheet:** filled map by `zip5`, color `MEDIAN([ClosePrice])` (sequential palette; the range is wide, so set the color range to the 5th-95th percentile).
- **Filters:** `Event Month` (range or single month), `city_clean`, `CountyOrParish`, `zip5`, `PropertySubType`; `Use for Metrics` = True; exclude `zip5` = `Unknown`.
- **Minimum sample:** add parameter `Min Sales` (default 10) and a boolean calculation `COUNT([ListingKey]) >= [Min Sales]`; filter it to True. A median from two sales is not a market signal.
- **Tooltip:** zip, median price, sales count, median price per sq ft.

### 2.4 Zip heat map: homes sold
- **Sheet:** filled map by `zip5`, color `COUNT([ListingKey])`. Same filters as 2.3 but use **all rows** (counts), and no minimum-sales filter.
- **Expect:** the highest counts are in the Coachella Valley (92253 has 2,685 sales) and the Inland Empire.

### 2.5 Own design: "Brokerage positioning"
- **Purpose:** show how the top brokerages differ by market position, not only by volume.
- **Sheet:** scatter of the top 25 offices. X `COUNT([ListingKey])` (units), Y `MEDIAN([ClosePrice])`, size `SUM([ClosePrice])`, color `MEDIAN([days_on_market])` or `AVG([close_to_original_list_ratio])`, label `list_office_clean`.
- **Filters:** same exclusions as 2.2 and the same global filters.
- **Takeaway:** for example, Compass is both highest in volume and in the upper-price band (median about $1.34M), while eXp and Real Broker sell at lower prices.

### Competitive dashboard layout
Page 1: agents and offices tables side by side with the filters. Page 2: the two heat maps stacked, with a shared month filter. Page 3: brokerage positioning.

---

## 3. Checks before you publish

| Check | Expected |
|---|---|
| Sum of monthly closed sales, Jan 2024-Apr 2026 (all rows) | 414,091 |
| Distinct new listings in `tableau_listings.csv` | matches `csv/monthly_market_activity.csv` (`new_listings`) for every month |
| Overall median close price, all rows | $822,540 |
| Overall median close price, `include_in_analysis` = True | $780,000 |
| Sold rows with `include_in_analysis` = True | 340,522 |
| Listing rows with `include_in_analysis` = True | 464,673 |
| Top office by units | Compass |

---

## 4. Publishing

The handbook says to publish to Tableau Public and also says the data is confidential and must not be distributed externally. Both cannot be followed with the row-level files. Options, in order of preference:

1. **Ask the program team** whether publishing the dashboards is allowed with the data embedded.
2. **Publish from an aggregated extract.** Build a separate data source at the grain the dashboards need (month x zip x city x county x PropertySubType, with counts, sums and medians; plus office and agent tables with their totals). No ListingKey, no coordinates, no individual transactions. I can generate those files from the existing exports.
3. If the above are not possible, keep the workbooks as `.twbx` files for the presentation and share screenshots.

Also: in Tableau Public, turn off **Show Download** on each workbook.
