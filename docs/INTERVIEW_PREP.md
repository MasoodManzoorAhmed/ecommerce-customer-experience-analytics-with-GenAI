# Interview Prep: Likely Questions and Model Answers

A living document: add a section at the end of every work day. **Every number here comes from code that was run** (see the results log in `docs/PROGRESS.md` and the CSVs in `sql/results/`). Practise saying the answers out loud in your own words. Don't memorise them word for word.

**How to use it**
- 🟢 = asked in almost every interview · 🟡 = common follow-up · 🔴 = hard / senior-level probe
- The bold first sentence of each answer is the 10-second version. The rest is there if they dig.

**Contents:** 1. The pitch · 2. Dataset & business question · 3. Environment & reproducibility · 4. Loading the data · 5. Staging layer · 6. Star schema · 7. Business queries (SQL) · 8. Insights & recommendations · 9. Judgement & behavioural · 9b. Data-quality audit · 9c. EDA & statistics · 9d. ML model · 9e. Power BI · 10. Coming next (questions to prepare later) · 11. Number cheat-sheet

---

## 1. The pitch

### 🟢 "Tell me about your project."
**I built an end-to-end analytics project on about 100,000 real orders from Olist, a Brazilian e-commerce marketplace, to answer one question: why do customers leave bad reviews, and can we predict and prevent late deliveries?**
I loaded 9 raw tables into DuckDB, built a cleaned staging layer and a star schema, and wrote 12 business analyses in SQL. The headline finding is that late orders average 2.27 stars against 4.29 for on-time orders, and only 3.0% of customers ever order again, so a late first delivery often loses that customer for good. I built a leakage-free late-delivery model where, under heavy drift, logistic regression beat LightGBM (test PR-AUC 0.094 vs 0.073, about 2× better than random). Next come a Power BI dashboard and two GenAI modules: a text-to-SQL assistant that I measure on an evaluation set, and a review-complaint classifier fine-tuned with LoRA.

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

### 🟢 "Show me where you first looked at the data."
**Section 0 of the data-quality audit notebook.** It lists the 9 tables (1,550,922 rows, 52 columns in total), profiles every column (an example value, number of distinct values, % missing), and shows sample rows from each table. The distinct counts are where the first problems show up: `customer_unique_id` has fewer values than `customer_id`, and `review_id` has fewer values than review rows.

### 🟡 "How do you know your SQL still works after a change?"
**An automated fresh-build test.** It rebuilds the whole database from the raw CSVs into a temporary file and runs every named query in the audit, business, EDA and feature files, failing if any query errors or returns nothing. It also caught a real issue during development: two "top 10" rankings changed between runs because of ties at the cut-off. I fixed that with tie-breakers, and three consecutive runs now give identical results.

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

## 7. Business queries (`sql/04_business_queries.sql`)

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

### 🟡 "Why does your worst-sellers table only show sellers with 100+ orders?"
**A seller with 3 orders and 1 late one shows 67% on-time, but that's luck, not a pattern.** 100 is the same threshold as SQL query q05 (worst sellers) and the `Worst Sellers Headline` measure, so the SQL, the table and the insight card all agree. 210 sellers meet it. In Power BI it's a visual-level filter on `Item-level Orders` ≥ 100.

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
The damage starts immediately. Just 1–3 days late drops the average to 3.29, and from 8 days late about 80% of reviews are 1–2 stars. Mann-Whitney U confirms it: p < 1e-300, rank-biserial r = −0.64 (large), mean gap −2.02★ with 95% CI [−2.06, −1.98].

### 🟢 "So what should the business do?"
**Focus delivery improvements on geography and specific sellers, and warn customers in advance when a delay is likely.**
- On-time rates vary from 82.64% (Maranhão, MA) to 95.96% (Paraná, PR). Rio de Janeiro is the big-volume weak spot at 87.89% on 12,351 orders. Category barely matters: the worst categories are all between 91.9% and 92.7%.
- Seller problems exist even in the best-served state: 8 of the 10 worst sellers are in São Paulo.
- Only 3.0% of customers ever order twice, so the first delivery decides the relationship. That's why I built a purchase-time late-delivery model; its top-1% riskiest orders are late 3.2× more often than average.

### 🟡 "Anything about payment methods?"
**Boleto orders take a median 29.06 hours to approve, against 0.27 hours for credit cards, and they're late more often (7.32% vs 6.69%).** Payment method is known at purchase time, so it's a valid feature for the late-delivery model. The approval time itself is only known afterwards, so I won't use it as a feature.

### 🟡 "How concentrated is the business?"
- **Sellers:** 533 of 2,970 sellers (17.9%) generate 80% of revenue, which is close to a textbook 80/20 split.
- **Geography:** São Paulo state alone is 38.3% of revenue.
- **Categories:** the top 7 of 74 categories make about half of revenue (49.9%).

### 🔴 "Correlation isn't causation. How do you know lateness *causes* bad reviews?"
**So far it's a strong association, not a proven cause.** Supporting evidence so far: a clear dose–response pattern (the later the delivery, the lower the score: 3.29 at 1–3 days late, about 80% 1–2 stars from 8 days late). In the EDA I checked the obvious confounder: within every one of 21 states, late orders score 1.63–2.62★ lower, so geography doesn't explain it away. Category was ruled out as a major driver on Day 1 (on-time rates barely vary by category). Module 2 will also show whether low-score reviews actually *mention* delivery problems in their text.

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

## 9b. Data-quality audit (Day 2)

### 🟢 "Walk me through your data-quality audit."
**I wrote 45 checks across all 9 tables. Each records the issue's size (count and %), a decision (fix, flag, keep or out of scope) and the action taken.**
The checks are SQL in `sql/03_data_quality_checks.sql`, with the decision written as metadata next to each query, so the measurement and the decision live together. A Python function runs them all and builds the audit table, and a unit test fails if any check is missing its decision. The result: 12 fixed, 17 flagged, 15 kept, 1 out of scope.

### 🟢 "What was the most important issue you found?"
**Identity. `customer_id` is created per order, so 99,441 ids represent only 96,096 real people.** Counting by `customer_id` makes everyone look like a one-time buyer and the repeat-customer rate meaningless. Close behind: duplicate reviews per order (547 orders) and a non-unique `review_id` (1,603 rows), which would double-count reviews.

### 🟡 "How did you decide whether to fix, flag or drop?"
**My rule: fix it if the correction is unambiguous, flag it if it's a genuine anomaly I can't correct, keep it if it's real behaviour, and never silently drop.**
Examples: a typo in a column name → fix. A carrier pickup before purchase (166 orders) → flag, because I can't know the true time. Free shipping (383 items) → keep, it's a genuine offer. I didn't drop a single order: 97,467 of 99,441 (98.01%) are clean, and the rest carry labels in `dq_flags`.

