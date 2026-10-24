# Progress Tracker

Update this file at the end of every work session: tick tasks, record real numbers, note decisions and blockers.
Also add that day's likely interview questions (with real numbers) to `docs/INTERVIEW_PREP.md`.

## Status: Day 5 in progress: Excel report done; Module 1 semantic layer + 46-question eval set done; local ablation complete: 34.8% → 39.1% → 65.2% → 76.1% → 82.6%; next: final model comparison (best config on north-mini-code + gemma, free quota), then accuracy-per-step chart + README

### Day 0: Setup
- [x] Project folder + docs created (PRD, goals, architecture, README, start prompt)
- [x] Python 3.12.10 installed; `.venv` created; `pip install -r requirements.txt` (exact versions in `requirements.lock.txt`)
- [x] Git repo initialised, first commit (`aa1b112`)
- [ ] GitHub repo created (`ecommerce-customer-experience-analytics`) and pushed
- [x] Dataset downloaded to `data/raw/` via `scripts/download_data.py` (Kaggle public endpoint, no API key needed)
- [x] `.env` created from `.env.example` (OpenRouter key, free tier; `LLM_MODEL=cohere/north-mini-code:free`); git-ignored and untracked (checked); key accepted by OpenRouter (usage $0)

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
- [x] Export for Power BI: `sql/07_powerbi_export.sql` + `scripts/export_powerbi.py` → `data/powerbi/*.parquet` (6 tables, git-ignored)
- [x] Expected values for reconciliation: `scripts/powerbi_expected_values.py` → `powerbi/expected_values.csv` (48 checks, all pass)
- [x] 51 DAX measures (`powerbi/measures.dax`, explained in `powerbi/DAX_MEASURES_NOTES.md`) + calculated column `dim_seller[Seller]`; theme (`powerbi/theme.json`, Option C "Storyteller")
- [x] Built 3 pages + Seller detail drill-through in Power BI Desktop (`powerbi/olist_cx_dashboard.pbix`); every page tested for All/2016/2017/2018; screenshots in `powerbi/screenshots/`
- [x] `powerbi/POWERBI_GUIDE.md` rewritten for the final "Storyteller" design (design system, all 4 pages as built, reconciliation)

