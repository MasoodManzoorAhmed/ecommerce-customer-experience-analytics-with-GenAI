# Project Requirements Document (PRD)

**Project:** E-commerce Customer Experience Analytics with ML & GenAI
**Owner:** Masood Manzoor Ahmed
**Version:** 1.0 · **Status:** Not started · **Target duration:** 10 days (all modules required)

---

## 1. Overview

An end-to-end analytics project on about 100,000 real orders from Olist, a Brazilian e-commerce marketplace (2016–2018). It answers one business question:

> **"Why do customers leave bad reviews, and can we predict and prevent late deliveries?"**

The project shows the full Data Analyst + Data Scientist + GenAI skill set: SQL data modelling, Python analysis, Power BI, Excel, a machine-learning model, and two GenAI modules (an evaluated text-to-SQL assistant, and LoRA fine-tuning compared against baselines), delivered as a deployed app with documentation and a demo video.

## 2. Problem Statement

A marketplace's reputation depends on customer reviews. Bad reviews reduce repeat purchases and seller trust. The business needs to know:

- **What drives low review scores**, and in particular how much late delivery contributes.
- **Which states, sellers and categories** perform worst on delivery and satisfaction.
- **Whether late deliveries can be predicted at purchase time**, so customers can be warned in advance or orders prioritised.
- **What unhappy customers actually complain about**, at scale, from free-text reviews.
- How non-technical managers can **get answers without writing SQL**.

## 3. Target Users (Personas)

| Persona | Needs | Served by |
|---|---|---|
| **Operations manager** | On-time performance by state and seller; at-risk orders | Power BI page 2, risk model, app |
| **Customer experience (CX) lead** | Review drivers, complaint themes | EDA insights, Module 2 themes, Power BI |
| **Category / seller manager** | Top and bottom sellers and categories, Pareto split | Power BI page 3, SQL analyses |
| **Executive** | Monthly KPIs and trends | Power BI page 1, Excel monthly report |
| **Non-technical business user** | Ask ad-hoc questions in plain English | GenAI Module 1 ("Ask the data") |

## 4. Scope

### In scope
- Olist public dataset (9 CSV tables) loaded into DuckDB.
- Star-schema data model and 10–12 business SQL analyses.
- EDA with 5 written business insights.
- A late-delivery classification model (purchase-time features only).
- A 3-page Power BI dashboard.
- An Excel monthly management report with a what-if sheet.
- GenAI Module 1: text-to-SQL assistant with an evaluation set, step-by-step improvement and guardrails.
- GenAI Module 2 (required): review complaint-theme classification comparing TF-IDF, a LoRA-tuned transformer and a zero-shot LLM.
- A written data-quality audit (every issue found, its size, the fix and the reason).
- Docker image + GitHub Actions CI.
- Streamlit app, deployed publicly.
- README, demo video, résumé bullets.

### Out of scope
- Real-time streaming or production data pipelines.
- Deep-learning time-series models (already covered by the Predictive Maintenance project).
- Recommendation systems and price optimisation.
- Any non-public or personal data.

## 5. Business Questions (Must Be Answered)

| # | Question | Method |
|---|---|---|
| BQ1 | How have orders and revenue developed by month, state and category? | SQL + Power BI |
| BQ2 | What is the on-time delivery rate, and which states, sellers and categories are worst? | SQL + Power BI |
| BQ3 | How much do late deliveries reduce review scores? | SQL + EDA (statistical test) |
| BQ4 | Who are the top sellers and categories, and what is the Pareto (80/20) split? | SQL (window functions) |
| BQ5 | What share of customers buy again, and what does cohort retention look like? | SQL (cohorts) |
| BQ6 | Which payment methods do customers use, and how do they relate to order value, approval time and delivery time? | SQL + Power BI |
| BQ7 | Can we predict late delivery at purchase time? | ML (LightGBM) |
| BQ8 | What do unhappy customers complain about? | GenAI Module 2 |

## 6. Functional Requirements

### FR-1 Data and SQL
- FR-1.1 Download the 9 Olist CSVs into `data/raw/` with a reproducible script (Kaggle API) or manually; raw data is git-ignored.
- FR-1.2 Load them into a DuckDB database file `data/olist.duckdb`.
- FR-1.3 Staging layer: correct types (timestamps), English category names, de-duplicated geolocation (one lat/long per zip prefix), cleaned text.
- FR-1.4 Star schema: `fact_orders`, `fact_order_items`, `dim_customer`, `dim_seller`, `dim_product`, `dim_date`.
- FR-1.5 10–12 business queries in `sql/04_business_queries.sql`, each with a comment stating the question and a one-line insight.

