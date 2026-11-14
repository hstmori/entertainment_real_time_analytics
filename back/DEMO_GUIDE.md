# Demo Guide

Kịch bản trình bày dự án trong khoảng 10 phút, kèm cách xử lý sự cố khi chạy demo.

## Trước buổi demo

1. Giải nén gói vào thư mục có đường dẫn ngắn, ví dụ `C:\Demo\RealTimeDataPipeline`.
2. Bấm đúp `1_Open_Dashboard.bat` một lần để kiểm tra dashboard mở được.
3. Nếu muốn demo pipeline live: mở Docker Desktop và chạy `2_Run_Pipeline_Demo.bat` trước một lần để tải sẵn image. Các lần sau chạy nhanh hơn nhiều.

## Kịch bản 10 phút

### 1. Bài toán — 1 phút

Doanh nghiệp giải trí có dữ liệu rời rạc giữa nền tảng streaming, hệ thống bán vé, check-in sự kiện và subscription. Dự án hợp nhất các sự kiện đó thành một pipeline gần real-time để theo dõi doanh thu, chất lượng streaming, hiệu quả sự kiện, membership và Customer 360.

### 2. Kiến trúc — 2 phút

Mở `docs/architecture.md`:

- Producer mô phỏng bốn hệ thống nguồn, validate theo data contract trước khi gửi.
- Kafka tách topic theo domain, giữ thứ tự theo partition key.
- Processor kiểm tra schema, retry, đẩy bản ghi lỗi sang DLQ và chỉ commit offset sau khi ghi thành công.
- Bronze giữ raw payload kèm Kafka lineage; Silver chuẩn hóa và khử trùng theo `event_id`; Gold là data product cho phân tích.

### 3. Chạy pipeline live — 2 phút

Bấm `2_Run_Pipeline_Demo.bat` và giải thích kết quả in ra: số sự kiện gửi/nhận, số lỗi đi DLQ, số `event_id` trùng (phải bằng 0), độ trễ P95 so với SLA 60 giây.

Trong lúc chờ, mở `contracts/jsonschema/booking-v1.schema.json` (data contract) và `src/entertainment_pipeline/stream_processor.py` (validation, micro-batch, manual commit).

Sau khi chạy xong có thể mở Trino UI tại http://localhost:8080 để thấy các query vừa chạy.

### 4. Tầng phân tích — 2 phút

Mở `docs/gold-metric-definitions.md` và một file trong `sql/gold`. Nhấn mạnh `sql/quality/phase4_reconciliation.sql`: Gold luôn được đối soát với Silver sau mỗi lần refresh. Metric `_proxy` được gắn nhãn rõ để không bị hiểu nhầm là số kế toán.

### 5. Dashboard Power BI — 2 phút

Bấm `1_Open_Dashboard.bat`. Dashboard có 10 trang:

| Trang | Câu hỏi trả lời |
|---|---|
| Trung tâm điều hành | Toàn cảnh doanh thu, margin, khách hàng, chương trình, cảnh báo vận hành |
| Doanh thu & Lợi nhuận | Doanh thu so với mục tiêu, margin theo dịch vụ, sự kiện đóng góp lớn nhất |
| Streaming | Người xem đồng thời, completion rate, chất lượng phát theo thiết bị |
| Vé & Sự kiện | Vé bán, sell-through, no-show, phễu đặt vé theo kênh |
| Hiệu quả Chương trình | Margin và trạng thái từng chương trình |
| Chi tiết Sự kiện | Vé tích lũy thực tế vs kế hoạch vs forecast cho một sự kiện |
| Thành viên | Đăng ký mới, gia hạn, hủy, MRR theo plan |
| Customer Portfolio & Spend Ranking | Cơ cấu khách theo hạng chi tiêu, hành vi theo hạng |
| Customer 360 Profile | Hồ sơ hợp nhất và đề xuất hành động cho một khách hàng |
| Vận hành Real-time | RPS, latency, error rate, hàng đợi, data lag theo dịch vụ |

Màu có ý nghĩa thống nhất trên mọi trang: cyan = doanh thu/quy mô, xanh lá = lợi nhuận/kết quả tốt, hổ phách = chi phí/độ trễ, đỏ = rủi ro, tím = khách hàng, xanh dương = streaming, xám = kế hoạch.

### 6. Nghiệm thu và cloud — 1 phút

Mở `docs/final-acceptance-report-2026-11-06.md`: 40/40 sự kiện, lag 0, P95 9,3 giây so với SLA 60 giây. Kết thúc bằng `docs/phase-6a-oci-deployment.md`: Terraform đã sẵn sàng cho OCI nhưng chưa apply vào tenancy thật.

## Câu hỏi thường gặp

**Vì sao dùng RustFS thay MinIO?**
Image Community Edition của MinIO đã bị rút khỏi public registry năm 2026; RustFS là S3-compatible store có image công khai, tái dựng được. Xem `docs/adr/0001-local-poc-stack.md`.

**Làm sao chứng minh không mất dữ liệu?**
Consumer chỉ commit offset sau khi Bronze/Silver ghi thành công hoặc bản ghi lỗi đã vào DLQ. Restart, replay và reconciliation đều có test và bằng chứng.

**Vì sao Power BI dùng CSV Import?**
Ổn định cho PoC local. Kiến trúc OCI chuyển nguồn BI sang Autonomous AI Lakehouse.

**Đã chạy trên cloud chưa?**
Chưa. OCI là blueprint đã kiểm tra cấu trúc; cần tenancy, quota và một lượt `terraform plan/apply` được duyệt.

## Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Bấm `.bat` bị Windows SmartScreen chặn | Chọn "More info" → "Run anyway". Script chỉ chạy PowerShell trong thư mục gói. |
| Dashboard mở nhưng không có số liệu | Trong Power BI bấm Home → Refresh. |
| Báo thiếu Power BI Desktop | Cài miễn phí từ Microsoft Store rồi chạy lại `1_Open_Dashboard.bat`. |
| Báo cổng 8080/9000/29092 đang bận | Tắt ứng dụng đang dùng cổng đó, hoặc chạy `4_Stop_Pipeline.bat` rồi chạy lại. |
| Docker báo thiếu bộ nhớ | Trong Docker Desktop → Settings → Resources, cấp tối thiểu 8 GB RAM. |
| Muốn chạy lại từ đầu | Chạy `4_Stop_Pipeline.bat` rồi `2_Run_Pipeline_Demo.bat`. |
