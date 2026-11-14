"""Measure conservative event-to-query latency for a correlated acceptance batch."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import math
import os
from typing import Any, Sequence
import uuid

from trino.dbapi import connect


def _milliseconds(later: datetime, earlier: datetime) -> int:
    return round((later - earlier).total_seconds() * 1_000)


def nearest_rank(values: Sequence[int], percentile: float) -> int:
    """Return an exact nearest-rank percentile for a non-empty sample."""

    if not values:
        raise ValueError("values must not be empty")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _latency_summary(values: Sequence[int]) -> dict[str, int]:
    return {
        "min": min(values),
        "p50": nearest_rank(values, 0.50),
        "p95": nearest_rank(values, 0.95),
        "p99": nearest_rank(values, 0.99),
        "max": max(values),
    }


def summarize_rows(
    rows: Sequence[Sequence[Any]],
    *,
    observed_at: datetime,
    expected_count: int,
    sla_milliseconds: int,
) -> dict[str, object]:
    """Summarize lineage, duplicates, and two latency definitions."""

    event_ids = [str(row[0]) for row in rows]
    event_types = [str(row[1]) for row in rows]
    occurred_at = [row[2] for row in rows]
    first_seen_at = [row[3] for row in rows]
    coordinates = [(str(row[4]), int(row[5]), int(row[6])) for row in rows]

    processing_latency = [
        _milliseconds(first_seen, occurred)
        for first_seen, occurred in zip(first_seen_at, occurred_at, strict=True)
    ]
    query_upper_bound = [_milliseconds(observed_at, occurred) for occurred in occurred_at]

    duplicate_event_ids = len(event_ids) - len(set(event_ids))
    duplicate_coordinates = len(coordinates) - len(set(coordinates))
    negative_processing = sum(value < 0 for value in processing_latency)
    negative_query = sum(value < 0 for value in query_upper_bound)
    arrived_over_sla = sum(value > sla_milliseconds for value in query_upper_bound)

    checks = {
        "expected_count": len(rows) == expected_count,
        "unique_event_ids": duplicate_event_ids == 0,
        "unique_source_coordinates": duplicate_coordinates == 0,
        "non_negative_processing_latency": negative_processing == 0,
        "non_negative_query_latency": negative_query == 0,
        "p95_within_sla": nearest_rank(query_upper_bound, 0.95) <= sla_milliseconds,
    }

    return {
        "status": "passed" if all(checks.values()) else "failed",
        "observed_at": observed_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "expected_count": expected_count,
        "observed_count": len(rows),
        "event_type_counts": dict(sorted(Counter(event_types).items())),
        "duplicate_event_ids": duplicate_event_ids,
        "duplicate_source_coordinates": duplicate_coordinates,
        "negative_processing_latency": negative_processing,
        "negative_query_latency": negative_query,
        "arrived_over_sla": arrived_over_sla,
        "sla_milliseconds": sla_milliseconds,
        "processing_latency_ms": _latency_summary(processing_latency),
        "query_upper_bound_latency_ms": _latency_summary(query_upper_bound),
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--sla-seconds", type=float, default=60.0)
    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.expected_count < 1:
        raise ValueError("--expected-count must be positive")
    if args.sla_seconds <= 0:
        raise ValueError("--sla-seconds must be positive")
    correlation_id = str(uuid.UUID(args.correlation_id))

    catalog = os.getenv("TRINO_CATALOG", "iceberg")
    schema = os.getenv("SILVER_SCHEMA", "silver")
    connection = connect(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "entertainment-acceptance-probe"),
        catalog=catalog,
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                SELECT event_id, event_type, occurred_at, first_seen_at,
                       source_topic, source_partition, source_offset
                FROM {catalog}.{schema}.events
                WHERE correlation_id = '{correlation_id}'
                ORDER BY occurred_at, event_id
                """
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    if not rows:
        result: dict[str, object] = {
            "status": "failed",
            "correlation_id": correlation_id,
            "expected_count": args.expected_count,
            "observed_count": 0,
            "error": "No Silver rows found for correlation_id",
        }
        return result

    result = {
        "correlation_id": correlation_id,
        **summarize_rows(
            rows,
            observed_at=datetime.now(UTC),
            expected_count=args.expected_count,
            sla_milliseconds=round(args.sla_seconds * 1_000),
        ),
    }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    result = run(build_parser().parse_args(argv))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