### FR-2 Data-quality audit and exploratory analysis
- FR-2.0 Notebook `notebooks/00_data_quality_audit.ipynb` + `docs/DATA_QUALITY_REPORT.md`: for every table, missing values, duplicates (e.g. non-unique review_id), impossible date sequences, multi-seller orders, Portuguese categories, geolocation duplicates, column-name typos. For each issue: size (count/%), the decision (fix, drop, flag, keep) and the reason.
- FR-2.1 Notebook `notebooks/01_eda.ipynb`: data quality checks, delivery-delay distribution, late vs on-time review scores with a statistical test, state and seasonality analysis.
- FR-2.2 Five written business insights with numbers, at the top of the notebook and in the README.

### FR-3 Machine learning: late-delivery prediction
- FR-3.1 Target: `is_late = delivered_customer_date > estimated_delivery_date`, for delivered orders only.
- FR-3.2 Features available **at purchase time only**; no post-purchase information (see the architecture document).
- FR-3.3 Time-based train/validation/test split.
- FR-3.4 Baseline (logistic regression) plus LightGBM; metrics PR-AUC, recall at the chosen precision; threshold chosen from a stated business cost.
- FR-3.5 SHAP global and local explanations.
- FR-3.6 Scores written to the `fact_order_risk` table; the model and preprocessing saved to `models/`.

### FR-4 Power BI dashboard
- FR-4.1 Three pages: Executive overview · Delivery & satisfaction · Sellers & categories (with drill-through).
- FR-4.2 A marked date table; 8–10 explicit DAX measures (Revenue, Orders, AOV, On-time %, Avg review, MoM %, YoY %, Rank, % of total).
- FR-4.3 Includes model risk scores and (after Module 2) complaint themes.
- FR-4.4 `.pbix` plus PNG screenshots committed to `powerbi/`.

### FR-5 Excel report
- FR-5.1 `excel/Monthly_CX_Report.xlsx`: data sheet, PivotTables (revenue by month × category; on-time % by state), PivotCharts, a slicer, XLOOKUP/SUMIFS KPI cells, conditional formatting.
- FR-5.2 A what-if sheet: the estimated impact on average review score if the on-time rate improves.

### FR-6 GenAI Module 1: "Ask the Data" (text-to-SQL)
- FR-6.1 An evaluation set of at least 40 questions with verified SQL and expected results (`genai/eval/text_to_sql_eval.jsonl`).
- FR-6.2 A baseline prompt (schema only) measured on **execution accuracy**.
- FR-6.3 Improvements added one at a time and each measured: (a) column descriptions, (b) a semantic layer (`genai/semantic_layer.yaml`), (c) dynamic few-shot retrieval, (d) a self-correction retry.
- FR-6.4 Guardrails: SELECT-only (parsed with sqlglot), allowed-tables list, automatic LIMIT, read-only connection, timeout.
- FR-6.5 Compare at least 2 LLMs on accuracy, response time and tokens per query (both are free models, so cost per query is US$0; tokens show what it would cost on a paid tier).
- FR-6.6 Results table + chart ("accuracy per step") in the README.

### FR-7 Streamlit app
- FR-7.1 Pages: KPIs · Late-delivery risk (input → probability + SHAP explanation) · Ask the data (shows the SQL + result + chart) · Review themes.
- FR-7.2 Deployed on Streamlit Community Cloud (or Docker + Cloud Run); secrets via platform secrets, not code.

### FR-8 GenAI Module 2: review complaint themes (required)
- FR-8.1 A theme taxonomy: late delivery · wrong/missing item · product quality · damaged · never arrived · other.
- FR-8.2 A gold test set: about 200 reviews labelled manually by the owner (test only).
- FR-8.3 Training set: about 1,500 reviews labelled by an LLM, spot-checked; split by order with no overlap with the gold set.
- FR-8.4 Compare TF-IDF + logistic regression, a LoRA-tuned multilingual transformer, and a zero-shot LLM on macro-F1, cost and speed.
- FR-8.5 Classify all reviews that have text using the chosen approach; results to the `fact_review_theme` table, Power BI and the app.
- FR-8.6 The result is reported honestly, whichever approach wins.

