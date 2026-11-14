"""Build validated Gold Iceberg tables from Silver using staging-and-swap."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Sequence
import uuid

from trino.dbapi import connect


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
MODEL_FILES = {
    "content_engagement_hourly": "01_content_engagement_hourly.sql",
    "booking_funnel_daily": "02_booking_funnel_daily.sql",
    "event_performance": "03_event_performance.sql",
    "subscription_daily": "04_subscription_daily.sql",
    "customer_360": "05_customer_360.sql",
    "customer_journey": "06_customer_journey.sql",
}


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return value


def _literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


@dataclass(frozen=True)
class GoldSettings:
    host: str
    port: int
    user: str
    catalog: str
    silver_schema: str
    gold_schema: str
    sql_dir: Path

    @classmethod
    def from_env(cls) -> "GoldSettings":
        return cls(
            host=os.getenv("TRINO_HOST", "localhost"),
            port=int(os.getenv("TRINO_PORT", "8080")),
            user=os.getenv("TRINO_USER", "entertainment-gold-builder"),
            catalog=_identifier(os.getenv("TRINO_CATALOG", "iceberg")),
            silver_schema=_identifier(os.getenv("SILVER_SCHEMA", "silver")),
            gold_schema=_identifier(os.getenv("GOLD_SCHEMA", "gold")),
            sql_dir=Path(os.getenv("GOLD_SQL_DIR", "sql/gold")),
        )


class GoldBuilder:
    def __init__(
        self,
        settings: GoldSettings,
        *,
        connection_factory: Callable[..., Any] = connect,
    ) -> None:
        self.settings = settings
        self.connection = connection_factory(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            catalog=settings.catalog,
        )

    def execute(self, sql: str) -> list[tuple[Any, ...]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            return list(cursor.fetchall()) if cursor.description else []
        finally:
            cursor.close()

    def _qualified(self, schema: str, table: str) -> str:
        return f"{self.settings.catalog}.{_identifier(schema)}.{_identifier(table)}"

    def ensure_audit_table(self) -> None:
        catalog = self.settings.catalog
        gold = self.settings.gold_schema
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{gold}")
        self.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {catalog}.{gold}.refresh_audit (
                run_id VARCHAR,
                model_name VARCHAR,
                refreshed_at TIMESTAMP(3) WITH TIME ZONE,
                row_count BIGINT,
                silver_snapshot_rows BIGINT,
                status VARCHAR
            ) WITH (format = 'PARQUET')
            """
        )

    def table_exists(self, table: str) -> bool:
        rows = self.execute(
            f"""
            SELECT count(*)
            FROM {self.settings.catalog}.information_schema.tables
            WHERE table_schema = {_literal(self.settings.gold_schema)}
              AND table_name = {_literal(table)}
            """
        )
        return bool(rows and rows[0][0])

    def load_query(self, model: str) -> str:
        path = self.settings.sql_dir / MODEL_FILES[model]
        if not path.is_file():
            raise FileNotFoundError(f"Gold SQL file not found: {path}")
        query = path.read_text(encoding="utf-8").strip().rstrip(";")
        return query.replace("{{catalog}}", self.settings.catalog).replace(
            "{{silver_schema}}", self.settings.silver_schema
        )

    def build_model(self, model: str) -> int:
        _identifier(model)
        gold = self.settings.gold_schema
        target = self._qualified(gold, model)
        staging_name = f"staging_{model}"
        backup_name = f"backup_{model}"
        staging = self._qualified(gold, staging_name)
        backup = self._qualified(gold, backup_name)

        self.execute(f"DROP TABLE IF EXISTS {staging}")
        self.execute(f"CREATE TABLE {staging} WITH (format = 'PARQUET') AS {self.load_query(model)}")
        rows = self.execute(f"SELECT count(*) FROM {staging}")
        row_count = int(rows[0][0])

        self.execute(f"DROP TABLE IF EXISTS {backup}")
        target_existed = self.table_exists(model)
        if target_existed:
            self.execute(f"ALTER TABLE {target} RENAME TO {backup_name}")
        try:
            self.execute(f"ALTER TABLE {staging} RENAME TO {model}")
        except Exception:
            if target_existed and self.table_exists(backup_name):
                self.execute(f"ALTER TABLE {backup} RENAME TO {model}")
            raise
        if target_existed:
            self.execute(f"DROP TABLE {backup}")
        return row_count

    def build_all(self) -> dict[str, object]:
        self.ensure_audit_table()
        source_rows = int(
            self.execute(
                f"SELECT count(*) FROM {self.settings.catalog}.{self.settings.silver_schema}.events"
            )[0][0]
        )
        run_id = str(uuid.uuid4())
        refreshed_at = datetime.now(UTC).isoformat(timespec="milliseconds")
        row_counts: dict[str, int] = {}

        for model in MODEL_FILES:
            row_count = self.build_model(model)
            row_counts[model] = row_count
            self.execute(
                f"""
                INSERT INTO {self.settings.catalog}.{self.settings.gold_schema}.refresh_audit
                VALUES (
                    {_literal(run_id)}, {_literal(model)},
                    from_iso8601_timestamp({_literal(refreshed_at)}),
                    {row_count}, {source_rows}, 'SUCCEEDED'
                )
                """
            )

        return {
            "status": "completed",
            "run_id": run_id,
            "silver_snapshot_rows": source_rows,
            "row_counts": row_counts,
        }

    def close(self) -> None:
        self.connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Gold analytical tables from Silver")
    parser.add_argument("--sql-dir", type=Path, default=None)
    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    settings = GoldSettings.from_env()
    if args.sql_dir is not None:
        settings = GoldSettings(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            catalog=settings.catalog,
            silver_schema=settings.silver_schema,
            gold_schema=settings.gold_schema,
            sql_dir=args.sql_dir,
        )
    builder = GoldBuilder(settings)
    try:
        summary = builder.build_all()
    finally:
        builder.close()
    print(json.dumps(summary, sort_keys=True))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    run(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

