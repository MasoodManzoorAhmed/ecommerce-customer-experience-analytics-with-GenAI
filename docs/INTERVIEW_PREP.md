# Interview Prep: Likely Questions and Model Answers

A living document: add a section at the end of every work day. **Every number here comes from code that was run** (see the results log in `docs/PROGRESS.md` and the CSVs in `sql/results/`). Practise saying the answers out loud in your own words. Don't memorise them word for word.

**How to use it**
- 🟢 = asked in almost every interview · 🟡 = common follow-up · 🔴 = hard / senior-level probe
- The bold first sentence of each answer is the 10-second version. The rest is there if they dig.

**Contents:** 1. The pitch · 2. Dataset & business question · 3. Environment & reproducibility · 4. Loading the data · 5. Staging layer · 6. Star schema · 7. Business queries (SQL) · 8. Insights & recommendations · 9. Judgement & behavioural · 10. Coming next (questions to prepare later) · 11. Number cheat-sheet

---

## 1. The pitch

### 🟢 "Tell me about your project."
**I built an end-to-end analytics project on about 100,000 real orders from Olist, a Brazilian e-commerce marketplace, to answer one question: why do customers leave bad reviews, and can we predict and prevent late deliveries?**
I loaded 9 raw tables into DuckDB, built a cleaned staging layer and a star schema, and wrote 12 business analyses in SQL. The headline finding is that late orders average 2.27 stars against 4.29 for on-time orders, and only 3.0% of customers ever order again, so a late first delivery often loses that customer for good. Next I'm building a late-delivery prediction model, a Power BI dashboard, and two GenAI modules: a text-to-SQL assistant that I measure on an evaluation set, and a review-complaint classifier fine-tuned with LoRA.

### 🟡 "Why this project and not a Kaggle competition?"
**Competitions give you a clean table and a metric. Real analyst work starts with messy, related tables and a business question.**
Olist has 9 tables, duplicate reviews, Portuguese text, missing dates and impossible timelines. That lets me show data modelling, data-quality judgement, SQL, ML and GenAI on one realistic problem.

### 🟡 "Why e-commerce?"
**It's the same kind of problem the employers I'm targeting deal with every day: delivery performance, customer satisfaction and retention.** That applies to e-commerce, quick-commerce, retail and logistics companies in India, the UAE and Germany.

---

## 2. Dataset and business question

### 🟢 "Describe the data."
**Olist public data, 2016–2018: 99,441 orders, 112,650 order items, 96,096 unique customers, 3,095 sellers, 32,951 products, 99,224 reviews, and about 1 million geolocation rows.**
Usable purchase dates run from 2016-09-04 to 2018-10-17, but 2016 is very thin (267 delivered orders), so trend analysis uses 2017-01 to 2018-08.

### 🟢 "What's the difference between `customer_id` and `customer_unique_id`?"
**`customer_id` is created for every order; `customer_unique_id` is the actual person.** There are 99,441 customer_ids but only 96,096 people. Using `customer_id` would make every customer look like a one-time buyer and make repeat-purchase analysis meaningless. My customer dimension is built on `customer_unique_id`.

### 🟡 "Why did you frame payments only as payment method?"
**I analyse checkout behaviour: which method customers use and how it affects approval and delivery time.** That's an operations question. For example, boleto (a bank-slip payment) has a median approval time of 29.06 hours against 0.27 hours for cards. I deliberately leave out instalment fields. That's a scope decision, and the column is excluded in the staging SQL.

---

## 3. Environment and reproducibility

### 🟡 "How would someone reproduce your work?"
**Clone the repo, create a Python 3.12 virtual environment, install `requirements.txt`, then run three scripts: `download_data.py`, `build_db.py` and `run_queries.py`.**
The download uses Kaggle's public endpoint, so no API key is needed. The database is rebuilt from scratch on every run, which makes the build idempotent. Exact package versions are frozen in `requirements.lock.txt`.

### 🟡 "Why Python 3.12 and not the latest?"
**Compatibility. LightGBM, SHAP and PyTorch reliably publish ready-built packages for 3.12, and 3.14 was too new for some of them.** Choosing a version your whole stack supports is part of reproducibility.

### 🟢 "How do you handle secrets / API keys?"
**Keys live only in a `.env` file, which is git-ignored. `.env.example` documents the variable names, and the deployed app reads keys from Streamlit secrets.** I confirmed `.env`, the raw data and the database are ignored with `git check-ignore` before the first commit.

### 🟡 "Why DuckDB rather than PostgreSQL or SQLite?"
**DuckDB is an in-process analytical database. It needs no server, it's columnar so aggregations are fast, it reads CSV and Parquet directly, and it's a single file I can ship with the app.** PostgreSQL would add a server to manage without adding anything for this use case. SQLite is row-oriented and built for transactions, not analytics.

