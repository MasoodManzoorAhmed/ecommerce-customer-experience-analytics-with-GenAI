-- =====================================================================
-- 02_star_schema.sql: staging views -> star schema tables
-- Facts: fact_orders (1 row/order), fact_order_items (1 row/item)
-- Dims:  dim_customer, dim_seller, dim_product, dim_date
-- Business definitions here must match genai/semantic_layer.yaml and Power BI:
--   is_late       = delivered date > estimated delivery date (delivered orders only;
--                   compared on DATES because the estimate has no time of day)
--   delivery_days = delivered_customer_ts - purchase_ts, in days
--   promised_days = estimated_delivery_date - purchase date, in days
-- Surrogate keys are integers numbered in natural-id order, so they are
-- deterministic across rebuilds and compact for Power BI relationships.
-- =====================================================================


-- ---------------------------------------------------------------------
-- dim_date: 1 row per calendar day, from the first purchase month to the
-- end of the year of the latest date in the data (estimates reach 2018-11).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT
        DATE_TRUNC('month', MIN(purchase_ts))::DATE                         AS start_date,
        (DATE_TRUNC('year', GREATEST(MAX(estimated_delivery_date),
                                     MAX(delivered_customer_ts)::DATE))
            + INTERVAL 1 YEAR - INTERVAL 1 DAY)::DATE                      AS end_date
    FROM stg_orders
)
SELECT
    CAST(STRFTIME(d, '%Y%m%d') AS INTEGER) AS date_key,
    d::DATE                                AS date,
    YEAR(d)                                AS year,
    QUARTER(d)                             AS quarter,
    MONTH(d)                               AS month,
    STRFTIME(d, '%B')                      AS month_name,
    STRFTIME(d, '%Y-%m')                   AS year_month,
    WEEKOFYEAR(d)                          AS iso_week,
    ISODOW(d)                              AS weekday_num,   -- 1 = Monday
    STRFTIME(d, '%A')                      AS weekday_name,
    ISODOW(d) IN (6, 7)                    AS is_weekend
FROM bounds,
     GENERATE_SERIES(start_date, end_date, INTERVAL 1 DAY) AS t(d);


-- ---------------------------------------------------------------------
-- dim_customer: 1 row per REAL person (customer_unique_id), not per order.
-- A person can order from several addresses (39 people span >1 state);
-- the address of their most recent order is kept.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_customer AS
WITH orders_per_person AS (
    SELECT
        c.customer_unique_id,
        c.zip_prefix,
        c.city,
        c.state,
        o.purchase_ts,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY o.purchase_ts DESC, o.order_id
        ) AS rn,
        MIN(o.purchase_ts) OVER (PARTITION BY c.customer_unique_id) AS first_purchase_ts,
        COUNT(*)           OVER (PARTITION BY c.customer_unique_id) AS n_orders
    FROM stg_customers AS c
    JOIN stg_orders    AS o ON o.customer_id = c.customer_id
)
SELECT
    ROW_NUMBER() OVER (ORDER BY p.customer_unique_id) AS customer_key,
    p.customer_unique_id,
    p.zip_prefix,
    p.city,
    p.state,
    g.lat,
    g.lng,
    p.first_purchase_ts::DATE AS first_purchase_date,
    p.n_orders
FROM orders_per_person AS p
LEFT JOIN stg_geolocation AS g ON g.zip_prefix = p.zip_prefix
WHERE p.rn = 1;


-- ---------------------------------------------------------------------
-- dim_seller: 1 row per seller, with coordinates for distance features.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_seller AS
SELECT
    ROW_NUMBER() OVER (ORDER BY s.seller_id) AS seller_key,
    s.seller_id,
    s.zip_prefix,
    s.city,
    s.state,
    g.lat,
    g.lng
FROM stg_sellers AS s
LEFT JOIN stg_geolocation AS g ON g.zip_prefix = s.zip_prefix;


-- ---------------------------------------------------------------------
-- dim_product: 1 row per product; volume derived from the 3 dimensions.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_product AS
SELECT
    ROW_NUMBER() OVER (ORDER BY product_id) AS product_key,
    product_id,
    category_en,
    category_pt,
    weight_g,
    length_cm * height_cm * width_cm        AS volume_cm3,
    photos_qty,
    product_name_length,
    product_description_length
FROM stg_products;


-- ---------------------------------------------------------------------
-- fact_order_items: 1 row per order item, linked to product and seller keys.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    p.product_key,
    s.seller_key,
    i.price,
    i.freight_value,
    i.shipping_limit_ts
FROM stg_order_items AS i
JOIN dim_product AS p ON p.product_id = i.product_id
JOIN dim_seller  AS s ON s.seller_id  = i.seller_id;


