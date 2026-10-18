-- =====================================================================
-- 04_data_quality_checks.sql: the data-quality audit, one check per block
-- Run by src/data_quality.py (notebooks/00_data_quality_audit.ipynb).
-- Each check returns ONE row: affected (rows with the issue), base (denominator).
-- Metadata lines (-- table/issue/decision/action) are parsed into the audit table.
-- decision vocabulary:
--   FIX     = corrected in sql/01_staging.sql
--   FLAG    = kept, labelled in fact_orders.dq_flags or excluded by a stated filter
--   KEEP    = genuine business behaviour, no change
--   SCOPE   = deliberately out of scope
-- =====================================================================


-- ============================ ORDERS =================================

-- name: orders_not_delivered
-- table: orders
-- issue: Orders not in status 'delivered' (shipped, canceled, unavailable, invoiced, processing, created, approved)
-- decision: KEEP
-- action: Kept in fact_orders; delivery metrics use is_delivered only, revenue = delivered orders only.
SELECT COUNT(*) FILTER (WHERE order_status <> 'delivered') AS affected, COUNT(*) AS base
FROM stg_orders;

-- name: orders_missing_approved_ts
-- table: orders
-- issue: Missing approval timestamp (141 canceled, 5 created, 14 delivered)
-- decision: FLAG
-- action: Kept as NULL; approval_hours is NULL for these orders and excluded from approval-time averages.
SELECT COUNT(*) FILTER (WHERE approved_ts IS NULL) AS affected, COUNT(*) AS base
FROM stg_orders;

-- name: orders_missing_delivery_ts
-- table: orders
-- issue: Missing customer delivery date (mostly shipped / canceled / unavailable orders)
-- decision: KEEP
-- action: Expected for undelivered orders; is_late and delivery_days are NULL unless is_delivered.
SELECT COUNT(*) FILTER (WHERE delivered_customer_ts IS NULL) AS affected, COUNT(*) AS base
FROM stg_orders;

-- name: orders_delivered_without_date
-- table: orders
-- issue: Status 'delivered' but no customer delivery date
-- decision: FLAG
-- action: dq_flags 'delivered_without_date'; treated as not delivered (is_delivered = false), so excluded from is_late.
SELECT COUNT(*) FILTER (WHERE order_status = 'delivered' AND delivered_customer_ts IS NULL) AS affected,
       COUNT(*) FILTER (WHERE order_status = 'delivered') AS base
FROM stg_orders;

-- name: orders_date_without_delivered_status
-- table: orders
-- issue: Canceled orders that nevertheless have a customer delivery date
-- decision: FLAG
-- action: dq_flags 'date_without_delivered_status'; status wins, so not counted as delivered.
SELECT COUNT(*) FILTER (WHERE order_status <> 'delivered' AND delivered_customer_ts IS NOT NULL) AS affected,
       COUNT(*) FILTER (WHERE delivered_customer_ts IS NOT NULL) AS base
FROM stg_orders;

-- name: orders_carrier_before_purchase
-- table: orders
-- issue: Carrier pickup timestamp earlier than purchase timestamp (impossible sequence)
-- decision: FLAG
-- action: dq_flags 'carrier_before_purchase'; carrier date not used as an ML feature (post-purchase anyway).
SELECT COUNT(*) FILTER (WHERE delivered_carrier_ts < purchase_ts) AS affected,
       COUNT(*) FILTER (WHERE delivered_carrier_ts IS NOT NULL) AS base
FROM stg_orders;

-- name: orders_customer_before_carrier
-- table: orders
-- issue: Delivered to customer before carrier pickup (impossible sequence)
-- decision: FLAG
-- action: dq_flags 'customer_before_carrier'; kept for is_late (customer date is the target), excluded in sensitivity checks.
SELECT COUNT(*) FILTER (WHERE delivered_customer_ts < delivered_carrier_ts) AS affected,
       COUNT(*) FILTER (WHERE delivered_customer_ts IS NOT NULL AND delivered_carrier_ts IS NOT NULL) AS base
FROM stg_orders;

