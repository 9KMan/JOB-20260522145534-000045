"""
Metric Store Pattern Module

Provides templates and utilities for creating canonical metric DataFlows
in DOMO using SQL DataFlows for reusable, auditable business metrics.
"""

from typing import Optional, Dict, Any, List


# SQL DataFlow template for canonical metrics store
METRIC_STORE_SQLFLOW_TEMPLATE = """
-- ============================================================
-- Metric Store SQL DataFlow Template
-- Canonical metric calculation for consistent reporting
-- ============================================================

-- Input: Raw source datasets
-- Output: metrics_store dataset with canonical metrics

-- Step 1: Source Data (replace with actual dataset IDs/names)
-- ASSUMPTION: Raw data contains date, region, and metric columns

-- Step 2: ISO Week Alignment
-- Aligns dates to ISO week (Monday start) for consistent week-over-week comparison
-- Uses WEEK(date, 1) for Monday-start weeks

-- Step 3: Metric Aggregation
-- Calculate the canonical metric value per dimension

-- Step 4: Output to metrics_store

-- ============================================================
-- METRIC: {metric_name}
-- Definition: {metric_definition}
-- Owner: {owner}
-- Refresh Schedule: {refresh_schedule}
-- ============================================================

CREATE OR REPLACE TABLE metrics_store AS
SELECT
    -- Dimension: ISO Week (Monday start)
    CASE
        WHEN DAYOFWEEK(CAST(date_col AS DATE)) = 1
        THEN DATE_SUB(CAST(date_col AS DATE), INTERVAL 6 DAY)
        ELSE DATE_SUB(CAST(date_col AS DATE), INTERVAL (DAYOFWEEK(CAST(date_col AS DATE)) - 2) DAY)
    END AS dimension_week,

    -- Dimension: Region
    COALESCE(region, 'Unknown') AS dimension_region,

    -- Dimension: Product/Category (if applicable)
    COALESCE(category, 'All') AS dimension_category,

    -- Metric: {metric_name}
    {metric_formula} AS metric_value,

    -- Metadata
    CURRENT_TIMESTAMP() AS etl_timestamp,
    '{dataflow_id}' AS dataflow_id,
    '{metric_key}' AS metric_key,
    FALSE AS verified

FROM raw_source_data

-- Filter to relevant date range
WHERE date_col >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)

-- Group by dimensions
GROUP BY
    dimension_week,
    dimension_region,
    dimension_category
;


-- ============================================================
-- Verification Query (for testing)
-- ============================================================
-- SELECT
--     dimension_week,
--     dimension_region,
--     SUM(metric_value) AS total_value
-- FROM metrics_store
-- GROUP BY dimension_week, dimension_region
-- ORDER BY dimension_week DESC
;
"""


def create_metric_store_sqlflow_template(
    metric_name: str,
    metric_key: str,
    metric_formula: str,
    metric_definition: str,
    owner: str = "DOMO Admin",
    refresh_schedule: str = "Daily at 6 AM",
    dataflow_id: str = "REPLACE_WITH_ACTUAL_ID",
) -> str:
    """
    Generate a SQL DataFlow template for creating canonical metrics.

    Args:
        metric_name: Business-friendly name for the metric (e.g., 'Weekly Revenue')
        metric_key: Unique key for the metric (e.g., 'weekly_revenue')
        metric_formula: SQL formula for calculating the metric
        metric_definition: Business definition of the metric
        owner: Metric owner name
        refresh_schedule: When the metric should be refreshed
        dataflow_id: DOMO dataflow ID

    Returns:
        str: Complete SQL DataFlow template

    Example:
        >>> template = create_metric_store_sqlflow_template(
        ...     metric_name="Weekly Revenue",
        ...     metric_key="weekly_revenue",
        ...     metric_formula="SUM(revenue)",
        ...     metric_definition="Total revenue per ISO week"
        ... )
    """
    return METRIC_STORE_SQLFLOW_TEMPLATE.format(
        metric_name=metric_name,
        metric_key=metric_key,
        metric_formula=metric_formula,
        metric_definition=metric_definition,
        owner=owner,
        refresh_schedule=refresh_schedule,
        dataflow_id=dataflow_id,
    )


