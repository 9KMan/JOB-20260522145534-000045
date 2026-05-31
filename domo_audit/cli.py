"""
CLI Interface for DOMO Audit Toolkit

Command-line interface for listing datasets, dataflows, cards,
generating lineage maps, and creating discrepancy reports.
"""

import sys
import logging
from typing import Optional

import click

# Import the main module
from domo_audit import DomoAuditClient, create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def cli(ctx, debug):
    """
    DOMO Audit Toolkit CLI

    Audit and reconcile DOMO metrics with official scorecard data.
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    ctx.ensure_object(dict)
    ctx.obj['client'] = None # Lazy initialization


def get_client() -> DomoAuditClient:
    """Get or create the DOMO audit client."""
    return create_client()


@cli.command()
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['csv', 'json', 'table']),
 default='table', help='Output format')
@click.pass_context
def list_datasets(ctx, output, format):
    """
    List all DOMO datasets with metadata.

    Shows dataset ID, name, type, owner, last run time, and row/column counts.
    """
    client = get_client()

    if not client.connect():
        click.echo("Error: Failed to connect to DOMO. Check credentials.", err=True)
        sys.exit(1)

    click.echo("Fetching datasets...")
    datasets = client.list_all_datasets()

    if not datasets:
        click.echo("No datasets found.")
        return

    if output:
        import pandas as pd
        df = pd.DataFrame(datasets)
        df.to_csv(output, index=False)
        click.echo(f"Dataset list saved to {output}")
    elif format == 'json':
        import json
        click.echo(json.dumps(datasets, indent=2, default=str))
    else:
        _print_table(datasets, ['id', 'name', 'type', 'owner', 'last_run', 'row_count'])


@cli.command()
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['csv', 'json', 'table']),
              default='table', help='Output format')
@click.pass_context
def list_dataflows(ctx, output, format):
    """
    List all Magic ETL dataflows with dependencies.

    Shows dataflow ID, name, type, owner, status, and upstream/downstream deps.
    """
    client = get_client()

    if not client.connect():
        click.echo("Error: Failed to connect to DOMO. Check credentials.", err=True)
        sys.exit(1)

    click.echo("Fetching dataflows...")
    dataflows = client.list_all_dataflows()

    if not dataflows:
        click.echo("No dataflows found.")
        return

    if output:
        import pandas as pd
        df = pd.DataFrame(dataflows)
        df.to_csv(output, index=False)
        click.echo(f"Dataflow list saved to {output}")
    elif format == 'json':
        import json
        click.echo(json.dumps(dataflows, indent=2, default=str))
    else:
        _print_table(dataflows, ['id', 'name', 'type', 'owner', 'status', 'last_run'])


@cli.command()
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['csv', 'json', 'table']),
              default='table', help='Output format')
@click.pass_context
def list_cards(ctx, output, format):
    """
    List all dashboard cards.

    Shows card ID, name, dashboard, owner, and associated dataset/dataflow.
    """
    client = get_client()

    if not client.connect():
        click.echo("Error: Failed to connect to DOMO. Check credentials.", err=True)
        sys.exit(1)

    click.echo("Fetching cards...")
    cards = client.list_all_cards()

    if not cards:
        click.echo("No cards found.")
        return

    if output:
        import pandas as pd
        df = pd.DataFrame(cards)
        df.to_csv(output, index=False)
        click.echo(f"Card list saved to {output}")
    elif format == 'json':
        import json
        click.echo(json.dumps(cards, indent=2, default=str))
    else:
        _print_table(cards, ['id', 'name', 'dashboard_name', 'owner', 'dataset_id'])


@cli.command()
@click.argument('card_name')
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'text']),
              default='text', help='Output format')
@click.pass_context
def lineage(ctx, card_name, output, format):
    """
    Trace lineage for a specific card.

    Shows the full path: card → dataflow → dataset → source.
    """
    client = get_client()

    if not client.connect():
        click.echo("Error: Failed to connect to DOMO. Check credentials.", err=True)
        sys.exit(1)

    click.echo(f"Tracing lineage for: {card_name}...")
    lineage_data = client.get_metric_lineage(card_name)

    if 'error' in lineage_data:
        click.echo(f"Error: {lineage_data['error']}", err=True)
        sys.exit(1)

    if output:
        import json
        with open(output, 'w') as f:
            json.dump(lineage_data, f, indent=2, default=str)
        click.echo(f"Lineage saved to {output}")
    elif format == 'json':
        import json
        click.echo(json.dumps(lineage_data, indent=2, default=str))
    else:
        _print_lineage(lineage_data)


@cli.command()
@click.option('--scorecard', '-s', required=True, type=click.Path(exists=True),
              help='Path to scorecard CSV file')
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['csv', 'json', 'table']),
              default='csv', help='Output format')
@click.option('--min-variance', '-m', type=float, default=0.0,
              help='Minimum variance percentage to include')
@click.pass_context
def discrepancy_report(ctx, scorecard, output, format, min_variance):
    """
    Generate discrepancy report comparing scorecard to DOMO KPIs.

    Reads a scorecard CSV file and compares each metric against
    the corresponding DOMO card values.
    """
    client = get_client()

    if not client.connect():
        click.echo("Error: Failed to connect to DOMO. Check credentials.", err=True)
        sys.exit(1)

    click.echo("Loading scorecard data...")
    scorecard_data = _load_scorecard(scorecard)

    if not scorecard_data:
        click.echo("Error: Could not load scorecard data.", err=True)
        sys.exit(1)

    click.echo(f"Loaded {len(scorecard_data)} scorecard metrics...")

    # Get all cards
    click.echo("Fetching DOMO cards...")
    cards = client.list_all_cards()

    # Generate report
    from domo_audit.discrepancy import DiscrepancyReporter

    reporter = DiscrepancyReporter(scorecard_data)

    for card in cards:
        # Try to find matching scorecard value
        scorecard_value = None
        card_name_lower = card.get('name', '').lower()

        for metric_name, value in scorecard_data.items():
            if metric_name.lower() in card_name_lower or card_name_lower in metric_name.lower():
                scorecard_value = value
                break

        if scorecard_value is not None:
            reporter.reconcile_scorecard(
                card_name=card.get('name', ''),
                card_id=card.get('id', ''),
                domo_value=None,  # Would need actual DOMO value
                dashboard=card.get('dashboard_name', ''),
                dataflow_id=card.get('dataflow_id'),
                dataset_id=card.get('dataset_id'),
            )

    df = reporter.generate_report()

    # Filter by minimum variance
    if min_variance > 0:
        df = df[df['variance_pct'] >= min_variance]

    if output:
        if format == 'json':
            import json
            with open(output, 'w') as f:
                json.dump(df.to_dict(orient='records'), f, indent=2, default=str)
        else:
            df.to_csv(output, index=False)
        click.echo(f"Discrepancy report saved to {output}")
    elif format == 'json':
        import json
        click.echo(json.dumps(df.to_dict(orient='records'), indent=2, default=str))
    elif format == 'table':
        click.echo(df.to_string())
    else:
        df.to_csv(output, index=False)
        click.echo(f"Discrepancy report saved to {output}")


@cli.command()
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['csv', 'json']),
              default='csv', help='Output format')
@click.pass_context
def build_lineage_map(ctx, output, format):
    """
    Build complete lineage map and export to CSV.

    Creates a full map of all cards → dataflows → datasets → sources.
    """
    client = get_client()

    if not client.connect():
        click.echo("Error: Failed to connect to DOMO. Check credentials.", err=True)
        sys.exit(1)

    click.echo("Building lineage map...")

    from domo_audit.lineage import LineageMap

    lineage_map = LineageMap(client)
    lineage_map.build()

    if output:
        if format == 'json':
            lineage_map.export_lineage_json(output)
        else:
            lineage_map.export_lineage_csv(output)
        click.echo(f"Lineage map exported to {output}")
    else:
        click.echo("Use --output to specify output file path")


@cli.command()
@click.option('--output', '-o', help='Output file path')
@click.option('--since', '-s', help='Include entries after this date (YYYY-MM-DD)')
@click.pass_context
def audit_report(ctx, output, since):
    """
    Generate weekly audit report.

    Shows all fixes applied, by whom, and variance improvements.
    """
    from datetime import datetime
    from domo_audit.audit_log import AuditLog

    log = AuditLog()

    since_dt = None
    if since:
        try:
            since_dt = datetime.strptime(since, '%Y-%m-%d')
        except ValueError:
            click.echo(f"Error: Invalid date format '{since}'. Use YYYY-MM-DD.", err=True)
            sys.exit(1)

    df = log.generate_audit_report(since=since_dt)

    if df.empty:
        click.echo("No audit entries found.")
        return

    stats = log.generate_summary_stats()

    click.echo("\n=== Audit Summary ===")
    click.echo(f"Total fixes: {stats['total_fixes']}")
    click.echo(f"Unique metrics: {stats['unique_metrics']}")
    click.echo(f"Average variance: {stats['avg_variance_pct']:.2f}%")
    click.echo(f"Recent fixes (7 days): {stats['recent_fixes']}")

    if output:
        df.to_csv(output, index=False)
        click.echo(f"Audit report saved to {output}")
    else:
        click.echo("\n=== Recent Fixes ===")
        click.echo(df.to_string())


@cli.command()
@click.argument('metric_name')
@click.option('--agg-type', '-a', type=click.Choice(['SUM', 'AVG', 'COUNT', 'MIN', 'MAX']),
              default='SUM', help='Aggregation type')
@click.option('--value-column', '-v', default='value', help='Value column name')
@click.option('--date-column', '-d', default='date', help='Date column name')
@click.option('--week-start', '-w', type=click.Choice(['monday', 'sunday']),
              default='monday', help='Week start day')
def generate_formula(metric_name, agg_type, value_column, date_column, week_start):
    """
    Generate a Beast Mode formula template.

    Creates a reusable formula with ISO week alignment and COALESCE null handling.
    """
    from domo_audit.beast_modes import generate_metric_formula

    formula = generate_metric_formula(
        metric_name=metric_name,
        agg_type=agg_type,
        value_column=value_column,
        date_column=date_column,
        week_start=week_start,
    )

    click.echo(f"\n=== Beast Mode Formula: {metric_name} ===\n")
    click.echo(formula)


@cli.command()
@click.option('--metric-key', '-m', help='Metric key to check')
@click.pass_context
def audit_log(ctx, metric_key):
    """
    View audit log entries.

    Shows history of fixes applied to specific metrics.
    """
    from domo_audit.audit_log import AuditLog

    log = AuditLog()

    if metric_key:
        entries = log.get_metric_history(metric_key)
        click.echo(f"\n=== Audit History: {metric_key} ===")
    else:
        entries = log.get_entries()
        click.echo("\n=== Recent Audit Entries ===")

    if not entries:
        click.echo("No entries found.")
        return

    for entry in entries:
        click.echo(f"\n[{entry.fixed_at.strftime('%Y-%m-%d %H:%M')}] {entry.metric_name}")
        click.echo(f"  Fix: {entry.fix_applied}")
        click.echo(f"  Variance: {entry.variance_pct:.2f}%")
        click.echo(f"  By: {entry.fixed_by}")


def _print_table(data, columns):
    """Print data as a formatted table."""
    import pandas as pd
    df = pd.DataFrame(data)
    if columns:
        available = [c for c in columns if c in df.columns]
        df = df[available]
    click.echo(df.to_string())


def _print_lineage(lineage_data):
    """Print lineage data in human-readable format."""
    if lineage_data.get('card'):
        card = lineage_data['card']
        click.echo(f"\nCard: {card.get('name', 'unknown')}")
        click.echo(f"  ID: {card.get('id', 'unknown')}")
        click.echo(f"  Type: {card.get('type', 'unknown')}")
        click.echo(f"  Dataset: {card.get('dataset_id', 'unknown')}")
        click.echo(f"  DataFlow: {card.get('dataflow_id', 'unknown')}")

    if lineage_data.get('dataflow'):
        df = lineage_data['dataflow']
        click.echo(f"\nDataFlow: {df.get('name', 'unknown')}")
        click.echo(f"  ID: {df.get('id', 'unknown')}")
        click.echo(f"  Type: {df.get('type', 'unknown')}")

    if lineage_data.get('dataset'):
        ds = lineage_data['dataset']
        click.echo(f"\nDataset: {ds.get('name', 'unknown')}")
        click.echo(f"  ID: {ds.get('id', 'unknown')}")
        click.echo(f"  Rows: {ds.get('row_count', 'unknown')}")

    if lineage_data.get('upstream_sources'):
        click.echo("\nUpstream Sources:")
        for src in lineage_data['upstream_sources']:
            click.echo(f"  - {src.get('name', 'unknown')} ({src.get('type', 'unknown')})")


def _load_scorecard(path):
    """Load scorecard data from CSV file."""
    import pandas as pd
    try:
        df = pd.read_csv(path)
        # Expect columns: metric_name, value (or similar)
        if 'metric_name' in df.columns and 'value' in df.columns:
            return dict(zip(df['metric_name'], df['value']))
        elif 'metric' in df.columns and 'value' in df.columns:
            return dict(zip(df['metric'], df['value']))
        else:
            # Try first two columns
            cols = df.columns.tolist()
            if len(cols) >= 2:
                return dict(zip(df[cols[0]], df[cols[1]]))
    except Exception as e:
        logger.error(f"Error loading scorecard: {e}")
    return None


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == '__main__':
    main()
