"""Runtime configuration for the Kafka producer and stream processor."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class KafkaSecuritySettings:
    """Optional TLS/SASL settings shared by Kafka producers and consumers."""

    security_protocol: str | None = None
    sasl_mechanism: str | None = None
    sasl_username: str | None = None
    sasl_password: str | None = None
    ssl_ca_location: str | None = None

    @classmethod
    def from_env(cls) -> "KafkaSecuritySettings":
        return cls(
            security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL") or None,
            sasl_mechanism=os.getenv("KAFKA_SASL_MECHANISM") or None,
            sasl_username=os.getenv("KAFKA_SASL_USERNAME") or None,
            sasl_password=os.getenv("KAFKA_SASL_PASSWORD") or None,
            ssl_ca_location=os.getenv("KAFKA_SSL_CA_LOCATION") or None,
        )

    def kafka_config(self) -> dict[str, object]:
        config: dict[str, object] = {}
        optional_values = {
            "security.protocol": self.security_protocol,
            "sasl.mechanism": self.sasl_mechanism,
            "sasl.username": self.sasl_username,
            "sasl.password": self.sasl_password,
            "ssl.ca.location": self.ssl_ca_location,
        }
        config.update({key: value for key, value in optional_values.items() if value})
        return config


@dataclass(frozen=True)
class ProducerSettings:
    """Settings loaded from environment variables with local-safe defaults."""

    bootstrap_servers: str = "localhost:29092"
    client_id: str = "entertainment-event-producer"
    contracts_dir: Path = Path("contracts/jsonschema")
    delivery_timeout_ms: int = 30_000
    security: KafkaSecuritySettings = field(default_factory=KafkaSecuritySettings)

    @classmethod
    def from_env(cls) -> "ProducerSettings":
        return cls(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
            client_id=os.getenv("KAFKA_CLIENT_ID", "entertainment-event-producer"),
            contracts_dir=Path(os.getenv("CONTRACTS_DIR", "contracts/jsonschema")),
            delivery_timeout_ms=int(os.getenv("KAFKA_DELIVERY_TIMEOUT_MS", "30000")),
            security=KafkaSecuritySettings.from_env(),
        )

    def kafka_config(self) -> dict[str, object]:
        config: dict[str, object] = {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "acks": "all",
            "enable.idempotence": True,
            "compression.type": "gzip",
            "linger.ms": 5,
            "request.timeout.ms": 10_000,
            "delivery.timeout.ms": self.delivery_timeout_ms,
        }
        config.update(self.security.kafka_config())
        return config


@dataclass(frozen=True)
class ProcessorSettings:
    """Settings for manual-commit Kafka consumption and Trino Iceberg writes."""

    bootstrap_servers: str = "localhost:29092"
    group_id: str = "entertainment-lakehouse-bronze-v1"
    client_id: str = "entertainment-stream-processor"
    contracts_dir: Path = Path("contracts/jsonschema")
    trino_host: str = "localhost"
    trino_port: int = 8080
    trino_user: str = "entertainment-pipeline"
    trino_catalog: str = "iceberg"
    bronze_schema: str = "bronze"
    silver_schema: str = "silver"
    auto_offset_reset: str = "earliest"
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    security: KafkaSecuritySettings = field(default_factory=KafkaSecuritySettings)

    @classmethod
    def from_env(cls) -> "ProcessorSettings":
        return cls(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
            group_id=os.getenv("KAFKA_CONSUMER_GROUP", "entertainment-lakehouse-bronze-v1"),
            client_id=os.getenv("KAFKA_PROCESSOR_CLIENT_ID", "entertainment-stream-processor"),
            contracts_dir=Path(os.getenv("CONTRACTS_DIR", "contracts/jsonschema")),
            trino_host=os.getenv("TRINO_HOST", "localhost"),
            trino_port=int(os.getenv("TRINO_PORT", "8080")),
            trino_user=os.getenv("TRINO_USER", "entertainment-pipeline"),
            trino_catalog=os.getenv("TRINO_CATALOG", "iceberg"),
            bronze_schema=os.getenv("BRONZE_SCHEMA", "bronze"),
            silver_schema=os.getenv("SILVER_SCHEMA", "silver"),
            auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest"),
            max_retries=int(os.getenv("PROCESSOR_MAX_RETRIES", "3")),
            retry_backoff_seconds=float(os.getenv("PROCESSOR_RETRY_BACKOFF_SECONDS", "1")),
            security=KafkaSecuritySettings.from_env(),
        )

    def kafka_config(self) -> dict[str, object]:
        config: dict[str, object] = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "client.id": self.client_id,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": self.auto_offset_reset,
            "isolation.level": "read_committed",
        }
        config.update(self.security.kafka_config())
        return config

