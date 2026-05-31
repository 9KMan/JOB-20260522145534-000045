-- ============================================================
-- Metric Store SQL DataFlow Template
-- Canonical metric calculation for consistent reporting
-- ============================================================
--
-- This template creates a SQL DataFlow that produces a canonical
-- metrics_store dataset. Each metric should have its own DataFlow
-- following this pattern.
--
-- Benefits:
-- - Single source of truth for each metric
-- - One fix propagates to all downstream cards
-- - Clear audit trail for metric lineage
-- - Consistent definitions across all dashboards
--
-- ============================================================

-- INPUT: Raw source datasets (replace with actual dataset IDs)
-- ASSUMPTION: Raw data contains date, region, and metric columns

-- ============================================================
-- METRIC: weekly_revenue
-- Definition: Total revenue per ISO week (Monday-Sunday)
-- Owner: [SET OWNER]
-- Refresh Schedule: Daily at 6 AM
-- Last Verified: [SET DATE]
-- ============================================================

CREATE OR REPLACE TABLE metrics_store AS

WITH source_data AS (
    -- Step 1: Select and prepare source data
    -- Replace 'raw_revenue_data' with actual dataset name/ID
    SELECT
        transaction_date AS date_col,
        region,
        category,
        revenue,
        customer_id
    FROM raw_revenue_data
    WHERE transaction_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
),

iso_week_aligned AS (
    -- Step 2: ISO Week Alignment
    -- Aligns dates to Monday start (ISO week standard)
    -- DOMO default is Sunday start, so we adjust
    SELECT
        *,
        CASE
            WHEN DAYOFWEEK(date_col) = 1
            THEN DATE_SUB(date_col, INTERVAL 6 DAY)
            ELSE DATE_SUB(date_col, INTERVAL (DAYOFWEEK(date_col) - 2) DAY)
        END AS dimension_week
    FROM source_data
),

aggregated AS (
    -- Step 3: Aggregate by ISO week and dimensions
    SELECT
        dimension_week,
        COALESCE(region, 'Unknown') AS dimension_region,
        COALESCE(category, 'All') AS dimension_category,
        SUM(revenue) AS metric_value,
        COUNT(DISTINCT customer_id) AS customer_count,
        COUNT(*) AS transaction_count,
        CURRENT_TIMESTAMP() AS etl_timestamp
    FROM iso_week_aligned
    GROUP BY
        dimension_week,
        dimension_region,
        dimension_category
)

-- Step 4: Final output with metadata
SELECT
    'weekly_revenue' AS metric_key,
    'Weekly Revenue' AS metric_name,
    metric_value,
    dimension_week,
    dimension_region,
    dimension_category,
    customer_count,
    transaction_count,
    etl_timestamp,
    'REPLACE_WITH_DATAFLOW_ID' AS dataflow_id,
    FALSE AS verified
FROM aggregated
ORDER BY dimension_week DESC, dimension_region, dimension_category
;

-- ============================================================
-- Verification Queries (for testing)
-- ============================================================

-- Check recent weeks
-- SELECT
--     dimension_week,
--     dimension_region,
--     SUM(metric_value) AS total_revenue
-- FROM metrics_store
-- WHERE metric_key = 'weekly_revenue'
-- GROUP BY dimension_week, dimension_region
-- ORDER BY dimension_week DESC
-- LIMIT 10
-- ;

-- Compare to source
-- SELECT
--     a.dimension_week,
--     a.dimension_region,
--     a.metric_value AS metrics_store_value,
--     b.source_value,
--     a.metric_value - b.source_value AS variance
-- FROM (
--     SELECT dimension_week, dimension_region, SUM(metric_value) AS metric_value
--     FROM metrics_store
--     GROUP BY dimension_week, dimension_region
-- ) a
-- JOIN (
--     SELECT
--         CASE
--             WHEN DAYOFWEEK(transaction_date) = 1
--             THEN DATE_SUB(transaction_date, INTERVAL 6 DAY)
--             ELSE DATE_SUB(transaction_date, INTERVAL (DAYOFWEEK(transaction_date) - 2) DAY)
--         END AS dimension_week,
--         COALESCE(region, 'Unknown') AS dimension_region,
--         SUM(revenue) AS source_value
--     FROM raw_revenue_data
--     GROUP BY dimension_week, dimension_region
-- ) b ON a.dimension_week = b.dimension_week AND a.dimension_region = b.dimension_region
-- ;

-- ============================================================
-- Common Metric Variations
-- ============================================================

-- ACTIVE CUSTOMERS (COUNT_DISTINCT with COALESCE)
-- SELECT
--     dimension_week,
--     COALESCE(region, 'Unknown') AS dimension_region,
--     COUNT(DISTINCT customer_id) AS active_customers
-- FROM your_data
-- GROUP BY dimension_week, dimension_region
-- ;

-- AVERAGE ORDER VALUE
-- SELECT
--     dimension_week,
--     COALESCE(region, 'Unknown') AS dimension_region,
--     SUM(revenue) / NULLIF(COUNT(*), 0) AS avg_order_value
-- FROM your_data
-- GROUP BY dimension_week, dimension_region
-- ;

-- CONVERSION RATE
-- SELECT
--     dimension_week,
--     COALESCE(region, 'Unknown') AS dimension_region,
--     SUM(conversions) / NULLIF(SUM(visits), 0) * 100 AS conversion_rate
-- FROM your_data
-- GROUP BY dimension_week, dimension_region
-- ;