-- name: orders_approved_before_purchase
-- table: orders
-- issue: Approval earlier than purchase (checked, impossible sequence)
-- decision: KEEP
-- action: None found; check retained so a future data refresh would surface it.
SELECT COUNT(*) FILTER (WHERE approved_ts < purchase_ts) AS affected,
       COUNT(*) FILTER (WHERE approved_ts IS NOT NULL) AS base
FROM stg_orders;

-- name: orders_delivered_before_purchase
-- table: orders
-- issue: Customer delivery earlier than purchase (checked, impossible sequence)
-- decision: KEEP
-- action: None found; check retained.
SELECT COUNT(*) FILTER (WHERE delivered_customer_ts < purchase_ts) AS affected,
       COUNT(*) FILTER (WHERE delivered_customer_ts IS NOT NULL) AS base
FROM stg_orders;

-- name: orders_without_items
-- table: orders
-- issue: Orders with no rows in order_items (767 of them canceled or unavailable)
-- decision: FLAG
-- action: dq_flags 'no_items'; kept in fact_orders via LEFT JOIN; order_value is NULL.
SELECT COUNT(*) FILTER (WHERE n_items IS NULL) AS affected, COUNT(*) AS base
FROM fact_orders;

-- name: orders_without_payment
-- table: orders
-- issue: Orders with no payment record
-- decision: FLAG
-- action: dq_flags 'no_payment'; payment_type_main is NULL and excluded from payment analysis.
SELECT COUNT(*) FILTER (WHERE payment_type_main IS NULL) AS affected, COUNT(*) AS base
FROM fact_orders;

-- name: orders_without_review
-- table: orders
-- issue: Orders with no review
-- decision: FLAG
-- action: dq_flags 'no_review'; excluded from review-score analysis (no imputation).
SELECT COUNT(*) FILTER (WHERE review_score IS NULL) AS affected, COUNT(*) AS base
FROM fact_orders;

-- name: orders_thin_2016
-- table: orders
-- issue: 2016 has very few orders (Sep 4, Oct 324, Nov 0, Dec 1): platform ramp-up / incomplete extract
-- decision: FLAG
-- action: Time trends start 2017-01; time-based ML split uses 2017+ for training.
SELECT COUNT(*) FILTER (WHERE YEAR(purchase_ts) = 2016) AS affected, COUNT(*) AS base
FROM stg_orders;

-- name: orders_truncated_2018_09_on
-- table: orders
-- issue: Orders purchased from 2018-09 onward (only 20, almost all canceled): extract cut-off
-- decision: FLAG
-- action: Monthly trends end 2018-08; these months are not used for trends or model testing.
SELECT COUNT(*) FILTER (WHERE purchase_ts >= TIMESTAMP '2018-09-01') AS affected, COUNT(*) AS base
FROM stg_orders;

-- name: orders_delivery_over_60_days
-- table: orders
-- issue: Delivered orders taking more than 60 days (max about 210 days): extreme but plausible
-- decision: KEEP
-- action: Kept (real customer experience); use medians / robust stats in EDA.
SELECT COUNT(*) FILTER (WHERE delivery_days > 60) AS affected,
       COUNT(*) FILTER (WHERE is_delivered) AS base
FROM fact_orders;

-- name: orders_approval_over_7_days
-- table: orders
-- issue: Approval taking more than 7 days after purchase
-- decision: KEEP
-- action: Kept; medians used for approval time; approval_hours is EDA-only (not an ML feature).
SELECT COUNT(*) FILTER (WHERE approval_hours > 168) AS affected,
       COUNT(*) FILTER (WHERE approval_hours IS NOT NULL) AS base
FROM fact_orders;


-- ============================ ORDER ITEMS ============================

-- name: items_duplicate_key
-- table: order_items
-- issue: Duplicate (order_id, order_item_id) keys (checked)
-- decision: KEEP
-- action: None found.
SELECT COUNT(*) - COUNT(DISTINCT order_id || '-' || order_item_id) AS affected, COUNT(*) AS base
FROM stg_order_items;

