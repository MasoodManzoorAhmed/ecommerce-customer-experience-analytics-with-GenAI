# CLAUDE.md: Instructions for the AI Assistant

## Project
**E-commerce Customer Experience Analytics with ML & GenAI**: an end-to-end portfolio project on the Olist Brazilian e-commerce dataset (Kaggle `olistbr/brazilian-ecommerce`, ~100k orders, 9 tables).
Business question: *"Why do customers leave bad reviews, and can we predict and prevent late deliveries?"*

**Read these before doing anything** (they are the source of truth):
- `docs/PROGRESS.md`: what's done, what's next, real results logged so far
- `docs/PROJECT_REQUIREMENTS.md`: scope, functional requirements (FR-1…FR-9), acceptance criteria
- `docs/ARCHITECTURE.md`: data model, ML design, GenAI module design, repo structure, decision log
- `docs/GOALS.md` (local only, not published): why the project exists, measurable targets, interview stories

## About the owner
- Masood: MSc Data Science (Greenwich). Targeting **Data Analyst (with GenAI)** and **Data Scientist** roles in India, UAE, Saudi Arabia, the UK and Germany, in **non-banking sectors**.
- **This is the only project on the résumé.** It must be interview-proof: the owner must be able to explain every line and decision.
- **Teach while building:** before each step, briefly explain *what* we're doing and *why*. After writing code, explain it block by block in plain language, including the likely interview questions about it.
- Keep explanations clear and simple; define every new term.

## Non-negotiable rules
1. **Never invent numbers.** Every metric or insight in the README/docs must come from code that was actually run. Log results in `docs/PROGRESS.md` with their source.
2. **No data leakage:** ML features must be known at purchase time (see ARCHITECTURE §4); time-based split; seller history from earlier orders only; preprocessing fitted on training data only.
3. **No secrets in the repo:** API keys only in `.env` (git-ignored) or Streamlit secrets. Check `.gitignore` before the first commit.
4. **Payments:** analyse `payment_type` (payment method) only. **Do not analyse instalments, credit or interest.** Frame payment work as "checkout behaviour / payment approval time".
5. **Do not suggest banking, lending or credit-risk examples, datasets or employers.**
6. **Honest comparisons:** in Module 1 and Module 2, report whichever approach actually wins.
7. **Run and verify:** execute the code, check outputs and row counts, and fix errors before moving on. Don't claim something works without running it.
8. **Scope discipline:** follow the 10-day plan. Cutting order if behind: Docker → Excel what-if sheet → app polish → Module 2 label volume. Never cut the data-quality audit, SQL, ML, Module 1 evaluation or Module 2.

## Environment
- Windows 11; shell: PowerShell or Git Bash. **Python 3.12** in `.venv` (Python 3.14 is also installed but too new for some packages; always use the venv).
- Project path: `D:\ecommerce-customer-experience-analytics` (no spaces in the path).
- Database: DuckDB file `data/olist.duckdb`; raw CSVs in `data/raw/` (both git-ignored).
- LLM: OpenAI-compatible client via OpenRouter; key in `.env` as `OPENROUTER_API_KEY`. **Free models only, US$0 spend, no credits (owner's decision, 2026-10-24):** default `cohere/north-mini-code:free`, comparison model `google/gemma-4-31b-it:free`. Free models are rate-limited (busy periods + a daily request cap without credits): cache every response, retry with backoff, run evaluations in small batches, and batch many items per request for Module 2 labelling.
- Module 2 fine-tuning runs on **Google Colab / Kaggle free GPU** using `requirements-finetune.txt`.

## Conventions
- SQL in `sql/` files (numbered), executed by scripts, not hard-coded in notebooks.
- Reusable Python in `src/` and `genai/`; notebooks call those functions.
- Business definitions (on-time, revenue, repeat customer) live in `genai/semantic_layer.yaml` and must match the SQL and Power BI.
- Ruff-clean code; tests in `tests/`; type hints and short docstrings.
- Fixed random seed = 42.
- At the **end of every session**: update `docs/PROGRESS.md` (tick tasks, log real results, decisions, next step).