### FR-9 Packaging and delivery
- FR-9.1 GitHub Actions CI running ruff + pytest (required). A `Dockerfile` that runs the Streamlit app, plus a Docker build step in CI (**nice-to-have, about 1–2 hours, the first item to cut**: Streamlit Community Cloud deployment doesn't need Docker).
- FR-9.2 README with results, screenshots, the data-quality summary and a demo video link.

## 7. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 Security | No API keys or secrets in the repo; `.env` is git-ignored; `.env.example` documents the variables. The LLM can only run read-only SELECT queries. |
| NFR-2 Reproducibility | Python 3.12 virtual environment, pinned `requirements.txt`, fixed random seeds, scripts that rebuild the database from the raw CSVs. |
| NFR-3 Correctness | No data leakage (time-based split, purchase-time features, fitting preprocessing on training data only). **All numbers in the docs and README come from actual runs, never invented.** |
| NFR-4 Cost | **US$0: free OpenRouter models only** (`cohere/north-mini-code:free`, `google/gemma-4-31b-it:free`); every response cached on disk; retries with backoff; evaluations run in batches to respect free-tier rate limits. |
| NFR-5 Performance | App pages load in < 3 s; text-to-SQL answers in < 10 s. |
| NFR-6 Code quality | Ruff lint clean; pytest tests for feature building, SQL guardrails and the evaluation harness; GitHub Actions CI. |
| NFR-7 Documentation | README with problem, architecture, results, how to run, screenshots, and dataset credit. |
| NFR-8 Platform | Developed on Windows; paths with no spaces; works on Linux for deployment. |

## 8. Data Requirements

- Source: Kaggle `olistbr/brazilian-ecommerce` (public; check and credit the licence).
- Files: `olist_orders_dataset.csv`, `olist_order_items_dataset.csv`, `olist_customers_dataset.csv`, `olist_order_payments_dataset.csv`, `olist_order_reviews_dataset.csv`, `olist_products_dataset.csv`, `olist_sellers_dataset.csv`, `olist_geolocation_dataset.csv`, `product_category_name_translation.csv`.
- Known issues: `customer_id` is per order (use `customer_unique_id`); Portuguese review text, often empty; non-unique `review_id`; ~1.4% of orders with illogical date sequences; duplicate geolocation zip prefixes; some orders are not delivered or cancelled.
- Payments: only `payment_type` (payment method) is analysed. Instalment fields are deliberately excluded from the analysis by owner choice.

## 9. Success Metrics / Acceptance Criteria

| Area | Acceptance criterion |
|---|---|
| SQL | 10–12 queries run cleanly from a fresh database build |
| EDA | 5 insights with numbers; late vs on-time review gap quantified with a statistical test |
| ML | PR-AUC reported on a time-based test set, better than the baseline; threshold justified; SHAP plots |
| Power BI | 3 pages, a working drill-through, measures documented |
| Excel | Pivots and what-if sheet working |
| Module 1 | ≥ 40-question evaluation set; accuracy per improvement step reported; guardrail tests pass |
| App | Publicly accessible URL |
| Module 2 | Macro-F1 for all three approaches on the gold set; the chosen approach applied to all reviews |
| Portfolio | README complete, 3-minute demo video, résumé bullets with real numbers |

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Data leakage in the ML model | Strict purchase-time feature list; time-based split; seller history computed from earlier orders only |
| LLM writes harmful or incorrect SQL | sqlglot SELECT-only validation, allowed-tables list, read-only connection, LIMIT, evaluation set |
| API cost overrun | Small models, caching, capped label volume |
| Power BI Service needs a work account | Commit the `.pbix` + screenshots; show it in the video |
| Free GPU limits for LoRA | Small multilingual model, QLoRA/Unsloth on Colab/Kaggle; reduce label volume if needed (Module 2 stays in scope) |
| Scope creep | Fixed 10-day plan; cutting order: Docker (nice-to-have) → Excel what-if sheet → app polish → Module 2 label volume (never drop the audit, SQL, model, Module 1 evaluation or Module 2) |

## 11. Milestones

| Day | Milestone |
|---|---|
| 1 | Environment + DuckDB star schema + SQL analyses |
| 2 | Data-quality audit + EDA + 5 insights |
| 3 | Late-delivery model + SHAP + risk table |
| 4 | Power BI dashboard |
| 5 | Excel report + Module 1 evaluation set & baseline |
| 6 | Module 1 improvements + guardrails + Streamlit app deployed |
| 7 | Dockerfile + CI, README draft, résumé, first job applications |
| 8–10 | Module 2 (labels → baselines → LoRA → apply to all reviews) · final README, demo video, LinkedIn post |

## 12. Deliverables Checklist

- [ ] `data/olist.duckdb` builds from the raw CSVs via a script
- [ ] `sql/` staging, star schema, business queries
- [ ] `notebooks/00_data_quality_audit.ipynb` + `docs/DATA_QUALITY_REPORT.md`
- [ ] `notebooks/01_eda.ipynb`, `notebooks/02_late_delivery_model.ipynb`
- [ ] `models/` saved model + metadata
- [ ] `powerbi/` .pbix + screenshots
- [ ] `excel/Monthly_CX_Report.xlsx`
- [ ] `genai/` semantic layer, evaluation set, text-to-SQL module, results
- [ ] `app/` Streamlit app (deployed URL)
- [ ] `genai/review_themes/` Module 2 notebooks + results
- [ ] `tests/` + CI workflow + `Dockerfile`
- [ ] README with results, screenshots, demo video link