-- name: items_free_freight
-- table: order_items
-- issue: Items with freight_value = 0 (free shipping)
-- decision: KEEP
-- action: Genuine free-shipping offers; kept. No items have price <= 0.
SELECT COUNT(*) FILTER (WHERE freight_value = 0) AS affected, COUNT(*) AS base
FROM stg_order_items;

-- name: items_multi_seller_orders
-- table: order_items
-- issue: Orders containing items from more than one seller
-- decision: KEEP
-- action: n_sellers stored; ML uses the primary seller (highest item value); seller rankings count the order for each seller.
SELECT COUNT(*) FILTER (WHERE n_sellers > 1) AS affected, COUNT(*) FILTER (WHERE n_items IS NOT NULL) AS base
FROM fact_orders;

-- name: items_high_value_orders
-- table: order_items
-- issue: Orders with item value above R$3,000 (max R$13,440)
-- decision: KEEP
-- action: Plausible high-ticket purchases; kept; medians reported alongside means.
SELECT COUNT(*) FILTER (WHERE order_value > 3000) AS affected, COUNT(*) FILTER (WHERE n_items IS NOT NULL) AS base
FROM fact_orders;


-- ============================ CUSTOMERS ==============================

-- name: customers_id_per_order
-- table: customers
-- issue: customer_id is created per order; the real person is customer_unique_id (extra ids = repeat orders)
-- decision: FIX
-- action: dim_customer built at customer_unique_id grain; repeat/cohort analysis uses it.
SELECT COUNT(*) - COUNT(DISTINCT customer_unique_id) AS affected, COUNT(*) AS base
FROM stg_customers;

-- name: customers_multiple_states
-- table: customers
-- issue: The same person (customer_unique_id) appears with addresses in more than one state
-- decision: FIX
-- action: dim_customer keeps the address of the most recent order.
SELECT COUNT(*) AS affected, (SELECT COUNT(DISTINCT customer_unique_id) FROM stg_customers) AS base
FROM (SELECT customer_unique_id FROM stg_customers GROUP BY 1 HAVING COUNT(DISTINCT state) > 1);

-- name: customers_zip_not_in_geolocation
-- table: customers
-- issue: Customer zip prefix has no coordinates (missing from source or only out-of-Brazil points)
-- decision: FLAG
-- action: lat/lng NULL in dim_customer; distance features will be NULL (LightGBM handles missing values natively).
SELECT COUNT(*) FILTER (WHERE lat IS NULL) AS affected, COUNT(*) AS base
FROM dim_customer;


-- ============================ PAYMENTS ===============================

-- name: payments_not_defined
-- table: order_payments
-- issue: payment_type = 'not_defined' (all with value 0)
-- decision: FLAG
-- action: Kept as its own category; too few to analyse (3 orders); excluded from method comparisons if needed.
SELECT COUNT(*) FILTER (WHERE payment_type = 'not_defined') AS affected, COUNT(*) AS base
FROM stg_payments;

-- name: payments_zero_value
-- table: order_payments
-- issue: Payment records with value 0 (6 voucher, 3 not_defined)
-- decision: KEEP
-- action: Zero-value vouchers are plausible; kept.
SELECT COUNT(*) FILTER (WHERE payment_value = 0) AS affected, COUNT(*) AS base
FROM stg_payments;

-- name: payments_total_mismatch
-- table: order_payments
-- issue: Order payment total differs from items + freight by more than R$1
-- decision: FLAG
-- action: dq_flags 'payment_total_mismatch'; revenue is defined from item prices, not payments, so unaffected.
SELECT COUNT(*) FILTER (WHERE dq_flags LIKE '%payment_total_mismatch%') AS affected,
       COUNT(*) FILTER (WHERE n_items IS NOT NULL AND payment_type_main IS NOT NULL) AS base
FROM fact_orders;

-- name: payments_instalments_excluded
-- table: order_payments
-- issue: payment_installments column present in source
-- decision: SCOPE
-- action: Not selected in stg_payments: the project analyses payment method only.
SELECT COUNT(*) AS affected, COUNT(*) AS base
FROM raw.order_payments;


