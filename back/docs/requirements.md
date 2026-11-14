# Phân rã yêu cầu và tiêu chí nghiệm thu

## 1. Mục tiêu nghiệp vụ

| ID | Mục tiêu | Kết quả cần hỗ trợ |
|---|---|---|
| BR-01 | Theo dõi hành vi người dùng gần real-time | Quan sát play/pause/search/page view theo thời gian, nội dung và thiết bị |
| BR-02 | Phân tích hiệu quả chương trình và sự kiện | Lượt quan tâm, booking, check-in, doanh thu và tỷ lệ chuyển đổi |
| BR-03 | Theo dõi transaction và booking | Trạng thái booking, số vé, giá trị giao dịch, lỗi và huỷ |
| BR-04 | Xây dựng Customer 360 | Hợp nhất hành vi, booking, tham dự và subscription theo customer key |
| BR-05 | Hỗ trợ dashboard và quyết định gần real-time | Dữ liệu Gold có thể truy vấn từ Trino và phục vụ Power BI |

## 2. Phạm vi dữ liệu ban đầu

| Domain | Kafka topic | Khóa partition đề xuất | Contract |
|---|---|---|---|
| Streaming/clickstream | `entertainment.user-activity.v1` | `customer_id` hoặc `session_id` | `user-activity-v1.schema.json` |
| Ticket/booking | `entertainment.booking.v1` | `booking_id` | `booking-v1.schema.json` |
| Membership/subscription | `entertainment.subscription.v1` | `customer_id` | `subscription-v1.schema.json` |
| Event attendance | `entertainment.event-attendance.v1` | `event_id` | `event-attendance-v1.schema.json` |
| Bản tin lỗi contract/processing | `entertainment.dead-letter.v1` | `source_topic` | Sẽ định nghĩa cùng stream processor |

## 3. Yêu cầu chức năng

- FR-01: Producer phải phát sự kiện có `event_id`, `event_version`, `occurred_at`, `source` và khóa nghiệp vụ.
- FR-02: Kafka phải tách topic theo domain, có partition key ổn định và version trong tên topic.
- FR-03: Consumer/stream processor phải kiểm tra schema, loại trùng theo `event_id` và chuyển bản tin lỗi sang dead-letter topic.
- FR-04: Dữ liệu hợp lệ phải được ghi vào Bronze ở trạng thái gần nguồn nhất và có metadata ingestion.
- FR-05: Silver phải chuẩn hóa timestamp, currency/status, xử lý duplicate và cung cấp customer key nhất quán.
- FR-06: Gold phải có bảng/aggregate cho hành vi nội dung, funnel booking, hiệu quả sự kiện, doanh thu subscription và Customer 360.
- FR-07: Trino phải truy vấn được các namespace Bronze/Silver/Gold.
- FR-08: Power BI phải kết nối được lớp Gold theo DirectQuery/ODBC hoặc Import có incremental refresh, tùy SLA thực tế.

## 4. Yêu cầu phi chức năng và giả định cần xác nhận

Các giá trị dưới đây là mục tiêu thiết kế ban đầu, không phải yêu cầu đã được business xác nhận:

| ID | Mục tiêu PoC | Cách đo |
|---|---|---|
| NFR-01 | P95 event-to-query latency <= 60 giây | `queryable_at - occurred_at` trên sự kiện test |
| NFR-02 | Không mất dữ liệu trong test restart consumer | So sánh số event hợp lệ produced, committed và stored |
| NFR-03 | Duplicate rate sau Silver = 0 theo `event_id` | Query kiểm tra `count(*) - count(distinct event_id)` |
| NFR-04 | 100% bản tin lỗi schema có trace trong DLQ | Đối chiếu test case invalid với DLQ |
| NFR-05 | Có thể replay theo topic/partition/offset | Chạy lại consumer vào namespace test độc lập |

Cần business xác nhận trước khi production hóa:

- Peak events/second, kích thước trung bình mỗi event và retention Kafka.
- Định nghĩa “real-time” theo từng dashboard; 5 giây, 1 phút hay 15 phút tạo ra kiến trúc khác nhau.
- Quy tắc định danh Customer 360 khi người dùng anonymous, nhiều thiết bị hoặc nhiều membership.
- Currency/timezone chuẩn, quy tắc hoàn tiền, huỷ vé và late-arriving events.
- PII classification, thời hạn lưu trữ, quyền truy cập và yêu cầu xoá dữ liệu.
- Các dịch vụ Oracle/OCI bắt buộc phải dùng và môi trường triển khai đích.

## 5. Ngoài phạm vi bước nền tảng

- Production-grade HA, TLS, SASL, RBAC, secrets manager và disaster recovery.
- Tích hợp nguồn thật hoặc CDC từ hệ thống transactional.
- Dữ liệu cá nhân thật.
- Dashboard Power BI hoàn chỉnh.
- Benchmark tải lớn và sizing production.

## 6. Definition of Done cho end-to-end PoC

1. Sinh được dữ liệu mẫu cho cả bốn domain và publish đúng topic/partition key.
2. Invalid event đi vào DLQ; valid event có thể truy vết từ Kafka offset đến Iceberg record.
3. Bronze, Silver, Gold là Iceberg tables truy vấn được qua Trino.
4. Có ít nhất một replay test, một duplicate test và một restart/recovery test.
5. Gold trả lời được năm nhóm câu hỏi nghiệp vụ BR-01 đến BR-05.
6. Power BI hiển thị dashboard test và độ trễ đo được phù hợp SLA đã chốt.
7. Có runbook khởi động, dừng, khôi phục và danh sách giới hạn của PoC.

