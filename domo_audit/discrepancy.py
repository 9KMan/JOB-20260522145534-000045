"""
Discrepancy Reporting Module

Provides functionality for reconciling scorecard values with DOMO KPIs,
calculating variance, and flagging critical discrepancies for prioritized fixes.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import pandas as pd

logger = logging.getLogger(__name__)


class DiscrepancyStatus(Enum):
    """Status levels for discrepancies."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    PENDING_REVIEW = "pending_review"


class BusinessImpact(Enum):
    """Business impact levels for prioritization."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Discrepancy:
    """
    Represents a single metric discrepancy between scorecard and DOMO.
    """
    metric_name: str
    card_id: str
    card_name: str
    dashboard: str
    scorecard_value: float
    domo_value: Optional[float]
    variance: Optional[float]
    variance_pct: Optional[float]
    status: DiscrepancyStatus
    business_impact: BusinessImpact
    root_cause: Optional[str] = None
    fix_applied: Optional[str] = None
    fix_status: str = "open"
    dataflow_id: Optional[str] = None
    dataset_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "card_id": self.card_id,
            "card_name": self.card_name,
            "dashboard": self.dashboard,
            "scorecard_value": self.scorecard_value,
            "domo_value": self.domo_value,
            "variance": self.variance,
            "variance_pct": self.variance_pct,
            "status": self.status.value,
            "business_impact": self.business_impact.value,
            "root_cause": self.root_cause,
            "fix_applied": self.fix_applied,
            "fix_status": self.fix_status,
            "dataflow_id": self.dataflow_id,
            "dataset_id": self.dataset_id,
            "notes": self.notes,
        }


class DiscrepancyReporter:
    """
    Manages discrepancy detection and reporting.
    """

    # Variance thresholds
    OK_THRESHOLD_PCT = 1.0  # <= 1% is OK
    WARNING_THRESHOLD_PCT = 5.0  # <= 5% is warning

    # High impact metric patterns (revenue-affecting)
    HIGH_IMPACT_PATTERNS = [
        "revenue",
        "sales",
        "profit",
        "margin",
        "bookings",
        "orders",
        "arr",
        "mrr",
        "customer",
        "conversion",
    ]

    def __init__(self, scorecard_data: Optional[Dict[str, float]] = None):
        """
        Initialize discrepancy reporter.

        Args:
            scorecard_data: Dict mapping metric names to expected scorecard values
        """
        self.scorecard_data = scorecard_data or {}
        self.discrepancies: List[Discrepancy] = []

    def reconcile_scorecard(
        self,
        card_name: str,
        card_id: str,
        domo_value: Optional[float],
        dashboard: str = "",
        dataflow_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> Discrepancy:
        """
        Compare a single card's value against the scorecard.

        Args:
            card_name: Name of the card
            card_id: DOMO card ID
            domo_value: Actual value from DOMO
            dashboard: Dashboard name
            dataflow_id: Associated dataflow ID
            dataset_id: Associated dataset ID

        Returns:
            Discrepancy: The calculated discrepancy
        """
        # Find matching scorecard value
        scorecard_value = self._find_scorecard_value(card_name)

        # Calculate variance
        variance, variance_pct = self.calculate_variance(domo_value, scorecard_value)

        # Determine status
        status = self._determine_status(variance_pct)

        # Determine business impact
        business_impact = self._determine_impact(card_name)

        # Determine likely root cause
        root_cause = self._identify_root_cause(card_name, variance_pct, dataflow_id)

        discrepancy = Discrepancy(
            metric_name=self._extract_metric_name(card_name),
            card_id=card_id,
            card_name=card_name,
            dashboard=dashboard,
            scorecard_value=scorecard_value or 0.0,
            domo_value=domo_value,
            variance=variance,
            variance_pct=variance_pct,
            status=status,
            business_impact=business_impact,
            root_cause=root_cause,
            dataflow_id=dataflow_id,
            dataset_id=dataset_id,
        )

        self.discrepancies.append(discrepancy)
        return discrepancy

    def _find_scorecard_value(self, card_name: str) -> Optional[float]:
        """Find the expected scorecard value for a card."""
        metric_name = self._extract_metric_name(card_name)

        # Direct match
        if metric_name in self.scorecard_data:
            return self.scorecard_data[metric_name]

        # Case-insensitive search
        for key, value in self.scorecard_data.items():
            if key.lower() == metric_name.lower():
                return value

        # Partial match
        for key, value in self.scorecard_data.items():
            if key.lower() in card_name.lower() or card_name.lower() in key.lower():
                return value

        return None

    def _extract_metric_name(self, card_name: str) -> str:
        """Extract the base metric name from a card name."""
        # Remove common suffixes
        name = card_name
        for suffix in [" - Current Week", " - MTD", " - YTD", " - WTD"]:
            if suffix in name:
                name = name.replace(suffix, "")
        return name.strip()

    def calculate_variance(
        self,
        domo_value: Optional[float],
        scorecard_value: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate variance between DOMO and scorecard values.

        Args:
            domo_value: Actual value from DOMO
            scorecard_value: Expected value from scorecard

        Returns:
            Tuple of (absolute variance, percentage variance)
        """
        if domo_value is None or scorecard_value is None:
            return None, None

        if scorecard_value == 0:
            return None, None

        variance = abs(domo_value - scorecard_value)
        variance_pct = (variance / abs(scorecard_value)) * 100

        return variance, variance_pct

    def _determine_status(self, variance_pct: Optional[float]) -> DiscrepancyStatus:
        """Determine discrepancy status based on variance percentage."""
        if variance_pct is None:
            return DiscrepancyStatus.PENDING_REVIEW

        if variance_pct <= self.OK_THRESHOLD_PCT:
            return DiscrepancyStatus.OK
        elif variance_pct <= self.WARNING_THRESHOLD_PCT:
            return DiscrepancyStatus.WARNING
        else:
            return DiscrepancyStatus.CRITICAL

    def _determine_impact(self, card_name: str) -> BusinessImpact:
        """Determine business impact based on metric patterns."""
        name_lower = card_name.lower()

        for pattern in self.HIGH_IMPACT_PATTERNS:
            if pattern in name_lower:
                return BusinessImpact.HIGH

        return BusinessImpact.MEDIUM

    def _identify_root_cause(
        self,
        card_name: str,
        variance_pct: Optional[float],
        dataflow_id: Optional[str],
    ) -> Optional[str]:
        """
        Identify likely root cause based on patterns.

        Common DOMO discrepancy causes:
        - Beast Mode date filter mismatch (ISO week vs Sunday start)
        - Magic ETL join type mismatch (LEFT vs INNER)
        - Date partitioning alignment (Monday-Sunday vs Sunday-Saturday)
        - Aggregation level mismatch (NULL handling)
        - Dataflow staleness (outdated data)
        - Lookup dataset not refreshed
        - One-to-many join duplication
        """
        if variance_pct is None:
            return "No scorecard value found for comparison"

        card_lower = card_name.lower()

        # Check for date-related keywords
        if any(kw in card_lower for kw in ["week", "date", "daily", "monthly"]):
            if variance_pct > 1:
                return "Possible ISO week alignment issue - verify WEEK(date,1) for Monday start"

        # Check for aggregation issues
        if any(kw in card_lower for kw in ["total", "sum", "count", "avg"]):
            if variance_pct > 1:
                return "Possible aggregation mismatch - verify COALESCE for NULL handling"

        # Dataflow staleness
        if variance_pct > 5:
            return "Check dataflow last run time - possible stale data"

        return None

    def flag_critical_discrepancies(
 self,
        min_impact: BusinessImpact = BusinessImpact.MEDIUM,
    ) -> List[Discrepancy]:
        """
        Get discrepancies prioritized by business impact.

        Args:
            min_impact: Minimum impact level to include

        Returns:
            List of Discrepancy objects sorted by impact and variance
        """
        impact_order = {
            BusinessImpact.HIGH: 0,
            BusinessImpact.MEDIUM: 1,
            BusinessImpact.LOW: 2,
        }

        critical = [
            d for d in self.discrepancies
            if d.status in [DiscrepancyStatus.CRITICAL, DiscrepancyStatus.WARNING]
            and impact_order.get(d.business_impact, 999) <= impact_order.get(min_impact, 999)
        ]

        # Sort by impact then by variance percentage
        critical.sort(
            key=lambda d: (
                impact_order.get(d.business_impact, 999),
                -(d.variance_pct or 0)
            )
        )

        return critical

    def generate_report(self) -> pd.DataFrame:
        """
        Generate a DataFrame report of all discrepancies.

        Returns:
            pd.DataFrame: Discrepancy report
        """
        if not self.discrepancies:
            return pd.DataFrame()

        rows = [d.to_dict() for d in self.discrepancies]
        df = pd.DataFrame(rows)

        # Sort by business impact and variance
        impact_order = {"high": 0, "medium": 1, "low": 2}
        df["_impact_order"] = df["business_impact"].map(impact_order)
        df = df.sort_values(["_impact_order", "variance_pct"], ascending=[True, False])
        df = df.drop("_impact_order", axis=1)

        return df

    def export_report(self, output_path: str, format: str = "csv") -> str:
        """
        Export discrepancy report to file.

        Args:
            output_path: Path to save the report
            format: Output format ('csv' or 'excel')

        Returns:
            str: Path to exported file
        """
        df = self.generate_report()

        if format == "excel":
            df.to_excel(output_path, index=False)
        else:
            df.to_csv(output_path, index=False)

        logger.info(f"Discrepancy report exported to {output_path}")
        return output_path


