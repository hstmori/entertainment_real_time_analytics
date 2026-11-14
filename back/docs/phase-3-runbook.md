# Phase 3 runbook

## Khởi động và khởi tạo

```powershell
./scripts/stack.ps1 up
./scripts/stack.ps1 build stream-processor stream-processor-replay
./scripts/stack.ps1 run stream-processor --initialize-only
```

## Chạy processor

Chạy liên tục:

```powershell
./scripts/stack.ps1 run stream-processor --batch-size 100 --flush-interval 10
```

Chạy hữu hạn để test:

```powershell
./scripts/stack.ps1 run stream-processor --batch-size 20 --flush-interval 2 `
  --max-messages 40 --idle-exit-seconds 10
```

Các invariants vận hành:

1. `enable.auto.commit=false`; processor chỉ synchronous commit sau khi sink và DLQ thành công.
2. Bronze idempotent theo `source_topic + source_partition + source_offset`.
3. Silver idempotent theo `event_id`; source của mỗi `MERGE` cũng được dedupe bằng `row_number()`.
4. Nếu Trino/DLQ lỗi, batch retry exponential backoff. Sau khi hết retry, process thoát non-zero và Kafka offset chưa được commit.
5. Khi chạy lại, Kafka replay batch chưa commit; hai `MERGE` không tạo trùng.

## Kiểm tra lag

```powershell
./scripts/stack.ps1 exec kafka /opt/kafka/bin/kafka-consumer-groups.sh `
  --bootstrap-server localhost:9092 --describe `
  --group entertainment-lakehouse-bronze-v1
```

Tất cả partition phải có `LAG = 0` sau khi one-shot processor hoàn tất.

## Kiểm tra dữ liệu và lineage

```powershell
./scripts/stack.ps1 exec trino trino --server http://localhost:8080 `
  --file /dev/stdin
```

Các query chuẩn nằm tại `sql/quality/phase3_checks.sql`. Bronze phải có số row bằng số Kafka coordinates hợp lệ; Silver phải có `duplicate_rows = 0`.

## DLQ

```powershell
./scripts/stack.ps1 exec kafka /opt/kafka/bin/kafka-console-consumer.sh `
  --bootstrap-server localhost:9092 --topic entertainment.dead-letter.v1 `
  --from-beginning --timeout-ms 10000
```

Mỗi record chứa `dead_letter_id` deterministic, source topic/partition/offset, group, error và raw payload. Replay bằng group khác có thể tạo thêm Kafka DLQ record cho cùng source offset, nhưng `dead_letter_id` vẫn giống nhau để downstream dedupe.

## Replay độc lập

Mỗi lượt replay phải dùng consumer group và schema đích mới. Ví dụ PowerShell:

```powershell
$replayArgs = @(
  '-e', 'BRONZE_SCHEMA=bronze_replay_v2',
  '-e', 'SILVER_SCHEMA=silver_replay_v2',
  '-e', 'KAFKA_CONSUMER_GROUP=entertainment-lakehouse-replay-v2',
  'stream-processor-replay',
  '--batch-size', '100',
  '--idle-exit-seconds', '10'
)
./scripts/stack.ps1 -Action run -RemainingArgs $replayArgs
```

Không dùng cùng schema replay cho hai processor chạy đồng thời. Chỉ xóa schema test sau khi đã đối chiếu row count và xác nhận đó không phải dữ liệu cần giữ.