-- ============================ REVIEWS ================================

-- name: reviews_multiple_per_order
-- table: order_reviews
-- issue: Orders with more than one review row
-- decision: FIX
-- action: stg_reviews keeps the most recently answered review per order (deterministic tie-breakers).
SELECT COUNT(*) AS affected, (SELECT COUNT(DISTINCT order_id) FROM raw.order_reviews) AS base
FROM (SELECT order_id FROM raw.order_reviews GROUP BY 1 HAVING COUNT(*) > 1);

-- name: reviews_id_shared_across_orders
-- table: order_reviews
-- issue: review_id is not unique: the same review_id is attached to several orders (rows affected)
-- decision: FIX
-- action: review_id is not used as a key; reviews are keyed by order_id.
SELECT COALESCE(SUM(n), 0) AS affected, (SELECT COUNT(*) FROM raw.order_reviews) AS base
FROM (SELECT review_id, COUNT(*) AS n FROM raw.order_reviews GROUP BY 1 HAVING COUNT(DISTINCT order_id) > 1);

-- name: reviews_no_comment_text
-- table: order_reviews
-- issue: Reviews with no comment text after cleaning (NULL, empty or whitespace only)
-- decision: KEEP
-- action: Score still used; theme classification (Module 2) runs only on reviews with text.
SELECT COUNT(*) FILTER (WHERE NOT has_comment) AS affected, COUNT(*) AS base
FROM stg_reviews;

-- name: reviews_whitespace_only_comment
-- table: order_reviews
-- issue: Comment present but whitespace only
-- decision: FIX
-- action: Trimmed and converted to NULL in stg_reviews.
SELECT COUNT(*) FILTER (WHERE review_comment_message IS NOT NULL AND TRIM(review_comment_message) = '') AS affected,
       COUNT(*) FILTER (WHERE review_comment_message IS NOT NULL) AS base
FROM raw.order_reviews;

-- name: reviews_comment_line_breaks
-- table: order_reviews
-- issue: Comments containing line breaks (break naive CSV/line parsing)
-- decision: FIX
-- action: Line breaks replaced by spaces in stg_reviews.
SELECT COUNT(*) FILTER (WHERE regexp_matches(review_comment_message, '[\r\n]')) AS affected,
       COUNT(*) FILTER (WHERE review_comment_message IS NOT NULL) AS base
FROM raw.order_reviews;

-- name: reviews_created_before_purchase
-- table: order_reviews
-- issue: Review creation date earlier than the purchase (impossible sequence)
-- decision: FLAG
-- action: Kept (score still valid); excluded from any review-timing analysis.
SELECT COUNT(*) FILTER (WHERE r.review_created_ts < o.purchase_ts) AS affected, COUNT(*) AS base
FROM stg_reviews AS r JOIN stg_orders AS o USING (order_id);

-- name: reviews_created_before_delivery
-- table: order_reviews
-- issue: Review created before the order was delivered (survey sent before arrival)
-- decision: KEEP
-- action: Real behaviour: customers can review undelivered parcels; relevant to 'never_arrived' theme in Module 2. Reviews are never ML features.
SELECT COUNT(*) FILTER (WHERE r.review_created_ts < o.delivered_customer_ts::DATE) AS affected,
       COUNT(*) AS base
FROM stg_reviews AS r JOIN stg_orders AS o USING (order_id)
WHERE o.delivered_customer_ts IS NOT NULL;

-- name: reviews_portuguese_text
-- table: order_reviews
-- issue: Review text is in Portuguese (all reviews with text)
-- decision: KEEP
-- action: Module 2 uses a multilingual model / LLM; no machine translation step.
SELECT COUNT(*) FILTER (WHERE has_comment) AS affected, COUNT(*) FILTER (WHERE has_comment) AS base
FROM stg_reviews;


-- ============================ PRODUCTS ===============================

