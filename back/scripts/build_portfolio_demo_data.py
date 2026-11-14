"""Build a deterministic, multi-period Power BI demo dataset from valid synthetic events."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from entertainment_pipeline.generator import EventGenerator
try:
    from scripts.build_executive_demo_tables import build_executive_tables
    from scripts.build_customer_dashboard_data import build_customer_dashboard_tables
except ModuleNotFoundError:  # Direct execution: python scripts/build_portfolio_demo_data.py
    from build_executive_demo_tables import build_executive_tables
    from build_customer_dashboard_data import build_customer_dashboard_tables


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _decimal(value: object | None) -> Decimal:
    return Decimal("0") if value is None else Decimal(str(value))


def _ratio(numerator: int, denominator: int) -> str:
    return "" if denominator == 0 else f"{numerator / denominator:.4f}"


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[dict[str, object]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            normalized = {
                key: (
                    "true" if value is True else
                    "false" if value is False else
                    format(value, "f") if isinstance(value, Decimal) else
                    value
                )
                for key, value in row.items()
            }
            writer.writerow(normalized)
    return len(materialized)


def _action(payload: dict[str, Any], event_type: str) -> str:
    field = {
        "user_activity": "activity_type",
        "booking": "booking_status",
        "subscription": "subscription_status",
        "event_attendance": "attendance_status",
    }[event_type]
    return str(payload[field]).lower()


def build_demo(
    output_dir: Path,
    *,
    count: int = 1_200,
    seed: int = 20_261_107,
    base_time: datetime = datetime(2026, 7, 29, tzinfo=UTC),
    event_interval_seconds: float = 7_200,
    customer_pool_size: int = 200,
    contracts_dir: Path = Path("contracts/jsonschema"),
    validate_contracts: bool = True,
) -> dict[str, object]:
    generator = EventGenerator(
        seed=seed,
        base_time=base_time,
        customer_pool_size=customer_pool_size,
        event_interval_seconds=event_interval_seconds,
    )
    registry = None
    if validate_contracts:
        from entertainment_pipeline.contracts import ContractRegistry

        registry = ContractRegistry(contracts_dir)
    events: list[dict[str, Any]] = []
    for generated in generator.iter_events(count=count, event_type="all"):
        payload = dict(generated.payload)
        if registry is not None:
            registry.validate(generated.event_type, payload)
        events.append({"event_type": generated.event_type, "payload": payload})

    snapshot_at = max(_parse_utc(item["payload"]["occurred_at"]) for item in events)

    content_groups: dict[tuple[object, ...], dict[str, Any]] = {}
    for item in events:
        if item["event_type"] != "user_activity":
            continue
        payload = item["payload"]
        occurred_at = _parse_utc(payload["occurred_at"])
        hour = occurred_at.replace(minute=0, second=0, microsecond=0)
        key = (hour, payload.get("content_id") or "__NO_CONTENT__", payload.get("device_type") or "")
        group = content_groups.setdefault(
            key,
            {"events": 0, "users": set(), "plays": 0, "completions": 0, "position": Decimal("0")},
        )
        group["events"] += 1
        group["users"].add(payload["customer_id"])
        group["plays"] += payload["activity_type"] == "play"
        group["completions"] += payload["activity_type"] == "complete"
        group["position"] += _decimal(payload.get("position_seconds"))
    content_rows = []
    for (hour, content_id, device_type), group in sorted(content_groups.items()):
        content_rows.append(
            {
                "event_hour_utc": _iso(hour),
                "event_date_utc": hour.date().isoformat(),
                "content_id": content_id,
                "device_type": device_type,
                "activity_events": group["events"],
                "active_users": len(group["users"]),
                "play_events": group["plays"],
                "completion_events": group["completions"],
                "completion_per_play_proxy": _ratio(group["completions"], group["plays"]),
                "observed_position_seconds": group["position"].quantize(Decimal("0.01")),
            }
        )

    booking_groups: dict[tuple[str, ...], dict[str, Any]] = {}
    event_booking: dict[tuple[str, str], dict[str, Any]] = {}
    attendance_groups: dict[str, dict[str, Any]] = {}
    for item in events:
        payload = item["payload"]
        occurred_at = _parse_utc(payload["occurred_at"])
        if item["event_type"] == "booking":
            status = payload["booking_status"]
            destination_id = payload.get("entertainment_event_id") or payload.get("content_id") or ""
            destination_type = "live_event" if payload.get("entertainment_event_id") else "content"
            key = (
                occurred_at.date().isoformat(), destination_type, destination_id,
                payload["booking_type"], payload.get("channel") or "", payload["currency"],
            )
            group = booking_groups.setdefault(key, {"statuses": Counter(), "confirmed_quantity": 0, "refunded_quantity": 0, "confirmed_amount": Decimal("0"), "refunded_amount": Decimal("0")})
            group["statuses"][status] += 1
            amount = _decimal(payload["amount"])
            quantity = int(payload["quantity"])
            if status == "confirmed":
                group["confirmed_quantity"] += quantity
                group["confirmed_amount"] += amount
            elif status == "refunded":
                group["refunded_quantity"] += quantity
                group["refunded_amount"] += amount

            live_event_id = payload.get("entertainment_event_id")
            if live_event_id:
                event_key = (live_event_id, payload["currency"])
                event_group = event_booking.setdefault(event_key, {"statuses": Counter(), "confirmed_tickets": 0, "refunded_tickets": 0, "net_value": Decimal("0"), "times": []})
                event_group["statuses"][status] += 1
                event_group["times"].append(occurred_at)
                if status == "confirmed":
                    event_group["confirmed_tickets"] += quantity
                    event_group["net_value"] += amount
                elif status == "refunded":
                    event_group["refunded_tickets"] += quantity
                    event_group["net_value"] -= amount
        elif item["event_type"] == "event_attendance":
            event_id = payload["entertainment_event_id"]
            group = attendance_groups.setdefault(event_id, {"statuses": Counter(), "times": []})
            group["statuses"][payload["attendance_status"]] += 1
            group["times"].append(occurred_at)

    booking_rows = []
    for key, group in sorted(booking_groups.items()):
        date_value, destination_type, destination_id, booking_type, channel, currency = key
        statuses = group["statuses"]
        total = sum(statuses.values())
        booking_rows.append(
            {
                "event_date_utc": date_value, "destination_type": destination_type,
                "destination_id": destination_id, "booking_type": booking_type,
                "channel": channel, "currency": currency, "booking_state_events": total,
                "initiated_events": statuses["initiated"], "confirmed_events": statuses["confirmed"],
                "cancelled_events": statuses["cancelled"], "refunded_events": statuses["refunded"],
                "failed_events": statuses["failed"], "confirmed_quantity": group["confirmed_quantity"],
                "refunded_quantity": group["refunded_quantity"], "confirmed_amount": group["confirmed_amount"],
                "refunded_amount": group["refunded_amount"],
                "net_booking_value_proxy": group["confirmed_amount"] - group["refunded_amount"],
                "confirmation_share_proxy": _ratio(statuses["confirmed"], total),
            }
        )

    event_performance_rows = []
    all_event_ids = sorted({key[0] for key in event_booking} | set(attendance_groups))
    for event_id in all_event_ids:
        booking_keys = sorted(key for key in event_booking if key[0] == event_id)
        if not booking_keys:
            booking_keys = [(event_id, "")]
        for key in booking_keys:
            booking = event_booking.get(key)
            attendance = attendance_groups.get(event_id)
            booking_statuses = Counter() if booking is None else booking["statuses"]
            attendance_statuses = Counter() if attendance is None else attendance["statuses"]
            attendance_count = sum(attendance_statuses.values())
            event_performance_rows.append(
                {
                    "entertainment_event_id": event_id, "currency": key[1],
                    "confirmed_bookings": booking_statuses["confirmed"],
                    "refunded_bookings": booking_statuses["refunded"],
                    "confirmed_tickets": 0 if booking is None else booking["confirmed_tickets"],
                    "refunded_tickets": 0 if booking is None else booking["refunded_tickets"],
                    "net_booking_value_proxy": Decimal("0") if booking is None else booking["net_value"],
                    "attendance_records": attendance_count, "checked_in": attendance_statuses["checked_in"],
                    "no_show": attendance_statuses["no_show"], "rejected": attendance_statuses["rejected"],
                    "attendance_rate_proxy": _ratio(attendance_statuses["checked_in"], attendance_count),
                    "no_show_rate_proxy": _ratio(attendance_statuses["no_show"], attendance_count),
                    "first_booking_event_at": "" if booking is None else _iso(min(booking["times"])),
                    "last_booking_event_at": "" if booking is None else _iso(max(booking["times"])),
                    "first_attendance_event_at": "" if attendance is None else _iso(min(attendance["times"])),
                    "last_attendance_event_at": "" if attendance is None else _iso(max(attendance["times"])),
                }
            )

    subscription_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in events:
        if item["event_type"] != "subscription":
            continue
        payload = item["payload"]
        occurred_at = _parse_utc(payload["occurred_at"])
        key = (occurred_at.date().isoformat(), payload["plan_id"], payload.get("currency") or "")
        group = subscription_groups.setdefault(key, {"statuses": Counter(), "mrr": Decimal("0"), "cancelled": Decimal("0")})
        status = payload["subscription_status"]
        amount = _decimal(payload.get("amount"))
        group["statuses"][status] += 1
        if status in {"started", "renewed", "upgraded"}:
            group["mrr"] += amount
        if status == "cancelled":
            group["cancelled"] += amount
    subscription_rows = []
    for (date_value, plan_id, currency), group in sorted(subscription_groups.items()):
        statuses = group["statuses"]
        subscription_rows.append(
            {
                "event_date_utc": date_value, "plan_id": plan_id, "currency": currency,
                "subscription_events": sum(statuses.values()), "started_events": statuses["started"],
                "renewed_events": statuses["renewed"], "upgraded_events": statuses["upgraded"],
                "downgraded_events": statuses["downgraded"], "paused_events": statuses["paused"],
                "cancelled_events": statuses["cancelled"], "expired_events": statuses["expired"],
                "mrr_event_value_proxy": group["mrr"], "cancelled_value_context": group["cancelled"],
            }
        )

    row_counts: dict[str, int] = {}
    row_counts["content_engagement_hourly.csv"] = _write_csv(output_dir / "content_engagement_hourly.csv", [
        "event_hour_utc", "event_date_utc", "content_id", "device_type", "activity_events",
        "active_users", "play_events", "completion_events", "completion_per_play_proxy",
        "observed_position_seconds",
    ], content_rows)
    row_counts["booking_funnel_daily.csv"] = _write_csv(output_dir / "booking_funnel_daily.csv", [
        "event_date_utc", "destination_type", "destination_id", "booking_type", "channel", "currency",
        "booking_state_events", "initiated_events", "confirmed_events", "cancelled_events",
        "refunded_events", "failed_events", "confirmed_quantity", "refunded_quantity",
        "confirmed_amount", "refunded_amount", "net_booking_value_proxy", "confirmation_share_proxy",
    ], booking_rows)
    row_counts["event_performance.csv"] = _write_csv(output_dir / "event_performance.csv", [
        "entertainment_event_id", "currency", "confirmed_bookings", "refunded_bookings",
        "confirmed_tickets", "refunded_tickets", "net_booking_value_proxy", "attendance_records",
        "checked_in", "no_show", "rejected", "attendance_rate_proxy", "no_show_rate_proxy",
        "first_booking_event_at", "last_booking_event_at", "first_attendance_event_at",
        "last_attendance_event_at",
    ], event_performance_rows)
    row_counts["subscription_daily.csv"] = _write_csv(output_dir / "subscription_daily.csv", [
        "event_date_utc", "plan_id", "currency", "subscription_events", "started_events",
        "renewed_events", "upgraded_events", "downgraded_events", "paused_events",
        "cancelled_events", "expired_events", "mrr_event_value_proxy", "cancelled_value_context",
    ], subscription_rows)
    customer_counts = build_customer_dashboard_tables(
        output_dir,
        events=events,
        snapshot_at=snapshot_at,
        seed=seed,
        customer_pool_size=customer_pool_size,
    )
    row_counts.update(customer_counts)
    all_dates = sorted({_parse_utc(item["payload"]["occurred_at"]).date().isoformat() for item in events})
    row_counts["date.csv"] = _write_csv(output_dir / "date.csv", ["date"], ({"date": value} for value in all_dates))

    executive_counts = build_executive_tables(
        output_dir,
        start_date=datetime.fromisoformat(all_dates[0]).date(),
        end_date=datetime.fromisoformat(all_dates[-1]).date(),
        seed=seed,
    )
    row_counts.update(executive_counts)

    model_rows = {
        "content_engagement_hourly": len(content_rows),
        "booking_funnel_daily": len(booking_rows),
        "event_performance": len(event_performance_rows),
        "subscription_daily": len(subscription_rows),
        "customer_360": customer_counts["customer_360.csv"],
        "customer_activity": customer_counts["customer_activity.csv"],
        "customer_affinity": customer_counts["customer_affinity.csv"],
        "customer_rank_share": customer_counts["customer_rank_share.csv"],
        "executive_daily": executive_counts["executive_daily.csv"],
        "streaming_realtime": executive_counts["streaming_realtime.csv"],
        "program_event": executive_counts["program_event.csv"],
        "event_sales_pace": executive_counts["event_sales_pace.csv"],
        "event_sales_detail": executive_counts["event_sales_detail.csv"],
        "operations_realtime": executive_counts["operations_realtime.csv"],
    }
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"portfolio-demo:{seed}:{base_time.isoformat()}:{count}"))
    refreshed_at = _iso(snapshot_at + timedelta(minutes=1))
    audit_rows = [
        {
            "run_id": run_id, "model_name": model_name, "refreshed_at": refreshed_at,
            "row_count": row_count, "silver_snapshot_rows": count, "status": "SUCCEEDED",
        }
        for model_name, row_count in model_rows.items()
    ]
    row_counts["refresh_audit.csv"] = _write_csv(output_dir / "refresh_audit.csv", [
        "run_id", "model_name", "refreshed_at", "row_count", "silver_snapshot_rows", "status",
    ], audit_rows)

    manifest = {
        "status": "generated",
        "classification": "deterministic synthetic portfolio demo data",
        "seed": seed,
        "event_count": count,
        "customer_pool_size": customer_pool_size,
        "customer_count": customer_counts["customer_360.csv"],
        "base_time": _iso(base_time),
        "max_event_time": _iso(snapshot_at),
        "event_interval_seconds": event_interval_seconds,
        "row_counts": row_counts,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/powerbi_demo"))
    parser.add_argument("--count", type=int, default=1_200)
    parser.add_argument("--seed", type=int, default=20_261_107)
    parser.add_argument("--base-time", default="2026-07-29T00:00:00Z")
    parser.add_argument("--event-interval-seconds", type=float, default=7_200)
    parser.add_argument("--customer-pool-size", type=int, default=200)
    parser.add_argument("--contracts-dir", type=Path, default=Path("contracts/jsonschema"))
    parser.add_argument(
        "--skip-contract-validation",
        action="store_true",
        help="Generate from the tested EventGenerator without importing jsonschema",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = build_demo(
        args.output_dir,
        count=args.count,
        seed=args.seed,
        base_time=_parse_utc(args.base_time),
        event_interval_seconds=args.event_interval_seconds,
        customer_pool_size=args.customer_pool_size,
        contracts_dir=args.contracts_dir,
        validate_contracts=not args.skip_contract_validation,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
