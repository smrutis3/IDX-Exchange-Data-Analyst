# IDX Exchange - MLS Analytics Internship

Repository tracking code, progress, and analytics deliverables for the **IDX Exchange 12-Week Data Analyst Internship Program**.

---

## 📌 Internship Roadmap

- [x] **Week 1:** Monthly Dataset Aggregation & Residential Filtering
- [x] **Weeks 2–3:** Dataset Structuring, Validation & FRED Mortgage Rate Enrichment
- [ ] **Weeks 4–5:** Data Cleaning, Transformation & Quality Checks
- [ ] **Week 6:** Feature Engineering & Housing Market Metrics
- [ ] **Week 7:** Outlier Detection (IQR Method) & Quality Flags
- [ ] **Weeks 8–10:** Tableau Dashboards (Market & Competitive Analysis)
- [ ] **Weeks 11–12:** Market Intelligence Report & Final Presentation

---

## 📅 Weekly Progress Log

### Week 1: Monthly Dataset Aggregation & Filtering
* Combined individual monthly MLS CSV files into unified datasets.
* Filtered strictly for `Residential` properties (`PropertyType == 'Residential'`).
* **Deliverables:** `week1_aggregation.py`, `week1_output.txt`.

---

### Weeks 2–3: Structuring, Validation & Mortgage Rate Enrichment

**Objective:** Audit missing data, compute key numeric distribution metrics, fetch live 30-year mortgage rates from FRED, resample weekly rates to monthly averages, and merge them into MLS datasets.

#### 📊 Execution Summary
* **Missing Value Analysis:** Audited all columns for high missingness (>90% null threshold).
* **Numeric Distribution Review:** Analyzed statistical metrics (min, max, mean, median, percentiles) for `ClosePrice`, `LivingArea`, and `DaysOnMarket`.
* **FRED Rate Enrichment:** Successfully fetched `MORTGAGE30US` series, computed monthly averages, and left-joined onto both datasets using `year_month`.
* **Validation:** Verified 0 null rate matches post-merge.

#### 📁 Key Deliverables
* `week2_3_validation_enrichment.py`: Data structure validation, distribution analysis, and FRED API join script.
* `week2_3_output.txt`: Execution log verifying missing value checks, summary stats, and 0-null rate validation.
* `sold_enriched.csv` & `listings_enriched.csv`: Master enriched files ready for cleaning.

---

## 🛠️ How to Run

Navigate to the project folder and execute:

```bash
# Week 1 Aggregation
python csv/week1_aggregation.py

# Weeks 2–3 Validation & Enrichment
python csv/week2_3_validation_enrichment.py