### Day 5: Excel + Module 1 (start)
- [x] `excel/Monthly_CX_Report.xlsx` built by `scripts/build_excel_report.py` (Excel COM automation) from `sql/08_excel_report.sql`: Summary (month + state selectors, XLOOKUP KPIs vs previous month / last year, formula key messages, 2 charts), Monthly (SUMIFS table), Categories + States (PivotTables, calculated fields, slicers, PivotCharts), What-if (2 Data Tables), Checks (19 reconciliations)
- [x] `genai/semantic_layer.yaml`: 12 metrics, 8 dimensions, 8 rules, joins; 8 core metrics proven equal to the Power BI values (`tests/test_semantic_layer.py`)
- [x] Eval set `genai/eval/text_to_sql_eval.yaml`: 46 questions (15 easy · 18 medium · 13 hard) with gold SQL; expected results `genai/eval/text_to_sql_expected.json` via `python -m genai.text_to_sql.eval_set`; `tests/test_eval_set.py` (single SELECT, allowed tables, in sync, no ties at LIMIT cut-offs)
- [x] LLM client (`genai/text_to_sql/llm_client.py`: disk cache, retry/backoff, pacing, stops on the daily free cap), guardrails (`guardrails.py`: sqlglot single SELECT, allowed tables, auto LIMIT, read-only + timeout), pipeline + evaluator (`pipeline.py`, `evaluate.py`: execution accuracy, order/column-name insensitive, rounding + fraction/percent tolerant); 24 new unit tests, no network
- [x] Baseline measured: **21/46 = 45.7%** (easy 60.0 · medium 50.0 · hard 23.1) on `cohere/north-mini-code:free`
- [x] Local open-source model added (Ollama `qwen2.5-coder:7b`, 16k context, `genai/ollama/Modelfile`): free, offline, no request cap; becomes the main model for the step-by-step ablation
- [x] Step a (column descriptions) measured on the local model: **34.8% → 39.1%** (+2 questions; re-scored with the corrected matcher)
- [x] Step a+b (semantic layer) on the local model: **39.1% → 65.2%** (+12 questions)
- [x] Step c (few-shot retrieval): `genai/text_to_sql/examples.yaml` (28 solved examples, patterns only), `retriever.py` (all-MiniLM-L6-v2 embeddings, top 3, offline); leakage tests (`tests/test_examples.py`); local model **65.2% → 76.1%**
- [x] Step d (self-correction: the error is sent back once) on the local model: **76.1% → 82.6%** (`pipeline.answer`, `tests/test_self_correction.py`)
- [ ] Final comparison of the best configuration on qwen (local), north-mini-code and gemma-4-31b (hosted, about 46 free requests each, one per day); re-ask m03/h01 for north-mini-code then

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
| 2026-10-19 | Best one-feature rule (chosen on valid) | distance_km (farther = riskier): valid PR-AUC 0.174, test 0.059 | notebook 02 §6, §9b |
| 2026-10-19 | **Test PR-AUC 95% CI (paired bootstrap, 1,000, seed 42)** | logistic 0.094 [0.087, 0.104]; vs LightGBM diff [−0.029, −0.016]; vs rule diff [−0.043, −0.029] | notebook 02 §9b |
| 2026-10-19 | Error analysis by month (test) | PR-AUC 0.181 (Apr) · 0.151 (May) · 0.058 (Jun, late rate 1.2%, precision 3.7%) · 0.075 (Jul) · 0.089 (Aug) | notebook 02 §12 |
| 2026-10-19 | Error analysis by state (recall at threshold) | PE 87.8% · CE 84.4% · BA 79.8% · RJ 79.1% … MG 18.3% · RS 27.5% · PR 29.5% | notebook 02 §12 |
| 2026-10-19 | Missed vs caught late orders (medians) | distance 319 vs 667 km; market late rate 9.6% vs 4.9% (1,421 late: 821 caught, 600 missed) | notebook 02 §12 |
| 2026-10-19 | Test classification metrics per model (threshold chosen on valid, 5:1) | Model 0 always on-time: acc 0.956, P/R/F1 0 · Model 1 rule (distance > ~1,161 km): acc 0.853, P 0.084, R 0.236, F1 0.124 · Model 2 logistic: acc 0.734, P 0.094, R 0.578, F1 0.161 · Model 3 LightGBM: acc 0.764, P 0.077, R 0.397, F1 0.130 | notebook 02 §5-§9 |
| 2026-10-19 | Test cost vs flag-nothing per model | rule 1.276 · logistic 1.541 · LightGBM 1.550 (none beats doing nothing under drift) | notebook 02 §9 |
| 2026-10-19 | Logistic regression at default threshold 0.5 | flags 0 of 32,150 test orders (identical to Model 0) | notebook 02 §7 |
| 2026-10-19 | Test ROC-AUC per model | rule 0.529 · logistic 0.727 · LightGBM 0.636 | notebook 02 §9 |
| 2026-10-19 | Power BI export | dim_date 852 · dim_customer 96,096 · dim_seller 3,095 · dim_product 32,951 · fact_orders 99,441 · fact_order_items 112,650 rows | `scripts/export_powerbi.py` |
| 2026-10-19 | Power BI expected values (from Parquet) | Delivered 96,470 · Revenue R$ 13,220,248.93 · AOV R$ 137.04 · On-time 93.23% · Avg review 4.16 · MoM Aug-2018 −3.33% · YoY Aug-2018 +51.18% · test risk band on-time: high 90.64%, low 99.06% | `powerbi/expected_values.csv` |
| 2026-10-19 | Model-table data checks | 96,203 rows; 0 duplicate order_ids (28 identical-feature rows are distinct orders); 5 of 23 features with missing values (train: seller_late_rate_90d 7.22%, seller_prior_late_rate 6.43%, distance_km 0.51%, weight/volume 0.04%); 0 infinite; none constant | notebook 02 §3 |
| 2026-10-19 | Missing-value fix proof | 6,182 missing (train, numeric) → 0 after preprocessing; 5 "was missing" indicators; 112 model inputs | notebook 02 §3.7 |
| 2026-10-19 | Skew / outliers (train) | skew: order_value 12.13, n_sellers 10.35, freight_value 8.81 …; kept as real orders | notebook 02 §3.5 |
| 2026-10-19 | Correlated features (train) | seller_orders_90d ~ seller_delivered_90d r = 0.989; late-rate pair 0.864; weight ~ volume 0.819 | notebook 02 §3.6 |
| 2026-10-19 | Log-transform test (valid PR-AUC) | best with log 0.273 vs without 0.284 → not used | notebook 02 §7 |
| 2026-10-19 | **Overfitting check (ROC-AUC train / valid / test)** | logistic 0.733 / 0.726 / 0.727 (no overfitting) · LightGBM 0.770 / 0.637 / 0.636 (overfits) | notebook 02 §10 |
| 2026-10-19 | Learning curve (logistic, train vs valid ROC-AUC) | 10% data: 0.740 vs 0.639 → 100%: 0.733 vs 0.726; valid plateaus from ~40% | notebook 02 §10 |
| 2026-10-19 | Calibration (test, by tenth) | top tenth predicted 10.1% vs actual 10.5%; lowest 1.0% vs 0.4%; 9th tenth 6.0% vs 9.8%; Brier 0.041 | notebook 02 §10 |
| 2026-10-24 | Break-even FN:FP ratio (top-k lists, logistic) | valid top 1% precision 38.8% → 1.6:1 · test top 1% 14.0% → 6.2:1, top 5-20% 8.4-8.8:1 (assumed ratio 5:1) | notebook 02 §11b |
| 2026-10-24 | Never-delivered orders (open past promised date at cut-off) | 1,702 (train 949 · valid 352 · test 401); late rate incl. them: test 4.42% → 5.60%, valid 12.88% → 14.34%, train 5.65% → 7.67% | notebook 02 §15 |
| 2026-10-24 | Label sensitivity (test) | mean predicted: on time 3.69% · never delivered 4.51% · delivered late 5.73%; PR-AUC lift on wider label 1.92× (vs 2.13×); re-trained on wider label 1.68× (wider) / 1.80× (delivered) | notebook 02 §15 |
| 2026-10-24 | Refit on train + valid (C = 0.01, no tuning) | test PR-AUC 0.094 → 0.103 (paired diff CI +0.003 to +0.015) · ROC-AUC 0.727 → 0.703 · mean predicted 3.78% → 9.95% (actual 4.42%) · top 1% precision 14.0% → 18.3% (break-even 4.5:1) · at Bayes threshold 1/6: cost 8,640 vs flag-none 7,105 (2017 model 7,103) | notebook 02 §16 |
| 2026-10-24 | Excel report reconciliation | 19/19 checks pass (15 vs SQL expected values, 4 internal); SP 2018-03 in Excel = SQL: R$ 377,034.34 · 2,971 orders · 90.58% on time · 4.13 avg review | `excel/Monthly_CX_Report.xlsx` Checks sheet; interaction test |
| 2026-10-24 | Excel Summary, Aug 2018 (all states) | revenue R$ 838,577 (MoM −3.3%, YoY +51.2%) · 6,351 orders · on-time 93.8% (−2.8 pts MoM) · 393 late · avg review 4.31 (late 2.99 vs on time 4.40) | Excel Summary sheet |
| 2026-10-24 | What-if (default: target on-time 96%, 50% of review gap recovered) | 183 late orders/month turned on time · avg review 4.156 → 4.184 (+0.028) · 49 fewer 1-2★ reviews/month; upper bound (99%, 100%): 4.27 stars, 202 fewer/month; base 6,597 delivered orders/month (2018) | Excel What-if sheet |
| 2026-10-24 | Review gap after controls (OLS: customer state, category, log order value, items, sellers, promised days, freight) | −2.03 adjusted vs −2.02 raw (95,824 reviewed delivered orders) | ad-hoc check this session; supports the what-if caveat |
| 2026-10-24 | Text-to-SQL eval set | 46 items (15 easy · 18 medium · 13 hard); 25 gold answers cross-checked against earlier verified results (e.g. revenue R$ 13,220,248.93, on-time 93.23%, MA 82.64%, risk bands 9.36/3.81/0.94%, 2018-03 18.96% late, 533 sellers for 80%, SP 38.34% of revenue) | `genai/eval/text_to_sql_expected.json` |
| 2026-10-24 | Eval-set fairness check | 11 ranking questions checked for ties at the cut-off; 1 found (office_furniture 91.946% vs baby 91.954% both round to 91.95%) → question changed to the 2 lowest | `tests/test_eval_set.py` |
| 2026-10-24 | **Text-to-SQL baseline** (schema only, `cohere/north-mini-code:free`) | **21/46 = 45.7%** · easy 9/15 (60.0%) · medium 9/18 (50.0%) · hard 3/13 (23.1%) · mean latency 9.89 s · ~420 prompt tokens · US$0 | `genai/results/text_to_sql_runs.csv` |
| 2026-10-24 | Baseline failure review (all 25 checked by re-running the SQL) | 17 ignored the delivered-orders rule · 2 used state names not codes (e15, h04) · 2 guessed stored values (e06 NULL vs 'unknown', h10 'credit card') · 1 customer definition (h05) · 1 empty reply (h07) · 1 h01 genuinely wrong · 1 false negative: m03 had the right numbers but 'January' vs '2018-01' (question ambiguous) → m03/h01 wording now says YYYY-MM | manual review this session |
| 2026-10-24 | Free-tier behaviour | 58 requests used before 'free-models-per-day' 429; client now stops immediately on that error instead of retrying | OpenRouter response |
| 2026-10-24 | **Local model baseline** (`ollama/qwen2.5-coder-16k`, schema only) | **16/46 = 34.8%** (first scored 37.0%; h04 re-scored wrong) · easy 60.0 · medium 33.3 · hard 7.7 · 8 execution errors · mean 19.2 s · ~461 prompt tokens · US$0 | `genai/results/text_to_sql_runs.csv` |
| 2026-10-24 | **Step a: + column descriptions** (local model) | **18/46 = 39.1%** (first scored 45.7%; e02, e14, h04 re-scored wrong) · gained e06, e15, h10, m03, m04; lost m18 · easy 60.0 · medium 38.9 · hard 15.4 · execution errors 8 → 4 · mean 23.8 s · ~2,221 prompt tokens | `genai/results/text_to_sql_runs.csv` |
| 2026-10-24 | Step-a failure review (all 25 re-run) | no false negatives; remaining causes: delivered-orders rule ignored (e03, e07, e09, e11, m01, m02, m07, m11, m13, m17, h12; m18 used order_status = 'delivered', 9,352 vs 9,351) · fan-out after joining items (m05 health_beauty R$ 36.7M vs 1.23M, m16, h02) · customer definition (m14, h05) · wrong columns/GROUP BY (4 execution errors: h03, h06, h07, h13) · h01, h09, h11 logic | manual review this session |
| 2026-10-24 | **Step a+b: + semantic layer** (local model) | **30/46 = 65.2%** (+10: e03, e07, e09, e11, m01, m02, m06, m07, m13, m18; lost h10) · easy 100.0 · medium 72.2 · hard 15.4 · 4 execution errors · mean 23.1 s · ~4,045 prompt tokens | `genai/results/text_to_sql_runs.csv` |
| 2026-10-24 | Step a+b failure review (all 16 re-run) | item-level revenue still without the delivered filter (m05, m16, h02: health_beauty R$ 1,258,681 vs 1,233,132) · delivered filter missing in month/YoY questions (m11, h12) · definitions (m14 counted all 93,350 customers with a delivered order; h13 not distinct orders) · logic (h01, h09, h10, h11) · 4 execution errors (h03, h05 avg(BOOLEAN), h06 GROUP BY, h07) · 1 borderline (m17 includes a NULL payment-method row; gold excludes it) | manual review this session |
| 2026-10-24 | **Evaluator correction** | The example-leakage test flagged that a ±0.05 / 0.01% numeric tolerance accepted wrong answers (4.19 vs 4.16 stars; 96,478 vs 96,470 delivered orders). New rule: match at the gold answer's 2-decimal precision, or the model's own coarser rounding. All 184 stored runs re-scored from their saved SQL (`evaluate --rescore`, no LLM calls): 4 verdicts changed, all correctly to wrong (local a: e02, e14, h04; local baseline: h04); north-mini-code and local a+b unchanged | `genai/text_to_sql/evaluate.py`, `tests/test_examples.py` |
| 2026-10-24 | **Step a+b+c: + 3 retrieved examples** (local model) | **35/46 = 76.1%** (+8: h06, h09, h10, h11, h12, m05, m14, m16; lost m04, m07, m10) · easy 100.0 · medium 72.2 · hard 53.8 (was 15.4) · 6 execution errors · mean 24.0 s · ~4,320 prompt tokens | `genai/results/text_to_sql_runs.csv` |
| 2026-10-24 | Step c failure review (all 11 re-run) | 6 execution errors (h03, h05 avg(BOOLEAN), h07, m04, m10, m11) · negative transfer: m10 'states with the longest delivery' copied the retrieved SELLER-state example; h13 computed review instead of on-time · h01 LAG inside the filtered window (Jan = NULL) · h02, m07 logic/filter · m17 borderline (NULL payment-method row) | manual review this session |
| 2026-10-24 | **Step a+b+c+d: + self-correction** (local model) | **38/46 = 82.6%** (+3: h05, m04, m11; no losses) · easy 100.0 · medium 83.3 · hard 61.5 · 6 queries retried, 3 fixed · mean 30.4 s · ~4,915 prompt tokens (both calls) · US$0 | `genai/results/text_to_sql_runs.csv` |
| 2026-10-24 | **Ablation summary, local qwen2.5-coder 7B** | baseline 34.8% → +a 39.1% → +b 65.2% → +c 76.1% → +d 82.6% (largest single gain: semantic layer, +12 questions) | runs file above |
| 2026-10-24 | Step d remaining failures (8) | 5 wrong results with no error, so no retry possible (h01 LAG in the filtered window, h02, h13 wrong metric, m07 missing delivered filter, m17 borderline NULL row) · 3 still failing after the retry (h03, m10 execution; h07 unparseable) | manual review this session |

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
| 2026-10-19 | Notebook 02 §3 (model data checks) and §10 (diagnostics) added; log transform added as a tuning option | Show missing/duplicate/outlier handling and over/underfitting evidence explicitly; log option kept only if validation improves (it didn't) |
| 2026-10-19 | Corrected interpretation: seller_orders_90d vs seller_delivered_90d opposite signs = collinearity (r = 0.989), not a 'backlog' signal | Read correlated pairs together in SHAP |
| 2026-10-19 | Accuracy reported but not used for selection | Do-nothing model scores 0.956 accuracy with zero recall; selection stays on validation PR-AUC |
| 2026-10-19 | Power BI fed by Parquet exports (no native DuckDB connector); model scores merged into fact_orders export | Types preserved; simpler model for report users |
| 2026-10-19 | Power BI model: header→lines (fact_orders 1→* fact_order_items), all single-direction; CROSSFILTER only inside [Avg Review (via items)] | Avoid ambiguous bi-directional paths; product/seller visuals use item-level measures |
| 2026-10-19 | Every DAX measure has an SQL-computed expected value | Reconciliation catches modelling/DAX mistakes |
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
| 2026-10-24 | Keep the delivered-only label; report never-delivered orders separately (5.60% "late or never delivered" on test) | Re-training on the wider label lowers lift (different causes: ~2/3 shipped and lost, ~1/3 never shipped) |
| 2026-10-24 | **Keep the 2017-trained model** as the saved artefact; document "refit on all recent data + monthly recalibration" as the production recipe | Refit ranks the top 1% better but over-predicts 2× after the Q1-2018 spike; recalibration can't be validated without touching the test set; Power BI page 2 stays consistent |
| 2026-10-24 | Excel built by Python driving Excel (pywin32 / COM); data pre-aggregated to additive counts | Real PivotTables, slicers and Data Tables, reproducible with one command; ratios rebuilt as sum ÷ sum so filters never average averages |
| 2026-10-24 | What-if default recovers 50% of the review gap; 100% shown only as an upper bound | The late-vs-on-time gap is observational; size the claim to the evidence |
| 2026-10-24 | **Free LLMs only, US$0, no credits** (owner's decision): `cohere/north-mini-code:free` (default) and `google/gemma-4-31b-it:free` (comparison) | Both answered a test SQL prompt correctly (1.9 s / 2.3 s); 4 other free models failed (rate-limited, empty answer, 403). Free tier is rate-limited, so: disk cache for every call, retry with backoff, small evaluation batches, several reviews per request for Module 2 labels |
| 2026-10-24 | Eval set stored as YAML (not JSONL as first planned) | Multi-line gold SQL stays readable and reviewable; expected results generated into JSON by running the gold SQL |
| 2026-10-24 | Semantic layer metrics carry an expression + table + filter, not full answer queries | Gives the LLM definitions without handing it the eval answers; tests run each metric and compare with Power BI |
| 2026-10-24 | Main ablation model = local `qwen2.5-coder:7b` (Ollama); hosted free models only for the final comparison | The 50-requests/day free cap made one step per day; local runs are unlimited and reproducible (pinned weights). north-mini-code baseline 45.7% kept as a logged data point |
| 2026-10-24 | Few-shot examples stored as YAML; retrieval with a local embedding model | Readable SQL; offline and free; tests forbid examples whose result equals any evaluation answer (prevents leakage) |
| 2026-10-24 | Numeric matching at the gold answer's precision (was ±0.05 / 0.01%) | The looser tolerance accepted wrong answers; all stored runs re-scored |

## Blockers / notes
- `ARCHITECTURE.md` artefact name changed: `models/late_delivery_model.pkl` (was `late_delivery_lgbm.pkl`) because logistic regression won.
- Global git identity on this PC is `sarkarmenssalon-creator`; first commit was authored as Masood Manzoor Ahmed via a per-commit override. Set a repo-local identity before the next commit.
- Power BI: no native DuckDB connector; plan is to export star-schema tables to Parquet on Day 4.