def reconcile_scorecard(
    scorecard_data: Dict[str, float],
    cards: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convenience function to reconcile scorecard with DOMO cards.

    Args:
        scorecard_data: Dict mapping metric names to expected values
        cards: List of card info dicts from DOMO

    Returns:
        List of discrepancy dicts
    """
    reporter = DiscrepancyReporter(scorecard_data)

    for card in cards:
        reporter.reconcile_scorecard(
            card_name=card.get("name", ""),
            card_id=card.get("id", ""),
            domo_value=None,  # Would need to fetch actual values
            dashboard=card.get("dashboard_name", ""),
            dataflow_id=card.get("dataflow_id"),
            dataset_id=card.get("dataset_id"),
        )

    return [d.to_dict() for d in reporter.discrepancies]


def calculate_variance(
    domo_value: float,
    scorecard_value: float,
) -> Tuple[float, float]:
    """
    Calculate percentage variance between two values.

    Args:
        domo_value: Actual value from DOMO
        scorecard_value: Expected value from scorecard

    Returns:
        Tuple of (absolute variance, percentage variance)
    """
    if scorecard_value == 0:
        return 0.0, 0.0

    variance = abs(domo_value - scorecard_value)
    variance_pct = (variance / abs(scorecard_value)) * 100

    return variance, variance_pct


def flag_critical_discrepancies(
    discrepancies: List[Dict[str, Any]],
    variance_threshold_pct: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Flag discrepancies that exceed variance threshold.

    Args:
        discrepancies: List of discrepancy dicts
        variance_threshold_pct: Minimum variance to flag

    Returns:
        List of critical discrepancy dicts
    """
    critical = []

    for d in discrepancies:
        variance_pct = d.get("variance_pct")
        if variance_pct is not None and variance_pct > variance_threshold_pct:
            d["flagged"] = True
            d["flag_reason"] = f"Variance {variance_pct:.2f}% exceeds threshold"
            critical.append(d)

    # Sort by variance descending
    critical.sort(key=lambda x: -(x.get("variance_pct") or 0))

    return critical