### 🔴 "How do you know your cleaning decisions didn't bias the results?"
**I ran a sensitivity check: the late rate is 6.77% across all 96,470 delivered orders and 6.67% across the 95,392 with no flags.** The headline metric barely moves, so keeping flagged orders doesn't distort it. I'll repeat this check for the model.

### 🟡 "Missing values: how did you handle them?"
**First I asked *why* they're missing.** Missing delivery dates line up with order status: shipped, cancelled and unavailable orders haven't been delivered, so that's expected. Only 8 "delivered" orders lack a date, and those are flagged. The 610 products with no category are the same 610 rows missing three other descriptive fields, so it's one cause, not four. I don't impute in SQL. LightGBM handles missing values natively, and any imputation for logistic regression will be fitted on training data only to avoid leakage.

### 🟡 "Anything surprising?"
**4,977 reviews (5.19%) were written before the parcel was delivered, and 71 before the purchase date.** Customers can review a parcel that hasn't arrived, which matters for the "never arrived" complaint theme in Module 2. It's also a good illustration of why review data must never be a model feature: in some cases it exists before the outcome we're predicting.

### 🟡 "What did you do about the geolocation table?"
**1,000,163 rows for 19,015 zip prefixes, 26.18% of them exact duplicates (261,831 rows), and 47 points outside Brazil.** I removed out-of-country points, then averaged to one row per zip. Without that, joining customers to locations would multiply rows. The side effect is documented: 269 customers and 7 sellers end up with no coordinates.

---

## 9c. EDA and statistics (Day 2)

### 🟢 "Which statistical test did you use for late vs on-time reviews, and why?"
**Mann-Whitney U, because review scores are ordinal (1–5 stars) and heavily skewed toward 5★, so a t-test's assumptions don't fit.** Mann-Whitney compares ranks: it asks whether a random late order tends to score lower than a random on-time order. Result: p < 1e-300, rank-biserial r = −0.64, which is a large effect.

### 🟢 "What's a p-value? Why also report an effect size?"
**The p-value is the probability of seeing a difference at least this large if there were really no difference. The effect size says how big the difference is.** With 95,824 reviewed orders, almost any difference is "significant". My payment-method example shows why: method vs lateness gives p = 0.0006, but Cramér's V is only 0.013, which is negligible. Significant doesn't mean important, so I lead with effect sizes.

### 🟡 "What's a confidence interval, and how did you get yours?"
**A range that would contain the true value in 95% of repeated samples. I used a bootstrap:** resample both groups with replacement 2,000 times (seed 42), recompute the mean difference each time, and take the 2.5th and 97.5th percentiles. Result: −2.02 stars, 95% CI [−2.06, −1.98]. The bootstrap doesn't assume a normal distribution, which suits skewed star ratings.

### 🔴 "Couldn't geography explain the gap? Remote states are late more often."
**I checked by comparing late and on-time orders within each state.** In all 21 states with at least 30 late reviewed orders, late orders score lower, by 1.63 to 2.62 stars. That's controlling for a confounder by stratifying. It's still observational, not causal. Module 2 adds independent evidence by checking whether low-score review text actually mentions delivery.

### 🟡 "Does it matter *how* late?"
**Yes, up to a point.** Among late orders, Spearman ρ = −0.40 between days late and score. The curve is flat while orders are early, drops sharply right after the promised date, then levels off near 1.5★. Customers react most to the promise being broken.

### 🟡 "What did you learn that changes how you'll build the model?"
**The late rate isn't stable over time.** It's about 3% in typical months but 12.40% in Nov 2017 and 18.96% in Mar 2018, while promised delivery times shrink through 2018. A random train/test split would mix those periods and give an over-optimistic score. A time-based split shows how the model would really perform on future orders. Also: estimates are padded (median 12.4 days early, 59.9% of orders arrive in under half the promised time), so `promised_days` will be a key feature, and its meaning changes over time.

