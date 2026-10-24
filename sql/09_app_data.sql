-- =====================================================================
-- 09_app_data.sql: small extracts for the Streamlit app (app/data/*.parquet, committed)
-- Run by scripts/export_app_data.py. The month x state KPI extract reuses
-- excel_monthly_state from 08_excel_report.sql (one definition, already reconciled).
-- Extracts hold additive counts and sums, so the app rebuilds every ratio as sum / sum
-- for any year or state filter (same rule as the Excel report).
-- =====================================================================


-- name: app_delay_reviews
-- Reviewed delivered orders by purchase month x customer state x delivery-delay bucket
-- (the same buckets as SQL q08 and the Power BI delay chart).
SELECT
    strftime(f.purchase_ts, '%Y-%m')                     AS year_month,
    year(f.purchase_ts)                                  AS year,
    c.state                                              AS customer_state,
    CASE
        WHEN f.delay_days <= -10 THEN '10+ days early'
        WHEN f.delay_days <=   0 THEN '0-9 days early'
        WHEN f.delay_days <=   3 THEN '1-3 days late'
        WHEN f.delay_days <=   7 THEN '4-7 days late'
        WHEN f.delay_days <=  14 THEN '8-14 days late'
        ELSE                          '15+ days late'
    END                                                  AS delay_bucket,
    COUNT(*)                                             AS reviews,
    SUM(f.review_score)                                  AS review_sum,
    COUNT(*) FILTER (WHERE f.review_score <= 2)          AS low_ratings
FROM fact_orders  AS f
JOIN dim_customer AS c ON c.customer_key = f.customer_key
WHERE f.is_delivered AND f.review_score IS NOT NULL
GROUP BY ALL
ORDER BY year_month, customer_state, delay_bucket;
