# Phase 2 smoke-test evidence - 2026-11-06

## Phạm vi

Xác minh event generator và Kafka producer chạy thật trên local Docker stack, bao gồm tính reproducible, JSON Schema validation, partition key, delivery và khả năng đọc lại từ broker.

## Phiên bản trực tiếp

- Python runtime: 3.12 (`python:3.12-slim`)
- `confluent-kafka==2.16.1`
- `jsonschema[format-nongpl]==4.26.0`
- `pytest==9.2.0`
- Kafka broker: `apache/kafka:4.1.0`

## Automated tests

Lệnh:

```powershell
./scripts/stack.ps1 build event-producer-test event-producer
./scripts/stack.ps1 run event-producer-test -q
```

Kết quả:

```text
9 passed in 1.47s
```

Các test bao phủ bốn event contracts, round-robin distribution, partition key, deterministic seed/base time, invalid payload rejection và CLI dry-run không cần Kafka.

## Dry-run contract validation

Lệnh:

```powershell
./scripts/stack.ps1 run event-producer --dry-run --count 8 --rate 0 --seed 42 `
  --base-time 2026-11-06T00:00:00Z --sample-limit 2
```

Kết quả: `status=validated`, sinh 8 sự kiện hợp lệ, đúng 2 sự kiện/domain, không ghi Kafka. Correlation ID cố định của lượt chạy là `f9e69ad7-e081-5299-98d1-38feaaa3490c`.

## Kafka live publish

Lệnh:

```powershell
./scripts/stack.ps1 run event-producer --count 40 --rate 40 --seed 42 `
  --base-time 2026-11-06T02:00:00Z --sample-limit 0
```

Producer summary:

```json
{
  "status": "published",
  "generated": 40,
  "delivered": 40,
  "generated_by_topic": {
    "entertainment.booking.v1": 10,
    "entertainment.event-attendance.v1": 10,
    "entertainment.subscription.v1": 10,
    "entertainment.user-activity.v1": 10
  },
  "delivered_by_topic": {
    "entertainment.booking.v1": 10,
    "entertainment.event-attendance.v1": 10,
    "entertainment.subscription.v1": 10,
    "entertainment.user-activity.v1": 10
  },
  "correlation_id": "4054a907-a370-56e2-b40d-ddc479255a3f",
  "elapsed_seconds": 1.0
}
```

## Broker offsets và consume-back

Sau batch, tổng high-watermark theo topic:

| Topic | Partition offsets | Tổng | Giải thích |
|---|---:|---:|---|
| `entertainment.booking.v1` | 3 + 2 + 5 | 10 | 10 sự kiện Phase 2 |
| `entertainment.event-attendance.v1` | 5 + 4 + 1 | 10 | 10 sự kiện Phase 2 |
| `entertainment.subscription.v1` | 2 + 4 + 4 | 10 | 10 sự kiện Phase 2 |
| `entertainment.user-activity.v1` | 6 + 2 + 3 | 11 | 10 sự kiện Phase 2 + 1 smoke event Phase 1 |
| `entertainment.dead-letter.v1` | 0 + 0 + 0 | 0 | Không có lỗi validation/delivery |

Kafka console consumer đọc từ đầu và kết thúc thành công với 10 booking, 10 attendance, 10 subscription và 11 user-activity messages. Sau khi loại 1 smoke event đã tồn tại từ Phase 1, produced count và consumed count của Phase 2 đều bằng 40.

## Kết luận

Phase 2 đạt exit criteria: dữ liệu sinh có thể tái lập, invalid fixture bị từ chối trong test, mọi event live được validate trước publish, delivery callback xác nhận 40/40 và broker cho phép đọc lại đủ batch. Stack vẫn sẵn sàng cho Phase 3 consumer-to-lakehouse.
