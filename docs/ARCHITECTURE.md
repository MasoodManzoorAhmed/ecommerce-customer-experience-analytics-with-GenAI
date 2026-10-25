# Architecture Document

**Project:** E-commerce Customer Experience Analytics with ML & GenAI · **Version:** 1.0

## 1. High-level architecture

```text
                 ┌──────────────────────── Kaggle: olistbr/brazilian-ecommerce (9 CSVs) ───────────────────────┐
                 │                                                                                               │
                 ▼                                                                                               │
   scripts/download_data.py ──► data/raw/*.csv ──► scripts/build_db.py ──► data/olist.duckdb                     │
                                                                          │                                      │
                          sql/01_staging.sql  (types, English categories, geo dedup, review dedup)               │
                          sql/02_star_schema.sql (facts + dims)                                                  │
                          sql/04_business_queries.sql (BQ1–BQ6)                                                  │
                                                                          │                                      │
          ┌───────────────────────────┬───────────────────────────┬──────┴──────────────┬───────────────────────┐
          ▼                           ▼                           ▼                     ▼                       ▼
  notebooks/01_eda.ipynb   notebooks/02_late_delivery_model  powerbi/*.pbix     excel/Monthly_CX_Report   genai/
  (insights, stats tests)  src/features.py, src/train.py     (3 pages)          (pivots, what-if)         ├─ text_to_sql (Module 1)
                           ─► models/ + fact_order_risk                                                    └─ review_themes (Module 2)
                                          │                                                                    │
                                          └──────────────────────────► app/ (Streamlit) ◄──────────────────────┘
                                                                        KPIs · Risk · Ask the data · Review themes
                                                                        ─► Streamlit Community Cloud
```

## 2. Technology choices (with reasons)

| Layer | Choice | Why (the interview answer) |
|---|---|---|
| Database | **DuckDB** | In-process analytical SQL engine, zero setup, fast on columnar data, reads CSV/Parquet directly, ships easily with the app. (PostgreSQL would add a server without adding learning value here.) |
| Language | **Python 3.12** | Stable versions of LightGBM, SHAP and transformers are available (3.14 is too new for some packages) |
| Data | pandas, NumPy, pyarrow | Standard analytics stack |
| Visualisation | matplotlib (notebooks, results chart), Plotly (app, planned) | Static for notebooks, interactive for the app |
| ML | scikit-learn (pipelines, **logistic regression**: the selected model), LightGBM (compared), **SHAP** | Both compared on a time-based split; logistic regression won under drift (decision D2); SHAP for explanations |
| BI | **Power BI Desktop** | The most requested BI tool in the target markets |
| Spreadsheet | Excel | Managers' everyday tool |
| LLM access | OpenAI-compatible SDK: **OpenRouter free models** + a **local model via Ollama** (`qwen2.5-coder:7b`) | One client, interchangeable models; US$0; the local model has no request limit |
| SQL safety | **sqlglot** | Parses SQL to enforce SELECT-only and allowed tables |
| Embeddings | sentence-transformers (e.g. `all-MiniLM-L6-v2`; multilingual model for Portuguese reviews) | Free, local, fast |
| Fine-tuning | Hugging Face **transformers + PEFT (LoRA)**, datasets, accelerate; Colab/Kaggle GPU | Parameter-efficient training on a free GPU |
| App | **Streamlit** | Fast to build, free hosting |
| Quality | ruff, pytest, GitHub Actions | Lint + tests on every push |

## 3. Data model (DuckDB)

### 3.1 Raw → staging

| Raw file | Staging view | Key transformations |
|---|---|---|
| olist_orders_dataset | `stg_orders` | Parse the 5 timestamps; keep `order_status` |
| olist_order_items_dataset | `stg_order_items` | Types; `shipping_limit_date` timestamp |
| olist_customers_dataset | `stg_customers` | Keep **`customer_unique_id`** (the real person) |
| olist_order_payments_dataset | `stg_payments` | Types |
| olist_order_reviews_dataset | `stg_reviews` | **One review per order** (keep the latest); trim text; flag `has_comment` |
| olist_products_dataset | `stg_products` | Join English category names; fix the dataset's column typos (`product_name_lenght` → `product_name_length`) |
| olist_sellers_dataset | `stg_sellers` | Types |
| olist_geolocation_dataset | `stg_geolocation` | **One row per zip prefix** (average lat/lng) |
| product_category_name_translation | used in `stg_products` | Portuguese → English |

### 3.2 Star schema

