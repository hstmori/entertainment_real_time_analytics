from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from entertainment_pipeline.contracts import ContractRegistry
from entertainment_pipeline.generator import EventGenerator
from entertainment_pipeline.lakehouse import IcebergSink
from entertainment_pipeline.stream_processor import decode_message
from tests.test_stream_processor import FakeMessage


class FakeCursor:
    description = None

    def __init__(self, statements: list[str]) -> None:
        self.statements = statements

    def execute(self, sql: str) -> None:
        self.statements.append(sql)

    def fetchall(self) -> list[list[object]]:
        return []

    def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.statements)

    def close(self) -> None:
        pass


def connection_factory(connection: FakeConnection):
    def factory(**_kwargs: object) -> FakeConnection:
        return connection
    return factory


def valid_event():
    now = datetime(2026, 11, 6, 3, 0, tzinfo=UTC)
    payload = next(EventGenerator(seed=42, base_time=now).iter_events(count=1, event_type="booking")).payload
    return decode_message(
        FakeMessage(json.dumps(payload).encode()),
        registry=ContractRegistry(Path("contracts/jsonschema")),
        consumer_group="test-group",
        now=now,
    )


def test_sink_builds_idempotent_bronze_and_silver_merges() -> None:
    connection = FakeConnection()
    sink = IcebergSink(
        host="trino",
        port=8080,
        user="test",
        catalog="iceberg",
        bronze_schema="bronze",
        silver_schema="silver",
        connection_factory=connection_factory(connection),
    )
    sink.write_batch([valid_event()])

    assert len(connection.statements) == 2
    assert "target.source_offset = source.source_offset" in connection.statements[0]
    assert "target.event_id = source.event_id" in connection.statements[1]
    assert "row_number() OVER" in connection.statements[1]
    assert "PARTITION BY event_id" in connection.statements[1]
    assert "WHEN NOT MATCHED" in connection.statements[0]
    assert "WHEN NOT MATCHED" in connection.statements[1]


def test_sink_rejects_unsafe_schema_identifier() -> None:
    with pytest.raises(ValueError, match="Unsafe SQL identifier"):
        IcebergSink(
            host="trino",
            port=8080,
            user="test",
            catalog="iceberg",
            bronze_schema="bronze;drop table x",
            silver_schema="silver",
            connection_factory=connection_factory(FakeConnection()),
        )

