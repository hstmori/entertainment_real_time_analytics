"""Validate compact synthetic dashboard datasets without third-party packages."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path


RANK_THRESHOLDS = {
    "Diamond": 10_000_000,
    "Platinum": 5_000_000,
    "Gold": 2_000_000,
    "Silver": 500_000,
    "Basic": 0,
}
RANK_ORDER = ["Diamond", "Platinum", "Gold", "Silver", "Basic"]


EXPECTED_GRAINS = {
    "program_event.csv": ("program_id", 1),
    "event_sales_pace.csv": ("program_id", 31),
    "event_sales_detail.csv": ("program_id", 16),
}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _reconcile_programs(programs: list[dict[str, str]], executive: list[dict[str, str]], data_dir: Path) -> None:
    """Program P&L, sales pace, channel breakdown and ExecutiveDaily 'Sự kiện' must tell the same story."""
    as_of = max(row["event_date_utc"] for row in executive)
    detail_sold: Counter[str] = Counter()
    detail_net: Counter[str] = Counter()
    for row in _read(data_dir / "event_sales_detail.csv"):
        detail_sold[row["program_id"]] += int(row["sold_tickets"])
        detail_net[row["program_id"]] += float(row["net_revenue"])
    last_actual: dict[str, int] = {}
    for row in _read(data_dir / "event_sales_pace.csv"):
        actual, forecast = row["actual_cumulative_tickets"], row["forecast_cumulative_tickets"]
        if actual:
            last_actual[row["program_id"]] = int(actual)
        if actual and forecast and int(forecast) < int(actual):
            raise ValueError(f"Forecast below tickets already sold for {row['program_id']} day {row['lead_day']}")

    program_revenue = 0.0
    for row in programs:
        program_id, sold = row["program_id"], int(row["tickets_sold"])
        ticket_revenue = float(row["ticket_gmv"]) + float(row["service_fee"]) - float(row["refund_value"])
        program_revenue += ticket_revenue + float(row["sponsor_revenue"])
        if sold > int(row["capacity"]):
            raise ValueError(f"Tickets sold exceed capacity for {program_id}")
        if detail_sold[program_id] != sold or last_actual.get(program_id, 0) != sold:
            raise ValueError(f"Tickets sold do not reconcile across tables for {program_id}")
        if abs(detail_net[program_id] - ticket_revenue) > 1:
            raise ValueError(f"Channel revenue does not reconcile for {program_id}")
        completed = row["event_date_utc"] <= as_of
        attended = int(row["attendees"]) + int(row["no_shows"])
        if (completed and attended != sold) or (not completed and attended):
            raise ValueError(f"Attendance inconsistent with event date for {program_id}")

    event_line = sum(float(row["net_revenue"]) for row in executive if row["business_line"] == "Sự kiện")
    if abs(event_line - program_revenue) > 1_000:
        raise ValueError(f"ExecutiveDaily 'Sự kiện' ({event_line:,.0f}) != program revenue ({program_revenue:,.0f})")


def validate(data_dir: Path, max_rows: int = 7_000) -> dict[str, object]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    row_counts = manifest["row_counts"]
    total_rows = sum(int(value) for value in row_counts.values())
    if total_rows > max_rows:
        raise ValueError(f"Demo row budget exceeded: {total_rows} > {max_rows}")

    for filename, expected in row_counts.items():
        rows = _read(data_dir / filename)
        if len(rows) != expected:
            raise ValueError(f"Manifest mismatch for {filename}: {len(rows)} != {expected}")

    programs = _read(data_dir / "program_event.csv")
    program_ids = {row["program_id"] for row in programs}
    if len(program_ids) != len(programs):
        raise ValueError("program_event.csv must have one row per program_id")

    for filename, (key, expected_count) in EXPECTED_GRAINS.items():
        counts = Counter(row[key] for row in _read(data_dir / filename))
        if set(counts) != program_ids or set(counts.values()) != {expected_count}:
            raise ValueError(f"Unexpected program grain in {filename}")

    executive = _read(data_dir / "executive_daily.csv")
    lines_by_date: dict[str, set[str]] = {}
    for row in executive:
        lines_by_date.setdefault(row["event_date_utc"], set()).add(row["business_line"])
    if {len(lines) for lines in lines_by_date.values()} != {4}:
        raise ValueError("ExecutiveDaily must contain four business lines per date")

    streaming = _read(data_dir / "streaming_realtime.csv")
    stream_counts = Counter(row["event_time_utc"] for row in streaming)
    if set(stream_counts.values()) != {16}:
        raise ValueError("StreamingRealtime must contain 4 devices x 4 regions per interval")

    operations = _read(data_dir / "operations_realtime.csv")
    operation_counts = Counter(row["event_time_utc"] for row in operations)
    if set(operation_counts.values()) != {4}:
        raise ValueError("OperationsRealtime must contain four services per interval")
    if not any(row["status"] == "Cảnh báo" for row in operations):
        raise ValueError("OperationsRealtime needs at least one demonstration alert")

    customers = _read(data_dir / "customer_360.csv")
    if len(customers) != len({row["customer_id"] for row in customers}):
        raise ValueError("Customer360 must contain one row per customer_id")
    for row in customers:
        spend = int(row["net_spend_12m"])
        expected_rank = next(rank for rank in RANK_ORDER if spend >= RANK_THRESHOLDS[rank])
        if row["member_rank"] != expected_rank:
            raise ValueError(f"Spend rank mismatch for {row['customer_id']}")
        if not row["member_rank_color"].startswith("#") or not row["behavior_risk_color"].startswith("#"):
            raise ValueError(f"Missing semantic color for {row['customer_id']}")
        reconciled_spend = (
            int(row["ticket_spend_12m"]) + int(row["subscription_spend_12m"]) +
            int(row["content_spend_12m"]) - int(row["refund_value_12m"])
        )
        if abs(reconciled_spend - spend) > 2:
            raise ValueError(f"Spend components do not reconcile for {row['customer_id']}")

    activities = _read(data_dir / "customer_activity.csv")
    if len(activities) != len({row["event_id"] for row in activities}):
        raise ValueError("CustomerActivity event_id must be unique")
    if {row["customer_id"] for row in activities} - {row["customer_id"] for row in customers}:
        raise ValueError("CustomerActivity contains unknown customers")

    affinity = _read(data_dir / "customer_affinity.csv")
    affinity_counts = Counter(row["customer_id"] for row in affinity)
    if set(affinity_counts) != {row["customer_id"] for row in customers} or set(affinity_counts.values()) != {4}:
        raise ValueError("CustomerAffinity must contain four rows per customer")

    rank_share = _read(data_dir / "customer_rank_share.csv")
    if len(rank_share) != 10:
        raise ValueError("CustomerRankShare must contain 2 metrics x 5 ranks")
    for metric_type in {row["metric_type"] for row in rank_share}:
        share = sum(float(row["metric_share"]) for row in rank_share if row["metric_type"] == metric_type)
        if abs(share - 1.0) > 0.00001:
            raise ValueError(f"Rank shares do not reconcile for {metric_type}: {share}")
    if (data_dir / "customer_journey.csv").exists():
        raise ValueError("Obsolete customer_journey.csv should be removed")
    for row in customers:
        if float(row["completion_rate"]) > 1:
            raise ValueError(f"Completion rate above 100% for {row['customer_id']}")

    _reconcile_programs(programs, executive, data_dir)

    return {
        "status": "valid",
        "classification": manifest["classification"],
        "files": len(row_counts),
        "total_rows": total_rows,
        "programs": len(programs),
        "executive_dates": len(lines_by_date),
        "streaming_intervals": len(stream_counts),
        "operations_intervals": len(operation_counts),
        "customers": len(customers),
        "customer_activities": len(activities),
        "customer_affinity_rows": len(affinity),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("artifacts/powerbi_demo"))
    parser.add_argument("--max-rows", type=int, default=7_000)
    args = parser.parse_args()
    print(json.dumps(validate(args.data_dir.resolve(), args.max_rows), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