| Table | Grain | Key columns |
|---|---|---|
| `fact_orders` | 1 row per order | order_id, customer_key, purchase_date_key, status, purchase_ts, approved_ts, estimated_delivery_ts, delivered_ts, **approval_hours**, **delivery_days**, **promised_days**, **is_late**, **delay_days**, order_value, freight_value, n_items, n_sellers, **payment_type_main** (payment method only; instalments excluded by design), review_score, has_comment, **dq_flags** (data-quality flags from the audit) |
| `fact_order_items` | 1 row per order item | order_id, item_id, product_key, seller_key, price, freight_value, shipping_limit_ts |
| `dim_customer` | 1 row per customer_unique_id | customer_key, customer_unique_id, city, state, lat, lng, first_purchase_date |
| `dim_seller` | 1 row per seller | seller_key, seller_id, city, state, lat, lng |
| `dim_product` | 1 row per product | product_key, product_id, category_en, weight_g, volume_cm3, photos_qty |
| `dim_date` | 1 row per day | date_key, date, year, quarter, month, month_name, week, weekday, is_weekend |
| `fact_order_risk` | 1 row per scored order | order_id, late_probability, risk_band, model_version, top_shap_features |
| `fact_review_theme` | 1 row per review with text | order_id, theme, confidence, method, model_version |

Definitions (also in `genai/semantic_layer.yaml`, so SQL, Power BI and the LLM use the same ones):
- **is_late** = delivered_ts > estimated_delivery_ts (delivered orders only)
- **delivery_days** = delivered_ts − purchase_ts (days)
- **promised_days** = estimated_delivery_ts − purchase_ts
- **revenue** = sum of item `price` (excluding freight), delivered orders only
- **repeat customer** = customer_unique_id with ≥ 2 distinct orders

## 4. ML design: late-delivery prediction

- **Population:** delivered orders with valid dates.
- **Target:** `is_late` (1/0). Expect class imbalance (roughly 1 in 10; measure the real figure in EDA).
- **Prediction moment:** order purchase/approval time. **Every feature must be known at that moment.**

| Allowed features (purchase time) | Forbidden (leakage) |
|---|---|
| promised_days, purchase month/weekday/hour, holiday-season flag | delivered_customer_date, delivered_carrier_date |
| seller–customer haversine distance, same_state flag, customer_state, seller_state | delay_days, delivery_days, is_late of the same order |
| price, freight_value, freight/price ratio, n_items, n_sellers | review_score, review text |
| **payment method** (e.g. boleto must be confirmed before approval, which can delay dispatch) | approval_hours (only known after approval; use it in EDA, not as a purchase-time feature) |
| product weight, volume, category | anything computed from future orders |
| **seller's historical late rate and order count, computed only from orders DELIVERED before this order's purchase** (rolling 90-day windows + all-time late rate) | |
| **platform context:** late rate of all orders delivered in the previous 30 days; 7-day vs 28-day order-volume ratio | |

- **Multi-seller orders:** use the primary seller (highest item value) for the seller features, plus `n_sellers`.
- **Split:** time-based (for example train ≤ 2017-12, validation 2018-01 to 2018-03, test 2018-04 onward; adjust after EDA to the actual date range).
- **Models:** logistic regression (scaled + one-hot) → LightGBM (`scale_pos_weight` or class weights). Tune on validation only. **Result (Day 3): logistic regression won** (valid PR-AUC 0.284 vs 0.213; test 0.094 vs 0.073) and is the production model.
- **Metrics:** PR-AUC (primary), ROC-AUC, recall at the chosen precision, confusion matrix at the threshold.
- **Threshold:** minimise expected cost = cost_FN × FN + cost_FP × FP (state the assumed costs).
- **Explainability:** SHAP (exact linear SHAP = coefficient × (value − training mean), cross-checked with `shap.LinearExplainer`): global importance and a per-order explanation in the app.
- **Artefacts:** `models/late_delivery_model.pkl` + `models/metadata.json` (features, threshold, metrics, training dates, version) + `models/order_risk_scores.parquet` (reloaded into `fact_order_risk` by `build_db.py`).

## 5. GenAI Module 1: "Ask the Data" (text-to-SQL)

### 5.1 Flow

```text
question ─► retrieve top-k similar solved examples (embeddings)        [step c]
         ─► build prompt: rules + schema + column descriptions [a] + semantic layer [b] + examples [c]
         ─► LLM ─► SQL ─► guardrails (sqlglot: SELECT-only, allowed tables, add LIMIT)
         ─► execute on READ-ONLY DuckDB connection (timeout)
              ├─ error ─► self-correction: send the error back to the LLM once  [d]
              └─ ok ─► result table + chart + the SQL shown to the user
```

