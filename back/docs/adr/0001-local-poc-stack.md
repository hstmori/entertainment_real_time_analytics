# ADR-0001: Local PoC stack cho Entertainment Lakehouse

- Status: Amended after live smoke test
- Date: 2026-11-06

## Context

Đề bài yêu cầu Apache Kafka và Oracle Lakehouse, đồng thời gợi ý MinIO, Trino và Power BI. Môi trường hiện tại cần một PoC có thể chạy trên một máy, minh họa đầy đủ ingestion -> lakehouse -> SQL -> BI nhưng không giả định quyền truy cập OCI. Khi smoke test ngày 2026-11-06, Docker Hub không còn repository `minio/minio` và `minio/mc`, còn Quay trả về HTTP 401 cho anonymous pull. Apache Iceberg cũng đã chuyển quickstart hiện hành sang RustFS.

## Decision

Sử dụng:

- Apache Kafka 4.1.0 single-node KRaft cho event backbone.
- RustFS 1.0.0 single-node cho object storage tương thích S3. Đây là lựa chọn local thay cho MinIO Community Edition đã EOL.
- Apache Iceberg table format và Iceberg REST fixture làm metadata catalog local.
- Trino làm SQL/query layer.
- Power BI ở lớp serving, triển khai sau khi Gold model ổn định.

Event contract dùng JSON Schema và topic name có version. Lakehouse dùng ba namespace Bronze/Silver/Gold.

## Consequences

Tích cực:

- Chạy local, không cần cloud account.
- Mô phỏng đúng vai trò storage/catalog/query của một lakehouse.
- Có thể thay RustFS bằng OCI Object Storage và catalog/query layer bằng dịch vụ production mà không đổi domain contracts.

Giới hạn:

- Single-node không kiểm chứng HA hay distributed scaling.
- Iceberg REST fixture là thành phần test/lab, metadata có thể không bền vững như production catalog.
- Security đang là local development credentials; chưa có TLS/SASL/RBAC.
- Power BI connectivity và SLA phải được kiểm tra trong môi trường thật.
- RustFS là công nghệ thay thế cho PoC; quyết định production vẫn cần architecture/security review.

## Alternatives considered

- Hive Metastore + database: bền vững hơn nhưng tăng số service và chi phí vận hành cho bước đầu.
- Spark/Flink ngay từ đầu: phù hợp production processing nhưng quá nặng trước khi contract và SLA được chốt.
- Ghi Parquet thuần: đơn giản nhưng thiếu transaction, schema evolution và table metadata cần cho lakehouse.
- MinIO Community Edition image/mirror cũ: bị loại vì không còn public image chính thức có thể pull/rebuild và không còn security maintenance phù hợp.

