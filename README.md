# E-commerce Customer Experience Analytics with ML & GenAI

> **Why do customers leave bad reviews, and can we predict and prevent late deliveries?**
> An end-to-end analysis of ~100,000 real e-commerce orders using **SQL, Python, Power BI, Excel, machine learning and GenAI**.

`SQL (DuckDB)` · `Python` · `pandas` · `Power BI` · `Excel` · `LightGBM` · `SHAP` · `LLM text-to-SQL` · `LoRA / PEFT` · `Streamlit`

**Status:** 🚧 In progress. See [docs/PROGRESS.md](docs/PROGRESS.md)

---

## Key Results

*(Filled in from actual runs; every number is traceable to a notebook or script.)*

| Area | Result |
|---|---|
| Late deliveries vs reviews | Late orders average **_ ★** vs **_ ★** for on-time orders |
| Worst delivery performance | _ |
| Late-delivery model | PR-AUC **_** (baseline _), flags **_%** of late orders at **_%** precision |
| "Ask the data" assistant | Execution accuracy **_% → _%** across improvement steps (40-question benchmark) |
| Review complaint themes | Macro-F1: TF-IDF _ · LoRA _ · zero-shot LLM _ |
| Recommendation | _ |

## What's Inside

| Component | Description |
|---|---|
| **Data-quality audit** | Every issue in the raw data (missing values, duplicate review IDs, impossible date sequences, multi-seller orders, Portuguese categories, duplicate geolocation) sized, fixed and justified. See [docs/DATA_QUALITY_REPORT.md](docs/DATA_QUALITY_REPORT.md) |
| **SQL data model** | DuckDB star schema (orders, items, customers, sellers, products, dates) + 12 business analyses: cohorts, Pareto, window functions |
| **EDA** | Data quality, delivery delays, late vs on-time reviews (statistical test), state and seasonality patterns |
| **Late-delivery model** | Purchase-time features only (no leakage), time-based split, logistic regression vs LightGBM, cost-based threshold, SHAP |
| **Power BI dashboard** | Executive overview · Delivery & satisfaction · Sellers & categories |
| **Excel report** | Monthly management report with PivotTables, slicers and a what-if sheet |
| **GenAI 1: Ask the data** | Natural-language questions → safe, read-only SQL; improved step by step (descriptions, semantic layer, few-shot retrieval, self-correction) and measured on a benchmark |
| **GenAI 2: Review themes** | Complaint-theme classification of Portuguese reviews: TF-IDF vs LoRA-tuned transformer vs zero-shot LLM |
| **Streamlit app** | KPIs, late-delivery risk, Ask the data, review themes |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```text
Olist CSVs → DuckDB (staging → star schema → SQL analyses)
   → EDA · LightGBM late-delivery model · Power BI · Excel
   → GenAI: text-to-SQL assistant (evaluated) · review-theme classifier (LoRA vs baselines)
   → Streamlit app (deployed)
```

## Screenshots

*(Power BI pages, app pages and the accuracy-per-step chart go here.)*

## Run It Locally

```bash
# 1. Python 3.12 virtual environment
py -3.12 -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# 2. Data: download the Olist dataset from Kaggle into data/raw/
python scripts/download_data.py   # or download manually (see below)

# 3. Build the DuckDB database
python scripts/build_db.py

# 4. Configure the LLM key (copy and edit)
copy .env.example .env

# 5. Run the app
streamlit run app/streamlit_app.py
```

## Project Structure

```text
docs/  sql/  scripts/  notebooks/  src/  models/  genai/  app/  powerbi/  excel/  tests/
```

## Documentation

- [Project Requirements](docs/PROJECT_REQUIREMENTS.md)
- [Goals](docs/GOALS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Progress](docs/PROGRESS.md)

## Dataset and Credits

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle). Real, anonymised commercial data from 2016–2018. Used for non-commercial portfolio purposes; see the dataset page for licence terms.

## Author

**Masood Manzoor Ahmed**: MSc Data Science (University of Greenwich)
[LinkedIn](https://www.linkedin.com/in/masoodmanzoorahmed) · [GitHub](https://github.com/MasoodManzoorAhmed)
