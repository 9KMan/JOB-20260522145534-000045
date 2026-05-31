"""
Beast Mode Formula Templates Module

Provides reusable Beast Mode formula templates for common calculations,
including ISO week alignment, COALESCE null handling, and join type detection.
"""

from typing import Optional, Dict, Any, List


# ISO Week alignment formula for Monday start
# This ensures dates align to Monday-Sunday weeks instead of DOMO default Sunday-Saturday
ISO_WEEK_ALIGN_MONDAY = """
CASE
    WHEN DAYOFWEEK({date_column}) = 1
    THEN DATE_SUB({date_column}, INTERVAL 6 DAY)
    ELSE DATE_SUB({date_column}, INTERVAL (DAYOFWEEK({date_column}) - 2) DAY)
END
"""

# ISO Week alignment for Sunday start (DOMO default)
ISO_WEEK_ALIGN_SUNDAY = """
CASE
    WHEN DAYOFWEEK({date_column}) = 1
    THEN {date_column}
    ELSE DATE_SUB({date_column}, INTERVAL (DAYOFWEEK({date_column}) - 1) DAY)
END
"""

# COALESCE null handling for SUM aggregations
# Use when NULL regions should be treated as 0
COALESCE_SUM_TEMPLATE = "COALESCE(SUM({column}), 0)"

# COALESCE for AVG - treats NULL as excluded from average
COALESCE_AVG_TEMPLATE = "COALESCE(AVG({column}), 0)"

# COALESCE for COUNT - treats NULL as 0 count
COALESCE_COUNT_TEMPLATE = "COALESCE(COUNT({column}), 0)"

# Week-over-Week comparison formula
WEEK_OVER_WEEK_TEMPLATE = """
SUM({value_column}) /
    SUM(CASE
        WHEN {date_column} >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
        AND {date_column} < DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        THEN {value_column}
        ELSE 0
    END)
- 1
"""

# Month-over-Month comparison formula
MONTH_OVER_MONTH_TEMPLATE = """
SUM({value_column}) /
    SUM(CASE
        WHEN {date_column} >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)
        AND {date_column} < DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        THEN {value_column}
        ELSE 0
    END)
- 1
"""

# Year-over-Year comparison formula
YEAR_OVER_YEAR_TEMPLATE = """
SUM({value_column}) /
    SUM(CASE
        WHEN {date_column} >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
        AND {date_column} < DATE_SUB(CURRENT_DATE(), INTERVAL 364 DAY)
        THEN {value_column}
        ELSE 0
    END)
- 1
"""

# Running total (cumulative sum)
RUNNING_TOTAL_TEMPLATE = """
SUM(SUM({value_column})) OVER (ORDER BY {date_column} ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
"""

# Moving average (7 day)
MOVING_AVG_7DAY_TEMPLATE = """
AVG(SUM({value_column})) OVER (ORDER BY {date_column} ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
"""

# Period-to-date (week to date)
WEEK_TO_DATE_TEMPLATE = """
SUM(CASE
    WHEN {date_column} >= DATE_SUB(CURRENT_DATE(), INTERVAL (DAYOFWEEK(CURRENT_DATE()) - 1) DAY)
    THEN {value_column}
    ELSE 0
END)
"""

# Same period last year comparison
SAME_PERIOD_LAST_YEAR_TEMPLATE = """
SUM(CASE
    WHEN {date_column} >= DATE_SUB(CURRENT_DATE(), INTERVAL 371 DAY)
    AND {date_column} < DATE_SUB(CURRENT_DATE(), INTERVAL 364 DAY)
    THEN {value_column}
    ELSE 0
END)
"""


def get_iso_week_formula(
    date_column: str = "date",
    week_start: str = "monday",
) -> str:
    """
    Get ISO week alignment formula.

    ISO weeks start on Monday. DOMO defaults to Sunday start.
    This formula aligns dates to the correct ISO week.

    Args:
        date_column: Name of the date column
        week_start: 'monday' or 'sunday'

    Returns:
        str: SQL formula for ISO week alignment
    """
    if week_start.lower() == "monday":
        return ISO_WEEK_ALIGN_MONDAY.format(date_column=date_column)
    else:
        return ISO_WEEK_ALIGN_SUNDAY.format(date_column=date_column)


def get_coalesce_formula(
    column: str,
    agg_type: str = "SUM",
    nullReplacement: int = 0,
) -> str:
    """
    Get COALESCE aggregation formula for null handling.

    Args:
        column: Column to aggregate
        agg_type: Aggregation type (SUM, AVG, COUNT)
        nullReplacement: Value to use for NULLs

    Returns:
        str: COALESCE aggregation formula
    """
    templates = {
        "SUM": COALESCE_SUM_TEMPLATE,
        "AVG": COALESCE_AVG_TEMPLATE,
        "COUNT": COALESCE_COUNT_TEMPLATE,
    }

    template = templates.get(agg_type.upper(), COALESCE_SUM_TEMPLATE)
    return template.format(column=column, nullReplacement=nullReplacement)


