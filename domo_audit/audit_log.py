"""
Audit Logging Module

Provides functionality for logging ETL fixes, tracking changes,
and generating audit reports for DOMO metric reconciliation.
"""

import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AuditLogEntry:
    """
    Represents a single audit log entry for a metric fix.
    """
    run_id: str
    metric_key: str
    metric_name: str
    scorecard_value: float
    domo_value: float
    variance_pct: float
    fix_applied: str
    fixed_by: str
    fixed_at: datetime
    card_id: Optional[str] = None
    dataflow_id: Optional[str] = None
    root_cause: Optional[str] = None
    status: str = "completed"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["fixed_at"] = self.fixed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditLogEntry":
        """Create from dictionary."""
        if isinstance(data.get("fixed_at"), str):
            data["fixed_at"] = datetime.fromisoformat(data["fixed_at"])
        return cls(**data)


class AuditLog:
    """
    Manages audit log entries for metric fixes and reconciliation.
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize audit log.

        Args:
            log_file: Optional path to CSV log file for persistence
        """
        self.log_file = log_file or "domo_audit_log.csv"
        self.entries: List[AuditLogEntry] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing log entries from file."""
        if Path(self.log_file).exists():
            try:
                df = pd.read_csv(self.log_file)
                for _, row in df.iterrows():
                    self.entries.append(AuditLogEntry.from_dict(row.to_dict()))
                logger.info(f"Loaded {len(self.entries)} existing log entries")
            except Exception as e:
                logger.warning(f"Could not load existing log file: {e}")

    def _save_to_file(self) -> None:
        """Save entries to CSV file."""
        if not self.entries:
            return

        try:
            df = pd.DataFrame([e.to_dict() for e in self.entries])
            df.to_csv(self.log_file, index=False)
            logger.info(f"Saved {len(self.entries)} entries to {self.log_file}")
        except Exception as e:
            logger.error(f"Could not save log file: {e}")

    def log_fix(
        self,
        metric_key: str,
        metric_name: str,
        scorecard_value: float,
        domo_value: float,
        variance_pct: float,
        fix_applied: str,
        fixed_by: str,
        card_id: Optional[str] = None,
        dataflow_id: Optional[str] = None,
        root_cause: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AuditLogEntry:
        """
        Record a fix that was applied to resolve a discrepancy.

        Args:
            metric_key: Unique metric identifier
            metric_name: Business-friendly metric name
            scorecard_value: Expected value from scorecard
            domo_value: Actual value from DOMO after fix
            variance_pct: Remaining variance percentage
            fix_applied: Description of the fix applied
            fixed_by: Who applied the fix
            card_id: DOMO card ID that was fixed
            dataflow_id: DOMO dataflow ID that was modified
            root_cause: Identified root cause
            notes: Additional notes

        Returns:
            AuditLogEntry: The created log entry
        """
        entry = AuditLogEntry(
            run_id=str(uuid.uuid4()),
            metric_key=metric_key,
            metric_name=metric_name,
            scorecard_value=scorecard_value,
            domo_value=domo_value,
            variance_pct=variance_pct,
            fix_applied=fix_applied,
            fixed_by=fixed_by,
            fixed_at=datetime.now(),
            card_id=card_id,
            dataflow_id=dataflow_id,
            root_cause=root_cause,
            status="completed",
            notes=notes,
        )

        self.entries.append(entry)
        self._save_to_file()

        logger.info(
            f"Logged fix for {metric_key}: {fix_applied} "
            f"(variance: {variance_pct:.2f}%)"
        )

        return entry

    def get_entries(
        self,
        metric_key: Optional[str] = None,
        fixed_by: Optional[str] = None,
        since: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[AuditLogEntry]:
        """
        Get filtered audit log entries.

        Args:
            metric_key: Filter by metric key
            fixed_by: Filter by who applied the fix
            since: Filter by date (entries after this date)
            status: Filter by status

        Returns:
            List of matching AuditLogEntry objects
        """
        results = self.entries

        if metric_key:
            results = [e for e in results if e.metric_key == metric_key]

        if fixed_by:
            results = [e for e in results if e.fixed_by == fixed_by]

        if since:
            results = [e for e in results if e.fixed_at >= since]

        if status:
            results = [e for e in results if e.status == status]

        return results

    def get_metric_history(self, metric_key: str) -> List[AuditLogEntry]:
        """
        Get all log entries for a specific metric.

        Args:
            metric_key: The metric to get history for

        Returns:
            List of AuditLogEntry objects for the metric
        """
        return self.get_entries(metric_key=metric_key)

    def generate_audit_report(
        self,
        since: Optional[datetime] = None,
        include_stats: bool = True,
    ) -> pd.DataFrame:
        """
        Generate a DataFrame audit report.

        Args:
            since: Only include entries after this date
            include_stats: Include summary statistics

        Returns:
            pd.DataFrame: Audit report
        """
        entries = self.entries
        if since:
            entries = [e for e in entries if e.fixed_at >= since]

        if not entries:
            return pd.DataFrame()

        df = pd.DataFrame([e.to_dict() for e in entries])

        # Sort by fixed_at descending
        df = df.sort_values("fixed_at", ascending=False)

        return df

    def generate_summary_stats(self) -> Dict[str, Any]:
        """
        Generate summary statistics for the audit log.

        Returns:
            Dict containing summary statistics
        """
        if not self.entries:
            return {
                "total_fixes": 0,
                "unique_metrics":0,
                "avg_variance_pct": 0,
                "max_variance_pct": 0,
                "fixes_by_user": {},
                "fixes_by_metric": {},
                "recent_fixes": 0,
            }

        df = pd.DataFrame([e.to_dict() for e in self.entries])

        stats = {
            "total_fixes": len(self.entries),
            "unique_metrics": df["metric_key"].nunique(),
            "avg_variance_pct": df["variance_pct"].mean(),
            "max_variance_pct": df["variance_pct"].max(),
            "min_variance_pct": df["variance_pct"].min(),
            "fixes_by_user": df["fixed_by"].value_counts().to_dict(),
            "fixes_by_metric": df["metric_key"].value_counts().to_dict(),
            "recent_fixes": len([
                e for e in self.entries
                if e.fixed_at >= datetime.now() - timedelta(days=7)
            ]),
        }

        return stats

    def export_report(
        self,
        output_path: str,
        since: Optional[datetime] = None,
        format: str = "csv",
    ) -> str:
        """
        Export audit report to file.

        Args:
            output_path: Path to save the report
            since: Only include entries after this date
            format: Output format ('csv' or 'excel')

        Returns:
            str: Path to exported file
        """
        df = self.generate_audit_report(since=since)

        if format == "excel":
            df.to_excel(output_path, index=False)
        else:
            df.to_csv(output_path, index=False)

        logger.info(f"Audit report exported to {output_path}")
        return output_path


def log_fix(
    metric_key: str,
    metric_name: str,
    scorecard_value: float,
    domo_value: float,
    variance_pct: float,
    fix_applied: str,
    fixed_by: str,
    **kwargs,
) -> AuditLogEntry:
    """
    Convenience function to log a single fix.

    Args:
        metric_key: Unique metric identifier
        metric_name: Business-friendly metric name
        scorecard_value: Expected value from scorecard
        domo_value: Actual value from DOMO after fix
        variance_pct: Remaining variance percentage
        fix_applied: Description of the fix applied
        fixed_by: Who applied the fix
        **kwargs: Additional arguments passed to AuditLog.log_fix

    Returns:
        AuditLogEntry: The created log entry
    """
    log = AuditLog()
    return log.log_fix(
        metric_key=metric_key,
        metric_name=metric_name,
        scorecard_value=scorecard_value,
        domo_value=domo_value,
        variance_pct=variance_pct,
        fix_applied=fix_applied,
        fixed_by=fixed_by,
        **kwargs,
    )


def generate_audit_report(
    output_path: str = "audit_report.csv",
    since: Optional[datetime] = None,
    log_file: Optional[str] = None,
) -> str:
    """
    Generate a weekly audit report.

    Args:
        output_path: Path to save the report
        since: Only include entries after this date
        log_file: Optional path to log file

    Returns:
        str: Path to exported file
    """
    log = AuditLog(log_file=log_file)
    return log.export_report(output_path, since=since)


def get_audit_summary(log_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get summary statistics for the audit log.

    Args:
        log_file: Optional path to log file

    Returns:
        Dict containing summary statistics
    """
    log = AuditLog(log_file=log_file)
    return log.generate_summary_stats()
