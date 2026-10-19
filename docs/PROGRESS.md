# Progress Tracker

Update this file at the end of every work session: tick tasks, record real numbers, note decisions and blockers.
Also add that day's likely interview questions (with real numbers) to `docs/INTERVIEW_PREP.md`.

## Status: Day 3 complete; next: Day 4 Power BI (export star schema + fact_order_risk to Parquet)

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
- [x] `sql/04_business_queries.sql` (12 queries + one-line insights), run by `scripts/run_queries.py`; results in `sql/results/*.csv`

### Day 2: Data-quality audit + EDA
- [x] `notebooks/00_data_quality_audit.ipynb` + `docs/DATA_QUALITY_REPORT.md`: 45 checks in `sql/03_data_quality_checks.sql` (decision + action stored beside each check), run by `src/data_quality.py`; tests in `tests/test_db.py` (4 pass)
- [x] `notebooks/01_eda.ipynb` + 5 insights (with numbers), incl. payment method vs approval/delivery time; stats in `src/stats.py` (tests in `tests/test_stats.py`), extracts in `sql/05_eda_queries.sql`; figures in `docs/figures/eda_*.png`

### Day 3: ML
- [x] `src/features.py` (purchase-time features; seller history from orders DELIVERED before purchase; rolling 90-day windows; market context); SQL `sql/06_ml_features.sql`; leakage tests `tests/test_features.py`
- [x] `notebooks/02_late_delivery_model.ipynb`: logistic regression vs LightGBM (**logistic wins**), PR-AUC, cost threshold, SHAP; code in `src/train.py`, `src/predict.py`
- [x] `fact_order_risk` + `models/` artefacts (`late_delivery_model.pkl`, `metadata.json`, `order_risk_scores.parquet`; reloaded by `build_db.py`)

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
| 2026-10-19 | Raw dataset size | 9 tables · 1,550,922 rows · 52 columns (all profiled: example, distinct count, missing %) | `00_data_quality_audit.ipynb` §0 (`src/data_quality.table_overview`, `column_profile`) |
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
| 2026-10-19 | **Late vs on-time review test** | Mann-Whitney U = 103,305,546, p < 1e-300, rank-biserial r = −0.64; mean 2.27 vs 4.29 (median 1 vs 5); diff −2.02★, 95% bootstrap CI [−2.06, −1.98] (2,000 resamples, seed 42); n = 6,381 late / 89,443 on time | `01_eda.ipynb` Insight 1 |
| 2026-10-19 | Late × (1–2★) chi-square | χ² = 15,064, p < 1e-300, Cramér's V = 0.40 | `01_eda.ipynb` Insight 1 |
| 2026-10-19 | Within-state check | late scores lower in 21 of 21 states with ≥30 late reviewed orders; gap 1.63–2.62★ | `01_eda.ipynb` Insight 2 |
| 2026-10-19 | Delay vs score (Spearman) | ρ = −0.18 all delivered; ρ = −0.40 late orders only | `01_eda.ipynb` Insight 2 |
| 2026-10-19 | Late rate by month | ~3% typical; 12.40% (2017-11), 14.13% (2018-02), 18.96% (2018-03); 2018-01 5.70% on 7,069 orders vs 2018-03 on 7,003; avg promised days 15.8 in 2018-08 | `eda_monthly_delivery` |
| 2026-10-19 | Estimate buffer | median 12.4 days early (mean 11.8); 59.9% delivered in under half the promised time | `01_eda.ipynb` Insight 4 |
| 2026-10-19 | Payment method vs approval | median approval boleto 29.06 h vs card 0.27 h; Kruskal-Wallis H = 32,338, ε² = 0.34; mean days after approval boleto 12.12 vs card 12.17 | `01_eda.ipynb` Insight 5 |
| 2026-10-19 | Payment method vs late | χ² = 17.4, p = 0.000586, Cramér's V = 0.013 (negligible) | `01_eda.ipynb` Insight 5 |
| 2026-10-19 | Written-comment rate | late 58.9% vs on time 39.3% | `01_eda.ipynb` bonus |
| 2026-10-19 | ML split sizes / late rate | train 2017: 43,426 (5.65%) · valid 2018-01..03: 20,627 (12.88%) · test 2018-04..08: 32,150 (4.42%) | `02_late_delivery_model.ipynb` §1 |
| 2026-10-19 | **Model selection (valid PR-AUC)** | logistic regression 0.284 (C=0.01, no class weight) vs best LightGBM 0.213 (of 24 configs; early-stopped at 1-14 trees) | §3 |
| 2026-10-19 | **Test PR-AUC (evaluated once)** | logistic regression 0.0943 (lift 2.13x over base rate 0.0442; ROC-AUC 0.727) · LightGBM 0.0725 (ROC-AUC 0.636) | §4 |
| 2026-10-19 | Test precision at top k% risk | top 1% 0.140 · top 5% 0.106 · top 10% 0.105 · top 20% 0.102 (lift 3.2x / 2.4x / 2.4x / 2.3x) | §4 |
| 2026-10-19 | Cost-based threshold (FN 5 : FP 1, chosen on valid) | 0.045; valid cost 0.745x of flag-nothing; **test: precision 9.4%, recall 57.8%, flags 27.3%, cost 10,951 vs 7,105 flag-nothing (1.54x)** | §5 |
| 2026-10-19 | Threshold sensitivity on test (cost / flag-nothing) | 3:1 → 1.795 · 5:1 → 1.541 · 10:1 → 1.250 | §5 |
| 2026-10-19 | Top SHAP drivers (test, mean abs log-odds) | promised_days 0.460 · distance_km 0.275 · customer_state 0.227 · same_state 0.192 · market_late_rate_30d 0.149 | §6 |
| 2026-10-19 | SHAP check | own linear SHAP = shap.LinearExplainer (max diff 0.00); contributions reproduce logit (max err 2.66e-15) | §6 |
| 2026-10-19 | Mean predicted vs actual late rate | test 3.78% vs 4.42%; valid 3.42% vs 12.88% | `fact_order_risk` check |
| 2026-10-19 | fact_order_risk | 96,203 scored orders (test: high 8,772 · medium 13,238 · low 10,140) | §7 |
| 2026-10-19 | Fresh-build SQL test | temp DB from raw CSVs; all named queries in 03/04/05/06 return rows (5 tests) | `tests/test_sql_build.py` |
| 2026-10-19 | Best one-feature rule (chosen on valid) | distance_km (farther = riskier): valid PR-AUC 0.174, test 0.059 | notebook 02 §3b/§4b |
| 2026-10-19 | **Test PR-AUC 95% CI (paired bootstrap, 1,000, seed 42)** | logistic 0.094 [0.087, 0.104]; vs LightGBM diff [−0.029, −0.016]; vs rule diff [−0.043, −0.029] | notebook 02 §4b |
| 2026-10-19 | Error analysis by month (test) | PR-AUC 0.181 (Apr) · 0.151 (May) · 0.058 (Jun, late rate 1.2%, precision 3.7%) · 0.075 (Jul) · 0.089 (Aug) | notebook 02 §6 |
| 2026-10-19 | Error analysis by state (recall at threshold) | PE 87.8% · CE 84.4% · BA 79.8% · RJ 79.1% … MG 18.3% · RS 27.5% · PR 29.5% | notebook 02 §6 |
| 2026-10-19 | Missed vs caught late orders (medians) | distance 319 vs 667 km; market late rate 9.6% vs 4.9% (1,421 late: 821 caught, 600 missed) | notebook 02 §6 |
| 2026-10-19 | Test classification metrics per model (threshold chosen on valid, 5:1) | Model 0 always on-time: acc 0.956, P/R/F1 0 · Model 1 rule (distance > ~1,161 km): acc 0.853, P 0.084, R 0.236, F1 0.124 · Model 2 logistic: acc 0.734, P 0.094, R 0.578, F1 0.161 · Model 3 LightGBM: acc 0.764, P 0.077, R 0.397, F1 0.130 | notebook 02 §4-§8 |
| 2026-10-19 | Test cost vs flag-nothing per model | rule 1.276 · logistic 1.541 · LightGBM 1.550 (none beats doing nothing under drift) | notebook 02 §8 |
| 2026-10-19 | Logistic regression at default threshold 0.5 | flags 0 of 32,150 test orders (identical to Model 0) | notebook 02 §6 |
| 2026-10-19 | Test ROC-AUC per model | rule 0.529 · logistic 0.727 · LightGBM 0.636 | notebook 02 §8 |

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
| 2026-10-19 | Audit notebook §0 = pandas first look (read_csv, .info(), .head()) + pandas-vs-DuckDB check (rows, columns, missing all match) | First step of the project is now saved and reproducible |
| 2026-10-19 | SQL renumbered: 03_data_quality_checks before 04_business_queries | Files read in the logical order (audit before analysis) |
| 2026-10-19 | q02–q06 sort on unrounded values + tie-breakers | Ties at the LIMIT boundary made top-10 lists change between runs; now identical across 3 runs |
| 2026-10-19 | README: step-by-step walkthrough, real Key Results, LightGBM claims corrected | Non-technical readers can follow the order; README matched logged results |
| 2026-10-19 | README walkthrough order = first look → clean (01/02) → audit (03) | `03_data_quality_checks.sql` reads the cleaned tables (47 references), so it runs after the build; it sizes raw issues and verifies the fixes |
| 2026-10-19 | Added fresh-build SQL test (skips without raw data) | PRD acceptance criterion "queries run cleanly from a fresh build" is now automated |
| 2026-10-19 | Added rule baseline, paired bootstrap CI and error analysis to notebook 02 | Show the model beats a simple rule and the gaps aren't noise; locate where it fails |
| 2026-10-19 | Notebook 02 restructured: one section per model (0 always on-time, 1 rule, 2 logistic, 3 LightGBM), each with classification_report + confusion matrix, then a comparison section | Reviewers expect per-model reports; presentation borrowed from the owner's Telco churn project, methodology kept (validation selection, cost threshold, CIs) |
| 2026-10-19 | Accuracy reported but not used for selection | Do-nothing model scores 0.956 accuracy with zero recall; selection stays on validation PR-AUC |
| 2026-10-19 | Added 'Dataset overview' (§0) to the audit notebook | The first look at the data (tables, columns, sample rows) was only in session output; now it's reproducible in the repo |
| 2026-10-19 | DQ check metadata (table/issue/decision/action) stored as comments beside each check SQL | Decision and measurement can't drift apart; a test fails if any check lacks metadata |
| 2026-10-19 | `src/db.py` shared parser + read-only `connect()`; `run_queries.py` refactored to use it (q09 output unchanged) | One implementation, reused by scripts, notebooks and later the app |
| 2026-10-19 | Reviews created before delivery kept (not flagged) | Genuine behaviour (5.19%); relevant to Module 2 'never_arrived'; reviews are never ML features |
| 2026-10-19 | Rank-based tests (Mann-Whitney, Spearman, Kruskal-Wallis) + effect sizes + bootstrap CI | Review scores are ordinal and J-shaped; with ~95k rows p-values are always tiny, so effect sizes carry the conclusion |
| 2026-10-19 | Ruff lints notebooks too; E402 ignored for `notebooks/*.ipynb` only | Notebooks must add the project root to sys.path before importing `src` |
| 2026-10-19 | **Day 3 implication:** time-based split is essential | Late rate spikes (2017-11, 2018-02/03) and promised days drift in 2018 |
| 2026-10-19 | Seller history counts only orders DELIVERED before the purchase (stricter than 'purchased before') | An earlier order still in transit has no known outcome at purchase time |
| 2026-10-19 | Rolling 90-day seller windows + market context (30-day platform late rate, 7d/28d volume ratio) replace all-time counts | All-time counts grow with platform age (non-stationary); decided on validation |
| 2026-10-19 | Keep `is_nov_dec` although constant in valid/test | Removing it dropped valid PR-AUC 0.267 → 0.188: it absorbs the 2017 holiday spike so other weights aren't distorted |
| 2026-10-19 | **Production model = logistic regression, not LightGBM** (ARCHITECTURE D2 revised) | Wins on validation (0.284 vs 0.213) and test; trees can't extrapolate under drift. Rule 6: report what wins |
| 2026-10-19 | No class weighting in final model | Higher valid PR-AUC (0.284 vs 0.267) and probabilities stay on the real base-rate scale |
| 2026-10-19 | Threshold from FN:FP = 5:1 on validation; reported as NOT transferring to test | Honest result: fixed threshold fails under a 3x base-rate drop; recommend monthly recalibration or top-k use |
| 2026-10-19 | Transparency: an earlier feature set was scored on test once before drift was diagnosed | Noted in notebook §3; all later choices made on validation only |
| 2026-10-19 | Seller/category on-time: an order counts for every seller/category in it | Simple, stated; multi-seller orders are 1,275 of 96,470 delivered (1.32%) |
| 2026-10-19 | Raw layer loaded with `all_varchar = true`; all type casting done in `sql/01_staging.sql` | Raw copy is exact; every cast is explicit and reviewable |
| 2026-10-19 | Download via Kaggle public endpoint instead of the Kaggle API key | Reproducible for anyone, no credential to manage |
| 2026-10-19 | Ruff line-length 100, rules E/F/I/UP/B (`pyproject.toml`); `.gitattributes` forces LF | One lint config for local + CI; consistent line endings for Linux deployment |

## Blockers / notes
- `ARCHITECTURE.md` artefact name changed: `models/late_delivery_model.pkl` (was `late_delivery_lgbm.pkl`) because logistic regression won.
- Global git identity on this PC is `sarkarmenssalon-creator`; first commit was authored as Masood Manzoor Ahmed via a per-commit override. Set a repo-local identity before the next commit.
- Power BI: no native DuckDB connector; plan is to export star-schema tables to Parquet on Day 4.
