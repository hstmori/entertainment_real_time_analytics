from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from entertainment_pipeline.acceptance_probe import nearest_rank, summarize_rows


def test_nearest_rank_percentiles_are_exact_for_small_acceptance_batch() -> None:
    values = list(range(1, 41))

    assert nearest_rank(values, 0.50) == 20
    assert nearest_rank(values, 0.95) == 38
    assert nearest_rank(values, 0.99) == 40


@pytest.mark.parametrize("percentile", [0, -0.1, 1.1])
def test_nearest_rank_rejects_invalid_percentile(percentile: float) -> None:
    with pytest.raises(ValueError):
        nearest_rank([1], percentile)


def test_acceptance_summary_reconciles_count_lineage_and_latency() -> None:
    base = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)
    rows = [
        (
            f"event-{index}",
            ("booking", "event_attendance", "subscription", "user_activity")[index % 4],
            base + timedelta(milliseconds=index * 100),
            base + timedelta(milliseconds=index * 100 + 500),
            "entertainment.test.v1",
            index % 3,
            index,
        )
        for index in range(40)
    ]

    result = summarize_rows(
        rows,
        observed_at=base + timedelta(seconds=8),
        expected_count=40,
        sla_milliseconds=60_000,
    )

    assert result["status"] == "passed"
    assert result["observed_count"] == 40
    assert result["duplicate_event_ids"] == 0
    assert result["duplicate_source_coordinates"] == 0
    assert result["processing_latency_ms"]["p95"] == 500
    assert result["query_upper_bound_latency_ms"]["p95"] == 8_000 - 200
