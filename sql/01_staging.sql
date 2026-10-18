-- =====================================================================
-- 01_staging.sql: raw (all text) -> staging views (typed, cleaned)
-- Run by scripts/build_db.py after the raw CSVs are loaded.
-- Rules: one staging view per source table, no business logic here
-- (no is_late, no revenue); only types, names, de-duplication, text cleanup.
-- Rows are not dropped here; data-quality flags are added in the audit / star schema.
-- =====================================================================


-- ---------------------------------------------------------------------
-- stg_orders: 1 row per order. Parse the 5 timestamps.
-- NULL timestamps are kept (e.g. 2,965 orders have no delivery date
-- because they were cancelled, unavailable or still in transit).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    CAST(order_purchase_timestamp      AS TIMESTAMP) AS purchase_ts,
    CAST(order_approved_at             AS TIMESTAMP) AS approved_ts,
    CAST(order_delivered_carrier_date  AS TIMESTAMP) AS delivered_carrier_ts,
    CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_customer_ts,
    -- the source stores the estimate as a date at 00:00:00, so keep it as a DATE
    CAST(order_estimated_delivery_date AS DATE)      AS estimated_delivery_date
FROM raw.orders;


-- ---------------------------------------------------------------------
-- stg_order_items: 1 row per (order_id, order_item_id).
-- Money as DECIMAL(10,2), not DOUBLE, so sums don't pick up float noise.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_order_items AS
SELECT
    order_id,
    CAST(order_item_id AS INTEGER)         AS order_item_id,
    product_id,
    seller_id,
    CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
    CAST(price         AS DECIMAL(10, 2))  AS price,
    CAST(freight_value AS DECIMAL(10, 2))  AS freight_value
FROM raw.order_items;


-- ---------------------------------------------------------------------
-- stg_customers: 1 row per customer_id (which is per ORDER in Olist).
-- customer_unique_id identifies the real person; use it for repeat-customer work.
-- Zip prefix stays TEXT: '01037' must not become 1037.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix AS zip_prefix,
    customer_city            AS city,
    customer_state           AS state
FROM raw.customers;


-- ---------------------------------------------------------------------
-- stg_payments: 1 row per payment record (an order can have several,
-- e.g. card + voucher). Payment METHOD only: payment_installments is
-- deliberately not selected (project rule: no instalment/credit analysis).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_payments AS
SELECT
    order_id,
    CAST(payment_sequential AS INTEGER)       AS payment_sequential,
    payment_type,
    CAST(payment_value      AS DECIMAL(10, 2)) AS payment_value
FROM raw.order_payments;


-- ---------------------------------------------------------------------
-- stg_reviews: exactly 1 review per order.
-- 547 orders have more than one review; keep the most recently answered
-- one (review_creation_date and review_id break any ties deterministically).
-- Comment text: line breaks -> spaces, trimmed, empty/whitespace -> NULL.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_reviews AS
WITH cleaned AS (
    SELECT
        review_id,
        order_id,
        CAST(review_score            AS INTEGER)   AS review_score,
        NULLIF(TRIM(regexp_replace(review_comment_title,   '[\r\n]+', ' ', 'g')), '')
                                                   AS comment_title,
        NULLIF(TRIM(regexp_replace(review_comment_message, '[\r\n]+', ' ', 'g')), '')
                                                   AS comment_message,
        CAST(review_creation_date    AS TIMESTAMP) AS review_created_ts,
        CAST(review_answer_timestamp AS TIMESTAMP) AS review_answered_ts
    FROM raw.order_reviews
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY review_answered_ts DESC, review_created_ts DESC, review_id
        ) AS rn
    FROM cleaned
)
SELECT
    review_id,
    order_id,
    review_score,
    comment_title,
    comment_message,
    comment_message IS NOT NULL AS has_comment,
    review_created_ts,
    review_answered_ts
FROM ranked
WHERE rn = 1;


-- ---------------------------------------------------------------------
-- stg_products: 1 row per product, English category names, typo-free columns.
-- The translation file is missing 2 categories; they are added here
-- explicitly. 610 products have no category at all -> 'unknown'.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_products AS
WITH translation AS (
    SELECT product_category_name, product_category_name_english
    FROM raw.category_translation
    UNION ALL
    SELECT * FROM (VALUES
        ('pc_gamer',                                      'pc_gamer'),
        ('portateis_cozinha_e_preparadores_de_alimentos', 'portable_kitchen_food_preparers')
    ) AS missing(product_category_name, product_category_name_english)
)
SELECT
    p.product_id,
    COALESCE(p.product_category_name, 'unknown')           AS category_pt,
    COALESCE(t.product_category_name_english, 'unknown')   AS category_en,
    CAST(p.product_name_lenght        AS INTEGER) AS product_name_length,
    CAST(p.product_description_lenght AS INTEGER) AS product_description_length,
    CAST(p.product_photos_qty         AS INTEGER) AS photos_qty,
    CAST(p.product_weight_g           AS INTEGER) AS weight_g,
    CAST(p.product_length_cm          AS INTEGER) AS length_cm,
    CAST(p.product_height_cm          AS INTEGER) AS height_cm,
    CAST(p.product_width_cm           AS INTEGER) AS width_cm
FROM raw.products AS p
LEFT JOIN translation AS t
    ON p.product_category_name = t.product_category_name;


-- ---------------------------------------------------------------------
-- stg_sellers: 1 row per seller.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix AS zip_prefix,
    seller_city            AS city,
    seller_state           AS state
FROM raw.sellers;


-- ---------------------------------------------------------------------
-- stg_geolocation: 1 row per zip prefix (1,000,163 raw rows -> 19,010 prefixes).
-- Points outside Brazil's bounding box (47 rows) are excluded before
-- averaging so a few bad coordinates can't drag a zip's centre abroad.
-- 5 prefixes had ONLY out-of-box points and therefore drop out (their
-- customers/sellers get NULL lat/lng, like zips missing from the source).
-- City/state = the most frequent value for that prefix.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_geolocation AS
WITH typed AS (
    SELECT
        geolocation_zip_code_prefix          AS zip_prefix,
        CAST(geolocation_lat AS DOUBLE)      AS lat,
        CAST(geolocation_lng AS DOUBLE)      AS lng,
        geolocation_city                     AS city,
        geolocation_state                    AS state
    FROM raw.geolocation
)
SELECT
    zip_prefix,
    AVG(lat)     AS lat,
    AVG(lng)     AS lng,
    MODE(city)   AS city,
    MODE(state)  AS state,
    COUNT(*)     AS n_points
FROM typed
WHERE lat BETWEEN -34.0 AND 5.3
  AND lng BETWEEN -74.0 AND -34.8
GROUP BY zip_prefix;
