"""Idempotent micro-batch writes to Bronze and Silver Iceberg tables via Trino."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
import re
from typing import Any

from trino.dbapi import connect

from .models import ValidatedEvent


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return value


def _string(value: object | None) -> str:
    if value is None:
        return "CAST(NULL AS VARCHAR)"
    return "'" + str(value).replace("'", "''") + "'"


def _timestamp(value: object) -> str:
    iso_value = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return f"from_iso8601_timestamp({_string(iso_value)})"


def _decimal(value: Decimal | None) -> str:
    if value is None:
        return "CAST(NULL AS DECIMAL(18,2))"
    return f"CAST({_string(value)} AS DECIMAL(18,2))"


class IcebergSink:
    """Create target tables and merge batches using deterministic lineage keys."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        catalog: str,
        bronze_schema: str,
        silver_schema: str,
        connection_factory: Callable[..., Any] = connect,
    ) -> None:
        self.catalog = _identifier(catalog)
        self.bronze_schema = _identifier(bronze_schema)
        self.silver_schema = _identifier(silver_schema)
        self.connection = connection_factory(
            host=host,
            port=port,
            user=user,
            catalog=self.catalog,
        )

    @property
    def bronze_table(self) -> str:
        return f"{self.catalog}.{self.bronze_schema}.raw_events"

    @property
    def silver_table(self) -> str:
        return f"{self.catalog}.{self.silver_schema}.events"

    def execute(self, sql: str) -> list[list[Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            return list(cursor.fetchall()) if cursor.description else []
        finally:
            cursor.close()

    def ensure_tables(self) -> None:
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{self.bronze_schema}")
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{self.silver_schema}")
        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.bronze_table} (
                ingestion_id VARCHAR,
                event_type VARCHAR,
                event_id VARCHAR,
                correlation_id VARCHAR,
                event_version INTEGER,
                occurred_at TIMESTAMP(3) WITH TIME ZONE,
                source VARCHAR,
                payload_json VARCHAR,
                payload_sha256 VARCHAR,
                source_topic VARCHAR,
                source_partition INTEGER,
                source_offset BIGINT,
                kafka_timestamp TIMESTAMP(3) WITH TIME ZONE,
                ingested_at TIMESTAMP(3) WITH TIME ZONE,
                ingested_date DATE,
                consumer_group VARCHAR
            )
            WITH (format = 'PARQUET', partitioning = ARRAY['ingested_date'])
            """
        )
        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.silver_table} (
                event_id VARCHAR,
                correlation_id VARCHAR,
                event_type VARCHAR,
                event_version INTEGER,
                occurred_at TIMESTAMP(3) WITH TIME ZONE,
                event_date DATE,
                source VARCHAR,
                customer_id VARCHAR,
                entity_id VARCHAR,
                status VARCHAR,
                amount DECIMAL(18,2),
                currency VARCHAR,
                payload_json VARCHAR,
                payload_sha256 VARCHAR,
                source_topic VARCHAR,
                source_partition INTEGER,
                source_offset BIGINT,
                first_seen_at TIMESTAMP(3) WITH TIME ZONE
            )
            WITH (format = 'PARQUET', partitioning = ARRAY['event_date'])
            """
        )

    def write_batch(self, events: Sequence[ValidatedEvent]) -> None:
        if not events:
            return
        self.execute(self._bronze_merge(events))
        self.execute(self._silver_merge(events))

    def _bronze_merge(self, events: Iterable[ValidatedEvent]) -> str:
        rows = ",\n".join(self._bronze_row(event) for event in events)
        columns = (
            "ingestion_id, event_type, event_id, correlation_id, event_version, "
            "occurred_at, source, payload_json, payload_sha256, source_topic, "
            "source_partition, source_offset, kafka_timestamp, ingested_at, "
            "ingested_date, consumer_group"
        )
        return f"""
            MERGE INTO {self.bronze_table} AS target
            USING (VALUES {rows}) AS source ({columns})
            ON target.source_topic = source.source_topic
               AND target.source_partition = source.source_partition
               AND target.source_offset = source.source_offset
            WHEN NOT MATCHED THEN INSERT ({columns})
            VALUES ({', '.join('source.' + item.strip() for item in columns.split(','))})
        """

    def _silver_merge(self, events: Iterable[ValidatedEvent]) -> str:
        rows = ",\n".join(self._silver_row(event) for event in events)
        columns = (
            "event_id, correlation_id, event_type, event_version, occurred_at, "
            "event_date, source, customer_id, entity_id, status, amount, currency, "
            "payload_json, payload_sha256, source_topic, source_partition, "
            "source_offset, first_seen_at"
        )
        return f"""
            MERGE INTO {self.silver_table} AS target
            USING (
                SELECT {columns}
                FROM (
                    SELECT batch_source.*,
                           row_number() OVER (
                               PARTITION BY event_id
                               ORDER BY source_topic, source_partition, source_offset
                           ) AS batch_rank
                    FROM (VALUES {rows}) AS batch_source ({columns})
                )
                WHERE batch_rank = 1
            ) AS source
            ON target.event_id = source.event_id
            WHEN NOT MATCHED THEN INSERT ({columns})
            VALUES ({', '.join('source.' + item.strip() for item in columns.split(','))})
        """

    @staticmethod
    def _bronze_row(event: ValidatedEvent) -> str:
        payload = event.payload
        return "(" + ", ".join(
            (
                _string(event.ingestion_id),
                _string(event.event_type),
                _string(event.event_id),
                _string(event.correlation_id),
                str(int(payload["event_version"])),
                _timestamp(event.occurred_at),
                _string(payload["source"]),
                _string(event.payload_json),
                _string(event.payload_sha256),
                _string(event.coordinates.topic),
                str(event.coordinates.partition),
                str(event.coordinates.offset),
                _timestamp(event.kafka_timestamp),
                _timestamp(event.ingested_at),
                f"CAST({_timestamp(event.ingested_at)} AS DATE)",
                _string(event.consumer_group),
            )
        ) + ")"

    @staticmethod
    def _silver_row(event: ValidatedEvent) -> str:
        payload = event.payload
        return "(" + ", ".join(
            (
                _string(event.event_id),
                _string(event.correlation_id),
                _string(event.event_type),
                str(int(payload["event_version"])),
                _timestamp(event.occurred_at),
                f"CAST({_timestamp(event.occurred_at)} AS DATE)",
                _string(payload["source"]),
                _string(payload.get("customer_id")),
                _string(event.entity_id),
                _string(event.status),
                _decimal(event.amount),
                _string(str(payload.get("currency", "")).upper() or None),
                _string(event.payload_json),
                _string(event.payload_sha256),
                _string(event.coordinates.topic),
                str(event.coordinates.partition),
                str(event.coordinates.offset),
                _timestamp(event.ingested_at),
            )
        ) + ")"

    def close(self) -> None:
        self.connection.close()

