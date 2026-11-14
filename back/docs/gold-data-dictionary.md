# Gold data dictionary và lineage

Nguồn chung: Kafka domain topics → `iceberg.bronze.raw_events` → `iceberg.silver.events` → các bảng dưới đây. SQL column-level transformation nằm trong `sql/gold/`.

## `gold.content_engagement_hourly`

Grain: giờ UTC × content × device.

| Field | Type | Ý nghĩa / lineage |
|---|---|---|
| `event_hour_utc` | timestamp with time zone | `date_trunc(hour, occurred_at UTC)` |
| `event_date_utc` | date | Ngày UTC từ event hour |
| `content_id` | varchar | Payload content; null map thành `__NO_CONTENT__` |
| `device_type` | varchar | `payload.device_type` |
| `activity_events` | bigint | Count Silver user activity |
| `active_users` | bigint | Distinct Silver customer key |
| `play_events` | bigint | Count activity `play` |
| `completion_events` | bigint | Count activity `complete` |
| `completion_per_play_proxy` | double | Complete/play ratio |
| `observed_position_seconds` | double | Sum payload position snapshot |

## `gold.booking_funnel_daily`

Grain: ngày × destination × booking type × channel × currency.

| Field | Type | Ý nghĩa / lineage |
|---|---|---|
| `event_date_utc` | date | Ngày của `occurred_at` UTC |
| `destination_type` | varchar | `live_event` hoặc `content` |
| `destination_id` | varchar | Event ID, fallback content ID |
| `booking_type` | varchar | `payload.booking_type` |
| `channel` | varchar | `payload.channel` |
| `currency` | varchar | Uppercase Silver currency |
| `booking_state_events` | bigint | Tổng booking state events |
| `initiated_events` | bigint | Count initiated |
| `confirmed_events` | bigint | Count confirmed |
| `cancelled_events` | bigint | Count cancelled |
| `refunded_events` | bigint | Count refunded |
| `failed_events` | bigint | Count failed |
| `confirmed_quantity` | bigint | Quantity confirmed |
| `refunded_quantity` | bigint | Quantity refunded |
| `confirmed_amount` | decimal(38,2) | Confirmed amount |
| `refunded_amount` | decimal(38,2) | Refunded amount |
| `net_booking_value_proxy` | decimal(38,2) | Confirmed less refunded |
| `confirmation_share_proxy` | double | Confirmed/all state events |

## `gold.event_performance`

Grain: entertainment event × currency.

| Field | Type | Ý nghĩa / lineage |
|---|---|---|
| `entertainment_event_id` | varchar | Payload live event key |
| `currency` | varchar | Booking currency; null nếu chỉ có attendance |
| `confirmed_bookings` | bigint | Confirmed booking event count |
| `refunded_bookings` | bigint | Refunded booking event count |
| `confirmed_tickets` | bigint | Confirmed quantity |
| `refunded_tickets` | bigint | Refunded quantity |
| `net_booking_value_proxy` | decimal(38,2) | Confirmed less refunded amount |
| `attendance_records` | bigint | Attendance event count |
| `checked_in` | bigint | Checked-in count |
| `no_show` | bigint | No-show count |
| `rejected` | bigint | Rejected count |
| `attendance_rate_proxy` | double | Checked-in/attendance records |
| `no_show_rate_proxy` | double | No-show/attendance records |
| `first_booking_event_at` | timestamp with time zone | Min booking occurred_at |
| `last_booking_event_at` | timestamp with time zone | Max booking occurred_at |
| `first_attendance_event_at` | timestamp with time zone | Min attendance occurred_at |
| `last_attendance_event_at` | timestamp with time zone | Max attendance occurred_at |

## `gold.subscription_daily`

Grain: ngày × plan × currency.

| Field | Type | Ý nghĩa / lineage |
|---|---|---|
| `event_date_utc` | date | Ngày occurred_at UTC |
| `plan_id` | varchar | Payload plan key |
| `currency` | varchar | Uppercase currency |
| `subscription_events` | bigint | Tổng subscription events |
| `started_events` | bigint | Count started |
| `renewed_events` | bigint | Count renewed |
| `upgraded_events` | bigint | Count upgraded |
| `downgraded_events` | bigint | Count downgraded |
| `paused_events` | bigint | Count paused |
| `cancelled_events` | bigint | Count cancelled |
| `expired_events` | bigint | Count expired |
| `mrr_event_value_proxy` | decimal(38,2) | Started + renewed + upgraded amount |
| `cancelled_value_context` | decimal(38,2) | Amount carried by cancellation events |

## `gold.customer_360`

