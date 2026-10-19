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

### 🟡 "What is SHAP, and how did you compute it?"
**SHAP splits a single prediction into contributions from each feature, so they add up to the prediction.** For a linear model it's exact: contribution = coefficient × (feature value − training average), in log-odds. I implemented that, cross-checked it against the `shap` library (identical, max difference 0.00), and checked that the contributions plus the baseline reproduce the model's output (error 2.66e-15). One-hot columns are summed back so each original feature gets one number.

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

---

## 10. Coming next: questions to prepare later

Fill these in as each part is built, using real results only.

**Day 2: Data-quality audit and EDA**
- *(Answered in sections 9b and 9c.)*

**Day 3: Machine learning**
- *(Answered in section 9d.)*

**Day 5: Excel**
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
