"""Shared records used between Kafka decoding and lakehouse persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True)
class SourceCoordinates:
    topic: str
    partition: int
    offset: int


@dataclass(frozen=True)
class ValidatedEvent:
    ingestion_id: str
    event_type: str
    payload: Mapping[str, Any]
    payload_json: str
    payload_sha256: str
    coordinates: SourceCoordinates
    kafka_timestamp: datetime
    ingested_at: datetime
    consumer_group: str

    @property
    def event_id(self) -> str:
        return str(self.payload["event_id"])

    @property
    def correlation_id(self) -> str:
        return str(self.payload["correlation_id"])

    @property
    def occurred_at(self) -> str:
        return str(self.payload["occurred_at"])

    @property
    def amount(self) -> Decimal | None:
        value = self.payload.get("amount")
        return None if value is None else Decimal(str(value))

    @property
    def entity_id(self) -> str | None:
        for field in ("booking_id", "subscription_id", "attendance_id", "content_id"):
            if self.payload.get(field) is not None:
                return str(self.payload[field])
        return None

    @property
    def status(self) -> str | None:
        for field in (
            "booking_status",
            "subscription_status",
            "attendance_status",
            "activity_type",
        ):
            if self.payload.get(field) is not None:
                return str(self.payload[field]).lower()
        return None


@dataclass(frozen=True)
class InvalidEvent:
    coordinates: SourceCoordinates
    raw_payload: str | None
    error_type: str
    error_message: str
    failed_at: datetime
    consumer_group: str

