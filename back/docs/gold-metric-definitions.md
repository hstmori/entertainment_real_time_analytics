# Gold metric definitions

## Quy tắc chung

- Grain và filter dưới đây là contract phân tích của PoC, chưa phải business sign-off.
- Mọi phân bổ ngày/giờ dùng `occurred_at` quy đổi UTC, không dùng ingestion time.
- Silver đã dedupe theo `event_id`; Gold không đọc trực tiếp Bronze.
- Không quy đổi ngoại tệ. Mọi amount chỉ được cộng trong cùng `currency`.
- Hậu tố `_proxy` đánh dấu phép đo gần đúng, không phải số liệu kế toán hay KPI đã phê duyệt.
- Full refresh đưa late-arriving events về đúng event date. Chưa có incremental watermark/restate policy.

## `gold.content_engagement_hourly`

Grain: giờ UTC × content × device. Activity không có content dùng `content_id='__NO_CONTENT__'` để không mất page view/search khi reconcile.

| Metric | Định nghĩa |
|---|---|
| `activity_events` | Số user-activity events trong grain |
| `active_users` | Distinct `customer_id` trong grain; không cộng trực tiếp qua nhiều grain |
| `play_events` | Events có `activity_type='play'` |
| `completion_events` | Events có `activity_type='complete'` |
| `completion_per_play_proxy` | completion events / play events trong cùng grain; null khi không có play |
| `observed_position_seconds` | Tổng position snapshot; không phải watch time vì event contract chưa có duration delta |

## `gold.booking_funnel_daily`

Grain: ngày UTC × destination type/id × booking type × channel × currency. Mỗi source row là một booking state event, không phải full lifecycle.

| Metric | Định nghĩa |
|---|---|
| `*_events` | Số state events theo status |
| `confirmed_quantity` | Quantity trên confirmed events |
| `refunded_quantity` | Quantity trên refunded events |
| `confirmed_amount` | Amount trên confirmed events |
| `refunded_amount` | Amount trên refunded events |
| `net_booking_value_proxy` | confirmed amount − refunded amount; cancelled/failed/initiated không tạo value |
| `confirmation_share_proxy` | confirmed events / mọi booking state events trong grain; không phải funnel conversion theo cohort |

## `gold.event_performance`

Grain thực tế: entertainment event × currency; attendance-only event có currency null. Booking và attendance được aggregate riêng trước khi join để tránh fan-out.

| Metric | Định nghĩa |
|---|---|
| `confirmed_tickets` | Quantity trên confirmed booking events của live event |
| `refunded_tickets` | Quantity trên refunded booking events |
| `checked_in`, `no_show`, `rejected` | Attendance records theo status |
| `attendance_rate_proxy` | checked-in / attendance records; không phải checked-in / tickets sold |
| `no_show_rate_proxy` | no-show / attendance records |
| `net_booking_value_proxy` | Confirmed less refunded booking amount trong currency gốc |

## `gold.subscription_daily`

Grain: ngày UTC × plan × currency.

| Metric | Định nghĩa |
|---|---|
| `*_events` | Số subscription events theo status |
| `mrr_event_value_proxy` | Amount của started + renewed + upgraded events; không phải active MRR hay recognized revenue |
| `cancelled_value_context` | Amount kèm cancelled event để phân tích context; không tự động là churned MRR |

## `gold.customer_360`

Grain: một row cho mỗi non-null synthetic `customer_id` xuất hiện trong Silver.

- `first_seen_at` và `last_seen_at`: biên thời gian quan sát qua bốn domain.
- `observed_days`: số ngày lịch giữa first/last seen, tính cả hai đầu.
- `recency_days`: khoảng cách ngày giữa `last_seen_at` và timestamp mới nhất trong snapshot Gold.
- `total_events` và `domain_count`: độ sâu và độ rộng hành vi quan sát.
- `active_days`, `sessions`, `distinct_content`, play/complete/search: mức độ tương tác content.
- `favorite_content_id`: content có nhiều activity events nhất; tie-break bằng content ID tăng dần.
- Booking tách initiated/confirmed/refunded/failed, confirmed tickets và latest booking time.
- `net_booking_value_proxy`: confirmed less refunded amount của customer; có thể âm khi chỉ thấy refund event.
- Attendance tách checked-in/no-show và tính `attendance_rate_proxy = checked_in / attendance records`.
- Latest subscription dùng `occurred_at DESC, event_id DESC`.
- `active_subscription_proxy=true` cho latest status started/renewed/upgraded/downgraded.
- `customer_segment_proxy` là phân loại rule-based theo thứ tự: Omnichannel (`domain_count >= 3`), Active subscriber, Buyer / attendee, Content engaged, Other observed.
- PoC không resolve anonymous users, household, shared device hoặc nhiều identity; production cần identity rules đã được business/privacy phê duyệt.

## `gold.customer_journey`

Grain: một row cho mỗi Silver event có non-null `customer_id`.

- `domain` map bốn event types thành Content, Booking, Attendance và Subscription.
- `action` là status/action đã chuẩn hóa từ Silver.
- Các context fields như session, device, content, booking, channel, destination, event và plan được giữ để drill-down.
- `booking_value_impact_proxy` cộng amount cho confirmed, trừ amount cho refunded và bằng 0 cho trạng thái khác.
- `subscription_value_context` giữ amount của subscription event để phân tích context; không phải MRR hay recognized revenue.
- `event_count=1` hỗ trợ aggregate ổn định trong Power BI.
- Timeline là chuỗi sự kiện quan sát, không phải causal journey, attribution hoặc funnel cohort.

## Cancellation, refund và late data

- Cancelled booking không cộng doanh thu và không được coi là refund.
- Refunded amount được trừ khỏi confirmed amount nhưng contract hiện tại không liên kết refund event với confirmed event trước đó trong lifecycle.
- Late events được đưa về event date ở lần full refresh kế tiếp. Với incremental production pipeline cần watermark, restatement window và audit thay đổi.
- Batch lịch sử Phase 2 có latency 802–830 giây vì dữ liệu được phát trước rồi processor mới chạy thủ công; đây là late-arrival fixture, không đại diện cho live path.
- Batch fresh Phase 6B ngày 2026-11-06 đạt P95 processing 3.308 giây và P95 event-to-Silver query upper bound 9.268 giây, với 0/40 records vượt SLA 60 giây. Xem `final-acceptance-report-2026-11-06.md`.

