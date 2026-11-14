# Customer 360 và Portfolio validation — 2026-11-07

## Phạm vi

Validation cho dữ liệu synthetic, script tái sử dụng, semantic model TMDL và PBIR source của hai trang `Customer Portfolio & Spend Ranking` và `Customer 360 Profile`.

## Dataset

- 200/200 customer keys duy nhất.
- 1.130 hoạt động gần đây, 800 affinity rows và 10 rank-share rows.
- Chi tiêu ròng 12 tháng reconcile đúng với ticket + subscription + content - refund.
- Hạng chỉ phụ thuộc chi tiêu ròng 12 tháng và đúng toàn bộ ngưỡng đã công bố.
- Hai nhóm rank-share đều cộng thành 100%.
- Mọi customer/activity/affinity foreign key đều hợp lệ.
- `customer_journey.csv` cũ không còn trong demo output.

## Semantic model và report source

- 16 tables, 120 measures và 12 active relationships.
- 10 report pages và 149 visuals.
- 163 PBIR/TMDL JSON files parse thành công.
- 16 CSV exports được tìm thấy và có schema đúng.
- Hai trang customer dùng visual native Power BI và theme màu hạng/rủi ro nhất quán.

## Kết quả kiểm tra

```text
Customer data validator: valid; 16 files; 6,595 rows
PBIP source validator:   valid; 16 tables; 120 measures; 12 relationships
Targeted customer test:  passed
Python compileall:       passed
TMDL load/export:        passed
```

Full `pytest` chưa chạy trên Python host vì môi trường thiếu package `pytest`. Docker fallback cũng chưa chạy vì Docker Desktop daemon không hoạt động; targeted test và hai validator độc lập đã chạy thành công.

## Giới hạn

1. Dataset là synthetic portfolio data; không dùng để tuyên bố business outcomes thật.
2. `customer_rank_share.csv` là snapshot toàn portfolio, không phải aggregate động cho mọi filter.
3. Cần Desktop Refresh và kiểm tra trực quan/filter interaction trước khi phát hành cho người dùng cuối.
