"""Deterministic synthetic events for the four Entertainment domains."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import random
from typing import Any, Iterator, Mapping
import uuid


EVENT_TYPES = (
    "user_activity",
    "booking",
    "subscription",
    "event_attendance",
)

TOPICS = {
    "user_activity": "entertainment.user-activity.v1",
    "booking": "entertainment.booking.v1",
    "subscription": "entertainment.subscription.v1",
    "event_attendance": "entertainment.event-attendance.v1",
}

PARTITION_KEY_FIELDS = {
    "user_activity": "customer_id",
    "booking": "booking_id",
    "subscription": "customer_id",
    "event_attendance": "entertainment_event_id",
}


@dataclass(frozen=True)
class GeneratedEvent:
    event_type: str
    topic: str
    key: str
    payload: Mapping[str, Any]


class EventGenerator:
    """Create reproducible, cross-domain synthetic events from a fixed seed."""

    def __init__(
        self,
        *,
        seed: int,
        base_time: datetime,
        correlation_id: str | None = None,
        customer_pool_size: int = 200,
        event_interval_seconds: float = 0.1,
    ) -> None:
        if base_time.tzinfo is None:
            raise ValueError("base_time must include timezone information")
        if customer_pool_size < 1:
            raise ValueError("customer_pool_size must be at least 1")
        if event_interval_seconds <= 0:
            raise ValueError("event_interval_seconds must be positive")
        self.seed = seed
        self.base_time = base_time.astimezone(UTC)
        self.customer_pool_size = customer_pool_size
        self.event_interval_seconds = event_interval_seconds
        self.random = random.Random(seed)
        self.correlation_id = correlation_id or str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"entertainment-pipeline:{seed}:{self.base_time.isoformat()}",
            )
        )

    def iter_events(self, *, count: int, event_type: str = "all") -> Iterator[GeneratedEvent]:
        if count < 1:
            raise ValueError("count must be at least 1")
        if event_type != "all" and event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")

        for sequence in range(count):
            selected_type = EVENT_TYPES[sequence % len(EVENT_TYPES)] if event_type == "all" else event_type
            payload = self._build_payload(selected_type, sequence)
            key_field = PARTITION_KEY_FIELDS[selected_type]
            yield GeneratedEvent(
                event_type=selected_type,
                topic=TOPICS[selected_type],
                key=str(payload[key_field]),
                payload=payload,
            )

    def _common(self, sequence: int) -> dict[str, Any]:
        occurred_at = self.base_time + timedelta(seconds=sequence * self.event_interval_seconds)
        return {
            "event_id": str(uuid.UUID(int=self.random.getrandbits(128), version=4)),
            "correlation_id": self.correlation_id,
            "event_version": 1,
            "occurred_at": occurred_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }

    def _build_payload(self, event_type: str, sequence: int) -> dict[str, Any]:
        builders = {
            "user_activity": self._user_activity,
            "booking": self._booking,
            "subscription": self._subscription,
            "event_attendance": self._event_attendance,
        }
        return builders[event_type](sequence)

    def _customer_id(self) -> str:
        return f"customer-{self.random.randint(1, self.customer_pool_size):04d}"

    def _user_activity(self, sequence: int) -> dict[str, Any]:
        activity_type = self.random.choice(
            ("page_view", "search", "play", "pause", "resume", "stop", "complete")
        )
        payload = {
            **self._common(sequence),
            "source": "streaming-app",
            "customer_id": self._customer_id(),
            "session_id": f"session-{self.random.randint(1, 500):05d}",
            "activity_type": activity_type,
            "content_id": None if activity_type in {"page_view", "search"} else f"content-{self.random.randint(1, 80):04d}",
            "device_type": self.random.choice(("web", "mobile", "tablet", "tv")),
            "position_seconds": None if activity_type in {"page_view", "search"} else round(self.random.uniform(0, 7_200), 2),
            "search_term": self.random.choice(("action", "comedy", "concert", "family", "thriller")) if activity_type == "search" else None,
        }
        return payload

    def _booking(self, sequence: int) -> dict[str, Any]:
        quantity = self.random.randint(1, 5)
        unit_price = self.random.choice((90_000, 120_000, 250_000, 500_000, 1_200_000))
        booking_type = self.random.choice(("movie_ticket", "event_ticket", "concert_ticket"))
        return {
            **self._common(sequence),
            "source": "booking-service",
            "booking_id": f"booking-{self.seed:04d}-{sequence:08d}",
            "customer_id": self._customer_id(),
            "booking_type": booking_type,
            "booking_status": self.random.choices(
                ("initiated", "confirmed", "cancelled", "refunded", "failed"),
                weights=(10, 65, 12, 5, 8),
                k=1,
            )[0],
            "quantity": quantity,
            "amount": quantity * unit_price,
            "currency": "VND",
            "content_id": f"content-{self.random.randint(1, 80):04d}" if booking_type == "movie_ticket" else None,
            "entertainment_event_id": None if booking_type == "movie_ticket" else f"live-event-{self.random.randint(1, 30):04d}",
            "venue_id": None if booking_type == "movie_ticket" else f"venue-{self.random.randint(1, 12):03d}",
            "channel": self.random.choice(("web", "mobile", "box_office", "partner")),
        }

    def _subscription(self, sequence: int) -> dict[str, Any]:
        status = self.random.choices(
            ("started", "renewed", "upgraded", "downgraded", "paused", "cancelled", "expired"),
            weights=(18, 45, 8, 5, 6, 12, 6),
            k=1,
        )[0]
        valid_from = self.base_time + timedelta(seconds=sequence * self.event_interval_seconds)
        valid_to = valid_from + timedelta(days=30) if status not in {"cancelled", "expired"} else valid_from
        return {
            **self._common(sequence),
            "source": "membership-service",
            "subscription_id": f"subscription-{self.random.randint(1, 300):05d}",
            "customer_id": self._customer_id(),
            "plan_id": self.random.choice(("basic-monthly", "premium-monthly", "family-monthly")),
            "subscription_status": status,
            "valid_from": valid_from.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "valid_to": valid_to.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "amount": self.random.choice((99_000, 149_000, 249_000)),
            "currency": "VND",
        }

    def _event_attendance(self, sequence: int) -> dict[str, Any]:
        return {
            **self._common(sequence),
            "source": "event-checkin-service",
            "attendance_id": f"attendance-{self.seed:04d}-{sequence:08d}",
            "entertainment_event_id": f"live-event-{self.random.randint(1, 30):04d}",
            "booking_id": f"booking-{self.random.randint(1, 500):08d}",
            "customer_id": self._customer_id(),
            "attendance_status": self.random.choices(
                ("checked_in", "rejected", "no_show"),
                weights=(88, 4, 8),
                k=1,
            )[0],
            "gate_id": f"gate-{self.random.randint(1, 8):02d}",
            "ticket_id": f"ticket-{self.random.randint(1, 2_000):08d}",
        }

