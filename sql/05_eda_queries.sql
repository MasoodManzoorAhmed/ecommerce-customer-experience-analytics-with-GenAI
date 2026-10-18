-- =====================================================================
-- 05_eda_queries.sql: extracts for notebooks/01_eda.ipynb
-- Population rules come from docs/DATA_QUALITY_REPORT.md:
--   delivered orders only (is_delivered); trends limited to 2017-01..2018-08.
-- =====================================================================


-- name: eda_delivered_orders
-- One row per delivered order with the columns the EDA needs.
SELECT
    f.order_id,
    f.purchase_ts,
    d.year_month,
    c.state                AS customer_state,
    f.is_late,
    f.delay_days,
    f.delivery_days,
    f.promised_days,
    f.approval_hours,
    f.payment_type_main,
    f.review_score,
    f.has_comment,
    f.order_value,
    f.freight_value,
    f.dq_flags
FROM fact_orders  AS f
JOIN dim_customer AS c ON c.customer_key = f.customer_key
JOIN dim_date     AS d ON d.date_key = f.purchase_date_key
WHERE f.is_delivered;


-- name: eda_monthly_delivery
-- Late rate, promised vs actual delivery time per purchase month (usable window).
SELECT
    d.year_month,
    COUNT(*)                                     AS delivered_orders,
    ROUND(100.0 * AVG(f.is_late::INT), 2)        AS late_pct,
    ROUND(AVG(f.promised_days), 1)               AS avg_promised_days,
    ROUND(AVG(f.delivery_days), 1)               AS avg_delivery_days
FROM fact_orders AS f
JOIN dim_date    AS d ON d.date_key = f.purchase_date_key
WHERE f.is_delivered
  AND d.year_month BETWEEN '2017-01' AND '2018-08'
GROUP BY d.year_month
ORDER BY d.year_month;
