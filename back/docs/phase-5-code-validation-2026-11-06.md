# Phase 5 PBIP và Desktop validation - 2026-11-06

## Phạm vi

Phase 5 được triển khai bằng PBIP source code. Sau source validation, project được mở và kiểm tra trực tiếp trong Power BI Desktop để xác nhận refresh, render, slicer interaction và DAX totals.

## Gold export

`powerbi-exporter` đọc sáu Gold tables qua Trino và tạo thêm Date dimension. Kết quả live:

| File | Rows |
|---|---:|
| `content_engagement_hourly.csv` | 10 |
| `booking_funnel_daily.csv` | 10 |
| `event_performance.csv` | 13 |
| `subscription_daily.csv` | 3 |
| `customer_360.csv` | 36 |
| `refresh_audit.csv` | 10 |
| `date.csv` | 1 |

## Semantic model

- 7 import tables serialized thành TMDL.
- 33 explicit DAX measures.
- 3 active many-to-one relationships tới Date.
- `DataRoot` parameter trỏ tới `artifacts/powerbi`.
- Các cột kỹ thuật/metric base được ẩn; business dimensions và explicit measures phục vụ report.

Power BI modeling validation đã import `model.bim`, export thành 11 TMDL files, rồi load lại TMDL thành công với đúng 7 tables, 33 measures và 3 relationships.

## PBIR report

- 4 pages: Tổng quan, Nội dung, Booking & Sự kiện, Customer 360.
- 52 visual definitions, gồm card, slicer, clustered column/bar, table và textbox.
- 59 JSON files parse thành công.
- Tất cả Column/Measure references trong visual definitions đều tồn tại trong semantic model.
- Không tạo `.pbix`; cache runtime do Desktop sinh nằm dưới `.pbi` và đã được `.gitignore` loại trừ khỏi source/package.
- Docker test image chạy thành công 22/22 automated tests, gồm các test mới cho export coverage và CSV type serialization.
- Generator trả lỗi có chủ đích khi `dashboard` đã tồn tại và không có `--overwrite`.

## Power BI Desktop validation

- Refresh từ bảy CSV hoàn tất không có source, credential hoặc privacy error; cửa sổ refresh biến mất trong lần quan sát sau 8 giây.
- Cả bốn trang `Tổng quan`, `Nội dung`, `Booking & Sự kiện` và `Customer 360` render card, chart, slicer và table.
- Model view hiển thị đúng 7 tables và 3 active many-to-one relationships tới Date.
- Slicer `latest_subscription_status=started` lọc Customer 360 từ 36 xuống 4 khách hàng và bảng chi tiết còn đúng 4 rows.
- Khi kiểm tra slicer, ba conditional-count cards trả `(Blank)` ở zero-state. Bốn Customer 360 measures đã được đổi sang `COALESCE(...,0)` trong generator, BIM, TMDL và live Desktop model; visual sau sửa hiển thị `4 / 0 / 0 / 0 / 4`.
- Project được lưu sau sửa lúc 15:47 theo giờ máy.

## DAX và CSV reconciliation

Một DAX query trả 31 KPI chính trong 17 ms. Các giá trị đối chiếu tuyệt đối với phép tổng hợp trực tiếp trên CSV export, gồm:

| Nhóm | Kết quả |
|---|---|
| Content | 10 activity events; 2 plays; 0 completes; 27,865.4 observed-position seconds |
| Booking | 10 events; 8 confirmed; 1 refunded; 1 failed; 22 confirmed tickets; 7,870,000 net booking proxy |
| Event | 13 live events; 15 confirmed tickets; 9 check-ins; 1 no-show; 90% attendance proxy |
| Subscription | 10 events; 4 starts; 3 renewals; 1 cancellation; 943,000 MRR event-value proxy |
| Customer 360 | 36 customers; 10 active; 8 with confirmed booking; 9 with check-in; 9 active-subscription proxy |
| Audit | 2 refresh runs; 10 model refresh records |

Lệnh kiểm tra:

```powershell
python scripts/validate_pbip.py --project-dir .
```

## Trạng thái nghiệm thu

Phase 5 đạt ở phạm vi PoC chức năng: PBIP source, Gold export, semantic metadata, Desktop refresh/render, slicer interaction và KPI reconciliation đều đã kiểm tra. Event-to-visual latency end-to-end chưa được nghiệm thu vì quy trình local hiện dùng Gold CSV export và Desktop Refresh thủ công; thời gian dưới 8 giây ở trên chỉ là giới hạn quan sát cho bước Desktop refresh, không phải SLA toàn pipeline.