### 5.2 Components (`genai/text_to_sql/`)
| File | Responsibility |
|---|---|
| `semantic_layer.yaml` (in `genai/`) | Business metric definitions shared with SQL and Power BI (step b); its `expected` test values are stripped before the prompt |
| `schema_descriptions.yaml` | Meaning, units and stored values of every column (step a) |
| `examples.yaml` | 28 solved question → SQL pairs for few-shot retrieval (step c); tests forbid any example whose result equals an evaluation answer |
| `retriever.py` | Embeds the examples (all-MiniLM-L6-v2, local) and returns the 3 most similar for a question |
| `guardrails.py` | sqlglot: one SELECT only, allowed tables only, no table functions, adds a LIMIT; execution on a read-only connection with file access off and a timeout |
| `llm_client.py` | OpenAI-compatible client (OpenRouter or local Ollama), temperature 0, disk cache, retry with backoff, pacing, stops on the free daily cap; records tokens and latency |
| `pipeline.py` | Builds the prompt for a configuration and runs `answer(question, client, config)`: SQL, result, error stage, tokens, latency; step d retries once with the error |
| `eval_set.py` | Loads and validates the evaluation set; runs the gold SQL into the expected results |
| `evaluate.py` | Runs the evaluation set for a configuration and model; **execution accuracy** (order- and column-name-insensitive, compared at the answer's precision); `--rescore` re-checks stored runs without LLM calls |
| `report.py` | Accuracy-per-step chart and summary table from the runs file |

### 5.3 Evaluation protocol
- `genai/eval/text_to_sql_eval.yaml`: 46 items `{id, question, gold_sql, difficulty, tags}` (YAML so multi-line SQL stays readable); the expected results are produced by running `gold_sql` (`python -m genai.text_to_sql.eval_set` → `genai/eval/text_to_sql_expected.json`). Tests check every gold query is a single SELECT on allowed tables, the stored results are in sync, and no ranking question has a tie at its cut-off.
- Configurations evaluated in order on one fixed model (local `qwen2.5-coder:7b`): baseline → +a → +a+b → +a+b+c → +a+b+c+d; then the best configuration on 2 hosted free models (`cohere/north-mini-code:free`, `google/gemma-4-31b-it:free`).
- Output: `genai/results/text_to_sql_runs.csv` (one row per question × configuration × model), `text_to_sql_summary.csv` and `accuracy_per_step.png` (`python -m genai.text_to_sql.report`); accuracy, mean latency and tokens per question (cost US$0).

## 6. GenAI Module 2 (required): review complaint themes

- **Taxonomy** (`genai/review_themes/taxonomy.yaml`): never_arrived · wrong_or_missing_item · damaged · late_delivery · product_quality · other, with definitions, Portuguese cues and a precedence order for reviews that mention several problems. The same file feeds the labelling guide, every LLM prompt and the app.
- **Data** (`sql/10_review_themes.sql`, `data.py`): 1-3 ★ reviews with a comment, title + comment as one text (14,375 review-order rows = 14,246 distinct reviews; a review can cover several orders). Gold set 200 (stratified by score × delivery situation, labelled by Claude, test only); train 1,500 from orders not in the gold set; seed 42.
- **Teacher labels** (`llm_labeler.py`): local `qwen2.5-coder:7b` labels the 1,500 training reviews, 20 per request, JSON reply; every reply cached; a parser that keeps each complete {id, theme} pair, so a cut-off reply loses only its tail.
- **Approaches** (all scored on the gold set by `evaluate.py`, macro-F1 primary):
  1. TF-IDF (word 1-2 grams + character 3-5 grams, accents stripped) + class-weighted logistic regression (`tfidf.py`).
  2. **BERTimbau** (`neuralmind/bert-base-portuguese-cased`, 110M) with **LoRA** (r=8 on query/value, 0.27% of weights trainable), class-weighted loss, 3 epochs on a laptop CPU (`lora.py`; the same script runs on a free Colab/Kaggle GPU).
  3. Zero-shot LLM with the taxonomy in the prompt (`llm_labeler.py gold`).
- **Result:** zero-shot LLM 0.781 > LoRA 0.714 > TF-IDF 0.697 macro-F1; speed 3.9 s vs 0.11 s vs 0.0006 s per review.
- **Production labelling** (`apply.py`): a **confidence cascade**: LoRA labels everything; reviews with top probability < 0.7 (38%) go to the LLM. Output → DuckDB `fact_review_theme` (review_id, order_id, theme, source) and `app/data/review_themes.parquet`. LoRA predictions are saved and LLM replies cached, so the run resumes after an interruption.
- **Label quality:** an independent second model (north-mini-code) labels the gold set; agreement with the gold labels is measured with Cohen's kappa (`evaluate.py agreement`).

## 7. Streamlit app (`app/`)

| Page | Content |
|---|---|
| Home / KPIs | Revenue, orders, on-time %, average review; late vs on-time review gap |
| Late-delivery risk | Inputs (state, seller, category, price, freight, promised days…) → probability, risk band, SHAP explanation |
| Ask the data | Question box → SQL (shown) + result table + auto chart; guardrail messages |
| Review themes | KPIs, theme shares, theme mix by delivery situation, example reviews, the three-approach comparison (filter by year and state) |

Deployment: Streamlit Community Cloud from GitHub (primary); a `Dockerfile` also runs the app anywhere (local, Cloud Run), and CI builds it on every push; the DuckDB file (or Parquet extracts) is included or built at start-up; the API key goes in Streamlit secrets.

## 8. Repository structure

```text
ecommerce-customer-experience-analytics/
├─ README.md · CLAUDE.md · requirements.txt · requirements.lock.txt · requirements-finetune.txt · pyproject.toml · .env.example · .gitignore
├─ docs/            PROJECT_REQUIREMENTS.md, GOALS.md, ARCHITECTURE.md, PROGRESS.md, DATA_QUALITY_REPORT.md, INTERVIEW_PREP.md, figures/
├─ data/            raw/ (git-ignored CSVs), olist.duckdb, powerbi/*.parquet (all git-ignored, rebuilt by scripts)
├─ scripts/         download_data.py, build_db.py, run_queries.py, export_powerbi.py, powerbi_expected_values.py, build_excel_report.py
├─ sql/             01_staging … 08_excel_report.sql (numbered, run in order), results/
├─ notebooks/       00_data_quality_audit.ipynb, 01_eda.ipynb, 02_late_delivery_model.ipynb
├─ src/             db.py, data_quality.py, stats.py, features.py, train.py, predict.py
├─ models/          late_delivery_model.pkl, metadata.json, order_risk_scores.parquet
├─ genai/           semantic_layer.yaml, text_to_sql/, eval/, results/, ollama/Modelfile, review_themes/ (Module 2)
├─ app/             Streamlit app (planned: streamlit_app.py, pages/)
├─ powerbi/         olist_cx_dashboard.pbix, measures.dax, DAX_MEASURES_NOTES.md, POWERBI_GUIDE.md, theme.json, expected_values.csv, screenshots/
├─ excel/           Monthly_CX_Report.xlsx
├─ tests/           SQL build, data quality, stats, features (leakage), training, text-to-SQL (eval set, semantic layer, guardrails, examples, self-correction)
└─ .github/workflows/ci.yml (planned, Day 7)
```

## 9. Configuration and secrets

`.env` (git-ignored) / Streamlit secrets:
```text
OPENROUTER_API_KEY=...
LLM_MODEL=...                # default small/cheap model
DUCKDB_PATH=data/olist.duckdb
```

## 10. Testing

- `test_features.py`: no forbidden columns in the feature set; seller history uses only earlier orders (temporal correctness).
- `test_guardrails.py`: rejects DROP/DELETE/UPDATE/INSERT, multi-statements, disallowed tables and file-reading table functions; adds a LIMIT; the execution connection cannot read files.
- `test_text_to_sql_eval.py`: result matching (order-insensitive, compared at the answer's precision), LLM cache, retries and the daily-cap stop.
- `test_eval_set.py`, `test_semantic_layer.py`, `test_schema_descriptions.py`, `test_examples.py`, `test_self_correction.py`: the evaluation set is valid and tie-free, the semantic layer equals the Power BI values, no test answer reaches the prompt, examples can't leak answers, the retry works.
- `test_sql_build.py`: a fresh database builds from the raw CSVs and every named query runs (skipped without the data).

## 11. Key design decisions (decision log)

| # | Decision | Alternatives | Reason |
|---|---|---|---|
| D1 | DuckDB | PostgreSQL, SQLite | Analytical speed, zero ops, portable |
| D2 | ~~LightGBM~~ **Logistic regression** for late delivery (revised Day 3) | LightGBM, deep learning, random forest | Planned LightGBM; under strong drift it early-stopped after a few trees and lost on validation and test. The linear model extrapolates and is exactly explainable |
| D3 | Evaluation-driven prompting for text-to-SQL, **no fine-tuning** | Fine-tune a small model for SQL | Errors come mostly from business definitions; a semantic layer + examples fix them more cheaply (to be confirmed by error analysis) |
| D4 | LoRA (BERTimbau) as the trained review-theme classifier, on CPU | Full fine-tuning, multilingual model, API-only | Few labels (1.5k) → PEFT trains 0.27% of weights, fits a laptop CPU in 21 min, small adapter; a Portuguese-specific BERT suits Portuguese reviews. Compared honestly: the zero-shot LLM scored higher (0.781 vs 0.714) |
| D5 | Time-based split | Random split | Prevents future leakage; mirrors deployment |
| D6 | Shared semantic layer | Separate definitions per tool | One definition of "late" and "revenue" across SQL, Power BI and the LLM |
| D7 | Confidence cascade (LoRA first, LLM below 0.7 confidence) for the final review labels | LLM only; LoRA only | LLM-level quality on the gold set while the LLM sees 38% of reviews (~7.6 h instead of ~20 h on the laptop); the threshold was scanned on the gold set, so it is reported as matching the LLM, not beating it |