---

## 4. Loading the data

### 🟢 "Why did you load every raw column as text?"
**So nothing is silently changed on load. Every type conversion is explicit and reviewable in the staging SQL.**
The concrete example is Brazilian zip prefixes like `01037`. Automatic type detection would read that as the integer 1037, and joins to the geolocation table would break.

### 🟡 "How did you verify the load was correct?"
**I counted rows with two independent readers, DuckDB and pandas, and they matched for all 9 tables.** This matters for the reviews file, where 3,852 comments contain line breaks. A naive line count would give the wrong number of rows.

### 🟡 "What does idempotent mean, and why does it matter here?"
**Running it twice gives the same result as running it once.** `build_db.py` deletes and rebuilds the database, and `download_data.py` skips files that already exist. No step depends on hidden leftover state.

---

## 5. Staging layer (`sql/01_staging.sql`)

### 🟢 "What's the purpose of a staging layer?"
**One clean, typed view per source table, so every later step starts from the same trusted base.** Staging contains no business logic (no "late", no "revenue") and drops no rows. Business rules go in the star schema, where they're defined once.

### 🟡 "Why views and not tables for staging?"
**Views are always in sync with the raw data, use no extra storage, and keep the logic in one place.** The star schema, on the other hand, is stored as tables because Power BI and the ML model read it many times.

### 🟢 "The reviews table has duplicates. How did you handle them?"
**547 orders had more than one review. I keep the most recently answered one using `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY answered DESC, created DESC, review_id)`.**
The extra sort columns are tie-breakers so the result is the same on every run. I checked first that there were no ties on answer time. Result: 98,673 reviews, exactly one per order.

### 🟡 "Why `DECIMAL` for money instead of `DOUBLE`?"
**Decimal arithmetic is exact. Floating point builds up tiny errors (0.1 + 0.2 ≠ 0.3).** That's why my revenue reconciles to the cent: R$13,591,643.70 in three different tables.

### 🟡 "How did you deal with the geolocation table?"
**It has 1,000,163 rows but only 19,015 zip prefixes. Joining to it directly would multiply rows.** I reduced it to one row per zip by averaging latitude and longitude. First I removed 47 points that fall outside Brazil's bounding box so they couldn't pull a zip's centre abroad. 5 zips had only bad points and dropped out, leaving 19,010. I documented that side effect.

### 🟡 "Any other cleaning?"
- **Categories:** the translation file was missing 2 Portuguese categories, which I added explicitly. 610 products with no category became `'unknown'`.
- **Column typos** in the source (`product_name_lenght`) were renamed.
- **Review text:** line breaks replaced with spaces and text trimmed; empty or whitespace-only comments became NULL. That leaves 40,748 of 98,673 reviews with real text, which feeds the GenAI review classifier later.

---

## 6. Star schema (`sql/02_star_schema.sql`)

### 🟢 "What is a star schema and why use one?"
**Fact tables (events with measures, like orders and items) in the centre, joined to dimension tables (who, what, where, when).** It keeps queries simple and fast, it's the model Power BI is built for, and each business definition lives in one place.
Mine has `fact_orders` (99,441 rows, one per order), `fact_order_items` (112,650), `dim_customer` (96,096), `dim_seller` (3,095), `dim_product` (32,951) and `dim_date` (852 days).

### 🟢 "How do you define a late delivery?"
**An order is late if its delivered date is after the estimated delivery date, counting delivered orders only.** I compare *dates*, not timestamps, because the estimate is stored at midnight. A timestamp comparison would count a parcel delivered at 3 pm on the promised day as late. That choice changes the count from 7,826 to 6,534 late orders: 1,292 orders would otherwise be misclassified. The real late rate is **6.77%**.

### 🔴 "What's fan-out and how did you avoid it?"
**If you join a one-to-many table (items) to orders and then sum an order-level value, every order is repeated once per item and totals are inflated.** I aggregate items and payments to one row per order in CTEs *first*, then join. The proof is reconciliation: total item revenue is identical in staging, the items fact and the orders fact.

### 🟡 "Why surrogate keys?"
**Small integer keys join faster and compress better than 32-character hash ids, especially in Power BI.** I generate them with `ROW_NUMBER() OVER (ORDER BY natural_id)`, so they're the same on every rebuild.

### 🟡 "Some orders have no items. Why didn't you drop them?"
**Dropping hides problems. I keep all 99,441 orders with LEFT JOINs and label issues in a `dq_flags` column.**
Flags include 775 orders with no items, 768 with no review, 249 where payment total ≠ items + freight, 166 where carrier pickup is before purchase, 23 delivered before pickup, 8 "delivered" with no date, 6 cancelled but with a delivery date, and 1 with no payment. 97,467 orders are clean. Each analysis then chooses its filter explicitly, and the Day 2 audit sizes every issue.

