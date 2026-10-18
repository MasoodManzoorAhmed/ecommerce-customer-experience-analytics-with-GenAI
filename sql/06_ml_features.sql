-- =====================================================================
-- 06_ml_features.sql: raw inputs for the late-delivery model (src/features.py)
-- Rule: every column in ml_orders must be KNOWN AT PURCHASE TIME, except the
-- target is_late. Delivery/carrier dates, review fields and approval time are
-- deliberately not selected (see src/features.FORBIDDEN_COLUMNS).
-- =====================================================================


-- name: ml_orders
-- One row per delivered order purchased 2017-01..2018-08 (usable window from the audit).
-- Multi-seller orders use the PRIMARY seller = seller of the highest-priced item
-- (ties -> lowest order_item_id); n_sellers keeps the multi-seller information.
WITH item_rank AS (
    SELECT
        i.order_id,
        i.seller_key,
        i.product_key,
        ROW_NUMBER() OVER (PARTITION BY i.order_id ORDER BY i.price DESC, i.order_item_id) AS rn
    FROM fact_order_items AS i
),
order_physical AS (
    SELECT
        i.order_id,
        SUM(p.weight_g)   AS total_weight_g,
        SUM(p.volume_cm3) AS total_volume_cm3
    FROM fact_order_items AS i
    JOIN dim_product      AS p ON p.product_key = i.product_key
    GROUP BY i.order_id
)
SELECT
    f.order_id,
    f.purchase_ts,
    f.promised_days,
    f.order_value,
    f.freight_value,
    f.n_items,
    f.n_sellers,
    f.payment_type_main,
    c.state            AS customer_state,
    c.lat              AS customer_lat,
    c.lng              AS customer_lng,
    s.seller_key,
    s.state            AS seller_state,
    s.lat              AS seller_lat,
    s.lng              AS seller_lng,
    p.category_en      AS primary_category,
    op.total_weight_g,
    op.total_volume_cm3,
    f.is_late          -- TARGET (only label; never a feature)
FROM fact_orders    AS f
JOIN dim_customer   AS c  ON c.customer_key = f.customer_key
JOIN item_rank      AS ir ON ir.order_id = f.order_id AND ir.rn = 1
JOIN dim_seller     AS s  ON s.seller_key = ir.seller_key
JOIN dim_product    AS p  ON p.product_key = ir.product_key
JOIN order_physical AS op ON op.order_id = f.order_id
WHERE f.is_delivered
  AND f.purchase_ts >= TIMESTAMP '2017-01-01'
  AND f.purchase_ts <  TIMESTAMP '2018-09-01'
ORDER BY f.purchase_ts, f.order_id;


-- name: ml_seller_events
-- Every (seller, order) pair, any status, with purchase and delivery times.
-- Used ONLY to build seller history: an event counts for a later order only if it
-- happened strictly before that order's purchase (src/features.add_seller_history).
SELECT DISTINCT
    i.seller_key,
    f.order_id,
    f.purchase_ts,
    CASE WHEN f.is_delivered THEN f.delivered_customer_ts END AS delivered_ts,
    f.is_late
FROM fact_order_items AS i
JOIN fact_orders      AS f ON f.order_id = i.order_id;
