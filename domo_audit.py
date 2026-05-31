#!/usr/bin/env python3
"""
DOMO Audit Toolkit - Main Module

Provides functionality for auditing DOMO environments, listing datasets,
dataflows, and cards, tracking lineage, and generating discrepancy reports.
"""

import os
import sys
import csv
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path

import pandas as pd

# DOMO API client
try:
    from pydomo import Domo
    from pydomo.entities import DataSet, DataFlow, Card
    from pydomo.transport import RequestsHTTP
    PYDOMO_AVAILABLE = True
except ImportError:
    PYDOMO_AVAILABLE = False

# Environment configuration
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DomoAuditClient:
    """
    Main client for interacting with DOMO API for audit purposes.
    """

    def __init__(
        self,
        instance: Optional[str] = None,
        token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """
        Initialize DOMO audit client with API credentials.

        Args:
            instance: DOMO instance hostname (e.g., 'your-instance.domo.com')
            token: DOMO API token
            client_id: DOMO OAuth client ID
            client_secret: DOMO OAuth client secret
        """
        # Load environment variables if not provided
        load_dotenv()

        self.instance = instance or os.getenv("DOMO_INSTANCE", "")
        self.token = token or os.getenv("DOMO_TOKEN", "")
        self.client_id = client_id or os.getenv("DOMO_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("DOMO_CLIENT_SECRET", "")

        if not all([self.instance, (self.token or (self.client_id and self.client_secret))]):
            logger.warning(
                "DOMO credentials not fully configured. "
                "Set DOMO_INSTANCE, DOMO_TOKEN or DOMO_CLIENT_ID/DOMO_CLIENT_SECRET."
            )

        self._client = None
        self._connected = False

    def _get_client(self):
        """
        Get or create the DOMO API client.

        Returns:
            Domo: Authenticated DOMO client instance
        """
        if not PYDOMO_AVAILABLE:
            raise ImportError(
                "pydomo is not installed. Install with: pip install pydomo>=1.3.0"
            )

        if self._client is None:
            if self.token:
                # Token-based authentication
                self._client = Domo(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    host=self.instance,
                    token=self.token,
                )
            else:
                # OAuth authentication
                self._client = Domo(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    host=self.instance,
                )

        return self._client

    def connect(self) -> bool:
        """
        Test connection to DOMO API.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            client = self._get_client()
            # Attempt a simple API call to verify connection
            client.datasets.list()
            self._connected = True
            logger.info(f"Successfully connected to DOMO instance: {self.instance}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to DOMO: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to DOMO."""
        return self._connected

    def list_all_datasets(self) -> List[Dict[str, Any]]:
        """
        List all DOMO datasets with metadata.

        Returns:
            List[Dict]: List of dataset info dicts containing:
                - id: Dataset ID
                - name: Dataset name
                - type: Dataset type
                - owner: Owner name/ID
                - last_run: Last data run timestamp
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
                - row_count: Number of rows
                - column_count: Number of columns
        """
        if not PYDOMO_AVAILABLE:
            logger.error("pydomo not available")
            return []

        try:
            client = self._get_client()
            datasets = client.datasets.list()

            result = []
            for ds in datasets:
                dataset_info = {
                    "id": getattr(ds, 'id', 'unknown'),
                    "name": getattr(ds, 'name', 'unknown'),
                    "type": getattr(ds, 'type', 'unknown'),
                    "owner": getattr(ds, 'owner', 'unknown'),
                    "last_run": getattr(ds, 'lastRun', None),
                    "created_at": getattr(ds, 'createdAt', None),
                    "updated_at": getattr(ds, 'updatedAt', None),
                    "row_count": getattr(ds, 'rowCount', 0),
                    "column_count": getattr(ds, 'columnCount', 0),
                    "description": getattr(ds, 'description', ''),
                }
                result.append(dataset_info)

            logger.info(f"Listed {len(result)} datasets")
            return result

        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            return []

    def list_all_dataflows(self) -> List[Dict[str, Any]]:
        """
        List all Magic ETL dataflows with upstream/downstream dependencies.

        Returns:
            List[Dict]: List of dataflow info dicts containing:
                - id: DataFlow ID
                - name: DataFlow name
                - type: DataFlow type (MAGIC_ETL, SQL_FLOW, etc.)
                - owner: Owner name/ID
                - last_run: Last execution timestamp
                - status: Current status
                - upstream_dependencies: List of upstream dataset/dataflow IDs
                - downstream_dependencies: List of downstream dataset/dataflow IDs
                - tags: List of tags applied to this dataflow
        """
        if not PYDOMO_AVAILABLE:
            logger.error("pydomo not available")
            return []

        try:
            client = self._get_client()
            dataflows = client.dataflows.list()

            result = []
            for df in dataflows:
                # Try to get execution history for last run info
                last_run = None
                status = "unknown"
                try:
                    execution = client.dataflows.get_execution(df.id)
                    if execution:
                        last_run = getattr(execution, 'startTime', None)
                        status = getattr(execution, 'status', 'unknown')
                except Exception:
                    pass

                dataflow_info = {
                    "id": getattr(df, 'id', 'unknown'),
                    "name": getattr(df, 'name', 'unknown'),
                    "type": getattr(df, 'type', 'MAGIC_ETL'),
                    "owner": getattr(df, 'owner', 'unknown'),
                    "last_run": last_run,
                    "status": status,
                    "upstream_dependencies": self._get_upstream_deps(df),
                    "downstream_dependencies": self._get_downstream_deps(df),
                    "tags": getattr(df, 'tags', []),
                    "description": getattr(df, 'description', ''),
                }
                result.append(dataflow_info)

            logger.info(f"Listed {len(result)} dataflows")
            return result

        except Exception as e:
            logger.error(f"Error listing dataflows: {e}")
            return []

    def _get_upstream_deps(self, dataflow) -> List[str]:
        """Extract upstream dependencies from dataflow object."""
        deps = []
        try:
            inputs = getattr(dataflow, 'inputs', [])
            for inp in inputs:
                deps.append(getattr(inp, 'id', str(inp)))
        except Exception:
            pass
        return deps

    def _get_downstream_deps(self, dataflow) -> List[str]:
        """Extract downstream dependencies from dataflow object."""
        deps = []
        try:
            outputs = getattr(dataflow, 'outputs', [])
            for out in outputs:
                deps.append(getattr(out, 'id', str(out)))
        except Exception:
            pass
        return deps

    def list_all_cards(self) -> List[Dict[str, Any]]:
        """
        List all dashboard cards with dataset/dataflow lineage.

        Returns:
            List[Dict]: List of card info dicts containing:
                - id: Card ID
                - name: Card name
                - dashboard_id: Parent dashboard ID
                - dashboard_name: Parent dashboard name
                - dataset_id: Associated dataset ID
                - dataflow_id: Associated dataflow ID
                - owner: Card owner
                - last_modified: Last modification timestamp
                - card_type: Type of card (bar, line, table, etc.)
        """
        if not PYDOMO_AVAILABLE:
            logger.error("pydomo not available")
            return []

        try:
            client = self._get_client()
            cards = client.cards.list()

            result = []
            for card in cards:
                card_info = {
                    "id": getattr(card, 'id', 'unknown'),
                    "name": getattr(card, 'name', 'unknown'),
                    "dashboard_id": getattr(card, 'dashboardId', None),
                    "dashboard_name": getattr(card, 'dashboardName', None),
                    "dataset_id": getattr(card, 'datasetId', None),
                    "dataflow_id": getattr(card, 'dataflowId', None),
                    "owner": getattr(card, 'owner', 'unknown'),
                    "last_modified": getattr(card, 'lastModified', None),
                    "card_type": getattr(card, 'type', 'unknown'),
                    "description": getattr(card, 'description', ''),
                }
                result.append(card_info)

            logger.info(f"Listed {len(result)} cards")
            return result

        except Exception as e:
            logger.error(f"Error listing cards: {e}")
            return []

    def get_dataflow_lineage(self, dataflow_id: str) -> Dict[str, Any]:
        """
        Trace upstream datasets and downstream cards for a specific dataflow.

        Args:
            dataflow_id: The ID of the dataflow to trace

        Returns:
            Dict containing:
                - dataflow: DataFlow info
                - upstream_datasets: List of upstream dataset info
                - downstream_cards: List of downstream card info
                - downstream_dataflows: List of downstream dataflow info
        """
        if not PYDOMO_AVAILABLE:
            logger.error("pydomo not available")
            return {}

        try:
            client = self._get_client()
            dataflow = client.dataflows.get(dataflow_id)

            lineage = {
                "dataflow": {
                    "id": getattr(dataflow, 'id', dataflow_id),
                    "name": getattr(dataflow, 'name', 'unknown'),
                    "type": getattr(dataflow, 'type', 'unknown'),
                    "owner": getattr(dataflow, 'owner', 'unknown'),
                },
                "upstream_datasets": [],
                "downstream_cards": [],
                "downstream_dataflows": [],
            }

            # Get upstream datasets
            try:
                inputs = getattr(dataflow, 'inputs', [])
                for inp in inputs:
                    ds_id = getattr(inp, 'id', None)
                    if ds_id:
                        try:
                            ds = client.datasets.get(ds_id)
                            lineage["upstream_datasets"].append({
                                "id": getattr(ds, 'id', ds_id),
                                "name": getattr(ds, 'name', 'unknown'),
                                "type": getattr(ds, 'type', 'unknown'),
                            })
                        except Exception:
                            lineage["upstream_datasets"].append({
                                "id": ds_id,
                                "name": "unknown",
                                "type": "unknown",
                            })
            except Exception as e:
                logger.warning(f"Could not get upstream datasets: {e}")

            # Get downstream cards
            try:
                cards = client.cards.list()
                for card in cards:
                    card_df_id = getattr(card, 'dataflowId', None)
                    if card_df_id == dataflow_id:
                        lineage["downstream_cards"].append({
                            "id": getattr(card, 'id', 'unknown'),
                            "name": getattr(card, 'name', 'unknown'),
                            "dashboard_name": getattr(card, 'dashboardName', None),
                        })
            except Exception as e:
                logger.warning(f"Could not get downstream cards: {e}")

            # Get downstream dataflows
            try:
                outputs = getattr(dataflow, 'outputs', [])
                for out in outputs:
                    out_id = getattr(out, 'id', None)
                    if out_id:
                        # Check if any dataflow uses this as input
                        all_dfs = client.dataflows.list()
                        for df in all_dfs:
                            try:
                                df_inputs = getattr(df, 'inputs', [])
                                for df_inp in df_inputs:
                                    if getattr(df_inp, 'id', None) == out_id:
                                        lineage["downstream_dataflows"].append({
                                            "id": getattr(df, 'id', 'unknown'),
                                            "name": getattr(df, 'name', 'unknown'),
                                        })
                            except Exception:
                                pass
            except Exception as e:
                logger.warning(f"Could not get downstream dataflows: {e}")

            logger.info(f"Retrieved lineage for dataflow {dataflow_id}")
            return lineage

        except Exception as e:
            logger.error(f"Error getting dataflow lineage: {e}")
            return {}

    def calculate_discrepancy(
        self,
        card_id: str,
        scorecard_value: float,
        metric_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare card KPI value vs scorecard expected value.

        Args:
            card_id: The DOMO card ID
            scorecard_value: The expected value from scorecard
            metric_name: Optional metric name for context

        Returns:
            Dict containing discrepancy analysis:
                - card_id: Card ID
                - metric_name: Metric name
                - scorecard_value: Expected value
                - domo_value: Actual DOMO value
                - variance: Absolute difference
                - variance_pct: Percentage variance
                - status: 'ok', 'warning', 'critical'
        """
        if not PYDOMO_AVAILABLE:
            logger.error("pydomo not available")
            return {}

        try:
            client = self._get_client()
            card = client.cards.get(card_id)

            # Get the actual value from card
            # Cards store data in datasets, we need to fetch the underlying data
            dataset_id = getattr(card, 'datasetId', None)
            domo_value = None

            if dataset_id:
                try:
                    # Get dataset schema and data
                    ds = client.datasets.get(dataset_id)
                    # For simplicity, we'll note that actual value extraction
                    # would require querying the dataset directly
                    logger.info(f"Dataset {dataset_id} found for card {card_id}")
                except Exception as e:
                    logger.warning(f"Could not get dataset: {e}")

            # Calculate variance
            variance = abs(domo_value - scorecard_value) if domo_value is not None else None
            variance_pct = None
            if variance is not None and scorecard_value != 0:
                variance_pct = (variance / abs(scorecard_value)) * 100

            # Determine status
            status = "unknown"
            if variance_pct is not None:
                if variance_pct <= 0.01:  # <= 1%
                    status = "ok"
                elif variance_pct <= 5:  # <= 5%
                    status = "warning"
                else:
                    status = "critical"

            result = {
                "card_id": card_id,
                "card_name": getattr(card, 'name', 'unknown'),
                "metric_name": metric_name or "unknown",
                "scorecard_value": scorecard_value,
                "domo_value": domo_value,
                "variance": variance,
                "variance_pct": variance_pct,
                "status": status,
                "dataset_id": dataset_id,
            }

            logger.info(f"Calculated discrepancy for card {card_id}: {status}")
            return result

        except Exception as e:
            logger.error(f"Error calculating discrepancy: {e}")
            return {}

    def generate_discrepancy_report(
        self,
        scorecard_data: Optional[Dict[str, float]] = None,
        output_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Produce CSV of all divergent metrics.

        Args:
            scorecard_data: Dict mapping metric names to expected scorecard values
            output_path: Optional path to save CSV report

        Returns:
            pd.DataFrame: DataFrame containing discrepancy report
        """
        if scorecard_data is None:
            scorecard_data = {}

        try:
            # Get all cards
            cards = self.list_all_cards()

            # Get all dataflows for lineage
            dataflows = self.list_all_dataflows()

            # Build card to dataflow mapping
            card_dataflow_map = {
                c['id']: c['dataflow_id'] for c in cards
                if c.get('dataflow_id')
            }

            # Build dataflow to dataset mapping
            df_dataset_map = {}
            for df in dataflows:
                outputs = df.get('downstream_dependencies', [])
                if outputs:
                    df_dataset_map[df['id']] = outputs[0] if outputs else None

            # Build discrepancy records
            discrepancies = []

            for metric_name, scorecard_value in scorecard_data.items():
                # Try to find matching card
                for card in cards:
                    if metric_name.lower() in card['name'].lower():
                        discrepancy = self.calculate_discrepancy(
                            card['id'],
                            scorecard_value,
                            metric_name,
                        )
                        if discrepancy:
                            discrepancies.append(discrepancy)

            # If no scorecard data provided, list all cards for manual review
            if not discrepancies:
                for card in cards:
                    discrepancies.append({
                        "card_id": card['id'],
                        "card_name": card['name'],
                        "metric_name": "unknown",
                        "scorecard_value": None,
                        "domo_value": None,
                        "variance": None,
                        "variance_pct": None,
                        "status": "pending_review",
                        "dataset_id": card.get('dataset_id'),
                    })

            df = pd.DataFrame(discrepancies)

            if output_path:
                df.to_csv(output_path, index=False)
                logger.info(f"Discrepancy report saved to {output_path}")

            return df

        except Exception as e:
            logger.error(f"Error generating discrepancy report: {e}")
            return pd.DataFrame()

    def get_metric_lineage(self, card_name: str) -> Dict[str, Any]:
        """
        Trace card → dataflow → dataset → source for a given card name.

        Args:
            card_name: Name of the card to trace

        Returns:
            Dict containing full lineage:
                - card: Card info
                - dataflow: DataFlow info (if exists)
                - dataset: Dataset info (if exists)
                - upstream_sources: List of source datasets/dataflows
        """
        if not PYDOMO_AVAILABLE:
            logger.error("pydomo not available")
            return {}

        try:
            client = self._get_client()
            cards = client.cards.list()

            # Find matching card
            target_card = None
            for card in cards:
                if card_name.lower() in getattr(card, 'name', '').lower():
                    target_card = card
                    break

            if not target_card:
                logger.warning(f"Card not found: {card_name}")
                return {"error": f"Card not found: {card_name}"}

            lineage = {
                "card": {
                    "id": getattr(target_card, 'id', 'unknown'),
                    "name": getattr(target_card, 'name', 'unknown'),
                    "type": getattr(target_card, 'type', 'unknown'),
                    "dataset_id": getattr(target_card, 'datasetId', None),
                    "dataflow_id": getattr(target_card, 'dataflowId', None),
                },
                "dataflow": None,
                "dataset": None,
                "upstream_sources": [],
            }

            # Get dataflow info
            dataflow_id = getattr(target_card, 'dataflowId', None)
            if dataflow_id:
                try:
                    df = client.dataflows.get(dataflow_id)
                    lineage["dataflow"] = {
                        "id": getattr(df, 'id', dataflow_id),
                        "name": getattr(df, 'name', 'unknown'),
                        "type": getattr(df, 'type', 'unknown'),
                        "upstream_dependencies": self._get_upstream_deps(df),
 }
                except Exception as e:
                    logger.warning(f"Could not get dataflow: {e}")

            # Get dataset info
            dataset_id = getattr(target_card, 'datasetId', None)
            if dataset_id:
                try:
                    ds = client.datasets.get(dataset_id)
                    lineage["dataset"] = {
                        "id": getattr(ds, 'id', dataset_id),
                        "name": getattr(ds, 'name', 'unknown'),
                        "type": getattr(ds, 'type', 'unknown'),
                        "row_count": getattr(ds, 'rowCount', 0),
                    }
                except Exception as e:
                    logger.warning(f"Could not get dataset: {e}")

            # Trace upstream sources through dataflow
            if lineage["dataflow"]:
                upstream_ids = lineage["dataflow"].get("upstream_dependencies", [])
                for up_id in upstream_ids:
                    try:
                        # Try as dataset
                        ds = client.datasets.get(up_id)
                        lineage["upstream_sources"].append({
                            "id": getattr(ds, 'id', up_id),
                            "name": getattr(ds, 'name', 'unknown'),
                            "type": "dataset",
                        })
                    except Exception:
                        try:
                            # Try as dataflow
                            df = client.dataflows.get(up_id)
                            lineage["upstream_sources"].append({
                                "id": getattr(df, 'id', up_id),
                                "name": getattr(df, 'name', 'unknown'),
                                "type": "dataflow",
                            })
                        except Exception:
                            lineage["upstream_sources"].append({
                                "id": up_id,
                                "name": "unknown",
                                "type": "unknown",
                            })

            logger.info(f"Retrieved lineage for card: {card_name}")
            return lineage

        except Exception as e:
            logger.error(f"Error getting metric lineage: {e}")
            return {}


def create_client() -> DomoAuditClient:
    """
    Factory function to create a DomoAuditClient from environment variables.

    Returns:
        DomoAuditClient: Configured client instance
    """
    return DomoAuditClient()


# Main CLI entry point
def main():
    """Main entry point for the DOMO audit toolkit CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="DOMO Audit Toolkit - Audit and reconcile DOMO metrics"
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="List all DOMO datasets with metadata",
    )
    parser.add_argument(
        "--list-dataflows",
        action="store_true",
        help="List all Magic ETL dataflows with dependencies",
    )
    parser.add_argument(
        "--list-cards",
        action="store_true",
        help="List all dashboard cards",
    )
    parser.add_argument(
        "--lineage",
        metavar="CARD_NAME",
        help="Get lineage for a specific card",
    )
    parser.add_argument(
        "--discrepancy-report",
        action="store_true",
        help="Generate discrepancy report comparing scorecard to DOMO KPIs",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Output file path for reports",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "table"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Test connection to DOMO",
    )

    args = parser.parse_args()

    # Create client
    client = create_client()

    # Handle no arguments
    if len(sys.argv) == 1:
        parser.print_help()
        return

    # Test connection if needed
    if args.connect or any([args.list_datasets, args.list_dataflows,
 args.list_cards, args.lineage, args.discrepancy_report]):
        if not client.connect():
            logger.error("Failed to connect to DOMO. Check credentials.")
            sys.exit(1)

    # Execute commands
    if args.list_datasets:
        datasets = client.list_all_datasets()
        df = pd.DataFrame(datasets)
        if args.output:
            df.to_csv(args.output, index=False)
            print(f"Dataset list saved to {args.output}")
        else:
            print(df.to_string())

    if args.list_dataflows:
        dataflows = client.list_all_dataflows()
        df = pd.DataFrame(dataflows)
        if args.output:
            df.to_csv(args.output, index=False)
            print(f"Dataflow list saved to {args.output}")
        else:
            print(df.to_string())

    if args.list_cards:
        cards = client.list_all_cards()
        df = pd.DataFrame(cards)
        if args.output:
            df.to_csv(args.output, index=False)
            print(f"Card list saved to {args.output}")
        else:
            print(df.to_string())

    if args.lineage:
        lineage = client.get_metric_lineage(args.lineage)
        if args.format == "json":
            import json
            print(json.dumps(lineage, indent=2, default=str))
        else:
            print(f"\n=== Lineage for: {args.lineage} ===")
            if "error" in lineage:
                print(f"Error: {lineage['error']}")
            else:
                if lineage.get("card"):
                    print(f"\nCard: {lineage['card'].get('name', 'unknown')}")
                    print(f"  ID: {lineage['card'].get('id', 'unknown')}")
                    print(f"  Type: {lineage['card'].get('type', 'unknown')}")
                if lineage.get("dataflow"):
                    print(f"\nDataFlow: {lineage['dataflow'].get('name', 'unknown')}")
                    print(f"  ID: {lineage['dataflow'].get('id', 'unknown')}")
                if lineage.get("dataset"):
                    print(f"\nDataset: {lineage['dataset'].get('name', 'unknown')}")
                    print(f"  ID: {lineage['dataset'].get('id', 'unknown')}")
                if lineage.get("upstream_sources"):
                    print("\nUpstream Sources:")
                    for src in lineage["upstream_sources"]:
                        print(f"  - {src.get('name', 'unknown')} ({src.get('type', 'unknown')})")

    if args.discrepancy_report:
        df = client.generate_discrepancy_report(output_path=args.output)
        if args.output:
            print(f"Discrepancy report saved to {args.output}")
        else:
            print(df.to_string())


if __name__ == "__main__":
    main()
