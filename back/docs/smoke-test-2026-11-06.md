# Local platform smoke test - 2026-11-06

## Environment

- Docker Client/Server: 29.9.2
- Docker Compose: 5.6.1
- Docker Desktop resources observed: 12 CPUs, approximately 8 GB memory
- Host: Windows, Docker Desktop Linux engine

## Stack under test

| Component | Image | Result |
|---|---|---|
| Apache Kafka | `apache/kafka:4.1.0` | Healthy |
| S3-compatible object store | `rustfs/rustfs:1.0.0` | Healthy |
| Iceberg REST fixture | `apache/iceberg-rest-fixture:latest` | Healthy |
| Trino | `trinodb/trino:484` | Healthy |
| Kafka topic bootstrap | `apache/kafka:4.1.0` | Exited 0 |
| Object-store bootstrap | `rustfs/rustfs:1.0.0` | Exited 0 |

## Checks and evidence

| Check | Observed result | Status |
|---|---|---|
| Foundation files | 9 required files found | Pass |
| JSON contracts | 4 schemas parsed and structurally checked | Pass |
| Compose config | `docker compose config --quiet` | Pass |
| Kafka topics | user-activity, booking, subscription, event-attendance, dead-letter | Pass |
| Kafka data path | Produced and consumed 1 deterministic smoke event | Pass |
| Object-store buckets | `warehouse`, `raw`, `checkpoints` | Pass |
| Iceberg REST | `/v1/config` returned supported endpoints | Pass |
| Trino catalog | `iceberg` present in `SHOW CATALOGS` | Pass |
| Lakehouse namespaces | `bronze`, `silver`, `gold` present | Pass |
| Iceberg write path | Create table -> insert 1 row -> select same row -> drop table | Pass |

Kafka smoke payload:

```json
{
  "event_id": "00000000-0000-4000-8000-000000000001",
  "event_version": 1,
  "source": "foundation-smoke-test"
}
```

Iceberg read-back result:

```text
event_id                              source
00000000-0000-4000-8000-000000000001 foundation-smoke-test
```

The temporary Iceberg table was dropped after verification. The Kafka smoke event remains in `entertainment.user-activity.v1` and is intentionally identifiable by `source=foundation-smoke-test`.

## Adaptation made during live validation

The original compose referenced MinIO Community Edition. Live pulls failed because Docker Hub no longer serves `minio/minio`/`minio/mc`, and Quay requires authorization. The local PoC was amended to RustFS 1.0.0, matching the current Apache Iceberg quickstart pattern for S3-compatible local storage. The role in the architecture remains object storage; OCI Object Storage is still the intended production mapping candidate.

## Remaining limitations

- Single-node lab only; no HA, TLS, RBAC or disaster recovery validation.
- Iceberg REST fixture stores its JDBC catalog in the container and is not a production metadata service.
- No application producer, stream processor, DLQ workflow or automated data-quality checks yet.
- Power BI connectivity and dashboard refresh have not been tested.
- `apache/iceberg-rest-fixture:latest` should be pinned to a verified digest before reproducible CI or release packaging.