### 🟡 "A customer ordered from different addresses. Which do you keep?"
**The address from their most recent order.** 39 people have addresses in more than one state. It's a small number, but the rule has to be stated and repeatable.

### 🟡 "Some orders were paid with two methods. How did you pick one?"
**The method with the largest amount; if amounts tie (188 orders), the earliest payment.** It's done in one line with `ARG_MAX(payment_type, (payment_value, -payment_sequential))`.

### 🔴 "How do you know your model is correct?"
**Three kinds of check: uniqueness (every key unique), completeness (row counts match staging: 99,441 orders and 112,650 items), and reconciliation (revenue matches to the cent across layers).** I also checked there are no orphans, meaning no fact row without a matching customer or date, and that `delay_days > 0` agrees with `is_late` for every delivered order.

---

## 7. Business queries (`sql/03_business_queries.sql`)

### 🟢 "Which SQL techniques did you use?"
**CTEs, window functions and aggregations, applied to real questions:**
- `LAG()` for month-on-month revenue growth (q01)
- `SUM() OVER ()` for % of total (q02)
- running totals `SUM() OVER (ORDER BY … ROWS UNBOUNDED PRECEDING)` for Pareto analysis (q03, q09)
- `GROUP BY ROLLUP` to add an overall row (q04)
- `HAVING` minimum volumes so small sellers don't dominate the "worst" lists (q05, q06)
- `COUNT(*) FILTER (WHERE …)` for conditional counts
- cohort retention (q11)

### 🟡 "Why the minimum-volume thresholds (100 orders per seller, 500 per category)?"
**Small samples give extreme rates. A seller with 2 orders and 1 late is "50% late" but that tells you nothing.** The threshold makes the ranking reflect performance, not noise.

### 🟡 "Why did you cut the monthly trend to 2017-01 to 2018-08?"
**2016 has only 267 delivered orders (November is missing entirely), and the last months of 2018 are cut off.** Including them produced meaningless figures like a +1,025,573% month-on-month jump. I documented why I trimmed rather than hiding it.

### 🔴 "Explain your cohort retention query."
**Each customer is assigned to the month of their first delivered order. Then I check whether they ordered again by the end of month +1, +3 and +6 after that.** I only include cohorts from 2017-01 to 2018-02, so every cohort has a full 6 months of observable data. Otherwise later cohorts would look worse just because less time had passed (this is called *right-censoring*).

### 🟡 "How do you make sure your SQL results are traceable?"
**A runner script executes each named query on a read-only connection and saves the output as a CSV in `sql/results/`.** Every number in my README points to a file produced by code. The read-only connection also means analysis can never modify the data.

---

## 8. Insights and recommendations

