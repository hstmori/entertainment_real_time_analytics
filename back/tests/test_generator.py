from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from entertainment_pipeline.contracts import ContractRegistry, ContractValidationError
from entertainment_pipeline.generator import (
    EVENT_TYPES,
    PARTITION_KEY_FIELDS,
    EventGenerator,
)


BASE_TIME = datetime(2026, 11, 6, tzinfo=UTC)
CONTRACTS_DIR = Path("contracts/jsonschema")


def make_generator() -> EventGenerator:
    return EventGenerator(seed=42, base_time=BASE_TIME)


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_each_domain_event_matches_contract(event_type: str) -> None:
    registry = ContractRegistry(CONTRACTS_DIR)
    event = next(make_generator().iter_events(count=1, event_type=event_type))

    registry.validate(event_type, event.payload)
    assert event.payload["event_version"] == 1
    assert str(event.payload["occurred_at"]).endswith("Z")


def test_all_mode_is_round_robin_and_balanced() -> None:
    events = list(make_generator().iter_events(count=12, event_type="all"))

    assert [event.event_type for event in events[:4]] == list(EVENT_TYPES)
    assert {event_type: sum(event.event_type == event_type for event in events) for event_type in EVENT_TYPES} == {
        event_type: 3 for event_type in EVENT_TYPES
    }


def test_partition_key_comes_from_contract_field() -> None:
    for event in make_generator().iter_events(count=4, event_type="all"):
        assert event.key == event.payload[PARTITION_KEY_FIELDS[event.event_type]]


def test_same_seed_and_base_time_are_reproducible() -> None:
    first = list(make_generator().iter_events(count=8, event_type="all"))
    second = list(make_generator().iter_events(count=8, event_type="all"))

    assert first == second


def test_customer_pool_and_business_time_spacing_are_configurable() -> None:
    generator = EventGenerator(
        seed=42,
        base_time=BASE_TIME,
        customer_pool_size=5,
        event_interval_seconds=3_600,
    )
    events = list(generator.iter_events(count=8, event_type="all"))

    assert all(1 <= int(str(event.payload["customer_id"]).split("-")[-1]) <= 5 for event in events)
    assert events[1].payload["occurred_at"] == "2026-11-06T01:00:00.000Z"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"customer_pool_size": 0}, "customer_pool_size"),
        ({"event_interval_seconds": 0}, "event_interval_seconds"),
    ],
)
def test_generator_rejects_invalid_population_settings(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        EventGenerator(seed=42, base_time=BASE_TIME, **kwargs)  # type: ignore[arg-type]


def test_invalid_payload_is_rejected() -> None:
    registry = ContractRegistry(CONTRACTS_DIR)
    event = next(make_generator().iter_events(count=1, event_type="booking"))
    invalid = dict(event.payload)
    invalid["currency"] = "VNĐ"

    with pytest.raises(ContractValidationError, match="currency"):
        registry.validate("booking", invalid)

