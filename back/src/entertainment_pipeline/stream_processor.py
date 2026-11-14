"""Kafka-to-Iceberg processor with validation, DLQ, lineage, and manual commits."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
import time
from typing import Any, Sequence
import uuid

from confluent_kafka import Consumer, KafkaException, Message, TopicPartition

from .config import ProcessorSettings
from .contracts import ContractRegistry
from .dead_letter import DeadLetterPublisher
from .generator import TOPICS
from .lakehouse import IcebergSink
from .models import InvalidEvent, SourceCoordinates, ValidatedEvent


TOPIC_EVENT_TYPES = {topic: event_type for event_type, topic in TOPICS.items()}
SOURCE_TOPICS = tuple(TOPIC_EVENT_TYPES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Kafka events and merge them into Iceberg")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--flush-interval", type=float, default=10.0, help="Maximum batch age in seconds")
    parser.add_argument("--poll-timeout", type=float, default=1.0)
    parser.add_argument("--max-messages", type=int, default=0, help="Exit after N records; 0 runs continuously")
    parser.add_argument("--idle-exit-seconds", type=float, default=0.0, help="Exit after an idle period; 0 disables")
    parser.add_argument("--group-id", default=None)
    parser.add_argument("--bootstrap-servers", default=None)
    parser.add_argument("--initialize-only", action="store_true", help="Create Iceberg schemas/tables and exit")
    return parser


def _message_coordinates(message: Message) -> SourceCoordinates:
    return SourceCoordinates(message.topic(), message.partition(), message.offset())


def decode_message(
    message: Message,
    *,
    registry: ContractRegistry,
    consumer_group: str,
    now: datetime | None = None,
) -> ValidatedEvent | InvalidEvent:
    ingested_at = now or datetime.now(UTC)
    coordinates = _message_coordinates(message)
    raw_bytes = message.value()
    raw_text = None if raw_bytes is None else raw_bytes.decode("utf-8", errors="replace")

    try:
        event_type = TOPIC_EVENT_TYPES[coordinates.topic]
        if raw_bytes is None:
            raise ValueError("Kafka message value is null")
        raw_text = raw_bytes.decode("utf-8")
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("Event payload must be a JSON object")
        registry.validate(event_type, payload)

        timestamp_ms = message.timestamp()[1]
        kafka_timestamp = (
            datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
            if timestamp_ms is not None and timestamp_ms >= 0
            else ingested_at
        )
        canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        ingestion_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"kafka:{coordinates.topic}:{coordinates.partition}:{coordinates.offset}",
            )
        )
        return ValidatedEvent(
            ingestion_id=ingestion_id,
            event_type=event_type,
            payload=payload,
            payload_json=canonical_json,
            payload_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            coordinates=coordinates,
            kafka_timestamp=kafka_timestamp,
            ingested_at=ingested_at,
            consumer_group=consumer_group,
        )
    except Exception as exc:
        return InvalidEvent(
            coordinates=coordinates,
            raw_payload=raw_text,
            error_type=type(exc).__name__,
            error_message=str(exc),
            failed_at=ingested_at,
            consumer_group=consumer_group,
        )


def commit_offsets(events: Sequence[ValidatedEvent | InvalidEvent]) -> list[TopicPartition]:
    high_watermarks: dict[tuple[str, int], int] = {}
    for event in events:
        coordinates = event.coordinates
        key = (coordinates.topic, coordinates.partition)
        high_watermarks[key] = max(high_watermarks.get(key, -1), coordinates.offset + 1)
    return [
        TopicPartition(topic, partition, offset)
        for (topic, partition), offset in sorted(high_watermarks.items())
    ]


def _with_retry(operation: Any, *, attempts: int, backoff_seconds: float) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(backoff_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if args.flush_interval <= 0 or args.poll_timeout <= 0:
        raise ValueError("--flush-interval and --poll-timeout must be positive")
    if args.max_messages < 0 or args.idle_exit_seconds < 0:
        raise ValueError("--max-messages and --idle-exit-seconds cannot be negative")

    settings = ProcessorSettings.from_env()
    if args.group_id:
        settings = replace(settings, group_id=args.group_id)
    if args.bootstrap_servers:
        settings = replace(settings, bootstrap_servers=args.bootstrap_servers)

    registry = ContractRegistry(settings.contracts_dir)
    sink = IcebergSink(
        host=settings.trino_host,
        port=settings.trino_port,
        user=settings.trino_user,
        catalog=settings.trino_catalog,
        bronze_schema=settings.bronze_schema,
        silver_schema=settings.silver_schema,
    )
    sink.ensure_tables()
    if args.initialize_only:
        sink.close()
        summary = {
            "status": "initialized",
            "bronze_table": sink.bronze_table,
            "silver_table": sink.silver_table,
        }
        print(json.dumps(summary, sort_keys=True))
        return summary

    consumer = Consumer(settings.kafka_config())
    dlq = DeadLetterPublisher(
        bootstrap_servers=settings.bootstrap_servers,
        client_id=f"{settings.client_id}-dlq",
        contracts_dir=settings.contracts_dir,
        security_config=settings.security.kafka_config(),
    )
    consumer.subscribe(list(SOURCE_TOPICS))

    pending: list[ValidatedEvent | InvalidEvent] = []
    counts: Counter[str] = Counter()
    started_at = time.monotonic()
    last_message_at = started_at
    batch_started_at = started_at

    def flush() -> None:
        nonlocal pending, batch_started_at
        if not pending:
            return
        valid = [event for event in pending if isinstance(event, ValidatedEvent)]
        invalid = [event for event in pending if isinstance(event, InvalidEvent)]

        def persist() -> int:
            sink.write_batch(valid)
            return dlq.publish(invalid)

        dlq_count = _with_retry(
            persist,
            attempts=settings.max_retries,
            backoff_seconds=settings.retry_backoff_seconds,
        )
        offsets = commit_offsets(pending)
        consumer.commit(offsets=offsets, asynchronous=False)
        counts["batches"] += 1
        counts["valid"] += len(valid)
        counts["invalid"] += len(invalid)
        counts["dlq_delivered"] += dlq_count
        counts["offset_commits"] += len(offsets)
        pending = []
        batch_started_at = time.monotonic()

    try:
        while True:
            message = consumer.poll(args.poll_timeout)
            now_monotonic = time.monotonic()
            if message is None:
                if pending and now_monotonic - batch_started_at >= args.flush_interval:
                    flush()
                if args.idle_exit_seconds and now_monotonic - last_message_at >= args.idle_exit_seconds:
                    break
                continue
            if message.error():
                raise KafkaException(message.error())

            pending.append(
                decode_message(
                    message,
                    registry=registry,
                    consumer_group=settings.group_id,
                )
            )
            counts["consumed"] += 1
            last_message_at = now_monotonic
            if len(pending) >= args.batch_size:
                flush()
            if args.max_messages and counts["consumed"] >= args.max_messages:
                break
        flush()
    finally:
        consumer.close()
        sink.close()

    summary = {
        "status": "completed",
        "group_id": settings.group_id,
        "bronze_schema": settings.bronze_schema,
        "silver_schema": settings.silver_schema,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        **dict(sorted(counts.items())),
    }
    print(json.dumps(summary, sort_keys=True))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    run(build_parser().parse_args(argv))
    return 0


def cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    cli()

