# Power BI PBIP runbook

## Kiến trúc serving

Power BI dùng Import từ 16 CSV. Export nghiệm thu pipeline được tạo từ Gold qua Trino; PBIP hiện tại trỏ tới một bộ demo deterministic gồm Customer 360, customer portfolio và các aggregate executive để trình bày đầy đủ mà không phụ thuộc driver ODBC trên máy kiểm tra.

Luồng dữ liệu:

```text
Iceberg Gold -> Trino -> powerbi-exporter -> artifacts/powerbi/*.csv (acceptance)
Synthetic valid events -> demo builder -> artifacts/powerbi_demo/*.csv (portfolio)
                                             |
                                             v
                                   PBIP semantic model (TMDL)
                                             |
                                             v
                                      PBIR report definition
```

`DataRoot` là Power Query parameter trong semantic model và hiện trỏ tới `artifacts/powerbi_demo` của checkout này. Nếu di chuyển project sang máy hoặc thư mục khác, cập nhật parameter trước khi Refresh.

Không trộn hai mục đích dữ liệu:

- `artifacts/powerbi` là export từ Gold dùng làm bằng chứng nghiệm thu kỹ thuật.
- `artifacts/powerbi_demo` là dataset synthetic portfolio có manifest, seed và phạm vi thời gian rõ ràng; không đại diện dữ liệu kinh doanh thật.

## Tái xuất dữ liệu Gold

Khi stack đang chạy và Gold đã được refresh:

```powershell
./scripts/stack.ps1 build powerbi-exporter
./scripts/stack.ps1 run powerbi-exporter
```

Exporter ghi atomically tám file CSV, bao gồm CustomerJourney, Date dimension và RefreshAudit. Không sửa CSV bằng tay vì chúng là artifact tái sinh từ Gold.

Tái sinh bộ portfolio demo:

```powershell
python scripts/build_portfolio_demo_data.py --output-dir artifacts/powerbi_demo
python scripts/validate_dashboard_demo_data.py --data-dir artifacts/powerbi_demo
```

## Tái sinh PBIP source

Generator mặc định từ chối chạy nếu `dashboard` đã tồn tại để tránh xóa thay đổi được lưu từ Power BI Desktop:

```powershell
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo
```

Chỉ dùng `--overwrite` khi chủ động muốn thay toàn bộ report/semantic definitions bằng scaffold từ code:

```powershell
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --overwrite
```

Sau khi generator tạo `model.bim`, semantic model cần được serialize thành thư mục TMDL `dashboard/EntertainmentAnalytics.SemanticModel/definition`. Project hiện tại đã chứa TMDL hoàn chỉnh; `model.bim` được giữ làm nguồn tái sinh và audit.

Khi chỉ cần thay một phần mà không xóa phần còn lại:

```powershell
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --model-only
python scripts/build_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo --report-only
```

## Kiểm tra không cần mở Desktop

```powershell
python scripts/validate_pbip.py --project-dir .. --data-dir artifacts/powerbi_demo
```

Validator kiểm tra JSON/PBIR, 10 trang, model bindings, 16 tables, 127 measures, model.bim khớp TMDL, 12 relationships, 16 exports, bảng màu dashboard và bảo đảm không lẫn cache/binary local. Report hiện có 149 visuals. Đây là source validation; không thay thế việc mở Desktop để Refresh, kiểm tra layout, filter interaction và hiệu năng thực tế.

## Cấu trúc dashboard

- `Trung tâm điều hành`: revenue, margin, customer, program status và service health.
- `Doanh thu & Lợi nhuận`: gross value, net revenue, contribution margin, target và cost.
- `Streaming`: concurrent viewers, completion, rebuffer và start failure ở grain 15 phút.
- `Vé & Sự kiện`: sell-through, funnel, channel và ticket tier.
- `Hiệu quả Chương trình`: portfolio, contribution margin, sales pace, break-even và status.
- `Chi tiết Sự kiện`: actual/plan/forecast theo lead day và hiệu quả kênh/hạng vé.
- `Thành viên`: started, renewed, cancelled, MRR proxy và event-to-member conversion.
- `Customer Portfolio & Spend Ranking`: tỷ lệ khách và chi tiêu theo hạng, spend × engagement, service mix và danh sách ưu tiên.
- `Customer 360 Profile`: hồ sơ hợp nhất, chi tiêu, hành vi, affinity, cross-service usage và hoạt động gần đây của một khách hàng.
- `Vận hành Real-time`: RPS, latency, error, queue, throughput và data lag ở grain 15 phút.

