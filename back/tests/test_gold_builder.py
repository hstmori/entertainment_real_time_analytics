from __future__ import annotations

from pathlib import Path

import pytest

from entertainment_pipeline.gold_builder import GoldBuilder, GoldSettings, MODEL_FILES


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.description = None
        self._rows: list[tuple[object, ...]] = []

    def execute(self, sql: str) -> None:
        self.connection.statements.append(sql)
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("select count(*) from iceberg.information_schema.tables"):
            self.description = [("count",)]
            self._rows = [(0,)]
        elif normalized.startswith("select count(*)"):
            self.description = [("count",)]
            self._rows = [(5,)]

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows

    def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        pass


def settings(**overrides: object) -> GoldSettings:
    values = {
        "host": "trino",
        "port": 8080,
        "user": "test",
        "catalog": "iceberg",
        "silver_schema": "silver",
        "gold_schema": "gold",
        "sql_dir": Path("sql/gold"),
    }
    values.update(overrides)
    return GoldSettings(**values)  # type: ignore[arg-type]


def factory(connection: FakeConnection):
    def create(**_kwargs: object) -> FakeConnection:
        return connection
    return create


def test_all_gold_queries_are_present_and_resolve_source_placeholders() -> None:
    connection = FakeConnection()
    builder = GoldBuilder(settings(), connection_factory=factory(connection))

    for model in MODEL_FILES:
        query = builder.load_query(model)
        assert "{{" not in query
        assert "iceberg.silver.events" in query
        assert query.upper().startswith("WITH")


def test_build_model_uses_staging_validation_and_rename() -> None:
    connection = FakeConnection()
    builder = GoldBuilder(settings(), connection_factory=factory(connection))

    row_count = builder.build_model("content_engagement_hourly")

    assert row_count == 5
    sql = "\n".join(connection.statements)
    assert "CREATE TABLE iceberg.gold.staging_content_engagement_hourly" in sql
    assert "SELECT count(*) FROM iceberg.gold.staging_content_engagement_hourly" in sql
    assert "ALTER TABLE iceberg.gold.staging_content_engagement_hourly RENAME TO content_engagement_hourly" in sql


def test_gold_builder_rejects_unsafe_schema_name() -> None:
    builder = GoldBuilder(
        settings(gold_schema="gold;drop"),
        connection_factory=factory(FakeConnection()),
    )
    with pytest.raises(ValueError, match="Unsafe SQL identifier"):
        builder.build_model("content_engagement_hourly")