### 🟢 "What's your most important finding?"
**Late delivery is strongly linked to bad reviews: late orders average 2.27 stars against 4.29 on time, and 62.4% of late orders get 1–2 stars against 9.3% of on-time ones.**
The damage starts immediately. Just 1–3 days late drops the average to 3.29, and from 8 days late about 80% of reviews are 1–2 stars. (I'll add a statistical significance test in the EDA notebook.)

### 🟢 "So what should the business do?"
**Focus delivery improvements on geography and specific sellers, and warn customers in advance when a delay is likely.**
- On-time rates vary from 82.64% (Maranhão, MA) to 95.96% (Paraná, PR). Rio de Janeiro is the big-volume weak spot at 87.89% on 12,351 orders. Category barely matters: the worst categories are all between 91.9% and 92.7%.
- Seller problems exist even in the best-served state: 8 of the 10 worst sellers are in São Paulo.
- Only 3.0% of customers ever order twice, so the first delivery decides the relationship. That's why a purchase-time late-delivery model is worth building.

### 🟡 "Anything about payment methods?"
**Boleto orders take a median 29.06 hours to approve, against 0.27 hours for credit cards, and they're late more often (7.32% vs 6.69%).** Payment method is known at purchase time, so it's a valid feature for the late-delivery model. The approval time itself is only known afterwards, so I won't use it as a feature.

### 🟡 "How concentrated is the business?"
- **Sellers:** 533 of 2,970 sellers (17.9%) generate 80% of revenue, which is close to a textbook 80/20 split.
- **Geography:** São Paulo state alone is 38.3% of revenue.
- **Categories:** the top 7 of 74 categories make about half of revenue (49.9%).

### 🔴 "Correlation isn't causation. How do you know lateness *causes* bad reviews?"
**So far it's a strong association, not a proven cause.** Supporting evidence so far: a clear dose–response pattern (the later the delivery, the lower the score: 3.29 at 1–3 days late, about 80% 1–2 stars from 8 days late). In the EDA I'll check whether it holds within each state and add a significance test and other confounder checks, for example whether late orders are concentrated in certain categories. Module 2 will also show whether low-score reviews actually *mention* delivery problems in their text.

---

## 9. Judgement and behavioural

### 🟢 "Tell me about a time a data decision changed a result."
**(STAR)** *Situation:* defining "late delivery". *Task:* pick a definition the business would accept. *Action:* I noticed the estimated delivery date is stored at midnight, so comparing timestamps would count same-day deliveries as late. I measured both versions. *Result:* 6,534 vs 7,826 late orders, a difference of 1,292. I chose the date comparison, documented it in a decision log, and the same definition will be used in SQL, Power BI and the LLM's semantic layer.

### 🟡 "Tell me about a mistake you caught."
**I wrote "about 1%" in a code comment for multi-seller orders before measuring it.** I have a rule that every number must come from code that was run, so I went back and measured: 1,275 of 96,470 delivered orders, 1.32%. The estimate happened to be close, but unchecked numbers are how wrong figures end up in reports.

### 🟡 "One of your assumptions turned out to be wrong. What happened?"
**I expected roughly 1 in 10 orders to be late; the real rate is 6.77%.** That matters because class imbalance affects model training and metric choice, so it's measured, not assumed.

### 🟡 "How do you document decisions?"
**A decision log in `docs/PROGRESS.md`: date, decision, reason.** Examples: date-based lateness, keeping all orders with data-quality flags, the review de-duplication rule, the geolocation filter. If someone asks why a number is what it is, the answer is written down.

---

## 10. Coming next: questions to prepare later

Fill these in as each part is built, using real results only.

**Day 2: Data-quality audit and EDA**
- Walk me through your data-quality audit. What was the biggest issue?
- Which statistical test did you use for late vs on-time reviews, and why? (e.g. Mann-Whitney U, because review scores are ordinal and not normally distributed)
- What's a p-value? What's an effect size, and why report both?

**Day 3: Machine learning**
- What is data leakage? Give an example from your project.
- Why a time-based split instead of a random split?
- How did you compute seller history without leakage?
- Why PR-AUC instead of accuracy or ROC-AUC with a 6.77% positive rate?
- How did you choose the classification threshold? What costs did you assume?
- What does SHAP show, and what were the top features?
- Did LightGBM actually beat logistic regression? By how much?

**Day 4–5: Power BI and Excel**
- Explain a DAX measure you wrote. What's the difference between a calculated column and a measure?
- Why do you need a marked date table?
- How does your what-if sheet work?

**Days 5–6: GenAI Module 1 (text-to-SQL)**
- How did you evaluate the LLM? What is execution accuracy?
- Which improvement helped most: column descriptions, the semantic layer, few-shot examples or self-correction?
- How do you stop the LLM running `DROP TABLE`?
- How did you compare models on accuracy, cost and latency?
- Why didn't you fine-tune for text-to-SQL?

**Days 8–10: GenAI Module 2 (review themes)**
- What is LoRA and why use it instead of full fine-tuning?
- How did you create labels? How did you check the LLM's labels?
- Which approach won: TF-IDF, LoRA or zero-shot? Why do you think so?
- Why macro-F1?

**Packaging**
- What does your CI pipeline check?
- How is the app deployed, and how are secrets handled there?

---

## 11. Number cheat-sheet (verified)

| Fact | Value | Source |
|---|---|---|
| Orders / items / unique customers | 99,441 / 112,650 / 96,096 | `build_db.py`, star schema checks |
| Delivered orders | 96,470 | `fact_orders` |
| Late-delivery rate (date-based) | **6.77%** (6,534) | `fact_orders.is_late` |
| Same-day deliveries a timestamp rule would misclassify | 1,292 | ad-hoc check |
| Avg review late vs on-time | **2.27 vs 4.29** | `q07` |
| 1–2 star share late vs on-time | 62.4% vs 9.3% | `q07` |
| Avg review 1–3 days late | 3.29 | `q08` |
| On-time range across states | 82.64% (MA) to 95.96% (PR); overall 93.23% | `q04` |
| Repeat customers | 3.0% (2,801 of 93,350) | `q10` |
| Seller Pareto | 17.9% of sellers = 80% of revenue | `q09` |
| Boleto vs card median approval | 29.06 h vs 0.27 h | `q12` |
| SP share of revenue | 38.3% | `q02` |
| Item revenue (all statuses, excl. freight) | R$13,591,643.70 | reconciliation |
| Reviews with comment text | 40,748 of 98,673 | `stg_reviews` |