Thiết kế, quy tắc segment và cách diễn giải chi tiết nằm tại [Customer 360 dashboard design](customer-360-dashboard.md).

## Quy ước nghiệp vụ

- Chỉ số có chữ `proxy` giữ nguyên giới hạn trong `docs/gold-metric-definitions.md`; không diễn giải thành doanh thu, MRR kế toán hoặc conversion đã sign-off.
- Tỷ lệ trong DAX được tính lại từ tử số/mẫu số trong filter context, không cộng hoặc lấy trung bình các tỷ lệ dòng.
- `observed_position_seconds` là vị trí quan sát trong event, không phải watch time.
- Customer identity chỉ dựa trên synthetic `customer_id`; chưa resolve anonymous/household/shared device.
- Attendance rate dùng attendance records làm mẫu số, không phải toàn bộ vé bán.

## Bảng màu dashboard

Màu của report được định nghĩa một chỗ duy nhất tại `scripts/pbip_colors.py` và đặt ở cấp visual, nên theme đăng ký trong report không cần đổi.

| Màu | Ý nghĩa |
|---|---|
| Cyan `#22D3EE` | Doanh thu, quy mô (GMV, vé bán, RPS) |
| Xanh lá `#34D399` | Lợi nhuận, kết quả tốt (margin, sell-through, gia hạn) |
| Hổ phách `#FBBF24` | Chi phí, độ trễ (chi phí biến đổi, hoàn tiền, latency, lag) |
| San hô `#F87171` / cam `#FB923C` | Rủi ro, thất bại (rebuffer, error rate, no-show, hủy) |
| Tím `#A78BFA` | Khách hàng, thành viên |
| Xanh dương `#60A5FA` | Streaming (watch hours, viewers) |
| Xám `#94A3B8` | Kế hoạch, sức chứa, mục tiêu |

Trạng thái chương trình, trạng thái dịch vụ, kết quả hoạt động, behavior risk và member rank được tô màu chữ trong bảng qua các measure ở display folder `Formatting` (`Màu …`).

- `build_pbip.py` áp bảng màu cho mọi visual khi sinh lại, và sao lưu thư mục sắp bị xóa vào `dashboard_backups/<thời gian>/` trước khi ghi đè.
- `validate_pbip.py` báo lỗi nếu bất kỳ visual nào lệch khỏi bảng màu hoặc thiếu measure màu trong `model.bim`/TMDL.
- Muốn đổi màu: sửa `scripts/pbip_colors.py`, chạy `python scripts/build_pbip.py --report-only`, rồi chạy lại validator. Đổi màu trực tiếp trong Desktop sẽ bị validator báo lệch.

## Kiểm tra trong Desktop

1. Mở `../dashboard/EntertainmentAnalytics.pbip`.
2. Kiểm tra `DataRoot`, sau đó Refresh.
3. Xác nhận mười trang render, không có visual lỗi và slicer/filter interaction đúng.
4. Trên Customer 360 Profile, chọn một customer và xác nhận KPI/profile/affinity/activity cùng thay đổi.
5. Đối chiếu acceptance export với Trino SQL; đối chiếu demo với `artifacts/powerbi_demo/manifest.json` và CSV tương ứng.
6. Ghi nhận thời gian refresh và latency event-to-visual trước khi nghiệm thu bản dashboard mới.

Lần kiểm tra 2026-11-06 đã xác nhận Refresh, bốn trang cũ, slicer interaction và DAX/CSV reconciliation. Xem `docs/phase-5-code-validation-2026-11-06.md`. Bản Customer 360 và Portfolio ngày 2026-11-07 đã qua data/model/report source validation; vẫn cần Desktop Refresh và kiểm tra tương tác trước khi phát hành.
