# Entertainment executive dashboard demo

## Phạm vi

PBIP dùng dữ liệu deterministic synthetic để trình diễn quyết định quản trị, không tuyên bố kết quả kinh doanh thật. Dataset được giữ dưới 7.000 dòng bằng cách sử dụng grain phù hợp cho dashboard thay vì mô phỏng transaction thô khối lượng lớn.

## Row budget

| Dataset | Grain | Dòng mặc định | Vai trò |
|---|---|---:|---|
| `executive_daily.csv` | ngày × 4 business lines | 400 | Doanh thu, chi phí, margin, target |
| `streaming_realtime.csv` | 15 phút × 4 thiết bị × 4 khu vực | 1.536 | Concurrent viewers và streaming quality |
| `program_event.csv` | một dòng/chương trình | 24 | Portfolio và event P&L |
| `event_sales_pace.csv` | chương trình × 31 lead days | 744 | Actual, plan và forecast trước sự kiện |
| `event_sales_detail.csv` | chương trình × 4 kênh × 4 hạng vé | 384 | Funnel, inventory, revenue và ROAS |
| `operations_realtime.csv` | 15 phút × 4 services | 384 | Latency, error, queue, throughput và freshness |
| Các bảng Customer/Gold demo | customer snapshot, activity, affinity và aggregate | 3.123 | Customer 360, spend ranking, membership và lineage demo |

Tổng mặc định: **6.595 dòng trên 16 CSV**. Date dimension gồm thêm 30 ngày tương lai để các chương trình sắp diễn ra lọc đúng.

## Trang PBIP

1. Trung tâm điều hành
2. Doanh thu & Lợi nhuận
3. Streaming
4. Vé & Sự kiện
5. Hiệu quả Chương trình
6. Chi tiết Sự kiện
7. Thành viên
8. Customer Portfolio & Spend Ranking
9. Customer 360 Profile
10. Vận hành Real-time

Report chỉ dùng visual native: card, slicer, line, clustered bar/column, table/matrix và textbox. Theme dark nằm tại `dashboard/entertainment-executive-theme.json`.

## Tái sinh và kiểm tra

```powershell
python scripts/build_portfolio_demo_data.py --output-dir artifacts/powerbi_demo --skip-contract-validation
python scripts/validate_dashboard_demo_data.py --data-dir artifacts/powerbi_demo
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --model-only
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --report-only
python scripts/validate_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo
```

`--skip-contract-validation` chỉ bỏ import thư viện schema trên host; generator và contracts vẫn có regression tests riêng trong project. Khi môi trường đã cài dependencies, bỏ cờ này để validate từng source event.

## Giới hạn

- Power BI Import từ CSV minh họa trải nghiệm dashboard, không chứng minh event-to-visual real-time.
- Financial fields và các trường `_proxy` là synthetic/analytical, chưa phải recognized revenue hoặc Finance sign-off.
- Customer identity là synthetic key, không có PII.
- Một cửa sổ cảnh báo Payment Gateway được tạo có chủ đích để kiểm tra trạng thái bất thường.
