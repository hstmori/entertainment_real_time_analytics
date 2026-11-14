# Event contracts

Mỗi Kafka topic có một JSON Schema độc lập để producer và consumer có thể validate mà không phụ thuộc file tham chiếu bên ngoài.

Quy ước chung:

- `event_id`: UUID duy nhất, dùng cho idempotency/deduplication.
- `event_version`: version payload; breaking change phải tạo topic/schema version mới.
- `occurred_at`: thời điểm nghiệp vụ ở UTC, ISO-8601.
- `source`: tên hệ thống phát sự kiện.
- `customer_id`: định danh đã pseudonymize trong production.
- Không tự ý thêm field khi schema đang đặt `additionalProperties: false`; cần review contract evolution.

Partition key nằm trong [requirements](../docs/requirements.md), không được suy ra ngẫu nhiên ở producer.

The directory contains versioned JSON Schema contracts for the four source topics and the dead-letter topic.

Source contracts are validated by both the synthetic producer and stream processor. `dead-letter-v1.schema.json` records deterministic error identity plus source topic, partition, offset, consumer group, failure details, and the original payload.
