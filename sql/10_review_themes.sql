-- =====================================================================
-- 10_review_themes.sql: review texts for GenAI Module 2 (complaint themes)
-- Run by genai/review_themes/data.py.
-- Scope: reviews with written text and 1-3 stars (the business question is why customers
-- leave BAD reviews; praise is not a complaint). All order statuses are kept, so complaints
-- about orders that never arrived are included.
-- =====================================================================


-- name: low_score_reviews
SELECT
    r.review_id,
    r.order_id,
    r.review_score,
    r.comment_title,
    r.comment_message,
    f.order_status,
    f.is_delivered,
    f.is_late,
    f.delay_days,
    c.state                              AS customer_state,
    strftime(f.purchase_ts, '%Y-%m')     AS year_month
FROM stg_reviews       AS r
JOIN fact_orders       AS f ON f.order_id = r.order_id
JOIN dim_customer      AS c ON c.customer_key = f.customer_key
WHERE r.review_score <= 3
  AND r.comment_message IS NOT NULL
  AND length(trim(r.comment_message)) > 0
ORDER BY r.review_id;
