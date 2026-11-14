"""Validated dead-letter publication for records rejected by the processor."""

from __future__ import annotations

from datetime import UTC
import json
from pathlib import Path
from typing import Mapping, Sequence
import uuid

from confluent_kafka import KafkaError, Producer
from jsonschema import Draft202012Validator, FormatChecker

from .models import InvalidEvent


DLQ_TOPIC = "entertainment.dead-letter.v1"


class DeadLetterPublisher:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        client_id: str,
        contracts_dir: Path,
        security_config: Mapping[str, object] | None = None,
    ) -> None:
        schema_path = contracts_dir / "dead-letter-v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())
        producer_config: dict[str, object] = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            "acks": "all",
            "enable.idempotence": True,
            "compression.type": "gzip",
            "delivery.timeout.ms": 30_000,
        }
        producer_config.update(security_config or {})
        self.producer = Producer(producer_config)

    @staticmethod
    def payload(event: InvalidEvent) -> dict[str, object]:
        coordinates = event.coordinates
        dead_letter_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"kafka:{coordinates.topic}:{coordinates.partition}:{coordinates.offset}",
            )
        )
        return {
            "dead_letter_id": dead_letter_id,
            "failed_at": event.failed_at.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "source_topic": coordinates.topic,
            "source_partition": coordinates.partition,
            "source_offset": coordinates.offset,
            "consumer_group": event.consumer_group,
            "error_type": event.error_type,
            "error_message": event.error_message[:4000],
            "raw_payload": event.raw_payload,
        }

    def publish(self, events: Sequence[InvalidEvent]) -> int:
        if not events:
            return 0
        errors: list[str] = []
        delivered = 0

        def callback(error: KafkaError | None, _message: object) -> None:
            nonlocal delivered
            if error is not None:
                errors.append(str(error))
            else:
                delivered += 1

        for event in events:
            payload = self.payload(event)
            validation_errors = list(self.validator.iter_errors(payload))
            if validation_errors:
                raise ValueError(f"Invalid DLQ payload: {validation_errors[0].message}")
            coordinates = event.coordinates
            key = f"{coordinates.topic}:{coordinates.partition}:{coordinates.offset}"
            self.producer.produce(
                DLQ_TOPIC,
                key=key.encode("utf-8"),
                value=json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                on_delivery=callback,
            )
            self.producer.poll(0)

        undelivered = self.producer.flush(30)
        if errors or undelivered or delivered != len(events):
            raise RuntimeError(
                f"DLQ delivery failed: delivered={delivered}, expected={len(events)}, "
                f"undelivered={undelivered}, errors={errors[:3]}"
            )
        return delivered

