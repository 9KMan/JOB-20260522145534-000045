"""
Lineage Tracking Module

Provides functionality for building and exporting data lineage maps
that trace cards → dataflows → datasets → source systems.
"""

import csv
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

import pandas as pd

from domo_audit import DomoAuditClient

logger = logging.getLogger(__name__)


class LineageMap:
    """
    Manages the full card → dataflow → dataset → source lineage map.
    """

    def __init__(self, client: Optional[DomoAuditClient] = None):
        """
        Initialize lineage map with optional DOMO client.

        Args:
            client: DomoAuditClient instance (creates new one if not provided)
        """
        self.client = client or DomoAuditClient()
        self._map: Dict[str, Any] = {}
        self._cards: List[Dict[str, Any]] = []
        self._dataflows: List[Dict[str, Any]] = []
        self._datasets: List[Dict[str, Any]] = []

    def build(self) -> Dict[str, Any]:
        """
        Build the complete lineage map from DOMO.

        Returns:
            Dict containing the full lineage map
        """
        logger.info("Building lineage map...")

        # Fetch all entities
        self._cards = self.client.list_all_cards()
        self._dataflows = self.client.list_all_dataflows()
        self._datasets = self.client.list_all_datasets()

        # Build mappings
        card_to_df = {}
        df_to_ds = {}
        ds_to_sources = {}

        # Map cards to dataflows
        for card in self._cards:
            if card.get('dataflow_id'):
                card_to_df[card['id']] = card['dataflow_id']

        # Map dataflows to datasets
        for df in self._dataflows:
            downstream = df.get('downstream_dependencies', [])
            if downstream:
                df_to_ds[df['id']] = downstream[0]  # First output dataset

        # Map datasets to sources (upstream deps of dataflows)
        for df in self._dataflows:
            upstream = df.get('upstream_dependencies', [])
            for ds_id in upstream:
                ds_to_sources[ds_id] = self._get_source_info(ds_id)

        # Build full lineage map
        self._map = {
            "generated_at": datetime.now().isoformat(),
            "cards": {},
            "dataflows": {},
            "datasets": {},
        }

        # Add cards with lineage
        for card in self._cards:
            card_id = card['id']
            df_id = card.get('dataflow_id')
            ds_id = card.get('dataset_id')

            self._map["cards"][card_id] = {
                "name": card.get('name', 'unknown'),
                "dashboard": card.get('dashboard_name', 'unknown'),
                "owner": card.get('owner', 'unknown'),
                "dataflow_id": df_id,
                "dataset_id": ds_id,
                "type": card.get('type', 'unknown'),
                "lineage": {
                    "dataflow": None,
                    "dataset": None,
                    "upstream_sources": [],
                }
            }

            # Add dataflow lineage
            if df_id and df_id in df_to_ds:
                target_ds_id = df_to_ds[df_id]
                self._map["cards"][card_id]["lineage"]["dataset"] = target_ds_id

                # Trace upstream through dataflow
                df = self._find_dataflow(df_id)
                if df:
                    upstream_ids = df.get('upstream_dependencies', [])
                    for up_id in upstream_ids:
                        source_info = ds_to_sources.get(up_id, {"id": up_id, "name": "unknown"})
                        self._map["cards"][card_id]["lineage"]["upstream_sources"].append(source_info)

        # Add dataflows
        for df in self._dataflows:
            self._map["dataflows"][df['id']] = {
                "name": df.get('name', 'unknown'),
                "type": df.get('type', 'unknown'),
                "owner": df.get('owner', 'unknown'),
                "status": df.get('status', 'unknown'),
                "last_run": df.get('last_run'),
                "upstream_dependencies": df.get('upstream_dependencies', []),
                "downstream_dependencies": df.get('downstream_dependencies', []),
            }

        # Add datasets
        for ds in self._datasets:
            self._map["datasets"][ds['id']] = {
                "name": ds.get('name', 'unknown'),
                "type": ds.get('type', 'unknown'),
                "owner": ds.get('owner', 'unknown'),
                "row_count": ds.get('row_count', 0),
                "last_run": ds.get('last_run'),
            }

        logger.info(f"Lineage map built: {len(self._map['cards'])} cards, "
                   f"{len(self._map['dataflows'])} dataflows, "
                   f"{len(self._map['datasets'])} datasets")

        return self._map

    def _find_dataflow(self, df_id: str) -> Optional[Dict[str, Any]]:
        """Find a dataflow by ID."""
        for df in self._dataflows:
            if df['id'] == df_id:
                return df
        return None

    def _get_source_info(self, ds_id: str) -> Dict[str, Any]:
        """Get information about a source dataset."""
        for ds in self._datasets:
            if ds['id'] == ds_id:
                return {
                    "id": ds['id'],
                    "name": ds.get('name', 'unknown'),
                    "type": ds.get('type', 'unknown'),
                }
        return {"id": ds_id, "name": "unknown", "type": "unknown"}

    def get_card_lineage(self, card_id: str) -> Dict[str, Any]:
        """
        Get lineage for a specific card.

        Args:
            card_id: The card ID to trace

        Returns:
            Dict containing card lineage
        """
        if not self._map:
            self.build()

        if card_id in self._map["cards"]:
            return self._map["cards"][card_id]

        return {"error": f"Card {card_id} not found in lineage map"}

    def get_dataflow_lineage(self, dataflow_id: str) -> Dict[str, Any]:
        """
        Get lineage for a specific dataflow.

        Args:
            dataflow_id: The dataflow ID to trace

        Returns:
            Dict containing dataflow lineage with upstream/downstream
        """
        if not self._map:
            self.build()

        if dataflow_id in self._map["dataflows"]:
            return self._map["dataflows"][dataflow_id]

        return {"error": f"Dataflow {dataflow_id} not found in lineage map"}

    def find_downstream_cards(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Find all cards that consume a specific dataset.

        Args:
            dataset_id: The dataset ID to search for

        Returns:
            List of card info dicts that use this dataset
        """
        if not self._map:
            self.build()

        cards = []
        for card_id, card_data in self._map["cards"].items():
            if card_data.get("dataset_id") == dataset_id:
                cards.append({
                    "id": card_id,
                    "name": card_data.get("name"),
                    "dashboard": card_data.get("dashboard"),
                })

        return cards

    def find_upstream_sources(self, card_id: str) -> List[Dict[str, Any]]:
        """
        Find all upstream sources for a card.

        Args:
            card_id: The card ID to trace upstream

        Returns:
            List of source info dicts
        """
        if not self._map:
            self.build()

        if card_id not in self._map["cards"]:
            return []

        card = self._map["cards"][card_id]
        return card.get("lineage", {}).get("upstream_sources", [])

    def export_lineage_csv(self, output_path: str) -> str:
        """
        Export lineage to CSV for Google Sheets import.

        Args:
            output_path: Path to save the CSV file

        Returns:
            str: Path to the exported file
        """
        if not self._map:
            self.build()

        rows = []

        # Export card lineage
        for card_id, card_data in self._map["cards"].items():
            upstream = card_data.get("lineage", {}).get("upstream_sources", [])
            upstream_names = " > ".join([s.get("name", "unknown") for s in upstream])

            rows.append({
                "entity_type": "card",
                "entity_id": card_id,
                "entity_name": card_data.get("name", "unknown"),
                "dashboard": card_data.get("dashboard", "unknown"),
                "owner": card_data.get("owner", "unknown"),
                "dataflow": self._map["dataflows"].get(
                    card_data.get("dataflow_id", ""), {}
                ).get("name", ""),
                "dataset": self._map["datasets"].get(
                    card_data.get("dataset_id", ""), {}
                ).get("name", ""),
                "upstream_sources": upstream_names,
                "last_run": card_data.get("lineage", {}).get("dataset", {}).get("last_run", ""),
            })

        # Export dataflow lineage
        for df_id, df_data in self._map["dataflows"].items():
            upstream_names = " > ".join(df_data.get("upstream_dependencies", []))
            downstream_names = " > ".join(df_data.get("downstream_dependencies", []))

            rows.append({
                "entity_type": "dataflow",
                "entity_id": df_id,
                "entity_name": df_data.get("name", "unknown"),
                "dashboard": "",
                "owner": df_data.get("owner", "unknown"),
                "dataflow": df_data.get("name", "unknown"),
                "dataset": "",
                "upstream_sources": upstream_names,
                "downstream_dependencies": downstream_names,
                "last_run": df_data.get("last_run", ""),
            })

        # Write CSV
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)

        logger.info(f"Lineage exported to {output_path}")
        return output_path

    def export_lineage_json(self, output_path: str) -> str:
        """
        Export lineage map as JSON.

        Args:
            output_path: Path to save the JSON file

        Returns:
            str: Path to the exported file
        """
        if not self._map:
            self.build()

        import json

        with open(output_path, 'w') as f:
            json.dump(self._map, f, indent=2, default=str)

        logger.info(f"Lineage JSON exported to {output_path}")
        return output_path

    def generate_inventory_report(self) -> pd.DataFrame:
        """
        Generate a comprehensive inventory report of all DOMO entities.

        Returns:
            pd.DataFrame: Combined inventory of cards, dataflows, and datasets
        """
        if not self._map:
            self.build()

        rows = []

        # Cards
        for card_id, card_data in self._map["cards"].items():
            rows.append({
                "entity_type": "card",
                "entity_id": card_id,
                "entity_name": card_data.get("name", "unknown"),
                "parent_name": card_data.get("dashboard", "unknown"),
                "owner": card_data.get("owner", "unknown"),
                "entity_type_detail": card_data.get("type", "unknown"),
                "dataflow_id": card_data.get("dataflow_id", ""),
                "dataset_id": card_data.get("dataset_id", ""),
            })

        # Dataflows
        for df_id, df_data in self._map["dataflows"].items():
            rows.append({
                "entity_type": "dataflow",
                "entity_id": df_id,
                "entity_name": df_data.get("name", "unknown"),
                "parent_name": "",
                "owner": df_data.get("owner", "unknown"),
                "entity_type_detail": df_data.get("type", "unknown"),
                "dataflow_id": df_id,
                "dataset_id": "",
            })

        # Datasets
        for ds_id, ds_data in self._map["datasets"].items():
            rows.append({
                "entity_type": "dataset",
                "entity_id": ds_id,
                "entity_name": ds_data.get("name", "unknown"),
                "parent_name": "",
                "owner": ds_data.get("owner", "unknown"),
                "entity_type_detail": ds_data.get("type", "unknown"),
                "dataflow_id": "",
                "dataset_id": ds_id,
            })

        return pd.DataFrame(rows)


def build_lineage_map(client: Optional[DomoAuditClient] = None) -> Dict[str, Any]:
    """
    Build the full lineage map.

    Args:
        client: Optional DomoAuditClient instance

    Returns:
        Dict containing the full lineage map
    """
    lineage_map = LineageMap(client)
    return lineage_map.build()


def export_lineage_csv(
    lineage_map: Optional[Dict[str, Any]] = None,
    output_path: str = "lineage_export.csv",
) -> str:
    """
    Export lineage to CSV.

    Args:
        lineage_map: Optional pre-built lineage map
        output_path: Path for output CSV

    Returns:
        str: Path to exported file
    """
    if lineage_map is None:
        lineage_map = build_lineage_map()

    map_obj = LineageMap()
    map_obj._map = lineage_map
    return map_obj.export_lineage_csv(output_path)