### 🟡 "What did you find about payment methods?"
**Boleto orders wait a median 29.06 hours for payment approval, against 0.27 hours for cards** (Kruskal-Wallis ε² = 0.34, large). Once approved, they ship just as fast: mean 12.12 vs 12.17 days from approval to delivery. So the extra time is checkout friction, not logistics. And method barely predicts lateness (Cramér's V = 0.013). Approval time is only known after purchase, so it's not a model feature; payment method is.

### 🟡 "Why a dumbbell chart for the state comparison?"
**It shows two values per state and the gap between them in one row, so the eye compares 21 gaps at once.** I sorted by gap size and used one colour per group, with a legend, so the meaning doesn't depend on colour alone.

---

## 9d. Machine learning: late-delivery model (Day 3)

### 🟢 "Walk me through your model."
**I predict, at the moment of purchase, whether an order will arrive after its estimated date.** 23 features, all known at checkout: the promised delivery time, distance and states, basket size and weight, payment method, the seller's recent track record, and platform-wide context. Time-based split: train on 2017, tune on Jan–Mar 2018, test once on Apr–Aug 2018. I compared logistic regression with LightGBM. **Logistic regression won** (test PR-AUC 0.094 vs 0.073, against a 0.044 base rate), so it's the production model. I explain every prediction with SHAP.

### 🟢 "How did you handle missing values and duplicates in your model data?"
**I checked the final model table before modelling: 0 duplicate orders, no infinite values, and 5 of 23 features with some missing values.** The biggest is the seller's recent late rate (7.2% missing in training), and it's missing for a reason: new sellers have no delivered orders yet, so the rate is *unknown*, not 0%. For logistic regression I fill missing values with the **training** median and add a 0/1 "was missing" column, so the model can still learn "this is a new seller". The cell after the fix proves it: 6,182 missing values before preprocessing, 0 after. LightGBM handles missing values natively. Nothing is filled in SQL, and the fill values are learned from training data only, so there's no leakage. (28 rows look identical but are different orders, so they stay.)

### 🟢 "Did you check for outliers?"
**Yes. Several features are heavily skewed** (order value has a skew of 12: median R$85, max R$13,440), **but they're real orders**, not errors; the impossible values were already fixed in the audit. So I kept them. For logistic regression, which is sensitive to extreme values, I **tested** a log transform as a tuning option. It scored lower on validation (0.273 vs 0.284), so I didn't use it. Tree models like LightGBM aren't affected by outliers.

### 🔴 "Is your model overfitting or underfitting?"
**I compared train, validation and test with ROC-AUC,** which doesn't move with the late rate (unlike PR-AUC). Logistic regression: 0.733 / 0.726 / 0.727, so **no overfitting**, and the learning curve gap closes from 0.10 to 0.008 as data grows. But even on training data it only reaches 0.733, and more data barely helps: that's **mild underfitting caused by limited information** at purchase time, not by too simple a model, since LightGBM didn't do better. LightGBM itself **does overfit**: 0.770 on train vs 0.636 on test, despite early stopping.

### 🟡 "Are your predicted probabilities reliable?"
**Roughly. I checked calibration on test by splitting orders into tenths by predicted risk.** The riskiest tenth is predicted at 10.1% and is actually 10.5% late; the model is slightly too high for the safest orders and too low in the 7th–9th tenths (6.0% vs 9.8%). Brier score 0.041. Good enough for risk bands; a recalibration step on recent data would sharpen it.

### 🟡 "Any correlated features?"
**Yes: seller orders vs deliveries in the last 90 days (r = 0.989), the two seller late rates (0.864), and weight vs volume (0.819).** Correlation doesn't hurt predictions much, and regularisation handles it, but it makes individual coefficients unreliable, so I interpret those pairs together.

### 🟢 "How many features does your dataset have?"
**Two answers: the raw data has 9 tables with 52 columns; my model uses 23 engineered features (19 numeric, 4 categorical), all known at purchase time.**
(The raw overview, with every column profiled, is section 0 of `notebooks/00_data_quality_audit.ipynb`; the model features are listed in section 2 of `notebooks/02`.) Many raw columns are IDs for joining or describe the outcome (delivery dates, review scores), so they can't be features. The 23 fall into seven groups: promise and timing (promised_days, weekday, hour, holiday flag), geography (distance, same state, customer and seller state), basket (value, freight, freight ratio, items, sellers), product (weight, volume, category), checkout (payment method), seller history (90-day orders, deliveries, late rate, all-time late rate), and platform context (30-day late rate, volume ratio). The target, `is_late`, is the label, not a feature.

### 🟢 "What is data leakage? Give an example from your project."
**Leakage is using information during training that wouldn't exist at prediction time. It makes test scores look great and the real model useless.** The obvious cases: delivery dates, delay days and review scores describe the outcome, so they're on a forbidden list, and a unit test fails if any of them appears in the features. The subtle case was seller history. "The seller's late rate from earlier orders" sounds safe, but an earlier order may still be *in transit* when the new one is placed, so its outcome isn't known yet. I count only orders **delivered before the purchase**, and a test with synthetic data proves an in-transit order is excluded.

### 🟢 "Why a time-based split instead of a random split?"
**Because the model will always predict the future from the past, and this data drifts a lot.** The late rate is 5.65% in 2017, 12.88% in Jan–Mar 2018 and 4.42% in Apr–Aug 2018. A random split would mix these periods, so the model would effectively see the future and the score would be over-optimistic. The time split shows how it would really perform.

### 🟢 "Why PR-AUC instead of accuracy or ROC-AUC?"
**With only 4–13% late orders, accuracy is meaningless: always predicting "on time" is 87–96% accurate.** ROC-AUC is flattering under imbalance because it rewards correctly ranking the many easy negatives. PR-AUC measures how well the *late* orders are ranked at the top, and a random model scores the base rate. So my 0.094 on test means 2.13× better than random, which is the honest way to state it.

### 🔴 "LightGBM is usually better on tabular data. Why did logistic regression win?"
**Drift.** LightGBM's early stopping halted after 1 to 14 trees in every configuration: what it learned from 2017 stopped helping on 2018 almost immediately. Trees also can't extrapolate. The validation period's platform late rate was far above anything in training, and a tree treats every value beyond its largest split the same. A linear model extends the trend. I tried 24 LightGBM configurations with stronger regularisation, all selected on validation, and the result held: 0.213 vs 0.284. The project rule is to report whichever wins, so the simpler model is in production.

### 🔴 "What did you do when the first model performed badly?"
**I diagnosed it instead of tuning harder.** Early stopping after a few trees pointed to a train/test mismatch, and the features showed why: all-time seller order counts keep growing as the platform ages, so 2018 values were outside the training range. I replaced them with rolling 90-day counts and added platform context features, all chosen on validation. I'm also transparent that an earlier feature set was scored on test once before I diagnosed the drift; that's written in the notebook.

### 🟡 "Any surprising result while building features?"
**Removing a feature that's all zeros in validation and test made the model much worse.** `is_nov_dec` (holiday season) never occurs in 2018 Jan–Aug, yet dropping it cut validation PR-AUC from 0.267 to 0.188. In training it absorbs the Black Friday spike. Without it, the model blames that spike on other features and their weights get distorted. It works as a control variable.

### 🟢 "How did you choose the threshold?"
**From business costs, on the validation set.** I assumed a missed late order costs 5 units (likely a 1–2★ review: 62.4% of late orders get one) and an unnecessary flag costs 1 unit (a proactive message), then picked the threshold minimising 5·FN + 1·FP: 0.045. Because 5:1 is an assumption, I also report 3:1 and 10:1.

### 🔴 "Did the threshold work on the test set?"
**No, and I report that.** On validation it cost 0.745× of doing nothing. On test, where the late rate fell from 12.88% to 4.42%, the same threshold flagged 27.3% of orders at 9.4% precision and cost 1.54× *more* than flagging nothing. At 5:1, a flag only pays off above about 17% precision, and even the riskiest 1% of test orders reach only 14.0%. The ranking still works (2.1–3.2× lift), but **a fixed threshold doesn't survive a three-fold change in the base rate.** In production I'd re-set it monthly on the latest labelled month, or use the model as a top-k priority list for cheap actions.

### 🟢 "What drives late-delivery risk according to your model?"
**From SHAP:** promised delivery days (a longer estimate means less risk, because padded promises are easier to keep), seller-to-customer distance (farther means more risk), customer state, same-state shipping (less risk), and recent platform and seller history. Seller orders and seller deliveries in the last 90 days point in opposite directions, but they're 99% correlated (r = 0.989), so that's **collinearity**: the linear model splits one signal into two opposite weights. I read such pairs together, never one by one.

### 🟢 "What is SHAP?"
**SHAP (SHapley Additive exPlanations) splits one prediction into a contribution from each feature, so that baseline + contributions = the model's output for that order.** It comes from game theory (Shapley values): the features are "players", the prediction is the "payout", and each feature gets its fair share of the difference between this order's score and the average order's score. A positive SHAP value pushes the risk up and a negative one pushes it down.

### 🟢 "Why did you use SHAP?"
Three reasons, one per audience:
- **Operations (one order):** "why is *this* order high risk?" A risk score alone isn't actionable; "the seller was late on its recent orders and the promise is short" tells someone what to do. The top-3 drivers are stored per order in `fact_order_risk` for the app.
- **Business (the whole model):** averaging the absolute SHAP values over test orders ranks what drives late risk overall: promised days 0.460, distance 0.275, customer state 0.227, same-state 0.192 (log-odds).
- **Me (model checking):** SHAP shows whether the model learned sensible directions. Longer promised time → less risk and longer distance → more risk make business sense. It also exposed **collinearity**: seller orders and seller deliveries in 90 days point in opposite directions because they're 99% correlated, so I read them together.

Why not just the coefficients? Coefficients are per *scaled, one-hot* column and say nothing about a specific order. SHAP gives one number per original feature, per order, in the same unit (log-odds), and the same idea works for tree models like LightGBM (via `TreeExplainer`), so explanations don't depend on the model type.

### 🟡 "How did you compute SHAP?"
**For a linear model SHAP is exact and simple: contribution = coefficient × (this order's transformed value − the training average of that value), in log-odds.**
1. Transform the order with the fitted pipeline (impute, scale, one-hot).
2. Subtract the **training** mean of each transformed column (stored on the model as `train_mean_`, the baseline).
3. Multiply by the logistic-regression coefficient.
4. Sum the one-hot and "was missing" columns back into their original feature, so `customer_state` gets one number instead of one per state column.

Code: `linear_contributions()` in `src/predict.py`. **Checks:** identical to the `shap` library's `LinearExplainer` (max difference 0.00), and baseline + contributions reproduce the model's log-odds exactly (error 2.66e-15).

### 🟡 "Walk me through one explained order."
The riskiest test order scored **46%** late risk, against a baseline of about **4.3%** for an average order. The biggest pushes up: the seller's 90-day late rate was 100% (**+1.47**), the customer is in RJ (**+0.63**), and the promise was only 16 days (**+0.52**, shorter than usual, so harder to keep). A 16.5 kg basket added +0.23. The 366 km distance pulled it down a little (**−0.16**, closer than average). In plain words: *a seller who has been late recently, shipping to a slow state, with a tight promise.*

### 🔴 "What are SHAP's limitations?"
- **It explains the model, not the world.** SHAP says what the model relies on, not what *causes* lateness. Promised days lowering risk means padded estimates are easier to keep, not that longer promises make parcels faster.
- **Correlated features share credit unpredictably.** The two seller-volume features split one signal into opposite weights, so correlated pairs are read together.
- **Units are log-odds**, so contributions add up in log-odds, not in percentage points. I convert only the final total back to a probability.
- **Features constant in a period** (e.g. `is_nov_dec` in the Apr-Aug test window) shift every order equally, so I left them off the test importance chart.

### 🟢 "What's your model's accuracy? Show me the classification report."
**Each model has its own section with a full classification report and confusion matrix; accuracy is in there, but I don't use it to choose.** On the test period: the do-nothing model ("never late") has the **highest** accuracy, 95.6%, and catches zero late orders. Logistic regression has 73.4% accuracy but the best late-class results: precision 9.4%, recall 57.8%, F1 0.161. So accuracy ranks the models backwards here; I use PR-AUC and late-class F1, and I show accuracy precisely to make that point.

### 🟡 "Why not just use the default 0.5 threshold?"
**Because at 0.5 my model flags nothing.** No test order's predicted probability reaches 0.5 when only ~4–6% of orders are late, so at 0.5 the model is identical to "never late". The threshold has to come from business costs: I minimise 5·missed + 1·false alarm on validation, which gives 0.045.

### 🔴 "How is this project better than your previous ML work?"
**In my Telco churn project I compared four models with classification reports, which made the results easy to read. This time I kept that presentation and fixed the methodology.** (1) Models are chosen on a separate validation set; in Telco I compared on the test set. (2) Tuning comes before saving; in Telco the saved model was saved before tuning. (3) Imbalance is handled without resampling across CV folds; in Telco, SMOTE ran before cross-validation, which inflates CV scores. (4) The threshold comes from business costs rather than 0.5. (5) I add a do-nothing baseline, a simple-rule baseline, bootstrap confidence intervals, leakage tests and an error analysis. The same model-comparison skills, applied more rigorously.

### 🔴 "Does your model beat a simple business rule?"
**Yes, and I tested it the same way as the models.** I built one-feature rules (e.g. "the farther the seller, the riskier"), learned each rule's direction on training data, and picked the best on validation: distance, with test PR-AUC 0.059. The model scores 0.094, and a paired bootstrap gives a difference CI of −0.043 to −0.029 for the rule, so the gap isn't luck. If a simple rule had won, I'd have recommended the rule.

### 🔴 "How do you know 0.094 vs 0.073 isn't just noise?"
**Paired bootstrap: I resampled the test orders 1,000 times, using the same orders for every model each time, and recomputed PR-AUC.** Logistic regression: 0.094 [95% CI 0.087–0.104]. The LightGBM-minus-logistic difference has a CI of −0.029 to −0.016, entirely below zero, so the ranking is reliable. Pairing matters: both models are scored on the same resampled orders, so the comparison isn't distorted by one resample happening to contain easier orders.

### 🟡 "Where does your model fail?"
**I did an error analysis on the test period.** By month, it ranks best in April–May (PR-AUC 0.15–0.18) and worst in June, when only 1.2% of orders were late. By state, it catches 78–88% of late orders in the North-East but only 18.3% in MG. The late orders it misses are short-distance (median 319 km vs 667 km for caught ones) and placed during platform-wide delay waves. That points to two fixes: model the platform late rate non-linearly, and add a dispatch-time model with carrier data.

### 🟡 "Is a PR-AUC of 0.094 good?"
**It's modest, and I'd say so.** It's 2.13× random. The model's top 1% of orders are late 14.0% of the time against 4.42% overall. Purchase-time data simply can't see most causes of lateness (carrier problems, weather, strikes), which happen after checkout. A useful next step would be a second model at dispatch time, with carrier and pickup information.

### 🟡 "Are the predicted probabilities meaningful?"
**Roughly, on test:** the average predicted risk is 3.78% against an actual 4.42%. I deliberately didn't use class weighting in the final model: it scored better on validation (0.284 vs 0.267) and keeps probabilities on the real scale. On validation the model predicted 3.42% against an actual 12.88%; it can't anticipate a regime it has never seen. That's why monitoring matters.

### 🔴 "When is your model actually worth using?"
**I turned the cost assumption into a break-even ratio.** Flagging pays off when precision × cost of a missed late order > (1 − precision) × cost of a false alarm. In the test period the riskiest 1% of orders are late 14.0% of the time, so a caught late order must be worth at least **6.2 false alarms** (it was 1.6 on validation). So the model suits cheap automatic actions, like a "may be delayed" message, not manual calls. That's the number to agree with operations, more than a threshold.

### 🔴 "Your label only covers delivered orders. What about orders that never arrived?"
**I checked it: 1,702 orders were still undelivered after their promised date at the data cut-off.** Counting them as late raises the test late rate from 4.42% to **5.60%**, so the delivered-only label understates the problem by about a quarter. But re-training on that wider label made the model worse (lift 2.13× → 1.80× on delivered orders), because they have different causes: about two-thirds were shipped and lost, one-third never left the seller. So I kept the delivered label and report never-delivered orders as a separate fulfilment problem.

### 🔴 "Did you retrain on train + validation before deploying?"
**"I tested refitting on train + validation. It ranked the top 1% better (18.3% precision) but over-predicted by 2× after the spike. The right production recipe is refit plus monthly recalibration. With the data I had, I couldn't validate that without touching the test set, so I kept the model whose test numbers are clean."**

The numbers behind it, if they dig deeper:
- **Better at ranking the riskiest orders:** test PR-AUC 0.094 → 0.103, paired bootstrap difference +0.003 to +0.015 (excludes 0); top-1% precision 14.0% → 18.3%, break-even ratio 6.2:1 → 4.5:1.
- **Worse overall and miscalibrated:** ROC-AUC 0.727 → 0.703; mean predicted 9.9% vs actual 4.4%, because it learned from the Q1-2018 spike (12.9% late).
- **Why I couldn't validate recalibration:** every month after March 2018 is the test set, so calibrating there would be leakage; calibrating on March 2018 (the 19% spike month) would inflate the probabilities further.
- **Why the decision matters downstream:** the dashboard's "predicted 3.78% vs actual 4.42%" stays true with the 2017 model; the refit would show 9.95% vs 4.42%.
- **The principle:** switch models when the new one is better *for its intended use and safe to ship*. Here the evidence was mixed and the safety step couldn't be verified.

### 🔴 "Why did you refit the model when you had already found the best one?"
**Because finding the best model and building the final model are two different steps.**
- **Step 1, choosing:** to compare models fairly I had to hold back Jan-Mar 2018 as validation. On it, logistic regression beat LightGBM and the simple rule, and I picked its settings (C = 0.01, no class weights) and the threshold. That answered *which model and which settings*.
- **Step 2, building:** once the choice is made, the validation months are no longer needed for choosing, and they're the **most recent** data before deployment, including the Q1-2018 delay spike. Throwing them away means the deployed model never sees the latest behaviour. So standard practice is to refit the **same** model with the **same** settings on all data before the test period. It's the same idea as scikit-learn's `GridSearchCV(refit=True)`, which refits the best settings on all the data by default.
- **Why it's not cheating:** no new model, no new tuning, and the rule ("refit the winner on train + valid") was fixed before I looked at the result. The test set was only used to *evaluate* it.
- **What happened:** it ranked the riskiest orders better (top-1% precision 14.0% → 18.3%) but over-predicted by 2× because it learned from the spike. So I kept the 2017 model as the saved one and documented "refit + monthly recalibration" as the production recipe.

**One-line version:** *"Validation is for choosing; once you've chosen, you retrain on everything you're allowed to use. I tested that properly, found it hurt calibration, and kept the cleaner model."*

### 🟡 "What's the cost-optimal threshold in theory?"
**For calibrated probabilities it's cost_FP / (cost_FP + cost_FN) = 1/6 for a 5:1 ratio, no tuning needed.** My 2017 model is close to calibrated on test (3.8% predicted vs 4.4% actual) and at 1/6 it flags almost nothing, which costs the same as flagging nothing (7,103 vs 7,105). That agrees with the break-even analysis: on test, almost no order is more than 1/6 likely to be late.

### 🟡 "How is the model used downstream?"
**Every order is scored into `fact_order_risk`: probability, risk band (high/medium/low relative to the threshold), model version, top-3 SHAP drivers and a split column.** Dashboards should filter to `split = 'test'` for honest numbers, because training-period scores are in-sample. The scores are saved to Parquet and reloaded on every database rebuild, and the model plus its metadata (features, threshold, metrics, dates) are saved in `models/`.

---

## 9e. Power BI (Day 4)

### 🟢 "How did you get the data into Power BI?"
**I exported the star schema from DuckDB to Parquet with a script and loaded the 6 files.** Power BI has no native DuckDB connector, and Parquet keeps column types (dates, decimals, true/false), whereas CSV makes Power BI guess. The export is reproducible: one command regenerates the files.

### 🟢 "Describe your data model."
**A star: dates and customers filter the orders table; products and sellers filter the order-lines table; orders filter their own lines.** Every relationship is many-to-one and single-direction. Where I needed the reverse direction (average review for a product category), I used `CROSSFILTER` inside that one measure instead of making the relationship two-way, which avoids ambiguous filter paths.

### 🟢 "What's the difference between a calculated column and a measure?"
**A calculated column is computed once per row at refresh and stored; a measure is computed at query time for whatever is filtered.** On-time % must be a measure: it has to change when someone selects a state or a month. `delay_bucket` is a fixed property of each order, so it's a column (I created it in SQL).

### 🟡 "Explain a DAX measure you wrote."
**Month-on-month revenue:** a variable holds this month's `[Revenue]`, another holds `CALCULATE([Revenue], DATEADD(dim_date[date], -1, MONTH))`, and `DIVIDE` returns the change while avoiding division by zero. It only works because `dim_date` is marked as the date table. Another one: `Seller Revenue Rank` uses `RANKX` over `ALLSELECTED(dim_seller[seller_id])`, so the ranking respects the page's slicers.

### 🔴 "Any DAX pitfalls you ran into?"
**BLANK equals FALSE in DAX.** Undelivered orders have a blank `is_late`, so a filter `is_late = FALSE()` would silently include them. My `Review Gap` measure is built on `[Avg Review]`, which already keeps delivered orders only. A second one: product and seller filters reach only the order-lines table, so counting orders per category needs `DISTINCTCOUNT` over the lines table (the "item-level" measures), not a count of the orders table.

### 🟢 "How do you know your dashboard numbers are right?"
**Reconciliation.** Before building it, I computed 22 expected values with SQL from the same exported files (total revenue, on-time %, MoM and YoY for August 2018, a state, a category, a seller rank, risk-band rates) using the same logic as each DAX measure. Every visual is checked against that table.

### 🟡 "What does the model page show?"
**Test-period orders only, grouped by risk band:** high-risk orders were on time 90.64% of the time and low-risk orders 99.06%, so late orders are about 10× more common in the high band. Training-period scores are excluded because they're in-sample.

### 🟢 "Walk me through your revenue vs review scatter chart." (Sellers & categories page)
**Each bubble is one of the 20 highest-revenue categories: X = revenue, Y = average review, size = number of orders. A dashed line marks the overall average review (4.16).** Bubbles below the line and to the right earn a lot but disappoint customers. Three of the top 5 earners sit below the line: bed_bath_table (R$1.02M, 4.00★), computers_accessories (R$0.89M, 4.08★) and watches_gifts (R$1.17M, 4.12★). office_furniture (R$0.27M, 3.64★) is the clear outlier and is coloured coral by a rule (review < 3.9).

### 🔴 "Your Y-axis starts at 3.6, not 0. Isn't that misleading?"
**It's zoomed on purpose, so I always quote the actual numbers.** Every category scores between 3.6 and 4.3, and an axis from 0 would squash them into one line. Zooming exaggerates visual gaps, though, so I'm careful: bed_bath_table is only 0.16★ below average, while office_furniture is 0.52★ below, which is the real outlier. (Bar charts must start at 0 because bar length encodes the value; scatter positions don't.)

### 🟡 "Why is the average line a constant line on the measure and not Power BI's 'Average' line?"
**Power BI's built-in Average line averages the 20 dots, so each category counts equally.** That gives a different number from the true average over all orders (4.16). I set a constant line to the `Avg Review` measure so the line shows the real overall average, and it updates with slicers.

### 🟡 "How does a user know which bubble is which?"
**Hovering shows a tooltip with the category name, revenue, review and order count.** I also added extra fields to the tooltip (on-time % and late rate), so a user can see *why* a category might score badly without crowding the chart with labels. For the single outlier I added a small text label, accepting that it's static and has to be checked when slicers change the view.

### 🔴 "8 of the 10 worst sellers are in São Paulo. So São Paulo sellers are the problem?"
**Not on its own. I checked the base rate first: 69% of all sellers with 100+ orders are in SP (145 of 210).** If SP sellers were no worse than anyone else, about 7 of the worst 10 would be from SP anyway, so 8 is only slightly more. The honest conclusion: the problem is a handful of individual sellers, not the region. The card shows both numbers so no one draws the wrong conclusion. (Supporting detail: orders from SP sellers are late 7.24% of the time vs 5.35% for other states, so there's a modest regional gap, but it doesn't make the region the main story.)

### 🟡 "What happens to your dashboard text when someone filters by year?"
**I tested every year and found titles that were typed numbers: "18% of sellers…" was true for all years but 32% in 2016.** I replaced them with measures (`Concentration Headline`, `Pareto Subtitle`, `Scatter Subtitle`), so text and numbers always agree. In 2016 no seller had 100+ orders, so the headline measure now says "n/a" instead of a broken "0 of".

### 🔴 "Is office_furniture rated badly because it's delivered late?"
**Only partly, and that's the interesting part.** Its on-time rate is 91.95% (about 8% late) against 93.23% overall (6.77% late), so it's only slightly worse, yet its review is 0.52★ below average. Lateness alone doesn't explain it. My hypothesis is product-related (damage, missing parts, assembly), which I test with the GenAI review analysis (Module 1) instead of guessing.

### 🟡 "Did a tooltip ever show you a wrong number?"
**Yes.** I added `Late Rate %` to the scatter tooltip and every category showed 6.77%, the overall rate. That measure counts the orders table, which product filters can't reach (they only filter the order-lines table). I removed it and kept `Item-level On-time %`, which counts orders through the lines table. Lesson: check that a measure actually responds to the filter context of the visual it's placed in.

---

## 9f. Excel monthly management report (Day 5)

### 🟢 "Walk me through your Excel report."
**It's the monthly pack an executive opens: pick a month and a state in two yellow cells, and everything updates.** The Summary compares the month with the previous month and the same month last year (8 KPIs, coloured green or red depending on whether a change is good for that metric), writes three key messages as formulas, and shows two trend charts. Behind it: a Monthly KPI table, two PivotTable sheets with slicers and PivotCharts (revenue by month × category; on-time % by state), a What-if sheet, and a Checks sheet. For August 2018: revenue R$ 838,577 (−3.3% on July, +51.2% on August 2017), on-time 93.8% (−2.8 pts).

### 🔴 "Why did you feed Excel aggregated data instead of the raw orders?"
**Because ratios must be rebuilt from additive pieces, never averaged.** The data sheets hold only counts and sums per month × state (556 rows) and month × state × category (11,670 rows): delivered orders, late orders, revenue, review sum, review count. Every ratio (on-time %, average review, AOV) is a formula *sum ÷ sum*, so it's correct for any filter. If I had stored a ready-made on-time % per state and averaged it, a state with 500 orders would weigh the same as SP with 40,000. It also keeps the file under 1 MB instead of 100k rows.

### 🔴 "How do you get on-time % in a PivotTable?"
**A calculated field: `on_time_orders / delivered_orders`.** PivotTable calculated fields work on the *sums* of each field, so each state's value is its on-time orders ÷ its orders, which is exactly right. (The trap: putting a pre-computed percentage column in the pivot and choosing "Average" gives a wrong, unweighted number.) The state table matches Power BI: MA 82.6% worst, PR 96.0% best.

### 🟡 "Which Excel functions did you use, and why?"
- **SUMIFS** in the Monthly table, with the state criterion `IF(sel_state="All","*",sel_state)`: the `*` wildcard means "any state", so one formula serves both "All" and a single state.
- **XLOOKUP** on the Summary to fetch the chosen, previous and last-year month (clearer than VLOOKUP: no column numbers, a built-in "not found" value).
- **LET** to build the previous-month key once (`2018-01` → `2017-12`), **VSTACK / SORT / UNIQUE** for the state drop-down list, **data validation** lists for the inputs, **named ranges** (`sel_month`, `wi_target`) so formulas read like sentences.
- **Conditional formatting**: green/red changes depending on each metric's "better when" direction, colour scales, data bars.

### 🟢 "How does your what-if sheet work?"
**It estimates how much the average review would rise if more orders arrived on time.** New average = today's average + (extra on-time share) × (share of the review gap recovered) × (on-time review − late review). Inputs: target on-time rate (default 96%; today 93.23%) and how much of the 2.02-star gap a rescued order recovers (default 50%). Result: about **183 late orders a month turned on time, average review 4.156 → 4.184 (+0.028), and 49 fewer 1-2 star reviews a month**. Two Excel **Data Tables** (What-If Analysis) show every combination from 94% to 99% and 25% to 100%; the upper bound is 4.27 stars and 202 fewer 1-2 star reviews a month.

### 🔴 "+0.03 stars is tiny. Why should anyone care?"
**Because the average hides where the change happens.** Late orders are only 6.8% of orders, so fixing many of them still moves the overall average a little, but each rescued order goes from a typical 2.27 towards 4.29 stars, and 1-2 star reviews (the ones that hurt reputation) fall by 49 a month in the default case. I'd present the 1-2 star count to a manager, not the average. I also chose a cautious default (50% of the gap) and show 100% only as an upper bound.

### 🔴 "Isn't the what-if just assuming lateness *causes* bad reviews?"
**Yes, so I sized the claim to the evidence.** The gap is large (−2.02 stars), it holds within every state, and it barely moves when I control for state, category, order value and basket size (−2.03 adjusted vs −2.02 raw). That's strong evidence, but still observational: orders that get rescued might differ from typical on-time ones. So the default recovers only half of the gap, the sheet says "plan on 25-50%", and the recommendation is to confirm with an A/B test before committing budget.

### 🟡 "How do you know the workbook is correct?"
**A Checks sheet with 19 reconciliations, all PASS.** 15 compare workbook formulas with values computed independently in SQL (the same expected values the Power BI report is checked against: 96,470 orders, R$ 13,220,248.93, 93.23% on time, 4.16 average review, August 2018 MoM −3.33% and YoY +51.18%, rating shares), and 4 are internal consistency checks (category data = order data, on-time + late = delivered). I also tested the interaction: São Paulo, March 2018 in Excel (R$ 377,034.34, 2,971 orders, 90.6% on time) equals the SQL result exactly. The Summary shows "19 of 19 pass", linked to the sheet.

### 🟡 "Why did you build it with Python instead of by hand?"
**So it's reproducible: one command rebuilds it from the database** (`python scripts/build_excel_report.py`). The script drives Excel itself (COM automation), so the PivotTables, slicers and Data Tables are genuine Excel objects that a manager can use, not a static export. When the data is refreshed, the report is rebuilt the same way, with the checks re-run.

### 🟡 "Your YoY growth shows +727% in January 2018. Is that right?"
**It's arithmetically right but not meaningful, so the report says so.** January 2017 had only 750 delivered orders because the marketplace was still ramping up (vs 7,069 in January 2018). The Monthly sheet tells readers to use YoY only from about May 2018 onwards, when the base month is mature. Spotting misleading-but-correct numbers is part of the job.

---

## 9g. GenAI Module 1: "Ask the data" (Day 5, in progress)

### 🟢 "What is a semantic layer, and why did you build one?"
**It's one file where business terms get a single, precise definition** (`genai/semantic_layer.yaml`): what "revenue" means (delivered orders, item prices, excluding freight), what "on-time rate" means (delivered orders only, as a percentage), that "customers" means people not orders, that "state" means the customer's state. Without it, an LLM writes SQL that *runs* but answers a different question, e.g. averaging reviews over cancelled orders too. The same definitions drive the SQL and Power BI, and a test proves 8 of them return exactly the Power BI values (R$ 13,220,248.93, 93.23% on time, 4.16 average review…), so every tool tells the same story.

### 🔴 "Give an example of a mistake the semantic layer prevents."
**Fan-out.** If you join orders to order items and then `SUM(order_value)`, every order is counted once per item and revenue is inflated. The layer tells the model: use item prices for category or seller revenue, and never sum an order-level column after joining items. Another: "how many customers" should be `COUNT(DISTINCT customer_key)` (people), not a count of orders.

### 🟢 "How did you build your evaluation set?"
**46 questions written the way a manager would ask them, each with hand-written gold SQL**: 15 easy (counts, totals), 18 medium (grouping, joins, time) and 13 hard (window functions, thresholds, Pareto, the model's risk bands). Each has tags for what it tests (metric definitions, fan-out, mapping "Rio de Janeiro" to RJ…), so I can see *which kind* of question fails, not just the overall score. The expected answers come from running the gold SQL, and I cross-checked 25 of them against results already verified elsewhere in the project.

### 🔴 "How do you know your evaluation set itself is right?"
**I tested it like code.** Every gold query must be a single SELECT on the allowed tables (parsed with sqlglot), the stored answers must match a fresh run, and every "top k" question is checked for a tie at position k. That check caught a real problem: the two worst categories by on-time rate (office_furniture 91.946%, baby 91.954%) both round to 91.95%, so "which category is worst?" had no single fair answer. I changed the question to "the 2 lowest". A flawed test set gives you a wrong accuracy number however good the model is.

### 🟡 "What is execution accuracy?"
**A generated query counts as correct if running it returns the same result as the gold query**, not if the SQL text looks the same. Two very different queries can both be right (a CTE vs a subquery), so comparing text would punish correct answers. The comparison ignores row order and column names and tolerates rounding.

### 🟡 "How do you stop the evaluation leaking into the prompt?"
**The few-shot examples the model sees are a separate file that may never contain an evaluation question**, and the semantic layer gives definitions (an expression and a filter), not ready-made answer queries. Otherwise the model would be copying answers and the accuracy would be meaningless.

### 🟢 "What was your baseline accuracy, and why so low?"
**45.7% (21 of 46) with only the schema in the prompt**: 60% on easy, 50% on medium, 23% on hard questions. I re-ran all 25 failures to see why, and the biggest cause was business knowledge, not SQL skill: **17 failures ignored the rule that revenue, reviews and delivery metrics use delivered orders only**, e.g. total revenue R$ 13.59M instead of R$ 13.22M because canceled orders were included. The SQL ran fine and looked right, which is exactly the danger. Others: state names instead of codes (`'Rio de Janeiro'` instead of `'RJ'` → 0 customers), guessing stored values (`'credit card'` vs `credit_card`), and one empty reply. Each group maps to an improvement step: column descriptions, the semantic layer, examples and a retry.

### 🔴 "Did you find any problems with your own evaluation?"
**Yes, one false negative.** For "orders delivered in each month of 2018" the model's numbers were exactly right, but it labelled months "January" while the gold answer used "2018-01". The question never specified a format, so marking it wrong was the test's fault. I fixed the wording ("show the month as YYYY-MM") for that and one similar question, disclosed it, and re-ask only those two. I didn't loosen the matcher to accept any label, because "top 5 states" must still name the right states.

### 🟡 "What happens when the free API quota runs out mid-evaluation?"
**The run stops cleanly and resumes later at no cost.** Every reply is cached on disk, so a rerun only asks the questions not yet answered. A quota error is never scored as a wrong answer (that would quietly lower the accuracy), and the client recognises OpenRouter's "free-models-per-day" message and stops at once instead of retrying for minutes. It hit the cap after 58 requests on the first day.

### 🟢 "Walk me through your accuracy improvements."
**One fixed model (local Qwen 2.5 Coder 7B), one change at a time, all 46 questions each time:**

| Step | What the prompt adds | Accuracy | Easy / medium / hard |
|---|---|---|---|
| Baseline | Table and column names | **34.8%** | 60.0 / 33.3 / 7.7 |
| + a | Column descriptions and stored values | **39.1%** | 60.0 / 38.9 / 15.4 |
| + b | Semantic layer (business definitions) | **63.0%** | 93.3 / 72.2 / 15.4 |
| + c | 3 retrieved similar solved examples | **76.1%** | 100 / 72.2 / 53.8 |
| + d | Self-correction: send the error back once | **80.4%** | 100 / 77.8 / 61.5 |

**The biggest single gain was the semantic layer (+11 questions)**: the model already knew SQL, it didn't know our business. Examples mainly helped hard questions (window functions, cumulative shares), and self-correction fixed 2 of the 6 queries that crashed. (These are the leak-free numbers: see the question about evaluation bugs.) All at US$0, on a laptop.

### 🔴 "What is few-shot retrieval, and can it hurt?"
**Instead of fixed examples, each question gets the 3 most similar solved examples, found by meaning with sentence embeddings** (`all-MiniLM-L6-v2`, run locally). It mostly helps, but I saw it hurt once: for "which states have the longest delivery time?", it retrieved an example about **seller** states and the model copied that join, answering the wrong question (negative transfer). The examples teach patterns on different metrics and periods, and a test forbids any example whose result equals an evaluation answer, so the model can't copy answers.

### 🔴 "Why can self-correction only fix some errors?"
**It only triggers when there is an error message to send back**: a blocked or crashing query. A query that runs and returns a wrong number gives no signal, so it can't be corrected; 5 of my 9 remaining failures are like that. That's why the evaluation set and the semantic layer matter more than retries: they target the silent errors.

### 🔴 "Did you ever find a bug in your evaluation?"
**Yes, twice, and fixing it lowered some scores.** First, a question with an ambiguous month format (a false negative). Second, my numeric tolerance was too loose: it accepted 4.19 stars as matching 4.16, and 96,478 delivered orders as matching 96,470. The anti-leakage test exposed it. I changed the rule to compare at the precision of the gold answer and re-scored every stored run from its saved SQL, with no new LLM calls: 4 verdicts changed, all from correct to wrong, and I logged both the old and corrected numbers. An evaluation you haven't tested can quietly flatter your model.

### 🔴 "Did any test data leak into your prompts?"
**Yes, and I found it in my own code review.** The semantic layer file also stored the expected value of each metric, for a test that checks the definitions against Power BI, and the whole file went into the prompt, so 7 evaluation answers (e.g. total revenue R$ 13,220,248.93) were visible to the model. I checked every stored answer: none had copied a number. But "probably not used" isn't proof, so I stripped the test values from the prompt, added a test that no answer can appear in it again, and re-ran the affected steps. The honest results dropped slightly: semantic layer 65.2% → **63.0%**, final 82.6% → **80.4%**. I report the leak-free numbers, and the history is in the progress log.

### 🟡 "Why free LLMs?"
**Cost discipline: the whole module runs at US$0** on two free OpenRouter models (`cohere/north-mini-code:free` and `google/gemma-4-31b-it:free`). Free models are rate-limited, so the design caches every response on disk, retries with backoff and runs the evaluation in batches. It's the same engineering you'd need under a production budget or quota.

---

## 10. Coming next: questions to prepare later

Fill these in as each part is built, using real results only.

**Day 2: Data-quality audit and EDA**
- *(Answered in sections 9b and 9c.)*

**Day 3: Machine learning**
- *(Answered in section 9d.)*

**Day 5: Excel**
- *(Answered in section 9f.)*

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
| Data-quality checks | 45 (FIX 12 · FLAG 17 · KEEP 15 · SCOPE 1) | `data_quality_audit.csv` |
| Clean orders | 97,467 of 99,441 (98.01%) | audit notebook |
| Late rate, flagged orders excluded | 6.67% (vs 6.77% all) | audit notebook |
| Reviews written before delivery | 4,977 (5.19%) | audit |
| Late vs on-time test | Mann-Whitney p < 1e-300, r = −0.64; gap −2.02★ [−2.06, −1.98] | `01_eda.ipynb` |
| Within-state check | late lower in 21/21 states, by 1.63–2.62★ | `01_eda.ipynb` |
| Late-rate spikes | 12.40% (Nov 2017), 18.96% (Mar 2018) vs ~3% typical | `01_eda.ipynb` |
| Estimate buffer | median 12.4 days early; 59.9% in < half the promised time | `01_eda.ipynb` |
| Boleto approval / days after approval | 29.06 h median; 12.12 vs card 12.17 days | `01_eda.ipynb` |
| Split late rates | train 5.65% · valid 12.88% · test 4.42% | `02_late_delivery_model.ipynb` |
| Valid PR-AUC: logistic vs LightGBM | 0.284 vs 0.213 | notebook 02 |
| Test PR-AUC: logistic vs LightGBM | 0.094 vs 0.073 (base rate 0.044; lift 2.13×) | notebook 02 |
| Top-1% / top-5% test precision | 14.0% / 10.6% | notebook 02 |
| Threshold (5:1) on test | precision 9.4%, recall 57.8%, cost 1.54× flag-nothing | notebook 02 |
| Top SHAP drivers | promised_days, distance_km, customer_state, same_state | notebook 02 |
| Test PR-AUC 95% CI | 0.094 [0.087, 0.104] (paired bootstrap) | notebook 02 |
| Best simple rule | distance_km, test PR-AUC 0.059 (model beats it) | notebook 02 |
| Recall by state at threshold | MG 18.3% … PE 87.8% | notebook 02 |
| Test accuracy / F1 (late) per model | always on-time 0.956 / 0 · rule 0.853 / 0.124 · logistic 0.734 / 0.161 · LightGBM 0.764 / 0.130 | notebook 02 §9 |
| Logistic at threshold 0.5 | flags 0 of 32,150 test orders | notebook 02 §7 |
| Missing values (model table) | 5 of 23 features; max 7.22% (train); 6,182 → 0 after preprocessing | notebook 02 §3 |
| Duplicates (model table) | 0 duplicate orders | notebook 02 §3 |
| Overfitting check (ROC-AUC train/valid/test) | logistic 0.733/0.726/0.727 · LightGBM 0.770/0.637/0.636 | notebook 02 §10 |
| Log-transform test | 0.273 vs 0.284 without → not used | notebook 02 §7 |
| Overall avg review (delivered) | 4.156 → shown as 4.16 | Parquet check, scatter line |
| Top-20 categories below avg (scatter) | bed_bath_table R$1.02M 4.00★ · computers_accessories R$0.89M 4.08★ · watches_gifts R$1.17M 4.12★ · office_furniture R$0.27M 3.64★ | Parquet check (Day 4) |
| office_furniture on-time (item-level) | 91.95% vs 93.23% overall (late ≈ 8% vs 6.77%) | Power BI tooltip + Parquet check |
| Categories with sales | 74 (7 make half of revenue) | Parquet check (Day 4) |
| Top 5 sellers by revenue | 4869f7a5 SP R$226,988 · 53243585 BA R$217,940 · 4a3ca931 SP R$196,882 (3.85★) · fa1c13f2 SP R$190,917 · 7c67e144 SP R$186,570 (3.50★) | Parquet check (Day 4) |
| Sellers with ≥100 orders | 210 (145 in SP = 69%); worst on-time 80.98% (06a2c3af, MA); 8 of worst 10 in SP | Parquet check (Day 4) |
| Highest-rated top-20 categories | stationery 4.30★ · pet_shop 4.27★ · perfumery 4.26★ | Parquet check (Day 4) |
