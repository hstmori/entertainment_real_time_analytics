from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from scripts.build_portfolio_demo_data import build_demo


def test_portfolio_demo_data_is_complete_and_reconciled(tmp_path: Path) -> None:
    manifest = build_demo(
        tmp_path,
        count=80,
        seed=42,
        base_time=datetime(2026, 1, 1, tzinfo=UTC),
        event_interval_seconds=3_600,
        customer_pool_size=20,
        validate_contracts=False,
    )

    expected = {
        "booking_funnel_daily.csv",
        "content_engagement_hourly.csv",
        "customer_360.csv",
        "customer_activity.csv",
        "customer_affinity.csv",
        "customer_rank_share.csv",
        "date.csv",
        "event_performance.csv",
        "refresh_audit.csv",
        "subscription_daily.csv",
        "executive_daily.csv",
        "streaming_realtime.csv",
        "program_event.csv",
        "event_sales_pace.csv",
        "event_sales_detail.csv",
        "operations_realtime.csv",
    }
    assert {path.name for path in tmp_path.glob("*.csv")} == expected
    assert manifest["event_count"] == 80
    assert manifest["classification"] == "deterministic synthetic portfolio demo data"
    assert manifest["row_counts"]["customer_activity.csv"] <= 80  # type: ignore[index]
    assert manifest["row_counts"]["customer_affinity.csv"] == 20 * 4  # type: ignore[index]
    assert manifest["row_counts"]["customer_rank_share.csv"] == 10  # type: ignore[index]
    assert manifest["row_counts"]["program_event.csv"] == 24  # type: ignore[index]
    assert manifest["row_counts"]["event_sales_pace.csv"] == 24 * 31  # type: ignore[index]
    assert sum(manifest["row_counts"].values()) < 7_000  # type: ignore[union-attr]

    with (tmp_path / "customer_360.csv").open(encoding="utf-8") as handle:
        customers = list(csv.DictReader(handle))
    assert customers
    assert len(customers) == len({row["customer_id"] for row in customers})
    assert {row["behavior_segment"] for row in customers}
    assert {row["member_rank"] for row in customers}
    assert all(row["member_rank_color"].startswith("#") for row in customers)

    thresholds = {"Diamond": 10_000_000, "Platinum": 5_000_000, "Gold": 2_000_000, "Silver": 500_000, "Basic": 0}
    rank_order = ["Diamond", "Platinum", "Gold", "Silver", "Basic"]
    for row in customers:
        spend = int(row["net_spend_12m"])
        expected_rank = next(rank for rank in rank_order if spend >= thresholds[rank])
        assert row["member_rank"] == expected_rank
        reconciled = int(row["ticket_spend_12m"]) + int(row["subscription_spend_12m"]) + int(row["content_spend_12m"]) - int(row["refund_value_12m"])
        assert abs(reconciled - spend) <= 2

    with (tmp_path / "customer_activity.csv").open(encoding="utf-8") as handle:
        activity = list(csv.DictReader(handle))
    assert len(activity) == len({row["event_id"] for row in activity})
    assert {row["customer_id"] for row in activity} <= {row["customer_id"] for row in customers}

    events_by_customer = Counter(row["customer_id"] for row in activity)
    domains_by_customer: dict[str, set[str]] = defaultdict(set)
    for row in activity:
        domains_by_customer[row["customer_id"]].add(row["domain"])

    assert sum(int(row["total_events"]) for row in customers) == 80
    for row in customers:
        customer_id = row["customer_id"]
        assert events_by_customer[customer_id] <= int(row["total_events"])
        if events_by_customer[customer_id]:
            assert domains_by_customer[customer_id]


def test_demo_tables_reconcile_across_pages(tmp_path: Path) -> None:
    from scripts.validate_dashboard_demo_data import validate

    build_demo(
        tmp_path,
        count=80,
        seed=42,
        base_time=datetime(2026, 1, 1, tzinfo=UTC),
        event_interval_seconds=3_600,
        customer_pool_size=20,
        validate_contracts=False,
    )

    assert validate(tmp_path)["status"] == "valid"
