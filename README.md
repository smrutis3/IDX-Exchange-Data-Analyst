# IDX Exchange - MLS Analytics Internship

Repository tracking code, progress, and analytics deliverables for the **IDX Exchange 12-Week Data Analyst Internship Program**.

---

## 📌 Internship Roadmap

- [x] **Week 1:** Monthly Dataset Aggregation & Residential Filtering
- [ ] **Weeks 2–3:** Dataset Structuring, Validation & FRED Mortgage Rate Enrichment
- [ ] **Weeks 4–5:** Data Cleaning, Transformation & Quality Checks
- [ ] **Week 6:** Feature Engineering & Housing Market Metrics
- [ ] **Week 7:** Outlier Detection (IQR Method) & Quality Flags
- [ ] **Weeks 8–10:** Tableau Dashboards (Market & Competitive Analysis)
- [ ] **Weeks 11–12:** Market Intelligence Report & Final Presentation

---

## 📅 Weekly Progress Log

### Week 1: Monthly Dataset Aggregation & Filtering

**Objective:** Combine individual monthly MLS CSV files from January 2024 through December 2024 into unified datasets, log row counts at each step, filter strictly for `Residential` properties, and export master files.

#### 📊 Execution Summary & Row Counts

| Dataset | Input Files | Raw Input Rows | Residential Rows Kept | Non-Residential Filtered | Saved Master CSV |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Sold Transactions** | 12 CSVs | **272,473** | **186,243** | 86,230 | `combined_sold_residential.csv` |
| **Listing Transactions** | 12 CSVs | **383,920** | **242,994** | 140,926 | `combined_listings_residential.csv` |

#### 📁 Key Deliverables
* `week1_aggregation.py`: Aggregation and residential filtering script.
* `week1_output.txt`: Execution log verifying row count integrity before and after filtering.

---

## 🛠️ How to Run

Navigate to the `csv` folder and execute the aggregation script:

```bash
python week1_aggregation.py