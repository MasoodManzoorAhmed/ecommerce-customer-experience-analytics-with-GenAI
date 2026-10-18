# Progress Tracker

Update this file at the end of every work session: tick tasks, record real numbers, note decisions and blockers.
Also add that day's likely interview questions (with real numbers) to `docs/INTERVIEW_PREP.md`.

## Status: Day 2 in progress: audit done; next: `notebooks/01_eda.ipynb` (5 insights + statistical test)

### Day 0: Setup
- [x] Project folder + docs created (PRD, goals, architecture, README, start prompt)
- [x] Python 3.12.10 installed; `.venv` created; `pip install -r requirements.txt` (exact versions in `requirements.lock.txt`)
- [x] Git repo initialised, first commit (`aa1b112`)
- [ ] GitHub repo created (`ecommerce-customer-experience-analytics`) and pushed
- [x] Dataset downloaded to `data/raw/` via `scripts/download_data.py` (Kaggle public endpoint, no API key needed)
- [ ] `.env` created from `.env.example` (OpenRouter or Gemini key) (needed by Day 5). `.env` git-ignore **confirmed** with `git check-ignore`

### Day 1: SQL
- [x] `scripts/build_db.py` loads 9 CSVs into `data/olist.duckdb` (raw schema, all columns as text; row counts cross-checked with pandas)
- [x] `sql/01_staging.sql` (8 views, all keys verified unique)
- [x] `sql/02_star_schema.sql` (6 tables; totals reconcile with staging; no orphan keys)
- [x] `sql/03_business_queries.sql` (12 queries + one-line insights), run by `scripts/run_queries.py`; results in `sql/results/*.csv`

### Day 2: Data-quality audit + EDA
- [x] `notebooks/00_data_quality_audit.ipynb` + `docs/DATA_QUALITY_REPORT.md`: 45 checks in `sql/04_data_quality_checks.sql` (decision + action stored beside each check), run by `src/data_quality.py`; tests in `tests/test_db.py` (4 pass)
- [ ] `notebooks/01_eda.ipynb` + 5 insights (with numbers), incl. payment method vs approval/delivery time

### Day 3: ML
- [ ] `src/features.py` (purchase-time features, seller history from earlier orders only)
- [ ] `notebooks/02_late_delivery_model.ipynb`: baseline vs LightGBM, PR-AUC, threshold, SHAP
- [ ] `fact_order_risk` + `models/` artefacts

### Day 4: Power BI
- [ ] 3 pages + measures + screenshots

### Day 5: Excel + Module 1 (start)
- [ ] `excel/Monthly_CX_Report.xlsx`
- [ ] `genai/semantic_layer.yaml`, eval set (≥ 40), baseline accuracy

### Day 6: Module 1 (finish) + app
- [ ] Steps a–d measured; guardrails + tests; model comparison
- [ ] Streamlit app deployed (URL: …)

### Day 7: Packaging (first pass)
- [ ] GitHub Actions CI (ruff + pytest) · Dockerfile (nice-to-have, cut first if short on time)
- [ ] README results filled in · résumé bullets · first 10 applications

### Days 8–10: Module 2 (required)
- [ ] Gold labels (≈ 200) · LLM labels (≈ 1,500) · TF-IDF baseline
- [ ] LoRA fine-tune + zero-shot comparison
- [ ] Apply to all reviews → `fact_review_theme` → Power BI/app
- [ ] Final README · 3-minute demo video · LinkedIn post

## Results log (real numbers only)

