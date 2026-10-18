-- =====================================================================
-- 03_business_queries.sql: business analyses on the star schema
-- Run with: python scripts/run_queries.py  (results -> sql/results/*.csv)
-- Each query: "-- name:" marker, the business question (BQ ref), and a
-- one-line INSIGHT written only from the actual output.
-- Shared definitions (match genai/semantic_layer.yaml):
--   revenue   = SUM(item price), excl. freight, delivered orders only
--   delivered = fact_orders.is_delivered; on-time = NOT is_late
-- =====================================================================


-- name: q01_monthly_trend
-- BQ1: How have orders and revenue developed month by month?
-- Limited to 2017-01..2018-08: 2016 has only 267 delivered orders (Nov missing)
-- and Sep/Oct 2018 are cut off, so their % changes are meaningless.
-- INSIGHT: Monthly revenue grew from R$0.11M (Jan 2017) to a R$0.83-0.98M plateau in 2018; Nov 2017 (Black Friday month) is the peak: 7,288 orders, +52.4% MoM.
SELECT
    d.year_month,
    COUNT(*)                                     AS delivered_orders,
    SUM(f.order_value)                           AS revenue,
    ROUND(AVG(f.order_value), 2)                 AS avg_order_value,
    ROUND(100.0 * (SUM(f.order_value) / LAG(SUM(f.order_value)) OVER (ORDER BY d.year_month) - 1), 1)
                                                 AS revenue_mom_pct
FROM fact_orders AS f
JOIN dim_date    AS d ON d.date_key = f.purchase_date_key
WHERE f.is_delivered
  AND d.year_month BETWEEN '2017-01' AND '2018-08'
GROUP BY d.year_month
ORDER BY d.year_month;


-- name: q02_revenue_by_state
-- BQ1: Which customer states generate the most revenue?
-- INSIGHT: Sao Paulo alone is 38.3% of revenue; SP + RJ + MG together are 63.3%, so demand is concentrated in the South-East.
SELECT
    c.state,
    COUNT(*)                                                         AS delivered_orders,
    SUM(f.order_value)                                               AS revenue,
    ROUND(100.0 * SUM(f.order_value) / SUM(SUM(f.order_value)) OVER (), 1) AS pct_of_revenue
FROM fact_orders  AS f
JOIN dim_customer AS c ON c.customer_key = f.customer_key
WHERE f.is_delivered
GROUP BY c.state
ORDER BY revenue DESC
LIMIT 10;


-- name: q03_category_pareto
-- BQ1/BQ4: Which product categories lead revenue, and how concentrated is it?
-- INSIGHT: Of 74 categories, the top 7 make 49.9% of revenue and the top 15 make 76.3%; health_beauty leads with 9.3%.
WITH cat AS (
    SELECT p.category_en, SUM(i.price) AS revenue
    FROM fact_order_items AS i
    JOIN fact_orders      AS f ON f.order_id = i.order_id
    JOIN dim_product      AS p ON p.product_key = i.product_key
    WHERE f.is_delivered
    GROUP BY p.category_en
)
SELECT
    RANK() OVER (ORDER BY revenue DESC)                                        AS rnk,
    category_en,
    revenue,
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 1)                           AS pct_of_revenue,
    ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / SUM(revenue) OVER (), 1)
                                                                               AS cumulative_pct,
    COUNT(*) OVER ()                                                           AS n_categories
FROM cat
ORDER BY revenue DESC
LIMIT 15;


-- name: q04_on_time_by_state
-- BQ2: What is the on-time delivery rate overall and by customer state?
-- (ROLLUP adds an overall row; states with < 500 delivered orders hidden)
-- INSIGHT: Overall on-time rate is 93.23%; it ranges from 82.64% (MA) to 95.96% (PR). RJ is the big-volume weak spot (87.89% on 12,351 orders), and SP delivers in 8.8 days on average vs 21.5 in MA.
SELECT
    COALESCE(c.state, 'ALL')                         AS state,
    COUNT(*)                                         AS delivered_orders,
    ROUND(100.0 * AVG(CASE WHEN f.is_late THEN 0 ELSE 1 END), 2) AS on_time_pct,
    ROUND(AVG(f.delivery_days), 1)                   AS avg_delivery_days,
    ROUND(AVG(f.promised_days), 1)                   AS avg_promised_days
FROM fact_orders  AS f
JOIN dim_customer AS c ON c.customer_key = f.customer_key
WHERE f.is_delivered
GROUP BY ROLLUP (c.state)
HAVING COUNT(*) >= 500
ORDER BY (c.state IS NOT NULL), on_time_pct;


-- name: q05_worst_sellers_on_time
-- BQ2: Which sellers have the worst on-time rate (min. 100 delivered orders)?
-- An order counts for every seller in it (multi-seller orders: 1,275 of 96,470 delivered = 1.32%).
-- INSIGHT: The worst seller (>=100 orders) is on time only 81.0% of the time (389 orders, MA); 8 of the 10 worst are SP-based, so seller-level issues exist even in the best-served state.
WITH seller_orders AS (
    SELECT DISTINCT i.seller_key, f.order_id, f.is_late
    FROM fact_order_items AS i
    JOIN fact_orders      AS f ON f.order_id = i.order_id
    WHERE f.is_delivered
)
SELECT
    s.seller_id,
    s.state                                                   AS seller_state,
    COUNT(*)                                                  AS delivered_orders,
    ROUND(100.0 * AVG(CASE WHEN so.is_late THEN 0 ELSE 1 END), 1) AS on_time_pct
FROM seller_orders AS so
JOIN dim_seller    AS s ON s.seller_key = so.seller_key
GROUP BY s.seller_id, s.state
HAVING COUNT(*) >= 100
ORDER BY on_time_pct
LIMIT 10;


-- name: q06_worst_categories_on_time
-- BQ2: Which categories have the worst on-time rate (min. 500 delivered orders)?
-- INSIGHT: Category barely matters: the 10 worst categories sit at 91.9-92.7% on-time vs 93.23% overall, a much narrower spread than across states (82.6-96.0%).
WITH cat_orders AS (
    SELECT DISTINCT p.category_en, f.order_id, f.is_late
    FROM fact_order_items AS i
    JOIN fact_orders      AS f ON f.order_id = i.order_id
    JOIN dim_product      AS p ON p.product_key = i.product_key
    WHERE f.is_delivered
)
SELECT
    category_en,
    COUNT(*)                                                   AS delivered_orders,
    ROUND(100.0 * AVG(CASE WHEN is_late THEN 0 ELSE 1 END), 1) AS on_time_pct
FROM cat_orders
GROUP BY category_en
HAVING COUNT(*) >= 500
ORDER BY on_time_pct
LIMIT 10;


-- name: q07_reviews_late_vs_on_time
-- BQ3: How much do late deliveries reduce review scores?
-- (statistical test follows in notebooks/01_eda.ipynb)
-- INSIGHT: Late orders average 2.27 stars vs 4.29 on time (-2.02); 62.4% of late orders get 1-2 stars vs 9.3% of on-time orders.
SELECT
    CASE WHEN is_late THEN 'late' ELSE 'on_time' END             AS delivery,
    COUNT(*)                                                     AS reviewed_orders,
    ROUND(AVG(review_score), 2)                                  AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 1) AS pct_1_2_stars,
    ROUND(100.0 * AVG(CASE WHEN review_score = 5 THEN 1 ELSE 0 END), 1)  AS pct_5_stars
FROM fact_orders
WHERE is_delivered AND review_score IS NOT NULL
GROUP BY 1
ORDER BY 1;


-- name: q08_reviews_by_delay
-- BQ3: Does satisfaction fall further the later the delivery?
-- INSIGHT: Damage starts immediately: just 1-3 days late drops the average to 3.29 (32.1% 1-2 stars); from 8+ days late about 80% of reviews are 1-2 stars.
SELECT
    CASE
        WHEN delay_days <= -10 THEN '1: 10+ days early'
        WHEN delay_days <=   0 THEN '2: 0-9 days early / on day'
        WHEN delay_days <=   3 THEN '3: 1-3 days late'
        WHEN delay_days <=   7 THEN '4: 4-7 days late'
        WHEN delay_days <=  14 THEN '5: 8-14 days late'
        ELSE                        '6: 15+ days late'
    END                                                          AS delay_bucket,
    COUNT(*)                                                     AS reviewed_orders,
    ROUND(AVG(review_score), 2)                                  AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 1) AS pct_1_2_stars
FROM fact_orders
WHERE is_delivered AND review_score IS NOT NULL
GROUP BY 1
ORDER BY 1;


-- name: q09_seller_pareto
-- BQ4: What share of sellers generates 80% of revenue?
-- INSIGHT: Classic Pareto: 533 of 2,970 sellers (17.9%) generate 80% of revenue; the top 20% of sellers generate 82.3%.
WITH seller_rev AS (
    SELECT i.seller_key, SUM(i.price) AS revenue
    FROM fact_order_items AS i
    JOIN fact_orders      AS f ON f.order_id = i.order_id
    WHERE f.is_delivered
    GROUP BY i.seller_key
),
ranked AS (
    SELECT
        revenue,
        ROW_NUMBER() OVER (ORDER BY revenue DESC)                          AS seller_rank,
        COUNT(*) OVER ()                                                   AS n_sellers,
        SUM(revenue) OVER (ORDER BY revenue DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / SUM(revenue) OVER ()                                         AS cum_share
    FROM seller_rev
)
SELECT
    MAX(n_sellers)                                                   AS sellers_with_revenue,
    MIN(seller_rank) FILTER (WHERE cum_share >= 0.8)                 AS sellers_for_80pct,
    ROUND(100.0 * MIN(seller_rank) FILTER (WHERE cum_share >= 0.8) / MAX(n_sellers), 1)
                                                                     AS pct_sellers_for_80pct,
    ROUND(100.0 * MAX(cum_share) FILTER (WHERE seller_rank <= 0.2 * n_sellers), 1)
                                                                     AS revenue_pct_top20_sellers
FROM ranked;


-- name: q10_repeat_customers
-- BQ5: What share of customers buy again? (customer_unique_id, delivered orders)
-- INSIGHT: Only 3.0% of customers (2,801 of 93,350) placed 2+ delivered orders, and they bring 5.51% of revenue: growth is acquisition-driven.
WITH per_person AS (
    SELECT customer_key, COUNT(*) AS n_orders, SUM(order_value) AS revenue
    FROM fact_orders
    WHERE is_delivered
    GROUP BY customer_key
)
SELECT
    COUNT(*)                                                        AS customers,
    COUNT(*) FILTER (WHERE n_orders >= 2)                           AS repeat_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE n_orders >= 2) / COUNT(*), 2) AS repeat_pct,
    ROUND(100.0 * SUM(revenue) FILTER (WHERE n_orders >= 2) / SUM(revenue), 2)
                                                                    AS repeat_revenue_pct,
    MAX(n_orders)                                                   AS max_orders_one_customer
FROM per_person;


-- name: q11_cohort_retention
-- BQ5: Of each monthly first-purchase cohort, what % ordered again by the end
-- of month +1, +3 and +6 after the cohort month? (cohorts 2017-01..2018-02,
-- so the full 6 months are observable before data ends in 2018-08)
-- INSIGHT: Repeat purchase within 6 months is 2.23-4.18% across the 2017-01..2018-02 cohorts (mean 3.03%): retention is weak, so the first delivery experience is decisive.
WITH orders AS (
    SELECT customer_key, purchase_ts
    FROM fact_orders
    WHERE is_delivered
),
first_order AS (
    SELECT customer_key, MIN(purchase_ts) AS first_ts
    FROM orders
    GROUP BY customer_key
),
returns AS (
    SELECT
        fo.customer_key,
        DATE_TRUNC('month', fo.first_ts)                              AS cohort,
        MIN(o.purchase_ts) FILTER (WHERE o.purchase_ts > fo.first_ts) AS next_ts
    FROM first_order AS fo
    JOIN orders      AS o USING (customer_key)
    GROUP BY fo.customer_key, fo.first_ts
)
SELECT
    STRFTIME(cohort, '%Y-%m')                                                         AS cohort,
    COUNT(*)                                                                          AS new_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE next_ts < cohort + INTERVAL 2 MONTH) / COUNT(*), 2) AS ret_by_m1_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE next_ts < cohort + INTERVAL 4 MONTH) / COUNT(*), 2) AS ret_by_m3_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE next_ts < cohort + INTERVAL 7 MONTH) / COUNT(*), 2) AS ret_by_m6_pct
FROM returns
WHERE cohort BETWEEN DATE '2017-01-01' AND DATE '2018-02-01'
GROUP BY cohort
ORDER BY cohort;


-- name: q12_payment_method
-- BQ6: Which payment methods do customers use, and how do they relate to
-- order value, approval time and delivery time? (payment METHOD only)
-- INSIGHT: Credit card is 75.5% of orders with the highest AOV (R$143.24); boleto's median approval takes 29.06 h vs 0.27 h for card, and boleto orders are late more often (7.32% vs 6.69%).
SELECT
    payment_type_main,
    COUNT(*)                                                        AS delivered_orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)              AS pct_orders,
    ROUND(AVG(order_value), 2)                                      AS avg_order_value,
    ROUND(MEDIAN(approval_hours), 2)                                AS median_approval_hours,
    ROUND(AVG(delivery_days), 1)                                    AS avg_delivery_days,
    ROUND(100.0 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END), 2)      AS late_pct
FROM fact_orders
WHERE is_delivered AND payment_type_main IS NOT NULL
GROUP BY payment_type_main
ORDER BY delivered_orders DESC;