-- ---------------------------------------------------------------------
-- fact_orders: 1 row per order (all 99,441, every status kept).
-- Items, payments and reviews are pre-aggregated to order grain and
-- LEFT JOINed so orders without them (775 without items) are not lost.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_orders AS
WITH items AS (
    SELECT
        order_id,
        SUM(price)                AS order_value,     -- excludes freight
        SUM(freight_value)        AS freight_value,
        COUNT(*)                  AS n_items,
        COUNT(DISTINCT seller_id) AS n_sellers
    FROM stg_order_items
    GROUP BY order_id
),
payments AS (
    -- payment METHOD with the largest amount; 188 orders tie on the max,
    -- broken by the earliest payment_sequential. Instalments are not used.
    SELECT
        order_id,
        ARG_MAX(payment_type, (payment_value, -payment_sequential)) AS payment_type_main,
        COUNT(DISTINCT payment_type)                                AS n_payment_methods,
        SUM(payment_value)                                          AS payment_total
    FROM stg_payments
    GROUP BY order_id
),
base AS (
    SELECT
        o.order_id,
        c.customer_key,
        CAST(STRFTIME(o.purchase_ts, '%Y%m%d') AS INTEGER) AS purchase_date_key,
        o.order_status,
        o.purchase_ts,
        o.approved_ts,
        o.delivered_carrier_ts,
        o.delivered_customer_ts,
        o.estimated_delivery_date,
        -- "delivered" = status delivered AND a delivery date exists
        (o.order_status = 'delivered' AND o.delivered_customer_ts IS NOT NULL) AS is_delivered,
        i.order_value,
        i.freight_value,
        i.n_items,
        i.n_sellers,
        p.payment_type_main,
        p.n_payment_methods,
        p.payment_total,
        r.review_score,
        r.has_comment
    FROM stg_orders          AS o
    JOIN stg_customers       AS sc ON sc.customer_id = o.customer_id
    JOIN dim_customer        AS c  ON c.customer_unique_id = sc.customer_unique_id
    LEFT JOIN items          AS i  ON i.order_id = o.order_id
    LEFT JOIN payments       AS p  ON p.order_id = o.order_id
    LEFT JOIN stg_reviews    AS r  ON r.order_id = o.order_id
)
SELECT
    order_id,
    customer_key,
    purchase_date_key,
    order_status,
    purchase_ts,
    approved_ts,
    delivered_carrier_ts,
    delivered_customer_ts,
    estimated_delivery_date,
    is_delivered,

    -- time measures (approval_hours is post-purchase: EDA only, never an ML feature)
    ROUND(DATE_DIFF('second', purchase_ts, approved_ts) / 3600.0, 2)            AS approval_hours,
    CASE WHEN is_delivered THEN
        ROUND(DATE_DIFF('second', purchase_ts, delivered_customer_ts) / 86400.0, 2)
    END                                                                          AS delivery_days,
    DATE_DIFF('day', purchase_ts::DATE, estimated_delivery_date)                AS promised_days,

    -- lateness, on DATES: delivered on the promised day = on time
    CASE WHEN is_delivered THEN
        delivered_customer_ts::DATE > estimated_delivery_date
    END                                                                          AS is_late,
    CASE WHEN is_delivered THEN
        DATE_DIFF('day', estimated_delivery_date, delivered_customer_ts::DATE)
    END                                                                          AS delay_days,  -- >0 late, <=0 on time

    order_value,
    freight_value,
    n_items,
    n_sellers,
    payment_type_main,
    n_payment_methods,
    review_score,
    has_comment,

    -- data-quality flags ('' = clean); sized and explained in the Day 2 audit
    CONCAT_WS(';',
        CASE WHEN order_status = 'delivered' AND delivered_customer_ts IS NULL
             THEN 'delivered_without_date' END,
        CASE WHEN order_status <> 'delivered' AND delivered_customer_ts IS NOT NULL
             THEN 'date_without_delivered_status' END,
        CASE WHEN delivered_carrier_ts < purchase_ts
             THEN 'carrier_before_purchase' END,
        CASE WHEN delivered_customer_ts < delivered_carrier_ts
             THEN 'customer_before_carrier' END,
        CASE WHEN n_items IS NULL       THEN 'no_items' END,
        CASE WHEN payment_type_main IS NULL THEN 'no_payment' END,
        CASE WHEN review_score IS NULL  THEN 'no_review' END,
        CASE WHEN ABS(payment_total - (order_value + freight_value)) > 1
             THEN 'payment_total_mismatch' END
    )                                                                            AS dq_flags
FROM base;
