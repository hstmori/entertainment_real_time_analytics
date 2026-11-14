"""CLI for validated synthetic event publication to Kafka."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import time
from typing import Sequence

from confluent_kafka import KafkaError, Producer

from .config import ProducerSettings
from .contracts import ContractRegistry
from .generator import EVENT_TYPES, EventGenerator


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("base time must include a timezone, for example 2026-11-06T00:00:00Z")
    return parsed.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate, validate, and publish Entertainment events")
    parser.add_argument("--count", type=int, default=100, help="Total number of events")
    parser.add_argument("--rate", type=float, default=20.0, help="Events per second; 0 disables throttling")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument(
        "--customer-pool-size",
        type=int,
        default=200,
        help="Number of synthetic customers available to the generator",
    )
    parser.add_argument(
        "--event-interval-seconds",
        type=float,
        default=0.1,
        help="Business-event time spacing; independent of publish rate",
    )
    parser.add_argument("--event-type", choices=("all", *EVENT_TYPES), default="all")
    parser.add_argument("--base-time", type=_parse_datetime, default=None, help="UTC ISO-8601 base time")
    parser.add_argument("--correlation-id", default=None, help="Run-level UUID; deterministic when omitted")
    parser.add_argument("--bootstrap-servers", default=None, help="Override KAFKA_BOOTSTRAP_SERVERS")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print samples without Kafka")
    parser.add_argument("--sample-limit", type=int, default=4, help="Number of event samples to print")
    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.count < 1:
        raise ValueError("--count must be at least 1")
    if args.rate < 0:
        raise ValueError("--rate cannot be negative")
    if args.sample_limit < 0:
        raise ValueError("--sample-limit cannot be negative")
    if args.customer_pool_size < 1:
        raise ValueError("--customer-pool-size must be at least 1")
    if args.event_interval_seconds <= 0:
        raise ValueError("--event-interval-seconds must be positive")

    settings = ProducerSettings.from_env()
    if args.bootstrap_servers:
        settings = ProducerSettings(
            bootstrap_servers=args.bootstrap_servers,
            client_id=settings.client_id,
            contracts_dir=settings.contracts_dir,
            delivery_timeout_ms=settings.delivery_timeout_ms,
            security=settings.security,
        )

    base_time = args.base_time or datetime.now(UTC)
    generator = EventGenerator(
        seed=args.seed,
        base_time=base_time,
        correlation_id=args.correlation_id,
        customer_pool_size=args.customer_pool_size,
        event_interval_seconds=args.event_interval_seconds,
    )
    contracts = ContractRegistry(settings.contracts_dir)
    producer = None if args.dry_run else Producer(settings.kafka_config())

    generated_counts: Counter[str] = Counter()
    delivery_counts: Counter[str] = Counter()
    delivery_errors: list[str] = []

    def on_delivery(error: KafkaError | None, message: object) -> None:
        if error is not None:
            delivery_errors.append(str(error))
            return
        topic = message.topic()  # type: ignore[attr-defined]
        delivery_counts[topic] += 1

    started_at = time.monotonic()
    for index, event in enumerate(
        generator.iter_events(count=args.count, event_type=args.event_type)
    ):
        contracts.validate(event.event_type, event.payload)
        generated_counts[event.topic] += 1
        serialized = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

        if index < args.sample_limit:
            print(json.dumps({"topic": event.topic, "key": event.key, "payload": event.payload}, ensure_ascii=False))

        if producer is not None:
            while True:
                try:
                    producer.produce(
                        topic=event.topic,
                        key=event.key.encode("utf-8"),
                        value=serialized.encode("utf-8"),
                        headers={"correlation_id": generator.correlation_id},
                        on_delivery=on_delivery,
                    )
                    break
                except BufferError:
                    producer.poll(0.1)
            producer.poll(0)

        if args.rate > 0:
            target_elapsed = (index + 1) / args.rate
            remaining = target_elapsed - (time.monotonic() - started_at)
            if remaining > 0:
                time.sleep(remaining)

    undelivered = 0
    if producer is not None:
        undelivered = producer.flush(settings.delivery_timeout_ms / 1000)

    if delivery_errors or undelivered:
        raise RuntimeError(
            f"Kafka delivery failed: errors={delivery_errors[:3]}, undelivered={undelivered}"
        )

    summary: dict[str, object] = {
        "status": "validated" if args.dry_run else "published",
        "seed": args.seed,
        "correlation_id": generator.correlation_id,
        "base_time": base_time.isoformat(),
        "customer_pool_size": args.customer_pool_size,
        "event_interval_seconds": args.event_interval_seconds,
        "generated": args.count,
        "generated_by_topic": dict(sorted(generated_counts.items())),
        "delivered": sum(delivery_counts.values()),
        "delivered_by_topic": dict(sorted(delivery_counts.items())),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(args)
    return 0


def cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    cli()