def get_week_over_week_formula(
    value_column: str = "value",
    date_column: str = "date",
) -> str:
    """
    Get week-over-week change formula.

    Args:
        value_column: Column containing the metric value
        date_column: Date column name

    Returns:
        str: Week-over-week Beast Mode formula
    """
    return WEEK_OVER_WEEK_TEMPLATE.format(
        value_column=value_column,
        date_column=date_column,
    )


def get_month_over_month_formula(
    value_column: str = "value",
    date_column: str = "date",
) -> str:
    """
    Get month-over-month change formula.

    Args:
        value_column: Column containing the metric value
        date_column: Date column name

    Returns:
        str: Month-over-month Beast Mode formula
    """
    return MONTH_OVER_MONTH_TEMPLATE.format(
        value_column=value_column,
        date_column=date_column,
    )


def get_year_over_year_formula(
    value_column: str = "value",
    date_column: str = "date",
) -> str:
    """
    Get year-over-year change formula.

    Args:
        value_column: Column containing the metric value
        date_column: Date column name

    Returns:
        str: Year-over-year Beast Mode formula
    """
    return YEAR_OVER_YEAR_TEMPLATE.format(
        value_column=value_column,
        date_column=date_column,
    )


def get_running_total_formula(
    value_column: str = "value",
    date_column: str = "date",
) -> str:
    """
    Get running total (cumulative sum) formula.

    Args:
        value_column: Column containing the metric value
        date_column: Date column name

    Returns:
        str: Running total Beast Mode formula
    """
    return RUNNING_TOTAL_TEMPLATE.format(
        value_column=value_column,
        date_column=date_column,
    )


def get_moving_average_formula(
    value_column: str = "value",
    date_column: str = "date",
    window_days: int = 7,
) -> str:
    """
    Get moving average formula.

    Args:
        value_column: Column containing the metric value
        date_column: Date column name
        window_days: Number of days for moving average window

    Returns:
        str: Moving average Beast Mode formula
    """
    return f"""
AVG(SUM({value_column})) OVER (ORDER BY {date_column} ROWS BETWEEN {window_days - 1} PRECEDING AND CURRENT ROW)
"""


def get_period_to_date_formula(
    value_column: str = "value",
    date_column: str = "date",
    period: str = "week",
) -> str:
    """
    Get period-to-date formula.

    Args:
        value_column: Column containing the metric value
        date_column: Date column name
        period: 'week', 'month', or 'quarter'

    Returns:
        str: Period-to-date Beast Mode formula
    """
    if period.lower() == "week":
        return WEEK_TO_DATE_TEMPLATE.format(
            value_column=value_column,
            date_column=date_column,
        )
    elif period.lower() == "month":
        return f"""
SUM(CASE
    WHEN {date_column} >= DATE_TRUNC('MONTH', CURRENT_DATE())
    THEN {value_column}
    ELSE 0
END)
"""
    else:
        return f"""
SUM(CASE
    WHEN {date_column} >= DATE_TRUNC('QUARTER', CURRENT_DATE())
    THEN {value_column}
    ELSE 0
END)
"""