def generate_beast_mode_formula(
    metric_name: str,
    agg_type: str = "SUM",
    date_column: str = "date",
    value_column: str = "value",
    week_start: str = "monday",
) -> str:
    """
    Generate reusable Beast Mode formula templates.

    Args:
        metric_name: Name of the metric
        agg_type: Aggregation type (SUM, AVG, COUNT, MIN, MAX)
        date_column: Name of the date column
        value_column: Name of the value column to aggregate
        week_start: Week start day ('monday' or 'sunday')

    Returns:
        str: Beast Mode formula string

    Example:
        >>> formula = generate_beast_mode_formula(
        ...     metric_name="revenue",
        ...     agg_type="SUM",
        ...     value_column="revenue"
        ... )
    """
    # ISO week alignment for Monday start
    if week_start.lower() == "monday":
        week_align = (
            f"CASE WHEN DAYOFWEEK({date_column}) = 1 "
            f"THEN DATE_SUB({date_column}, INTERVAL 6 DAY) "
            f"ELSE DATE_SUB({date_column}, INTERVAL (DAYOFWEEK({date_column}) - 2) DAY) END"
        )
    else:  # Sunday start
        week_align = (
            f"CASE WHEN DAYOFWEEK({date_column}) = 1 "
            f"THEN {date_column} "
            f"ELSE DATE_SUB({date_column}, INTERVAL (DAYOFWEEK({date_column}) - 1) DAY) END"
        )

    # Aggregation templates
    agg_templates = {
        "SUM": f"SUM({value_column})",
        "AVG": f"AVG({value_column})",
        "COUNT": f"COUNT({value_column})",
        "MIN": f"MIN({value_column})",
        "MAX": f"MAX({value_column})",
        "COUNT_DISTINCT": f"COUNT(DISTINCT {value_column})",
    }

    agg_formula = agg_templates.get(agg_type.upper(), f"SUM({value_column})")

    # Full formula with ISO week alignment
    formula = f"""
-- {metric_name} Metric
-- Week starting: {week_start.upper()}
-- Aggregation: {agg_type}

{agg_formula}
"""
    return formula.strip()


def generate_iso_week_formula(date_column: str = "date", week_start: str = "monday") -> str:
    """
    Generate ISO week alignment formula for Beast Mode.

    ISO weeks start on Monday. This formula adjusts dates to align
    to the Monday of each ISO week.

    Args:
        date_column: Name of the date column
        week_start: 'monday' or 'sunday'

    Returns:
        str: SQL formula for ISO week alignment
    """
    if week_start.lower() == "monday":
        return (
            f"CASE WHEN DAYOFWEEK({date_column}) = 1 "
            f"THEN DATE_SUB({date_column}, INTERVAL 6 DAY) "
            f"ELSE DATE_SUB({date_column}, INTERVAL (DAYOFWEEK({date_column}) - 2) DAY) END"
        )
    else:
        return (
            f"CASE WHEN DAYOFWEEK({date_column}) = 1 "
            f"THEN {date_column} "
            f"ELSE DATE_SUB({date_column}, INTERVAL (DAYOFWEEK({date_column}) - 1) DAY) END"
        )


def generate_coalesce_agg(
    value_column: str,
    agg_type: str = "SUM",
    nullReplacement: int = 0,
) -> str:
    """
    Generate COALESCE aggregation template for null handling.

    DOMO sometimes treats NULL regions as excluded rather than zero.
    Use COALESCE to treat NULL as the specified replacement value.

    Args:
        value_column: Column to aggregate
        agg_type: Aggregation type (SUM, AVG, COUNT)
        nullReplacement: Value to use for NULLs (default 0)

    Returns:
        str: COALESCE aggregation formula
    """
    return f"COALESCE({agg_type}({value_column}), {nullReplacement})"


def generate_week_over_week_formula(
    metric_name: str,
    value_column: str = "value",
    date_column: str = "date",
) -> str:
    """
    Generate week-over-week comparison formula.

    Compares current week value to previous week value and
    calculates the percentage change.

    Args:
        metric_name: Name of the metric for labeling
        value_column: Column containing the metric value
        date_column: Date column name

    Returns:
        str: Week-over-week Beast Mode formula
    """
    return f"""
-- {metric_name} Week-over-Week Change
-- Current Week vs Previous Week

SUM({value_column}) /
SUM(CASE WHEN {date_column} >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
         AND {date_column} < DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
         THEN {value_column} ELSE 0 END)
- 1
"""


