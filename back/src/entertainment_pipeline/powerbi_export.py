"""Export governed Gold tables to deterministic CSV files for the PBIP model."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Sequence

from trino.dbapi import connect


EXPORTS = {
    "content_engagement_hourly.csv": "SELECT * FROM {gold}.content_engagement_hourly ORDER BY event_hour_utc, content_id, device_type",
    "booking_funnel_daily.csv": "SELECT * FROM {gold}.booking_funnel_daily ORDER BY event_date_utc, destination_type, destination_id, channel",
    "event_performance.csv": "SELECT * FROM {gold}.event_performance ORDER BY entertainment_event_id, currency",
    "subscription_daily.csv": "SELECT * FROM {gold}.subscription_daily ORDER BY event_date_utc, plan_id, currency",
    "customer_360.csv": "SELECT * FROM {gold}.customer_360 ORDER BY customer_id",
    "customer_journey.csv": "SELECT * FROM {gold}.customer_journey ORDER BY occurred_at, event_id",
    "refresh_audit.csv": "SELECT * FROM {gold}.refresh_audit ORDER BY refreshed_at, model_name",
    "date.csv": """
        SELECT DISTINCT event_date_utc AS date
        FROM (
            SELECT event_date_utc FROM {gold}.content_engagement_hourly
            UNION ALL
            SELECT event_date_utc FROM {gold}.booking_funnel_daily
            UNION ALL
            SELECT event_date_utc FROM {gold}.subscription_daily
            UNION ALL
            SELECT event_date_utc FROM {gold}.customer_journey
        )
        ORDER BY date
    """,
}


def _csv_value(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(timezone.utc)
            return normalized.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return normalized.isoformat(timespec="milliseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def export_tables(output_dir: Path) -> dict[str, int]:
    catalog = os.getenv("TRINO_CATALOG", "iceberg")
    schema = os.getenv("GOLD_SCHEMA", "gold")
    gold = f"{catalog}.{schema}"
    connection = connect(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "entertainment-powerbi-exporter"),
        catalog=catalog,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    try:
        for filename, query_template in EXPORTS.items():
            cursor = connection.cursor()
            try:
                cursor.execute(query_template.format(gold=gold))
                rows = cursor.fetchall()
                headers = [str(column[0]) for column in cursor.description]
            finally:
                cursor.close()

            destination = output_dir / filename
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(headers)
                writer.writerows([_csv_value(value) for value in row] for row in rows)
            temporary.replace(destination)
            counts[filename] = len(rows)
    finally:
        connection.close()
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/powerbi"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    counts = export_tables(args.output_dir)
    print(json.dumps({"status": "exported", "row_counts": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

