# Phase 3 smoke-test evidence - 2026-11-06

## Phạm vi

Kiểm thử live Kafka-to-Iceberg: manual commit, restart/recovery, JSON Schema rejection, DLQ trace, Bronze lineage, Silver dedupe trong/giữa micro-batch và replay sang schema độc lập.

## Automated tests

```text
16 passed in 1.67s
```

Test bao phủ generator/producer cũ và các nhánh Phase 3: valid decode, malformed JSON, schema violation, deterministic DLQ ID, high-watermark commit, SQL identifier safety và idempotent Bronze/Silver merge.

## Restart test - NFR-02

Consumer group: `entertainment-lakehouse-bronze-v1`.

| Lượt chạy | Consumed | Valid | Invalid -> DLQ | Batch |
|---|---:|---:|---:|---:|
| Trước restart | 20 | 19 | 1 | 2 |
| Sau restart | 21 | 21 | 0 | 3 |
| Tổng | 41 | 40 | 1 | 5 |

Invalid record là foundation smoke event cũ tại `entertainment.user-activity.v1`, partition 2, offset 0; event này có trước contract đầy đủ và thiếu các trường bắt buộc.

Sau restart:

```text
Bronze rows:        40
Unique lineage:     40
Silver rows:        40
Distinct event_id:  40
Silver duplicates:   0
```

Consumer-group describe cho thấy `LAG = 0` trên toàn bộ 12 source partitions.

## Duplicate test - NFR-03

Phát lại đúng batch deterministic 40 events của Phase 2 (`seed=42`, base time `2026-11-06T02:00:00Z`) rồi xử lý bằng cùng consumer group.

```text
Bronze rows:             80
Unique Kafka lineage:    80
Bronze distinct event_id:40
Silver rows:             40
Silver distinct event_id:40
Silver duplicate rows:    0
```

Bronze giữ cả hai lần phát vì Kafka offsets khác nhau. Silver giữ một record/event ID.

Trong lượt replay đầu, test phát hiện duplicate cùng `event_id` trong cùng micro-batch có thể cùng được insert khi target chưa chứa ID đó. Source của Silver `MERGE` đã được sửa để dùng `row_number() over (partition by event_id ...)`; automated tests và replay v2 xác nhận bản sửa.

## DLQ trace - NFR-04

DLQ record có:

- `dead_letter_id=908a68db-f876-51ff-b8b3-12e2b6b536d0`
- `source_topic=entertainment.user-activity.v1`
- `source_partition=2`
- `source_offset=0`
- `error_type=ContractValidationError`
- raw payload và danh sách required fields bị thiếu

Main và hai replay groups tạo ba DLQ records cho cùng source coordinate; cả ba có cùng deterministic `dead_letter_id`. Vì vậy invalid source có trace 100%, đồng thời downstream có khóa để dedupe replay traces.

## Replay độc lập - NFR-05 hỗ trợ

Replay group `entertainment-lakehouse-replay-v2` đọc đủ 81 records vào `bronze_replay_v2` và `silver_replay_v2`:

```text
Consumed:               81
Valid:                  80
Invalid -> DLQ:          1
Replay Bronze rows:     80
Replay unique lineage:  80
Replay Silver rows:     40
Replay distinct IDs:    40
Replay duplicates:       0
```

Hai bảng/schema của lượt replay lỗi ban đầu đã được xóa sau khi bản sửa được xác nhận. Bảng chính và replay v2 được giữ làm bằng chứng.

## Kết luận

Phase 3 đạt exit criteria. Mỗi Bronze row truy vết được về topic/partition/offset; restart không mất record và lag trở về 0; Silver không có duplicate; invalid record có DLQ trace; replay độc lập tái dựng đúng kết quả.