def get_metric_store_schema() -> Dict[str, Any]:
    """
    Get the recommended schema for a metrics_store dataset.

    Returns:
        Dict containing schema definition for metrics_store
    """
    return {
        "metric_key": {
            "type": "VARCHAR",
            "description": "Unique metric identifier (e.g., 'weekly_revenue')",
            "example": "weekly_revenue",
        },
        "metric_name": {
            "type": "VARCHAR",
            "description": "Business-friendly metric name",
            "example": "Weekly Revenue",
        },
        "metric_value": {
            "type": "DECIMAL",
            "description": "The calculated metric value",
            "example": "125000.50",
        },
        "dimension_week": {
            "type": "DATE",
            "description": "ISO week ending date (Monday)",
            "example": "2026-05-25",
        },
        "dimension_region": {
            "type": "VARCHAR",
            "description": "Regional breakdown",
            "example": "Northeast",
        },
        "dimension_category": {
            "type": "VARCHAR",
            "description": "Product/category breakdown",
            "example": "Enterprise",
        },
        "etl_timestamp": {
            "type": "TIMESTAMP",
            "description": "When the metric was calculated",
            "example": "2026-05-31 12:00:00",
        },
        "dataflow_id": {
            "type": "VARCHAR",
            "description": "Which dataflow produced this metric",
            "example": "abc123",
        },
        "verified": {
            "type": "BOOLEAN",
            "description": "Whether this metric has been verified against scorecard",
            "example": "true",
        },
    }


def get_audit_log_schema() -> Dict[str, Any]:
    """
    Get the schema for an audit_log dataset.

    Returns:
        Dict containing schema definition for audit_log
    """
    return {
        "run_id": {
            "type": "UUID",
            "description": "Unique run identifier",
            "example": "550e8400-e29b-41d4-a716-446655440000",
        },
        "metric_key": {
            "type": "VARCHAR",
            "description": "Which metric was audited",
            "example": "weekly_revenue",
        },
        "scorecard_value": {
            "type": "DECIMAL",
            "description": "Expected value from official scorecard",
            "example": "125000.00",
        },
        "domo_value": {
            "type": "DECIMAL",
            "description": "Actual value from DOMO card",
            "example": "124500.00",
        },
        "variance_pct": {
            "type": "DECIMAL",
            "description": "Percentage variance between scorecard and DOMO",
            "example": "0.4",
        },
        "fix_applied": {
            "type": "TEXT",
            "description": "Description of fix applied",
            "example": "Updated Beast Mode to use ISO week alignment",
        },
        "fixed_by": {
            "type": "VARCHAR",
            "description": "Who applied the fix",
            "example": "jsmith@company.com",
        },
        "fixed_at": {
            "type": "TIMESTAMP",
            "description": "When the fix was applied",
            "example": "2026-05-31 14:30:00",
        },
    }


def validate_metric_formula(formula: str) -> Dict[str, Any]:
    """
    Validate a metric formula for common issues.

    Args:
        formula: The formula string to validate

    Returns:
        Dict with validation results:
            - is_valid: bool
            - issues: List of issue descriptions
            - warnings: List of warning descriptions
    """
    issues = []
    warnings = []

    # Check for common problems
    if "NULL" in formula and "COALESCE" not in formula:
        warnings.append("Formula contains NULL but not COALESCE - NULLs may cause issues")

    if "JOIN" in formula.upper():
        if "LEFT JOIN" not in formula.upper() and "INNER JOIN" not in formula.upper():
            warnings.append("JOIN detected - verify join type matches scorecard logic")

    if "DAYOFWEEK" not in formula.upper() and "WEEK(" in formula.upper():
        warnings.append("WEEK() function used without DAYOFWEEK - verify week start alignment")

    # Check for aggregation
    has_agg = any(agg in formula.upper() for agg in ["SUM(", "AVG(", "COUNT(", "MIN(", "MAX("])
    if not has_agg:
        warnings.append("No aggregation function found - metric may not aggregate correctly")

    is_valid = len(issues) == 0

    return {
        "is_valid": is_valid,
        "issues": issues,
        "warnings": warnings,
    }
