-- =====================================================================
-- 07_powerbi_export.sql: tables exported to Parquet for the Power BI report
-- Run by scripts/export_powerbi.py -> data/powerbi/<name>.parquet (git-ignored).
-- Power BI model (all relationships many-to-one, single direction):
--   dim_date     1 -> * fact_orders       (date_key = purchase_date_key)
--   dim_customer 1 -> * fact_orders       (customer_key)
--   fact_orders  1 -> * fact_order_items  (order_id)   order header -> order lines
--   dim_product  1 -> * fact_order_items  (product_key)
--   dim_seller   1 -> * fact_order_items  (seller_key)
-- Money is DECIMAL(18,2) (Power BI "fixed decimal"); definitions match fact_orders.
-- =====================================================================


-- name: dim_date
SELECT * FROM dim_date ORDER BY date_key;


-- name: dim_customer
SELECT customer_key, customer_unique_id, city, state, lat, lng, first_purchase_date, n_orders
FROM dim_customer;


-- name: dim_seller
SELECT seller_key, seller_id, city, state, lat, lng
FROM dim_seller;


-- name: dim_product
SELECT product_key, product_id, category_en, weight_g, volume_cm3, photos_qty
FROM dim_product;


-- name: fact_orders
-- One row per order (all 99,441). Model scores from fact_order_risk are joined in
-- (NULL for orders the model didn't score: undelivered or outside 2017-01..2018-08).
-- delay_bucket uses the same buckets as sql/04_business_queries.sql q08.
SELECT
    f.order_id,
    f.customer_key,
    f.purchase_date_key,
    f.purchase_ts::DATE                       AS purchase_date,
    f.order_status,
    f.is_delivered,
    f.is_late,
    f.delivery_days,
    f.promised_days,
    f.delay_days,
    CASE
        WHEN NOT f.is_delivered     THEN NULL
        WHEN f.delay_days <= -10    THEN '1: 10+ days early'
        WHEN f.delay_days <=   0    THEN '2: 0-9 days early / on day'
        WHEN f.delay_days <=   3    THEN '3: 1-3 days late'
        WHEN f.delay_days <=   7    THEN '4: 4-7 days late'
        WHEN f.delay_days <=  14    THEN '5: 8-14 days late'
        ELSE                             '6: 15+ days late'
    END                                       AS delay_bucket,
    f.approval_hours,
    CAST(f.order_value   AS DECIMAL(18, 2))   AS order_value,
    CAST(f.freight_value AS DECIMAL(18, 2))   AS freight_value,
    f.n_items,
    f.n_sellers,
    f.payment_type_main,
    f.review_score,
    f.has_comment,
    f.dq_flags,
    r.late_probability,
    r.risk_band,
    r.split                                   AS model_split
FROM fact_orders AS f
LEFT JOIN fact_order_risk AS r ON r.order_id = f.order_id;


-- name: fact_order_items
SELECT
    order_id,
    order_item_id,
    product_key,
    seller_key,
    CAST(price         AS DECIMAL(18, 2)) AS price,
    CAST(freight_value AS DECIMAL(18, 2)) AS freight_value
FROM fact_order_items;