def detect_join_type_issue(
    dataflow_name: str,
    joinExpressions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Detect potential join type mismatches in Magic ETL.

    LEFT JOIN vs INNER JOIN can cause different row counts.
    This function checks for common join patterns that may cause issues.

    Args:
        dataflow_name: Name of the dataflow
        joinExpressions: List of join expressions (if known)

    Returns:
        Dict with detection results:
            - has_issue: bool
            - issue_type: str
            - description: str
            - recommendation: str
    """
    result = {
        "has_issue": False,
        "issue_type": None,
        "description": None,
        "recommendation": None,
    }

    if joinExpressions is None:
        joinExpressions = []

    # Check for multiple joins that might cause duplication
    if len(joinExpressions) > 3:
        result["has_issue"] = True
        result["issue_type"] = "multiple_joins"
        result["description"] = (
            f"Dataflow '{dataflow_name}' has {len(joinExpressions)} join operations. "
            "Multiple joins can cause row duplication if relationships are not 1:1."
        )
        result["recommendation"] = (
            "Review join cardinality. Consider using DISTINCT or GROUP BY "
            "before joining to deduplicate source data."
        )

    # Check for potential one-to-many issues
    for expr in joinExpressions:
        if "LEFT" not in expr.upper() and "INNER" not in expr.upper():
            result["has_issue"] = True
            result["issue_type"] = "ambiguous_join_type"
            result["description"] = (
                f"Join expression '{expr}' does not specify LEFT or INNER join type."
            )
            result["recommendation"] = (
                "Explicitly specify join type to ensure correct row inclusion."
            )

    return result


def validate_beast_mode_formula(formula: str) -> Dict[str, Any]:
    """
    Validate a Beast Mode formula for common issues.

    Args:
        formula: The Beast Mode formula string to validate

    Returns:
        Dict with validation results:
            - is_valid: bool
            - issues: List of issue descriptions
            - warnings: List of warning descriptions
            - suggestions: List of suggested improvements
    """
    issues = []
    warnings = []
    suggestions = []

    formula_upper = formula.upper()
    formula_lower = formula.lower()

    # Check for aggregation
    has_agg = any(
        agg in formula_upper
        for agg in ["SUM(", "AVG(", "COUNT(", "MIN(", "MAX("]
    )
    if not has_agg:
        warnings.append("No aggregation function found - formula may not aggregate correctly")

    # Check for date alignment
    if "WEEK(" in formula_upper and "DAYOFWEEK" not in formula_upper:
        warnings.append(
            "WEEK() function used without DAYOFWEEK - verify week start alignment "
            "matches scorecard (Monday start uses WEEK(date, 1))"
        )

    # Check for NULL handling
    if "NULL" in formula_upper and "COALESCE" not in formula_upper:
        warnings.append(
            "Formula contains NULL but not COALESCE - NULLs may cause incorrect aggregations. "
            "Consider wrapping with COALESCE(..., 0)"
        )

    # Check for division by zero
    if "/0" in formula_lower or "/0" in formula_lower:
        issues.append("Potential division by zero - add NULLIF to prevent errors")

    # Check for proper CASE syntax
    if formula_upper.count("CASE") != formula_upper.count("END"):
        issues.append("Mismatched CASE/END syntax")

    # Check for date filter presence
    if "CURRENT_DATE()" in formula_upper:
        suggestions.append(
            "Formula uses CURRENT_DATE() - verify this matches the scorecard date range"
        )

    # Check for ISO week patterns
    if "DAYOFWEEK" in formula_upper:
        suggestions.append(
            "Formula uses DAYOFWEEK - ensure Monday start alignment (DAYOFWEEK=1 is Sunday)"
        )

    is_valid = len(issues) == 0

    return {
        "is_valid": is_valid,
        "issues": issues,
        "warnings": warnings,
        "suggestions": suggestions,
    }


def generate_metric_formula(
    metric_name: str,
    agg_type: str = "SUM",
    value_column: str = "value",
    date_column: str = "date",
    week_start: str = "monday",
    include_null_handling: bool = True,
) -> str:
    """
    Generate a complete metric formula with common patterns.

    Args:
        metric_name: Name of the metric
        agg_type: Aggregation type (SUM, AVG, COUNT)
        value_column: Column containing the value
        date_column: Date column name
        week_start: 'monday' or 'sunday'
        include_null_handling: Whether to include COALESCE

    Returns:
        str: Complete Beast Mode formula
    """
    parts = []

    # Add comment
    parts.append(f"-- {metric_name}")
    parts.append(f"-- Aggregation: {agg_type}")
    parts.append(f"-- Week start: {week_start.upper()}")

    # Generate aggregation
    if include_null_handling:
        agg_formula = get_coalesce_formula(value_column, agg_type)
    else:
        agg_templates = {
            "SUM": f"SUM({value_column})",
            "AVG": f"AVG({value_column})",
            "COUNT": f"COUNT({value_column})",
            "MIN": f"MIN({value_column})",
            "MAX": f"MAX({value_column})",
        }
        agg_formula = agg_templates.get(agg_type.upper(), f"SUM({value_column})")

    parts.append(agg_formula)

    return "\n".join(parts)


# Common metric formula templates
METRIC_TEMPLATES = {
    "weekly_revenue": {
        "name": "Weekly Revenue",
        "formula": get_coalesce_formula("revenue", "SUM"),
        "description": "Total revenue per ISO week",
        "unit": "USD",
    },
    "weekly_orders": {
        "name": "Weekly Orders",
        "formula": get_coalesce_formula("orders", "COUNT"),
        "description": "Total orders per ISO week",
        "unit": "count",
    },
    "avg_order_value": {
        "name": "Average Order Value",
        "formula": f"AVG({get_coalesce_formula('revenue', 'SUM')})",
        "description": "Average revenue per order",
        "unit": "USD",
    },
    "active_customers": {
        "name": "Active Customers",
        "formula": get_coalesce_formula("customer_id", "COUNT_DISTINCT"),
        "description": "Unique active customers per week",
        "unit": "count",
    },
    "conversion_rate": {
        "name": "Conversion Rate",
        "formula": "SUM(conversions) / SUM(visits) * 100",
        "description": "Visitor to customer conversion",
        "unit": "percent",
    },
}


def get_metric_template(metric_key: str) -> Optional[Dict[str, Any]]:
    """
    Get a pre-defined metric template.

    Args:
        metric_key: Key for the metric template

    Returns:
        Dict containing template info or None if not found
    """
    return METRIC_TEMPLATES.get(metric_key)