| Date | Metric | Value | Source (notebook/script) |
|---|---|---|---|
| 2026-10-19 | Raw row counts | orders 99,441 · order_items 112,650 · customers 99,441 · order_payments 103,886 · order_reviews 99,224 · products 32,951 · sellers 3,095 · geolocation 1,000,163 · category_translation 71 | `scripts/build_db.py` (matched by pandas) |
| 2026-10-19 | Distinct customer_unique_id | 96,096 (vs 99,441 customer_id) | ad-hoc DuckDB check |
| 2026-10-19 | Purchase timestamp range | 2016-09-04 21:15:19 → 2018-10-17 17:30:18 | ad-hoc DuckDB check |
| 2026-10-19 | Reviews: rows / distinct review_id / distinct order_id | 99,224 / 98,410 / 98,673 (duplicates confirmed; dedup in staging) | ad-hoc DuckDB check |
| 2026-10-19 | Staging row counts | stg_orders 99,441 · stg_order_items 112,650 · stg_customers 99,441 · stg_payments 103,886 · stg_reviews 98,673 · stg_products 32,951 · stg_sellers 3,095 · stg_geolocation 19,010 | `sql/01_staging.sql` + verification query |
| 2026-10-19 | Reviews with comment text | 40,748 of 98,673 (after trim/blank→NULL) | `stg_reviews` |
| 2026-10-19 | Orders with no review | 768 | `stg_orders` vs `stg_reviews` |
| 2026-10-19 | Zip prefixes not in geolocation | customers 278 · sellers 7 (raw); +5 prefixes removed by bbox filter | ad-hoc DuckDB check |
| 2026-10-19 | Star schema row counts | fact_orders 99,441 · fact_order_items 112,650 · dim_customer 96,096 · dim_seller 3,095 · dim_product 32,951 · dim_date 852 (2016-09-01 → 2018-12-31) | `sql/02_star_schema.sql` + verification query |
| 2026-10-19 | Item revenue reconciliation | R$13,591,643.70 identical in stg_order_items, fact_order_items, fact_orders (all statuses, excl. freight) | verification query |
| 2026-10-19 | **Late-delivery rate** | **6.77%** (6,534 late of 96,470 delivered; date-based) | `fact_orders.is_late` |
| 2026-10-19 | Late count if compared on timestamps instead | 7,826 (1,292 same-day deliveries would be miscounted) | ad-hoc DuckDB check |
| 2026-10-19 | Main payment method (orders) | credit_card 74,975 · boleto 19,784 · voucher 3,151 · debit_card 1,527 · not_defined 3 · none 1 | `fact_orders.payment_type_main` |
| 2026-10-19 | dq_flags | no_items 775 · no_review 768 · payment_total_mismatch 249 · carrier_before_purchase 166 · customer_before_carrier 23 · delivered_without_date 8 · date_without_delivered_status 6 · no_payment 1; clean orders 97,467 | `fact_orders.dq_flags` |
| 2026-10-19 | Q01 monthly revenue | R$111,798 (2017-01) → R$826k–978k/month in 2018-01..08; peak 2017-11: 7,288 orders, +52.4% MoM | `sql/results/q01_monthly_trend.csv` |
| 2026-10-19 | Q02 revenue share by state | SP 38.3% · RJ 13.3% · MG 11.7% | `q02_revenue_by_state.csv` |
| 2026-10-19 | Q03 category concentration | 74 categories; top 7 = 49.9%, top 15 = 76.3%; #1 health_beauty 9.3% | `q03_category_pareto.csv` |
| 2026-10-19 | Q04 on-time by state | overall 93.23%; worst MA 82.64%, CE 86.26%; best PR 95.96%; avg delivery SP 8.8 d vs MA 21.5 d | `q04_on_time_by_state.csv` |
| 2026-10-19 | Q05 worst seller (≥100 orders) | 81.0% on-time (389 orders, MA); 8 of worst 10 in SP | `q05_worst_sellers_on_time.csv` |
| 2026-10-19 | Q06 worst categories (≥500 orders) | 91.9%–92.7% on-time (narrow spread) | `q06_worst_categories_on_time.csv` |
| 2026-10-19 | **Q07 late vs on-time review** | **2.27 vs 4.29 avg stars; 1–2 stars 62.4% vs 9.3%** | `q07_reviews_late_vs_on_time.csv` |
| 2026-10-19 | Q08 review by delay | 1–3 d late: 3.29 avg (32.1% 1–2★); 8–14 d late: 1.67 (80.2%); 15+ d: 1.72 (78.4%) | `q08_reviews_by_delay.csv` |
| 2026-10-19 | Q09 seller Pareto | 533 of 2,970 sellers (17.9%) = 80% of revenue; top 20% = 82.3% | `q09_seller_pareto.csv` |
| 2026-10-19 | Q10 repeat customers | 3.0% (2,801 of 93,350) with ≥2 delivered orders; 5.51% of revenue | `q10_repeat_customers.csv` |
| 2026-10-19 | Q11 cohort repeat by month +6 | 2.23%–4.18% (mean 3.03%), cohorts 2017-01..2018-02 | `q11_cohort_retention.csv` |
| 2026-10-19 | Q12 payment method | card 75.5% of orders, AOV R$143.24; boleto median approval 29.06 h vs card 0.27 h; late % boleto 7.32 vs card 6.69 | `q12_payment_method.csv` |
| 2026-10-19 | DQ audit decisions | 45 checks: FIX 12 · FLAG 17 · KEEP 15 · SCOPE 1 | `sql/results/data_quality_audit.csv` |
| 2026-10-19 | Clean orders (no dq_flags) | 97,467 of 99,441 (98.01%) | audit notebook §5 |
| 2026-10-19 | Late rate sensitivity | 6.77% all delivered (96,470) vs 6.67% delivered with no flags (95,392) | audit notebook §5 |
| 2026-10-19 | Reviews created before delivery / before purchase | 4,977 (5.19%) / 71 | `reviews_created_before_delivery`, `reviews_created_before_purchase` |
| 2026-10-19 | review_id shared across orders | 1,603 rows (789 review_ids) | audit + ad-hoc check |
| 2026-10-19 | Geolocation exact duplicate rows | 261,831 of 1,000,163 (26.18%) | `geo_exact_duplicate_rows` |
| 2026-10-19 | Orders without items: canceled / unavailable | 164 / 603 (767 of 775) | ad-hoc check |
| 2026-10-19 | Delivered orders missing approval timestamp | 14 | audit notebook §2 |

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-19 | Staging = views; no rows dropped; no business logic | Raw stays the single source; filtering decisions are made visibly in the star schema / audit |
| 2026-10-19 | One review per order: latest `review_answer_timestamp` (ties → creation date → review_id) | 547 orders have >1 review; no ties on answer ts observed |
| 2026-10-19 | `payment_installments` not selected in `stg_payments` | Project rule 4 (payment method only) |
| 2026-10-19 | Added 2 missing category translations by hand; NULL category → 'unknown' | Translation file lacks `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos` |
| 2026-10-19 | Geolocation: drop points outside Brazil bbox (lat −34..5.3, lng −74..−34.8) before averaging per zip | 47 bad points; avoids zip centres pulled abroad |
| 2026-10-19 | Estimated delivery kept as DATE (source is always 00:00:00) | Enables the date-based `is_late` below |
| 2026-10-19 | `is_late` = delivered **date** > estimated date (delivered = status 'delivered' AND delivery date present) | Estimate has no time of day; timestamp comparison would wrongly mark 1,292 same-day deliveries late (7,826 vs 6,534) |
| 2026-10-19 | `fact_orders` keeps all 99,441 orders; items/payments/reviews LEFT JOINed; issues go to `dq_flags` | Don't silently drop 775 item-less orders etc.; each analysis filters explicitly |
| 2026-10-19 | `payment_type_main` = method with largest amount; ties (188 orders) → earliest payment_sequential | Deterministic; payment method only (rule 4) |
| 2026-10-19 | `dim_customer` at customer_unique_id grain; address from most recent order | 96,096 people vs 99,441 order-level customer_ids; 39 people span >1 state |
| 2026-10-19 | Integer surrogate keys via ROW_NUMBER over natural id | Deterministic across rebuilds; compact Power BI relationships |
| 2026-10-19 | Q01 trend limited to 2017-01..2018-08 | 2016 has only 267 delivered orders (Nov missing); late-2018 months truncated, so MoM % is meaningless there |
| 2026-10-19 | Query results saved as CSV in `sql/results/` and committed | Every README number traceable to a file produced by code |
| 2026-10-19 | DQ check metadata (table/issue/decision/action) stored as comments beside each check SQL | Decision and measurement can't drift apart; a test fails if any check lacks metadata |
| 2026-10-19 | `src/db.py` shared parser + read-only `connect()`; `run_queries.py` refactored to use it (q09 output unchanged) | One implementation, reused by scripts, notebooks and later the app |
| 2026-10-19 | Reviews created before delivery kept (not flagged) | Genuine behaviour (5.19%); relevant to Module 2 'never_arrived'; reviews are never ML features |
| 2026-10-19 | Seller/category on-time: an order counts for every seller/category in it | Simple, stated; multi-seller orders are 1,275 of 96,470 delivered (1.32%) |
| 2026-10-19 | Raw layer loaded with `all_varchar = true`; all type casting done in `sql/01_staging.sql` | Raw copy is exact; every cast is explicit and reviewable |
| 2026-10-19 | Download via Kaggle public endpoint instead of the Kaggle API key | Reproducible for anyone, no credential to manage |
| 2026-10-19 | Ruff line-length 100, rules E/F/I/UP/B (`pyproject.toml`); `.gitattributes` forces LF | One lint config for local + CI; consistent line endings for Linux deployment |

## Blockers / notes
- Global git identity on this PC is `sarkarmenssalon-creator`; first commit was authored as Masood Manzoor Ahmed via a per-commit override. Set a repo-local identity before the next commit.
- Power BI: no native DuckDB connector; plan is to export star-schema tables to Parquet on Day 4.
