from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from entertainment_pipeline.powerbi_export import EXPORTS, _csv_value


def test_powerbi_export_covers_all_governed_datasets() -> None:
    assert set(EXPORTS) == {
        "booking_funnel_daily.csv",
        "content_engagement_hourly.csv",
        "customer_360.csv",
        "customer_journey.csv",
        "date.csv",
        "event_performance.csv",
        "refresh_audit.csv",
        "subscription_daily.csv",
    }


def test_csv_value_is_stable_for_business_types() -> None:
    assert _csv_value(Decimal("10.500")) == "10.500"
    assert _csv_value(date(2026, 11, 6)) == "2026-11-06"
    assert _csv_value(True) == "true"
    assert _csv_value(False) == "false"
    assert _csv_value(None) == ""


def test_csv_value_normalizes_aware_datetime_to_utc() -> None:
    value = datetime(2026, 11, 6, 2, 3, 4, 567000, tzinfo=UTC)

    assert _csv_value(value) == "2026-11-06T02:03:04.567Z"
