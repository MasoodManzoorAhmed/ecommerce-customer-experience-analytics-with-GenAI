# Progress Tracker

Update this file at the end of every work session: tick tasks, record real numbers, note decisions and blockers.

## Status: Day 0 (project set up, nothing built yet)

### Day 0: Setup
- [x] Project folder + docs created (PRD, goals, architecture, README, start prompt)
- [ ] Python 3.12 installed; `.venv` created; `pip install -r requirements.txt`
- [ ] Git repo initialised, first commit, GitHub repo created (`ecommerce-customer-experience-analytics`)
- [ ] Kaggle account + dataset downloaded to `data/raw/`
- [ ] `.env` created from `.env.example` (OpenRouter or Gemini key); **confirm `.env` is git-ignored**

### Day 1: SQL
- [ ] `scripts/build_db.py` loads 9 CSVs into `data/olist.duckdb`
- [ ] `sql/01_staging.sql`
- [ ] `sql/02_star_schema.sql`
- [ ] `sql/03_business_queries.sql` (10–12 queries + one-line insights)

### Day 2: Data-quality audit + EDA
- [ ] `notebooks/00_data_quality_audit.ipynb` + `docs/DATA_QUALITY_REPORT.md` (each issue: size, fix, reason)
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

## Decisions log

| Date | Decision | Reason |
|---|---|---|

## Blockers / notes