Grain: một row/customer.

| Field | Type | Ý nghĩa / lineage |
|---|---|---|
| `customer_id` | varchar | Conformed synthetic customer key |
| `first_seen_at` | timestamp with time zone | Earliest occurred_at across domains |
| `last_seen_at` | timestamp with time zone | Latest occurred_at across domains |
| `observed_days` | bigint | Inclusive calendar days between first/last seen |
| `recency_days` | bigint | Days from last seen to snapshot max occurred_at |
| `total_events` | bigint | All observed events for customer |
| `domain_count` | bigint | Distinct observed event domains |
| `activity_events` | bigint | User activity count |
| `active_days` | bigint | Distinct UTC dates with activity |
| `sessions` | bigint | Distinct non-null activity session IDs |
| `distinct_content` | bigint | Distinct non-null activity content IDs |
| `play_events` | bigint | Activity events with play action |
| `completion_events` | bigint | Activity events with complete action |
| `search_events` | bigint | Activity events with search action |
| `last_activity_at` | timestamp with time zone | Latest activity occurred_at |
| `favorite_content_id` | varchar | Most frequent content by events |
| `favorite_content_events` | bigint | Event count cho favorite content |
| `booking_state_events` | bigint | Booking event count |
| `initiated_bookings` | bigint | Initiated booking event count |
| `confirmed_bookings` | bigint | Confirmed booking event count |
| `refunded_bookings` | bigint | Refunded booking event count |
| `failed_bookings` | bigint | Failed booking event count |
| `confirmed_tickets` | bigint | Quantity on confirmed booking events |
| `net_booking_value_proxy` | decimal(38,2) | Customer confirmed less refunded amount |
| `last_booking_at` | timestamp with time zone | Latest booking occurred_at |
| `attendance_records` | bigint | Attendance event count |
| `checked_in_events` | bigint | Checked-in event count |
| `no_show_events` | bigint | No-show event count |
| `attendance_rate_proxy` | double | Checked-in / attendance records |
| `last_attendance_at` | timestamp with time zone | Latest attendance occurred_at |
| `subscription_events` | bigint | Subscription event count |
| `latest_subscription_status` | varchar | Status của subscription event mới nhất |
| `latest_plan_id` | varchar | Plan của subscription event mới nhất |
| `latest_subscription_at` | timestamp with time zone | Latest subscription occurred_at |
| `active_subscription_proxy` | boolean | Latest status nằm trong active-like set |
| `customer_segment_proxy` | varchar | Rule-based observed-behavior segment |

## `gold.customer_journey`

Grain: một row/customer event.

| Field | Type | Ý nghĩa / lineage |
|---|---|---|
| `event_id` | varchar | Unique Silver event ID |
| `customer_id` | varchar | Conformed synthetic customer key |
| `occurred_at` | timestamp with time zone | Business event timestamp |
| `event_date_utc` | date | UTC date from occurred_at |
| `event_hour_utc` | timestamp with time zone | UTC hour from occurred_at |
| `event_type` | varchar | Silver domain event type |
| `domain` | varchar | Content, Booking, Attendance hoặc Subscription |
| `action` | varchar | Normalized Silver status/action |
| `source` | varchar | Source application/service |
| `session_id` | varchar | Activity session context |
| `device_type` | varchar | Activity device context |
| `content_id` | varchar | Content context |
| `search_term` | varchar | Search context |
| `booking_id` | varchar | Booking context key |
| `booking_type` | varchar | Booking product/type |
| `channel` | varchar | Booking channel |
| `destination_id` | varchar | Event ID, fallback content ID |
| `entertainment_event_id` | varchar | Live event key |
| `plan_id` | varchar | Subscription plan key |
| `quantity` | bigint | Booking quantity, else 0 |
| `amount` | decimal(38,2) | Event amount in source currency |
| `currency` | varchar | Uppercase source currency |
| `booking_value_impact_proxy` | decimal(38,2) | Confirmed positive, refunded negative, else 0 |
| `subscription_value_context` | decimal(38,2) | Subscription event amount context |
| `event_count` | integer | Constant 1 for aggregation |

## `gold.refresh_audit`

| Field | Type | Ý nghĩa |
|---|---|---|
| `run_id` | varchar | UUID của một Gold build |
| `model_name` | varchar | Tên model đã refresh |
| `refreshed_at` | timestamp with time zone | Thời điểm UTC của build |
| `row_count` | bigint | Row count staging trước swap |
| `silver_snapshot_rows` | bigint | Số Silver rows khi build bắt đầu |
| `status` | varchar | `SUCCEEDED` khi model swap và audit insert thành công |