-- name: products_missing_category
-- table: products
-- issue: Products with no category (also missing name/description length and photo count)
-- decision: FIX
-- action: category set to 'unknown' in stg_products; kept in all analyses.
SELECT COUNT(*) FILTER (WHERE product_category_name IS NULL) AS affected, COUNT(*) AS base
FROM raw.products;

-- name: products_untranslated_category
-- table: products
-- issue: Products whose category is missing from the translation file (pc_gamer, portateis_cozinha...)
-- decision: FIX
-- action: Two translations added explicitly in stg_products.
SELECT COUNT(*) AS affected, (SELECT COUNT(*) FROM raw.products) AS base
FROM raw.products AS p
LEFT JOIN raw.category_translation AS t USING (product_category_name)
WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL;

-- name: products_missing_dimensions
-- table: products
-- issue: Products with missing weight/size
-- decision: FLAG
-- action: Left NULL (LightGBM handles missing values); not imputed in SQL.
SELECT COUNT(*) FILTER (WHERE weight_g IS NULL OR length_cm IS NULL) AS affected, COUNT(*) AS base
FROM stg_products;

-- name: products_zero_weight
-- table: products
-- issue: Products with weight_g = 0 (physically implausible)
-- decision: FLAG
-- action: Kept; tiny count; treated as missing in ML feature engineering.
SELECT COUNT(*) FILTER (WHERE weight_g = 0) AS affected, COUNT(*) AS base
FROM stg_products;

-- name: products_column_typos
-- table: products
-- issue: Source column names misspelled ('product_name_lenght', 'product_description_lenght')
-- decision: FIX
-- action: Renamed to *_length in stg_products.
SELECT COUNT(*) AS affected,
       (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'raw' AND table_name = 'products') AS base
FROM information_schema.columns
WHERE table_schema = 'raw' AND table_name = 'products' AND column_name LIKE '%lenght%';


-- ============================ SELLERS ================================

-- name: sellers_zip_not_in_geolocation
-- table: sellers
-- issue: Seller zip prefix has no coordinates
-- decision: FLAG
-- action: lat/lng NULL in dim_seller; distance features NULL for those sellers.
SELECT COUNT(*) FILTER (WHERE lat IS NULL) AS affected, COUNT(*) AS base
FROM dim_seller;


-- ============================ GEOLOCATION ============================

-- name: geo_exact_duplicate_rows
-- table: geolocation
-- issue: Exact duplicate rows (same zip, lat, lng, city, state)
-- decision: FIX
-- action: Collapsed by aggregating to one row per zip prefix in stg_geolocation.
SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw.geolocation)) AS affected, COUNT(*) AS base
FROM raw.geolocation;

-- name: geo_multiple_rows_per_zip
-- table: geolocation
-- issue: Many coordinate rows per zip prefix (joining directly would multiply rows)
-- decision: FIX
-- action: One row per zip prefix (average lat/lng, most frequent city/state).
SELECT COUNT(*) - COUNT(DISTINCT geolocation_zip_code_prefix) AS affected, COUNT(*) AS base
FROM raw.geolocation;

-- name: geo_outside_brazil
-- table: geolocation
-- issue: Coordinates outside Brazil's bounding box (lat -34..5.3, lng -74..-34.8)
-- decision: FIX
-- action: Excluded before averaging; 5 zip prefixes had only such points and get no coordinates.
SELECT COUNT(*) FILTER (WHERE NOT (CAST(geolocation_lat AS DOUBLE) BETWEEN -34.0 AND 5.3
                               AND CAST(geolocation_lng AS DOUBLE) BETWEEN -74.0 AND -34.8)) AS affected,
       COUNT(*) AS base
FROM raw.geolocation;

-- name: geo_city_spelling_variants
-- table: customers
-- issue: Same customer zip prefix with more than one city spelling
-- decision: KEEP
-- action: City names are not used as join keys (state and zip are); left as is.
SELECT COUNT(*) AS affected, (SELECT COUNT(DISTINCT customer_zip_code_prefix) FROM raw.customers) AS base
FROM (SELECT customer_zip_code_prefix FROM raw.customers GROUP BY 1 HAVING COUNT(DISTINCT customer_city) > 1);
