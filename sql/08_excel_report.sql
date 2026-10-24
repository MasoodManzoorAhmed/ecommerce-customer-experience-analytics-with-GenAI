-- =====================================================================
-- 08_excel_report.sql: data sheets of the Excel monthly management report
-- Run by scripts/build_excel_report.py -> excel/Monthly_CX_Report.xlsx.
-- Excel gets pre-aggregated, additive counts and sums (not 100k raw rows): every ratio
-- in the workbook (on-time %, average review, AOV) is rebuilt from these by formulas,
-- so it stays correct after any filter, pivot or slicer.
-- Definitions match fact_orders and the Power BI measures:
--   delivered = is_delivered; revenue = item price of delivered orders (excl. freight);
--   on-time = delivered - late (is_late = TRUE); ratings use delivered orders with a review.
-- =====================================================================


-- name: excel_monthly_state
-- One row per purchase month x customer state (delivered orders only).
-- state_500_plus flags states with 500+ delivered orders over the whole period (the same
-- volume rule as SQL q04 and the Power BI state chart), used as a pivot filter.
WITH item_revenue AS (
    SELECT order_id, SUM(price) AS revenue
    FROM fact_order_items
    GROUP BY order_id
),
month_state AS (
SELECT
    strftime(f.purchase_ts, '%Y-%m')                                        AS year_month,
    year(f.purchase_ts)                                                     AS year,
    c.state                                                                 AS customer_state,
    COUNT(*)                                                                AS delivered_orders,
    COUNT(*) FILTER (WHERE f.is_late)                                       AS late_orders,
    COUNT(*) - COUNT(*) FILTER (WHERE f.is_late)                            AS on_time_orders,
    CAST(COALESCE(SUM(r.revenue), 0) AS DOUBLE)                             AS revenue,
    COUNT(f.delivery_days)                                                  AS delivery_days_n,
    COALESCE(SUM(f.delivery_days), 0)                                       AS delivery_days_sum,
    COUNT(f.review_score)                                                   AS reviews,
    COALESCE(SUM(f.review_score), 0)                                        AS review_sum,
    COUNT(f.review_score) FILTER (WHERE f.is_late = FALSE)                  AS reviews_on_time,
    COALESCE(SUM(f.review_score) FILTER (WHERE f.is_late = FALSE), 0)       AS review_sum_on_time,
    COUNT(f.review_score) FILTER (WHERE f.is_late)                          AS reviews_late,
    COALESCE(SUM(f.review_score) FILTER (WHERE f.is_late), 0)               AS review_sum_late,
    COUNT(*) FILTER (WHERE f.review_score <= 2 AND f.is_late = FALSE)       AS low_ratings_on_time,
    COUNT(*) FILTER (WHERE f.review_score <= 2 AND f.is_late)               AS low_ratings_late,
    COUNT(*) FILTER (WHERE f.review_score = 5 AND f.is_late = FALSE)        AS five_stars_on_time,
    COUNT(*) FILTER (WHERE f.review_score = 5 AND f.is_late)                AS five_stars_late
FROM fact_orders       AS f
JOIN dim_customer      AS c ON c.customer_key = f.customer_key
LEFT JOIN item_revenue AS r ON r.order_id = f.order_id
WHERE f.is_delivered
GROUP BY ALL
)
SELECT
    *,
    CASE WHEN SUM(delivered_orders) OVER (PARTITION BY customer_state) >= 500
         THEN 'yes' ELSE 'no' END AS state_500_plus
FROM month_state
ORDER BY year_month, customer_state;


-- name: excel_category
-- One row per purchase month x customer state x product category (delivered orders only).
-- orders = orders containing the category (an order with two categories counts in both,
-- so orders are NOT additive across categories; revenue and items are).
SELECT
    strftime(f.purchase_ts, '%Y-%m')         AS year_month,
    year(f.purchase_ts)                      AS year,
    c.state                                  AS customer_state,
    p.category_en                            AS category,
    COUNT(DISTINCT i.order_id)               AS orders,
    COUNT(*)                                 AS items,
    CAST(SUM(i.price) AS DOUBLE)             AS revenue
FROM fact_order_items AS i
JOIN fact_orders      AS f ON f.order_id = i.order_id
JOIN dim_customer     AS c ON c.customer_key = f.customer_key
JOIN dim_product      AS p ON p.product_key = i.product_key
WHERE f.is_delivered
GROUP BY ALL
ORDER BY year_month, customer_state, category;
