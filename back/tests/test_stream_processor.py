from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from entertainment_pipeline.contracts import ContractRegistry
from entertainment_pipeline.dead_letter import DeadLetterPublisher
from entertainment_pipeline.generator import EventGenerator
from entertainment_pipeline.models import InvalidEvent, SourceCoordinates, ValidatedEvent
from entertainment_pipeline.stream_processor import commit_offsets, decode_message


CONTRACTS_DIR = Path("contracts/jsonschema")
NOW = datetime(2026, 11, 6, 3, 0, tzinfo=UTC)


class FakeMessage:
    def __init__(self, payload: bytes, *, topic: str = "entertainment.booking.v1", partition: int = 1, offset: int = 7) -> None:
        self._payload = payload
        self._topic = topic
        self._partition = partition
        self._offset = offset

    def value(self) -> bytes:
        return self._payload

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return self._partition

    def offset(self) -> int:
        return self._offset

    def timestamp(self) -> tuple[int, int]:
        return (1, 1_794_000_000_000)


def booking_payload() -> dict[str, object]:
    generator = EventGenerator(seed=42, base_time=NOW)
    return dict(next(generator.iter_events(count=1, event_type="booking")).payload)


def test_decode_valid_message_adds_kafka_lineage() -> None:
    payload = booking_payload()
    result = decode_message(
        FakeMessage(json.dumps(payload).encode()),
        registry=ContractRegistry(CONTRACTS_DIR),
        consumer_group="test-group",
        now=NOW,
    )

    assert isinstance(result, ValidatedEvent)
    assert result.coordinates == SourceCoordinates("entertainment.booking.v1", 1, 7)
    assert result.event_id == payload["event_id"]
    assert result.consumer_group == "test-group"
    assert len(result.payload_sha256) == 64


def test_decode_invalid_message_becomes_dlq_candidate() -> None:
    payload = booking_payload()
    payload["currency"] = "VNĐ"
    result = decode_message(
        FakeMessage(json.dumps(payload).encode()),
        registry=ContractRegistry(CONTRACTS_DIR),
        consumer_group="test-group",
        now=NOW,
    )

    assert isinstance(result, InvalidEvent)
    assert result.error_type == "ContractValidationError"
    assert "currency" in result.error_message


def test_malformed_json_becomes_dlq_candidate() -> None:
    result = decode_message(
        FakeMessage(b"{not-json"),
        registry=ContractRegistry(CONTRACTS_DIR),
        consumer_group="test-group",
        now=NOW,
    )
    assert isinstance(result, InvalidEvent)
    assert result.error_type == "JSONDecodeError"


def test_commit_offsets_uses_next_highest_offset_per_partition() -> None:
    invalid = [
        InvalidEvent(SourceCoordinates("topic-a", 0, 3), None, "x", "x", NOW, "g"),
        InvalidEvent(SourceCoordinates("topic-a", 0, 5), None, "x", "x", NOW, "g"),
        InvalidEvent(SourceCoordinates("topic-a", 1, 2), None, "x", "x", NOW, "g"),
    ]
    offsets = commit_offsets(invalid)
    assert [(item.topic, item.partition, item.offset) for item in offsets] == [
        ("topic-a", 0, 6),
        ("topic-a", 1, 3),
    ]


def test_dead_letter_id_is_deterministic_for_source_offset() -> None:
    event = InvalidEvent(
        SourceCoordinates("topic-a", 0, 5),
        "bad",
        "ValueError",
        "bad value",
        NOW,
        "group-a",
    )
    first = DeadLetterPublisher.payload(event)
    second = DeadLetterPublisher.payload(event)
    assert first == second
    assert first["source_offset"] == 5

