# Phase 4 smoke-test evidence - 2026-11-06

## Automated validation

- Automated tests: `19 passed in 1.82s`.
- Required files: validation passed.
- JSON Schemas: 5 valid.
- Docker Compose syntax: valid.

## Gold refresh

Hai lượt refresh thành công. Lượt hai kiểm thử đường staging → backup → swap khi target đã tồn tại.

```text
run_id: bc932194-db01-441e-a258-08e3c582641a
Silver snapshot: 40 rows

content_engagement_hourly: 10 rows
booking_funnel_daily:      10 rows
event_performance:         13 rows
subscription_daily:        3 rows
customer_360:             36 rows
```

`refresh_audit` có 10 records cho 2 runs × 5 models.

## Reconciliation

| Domain | Silver | Gold aggregate | Chênh lệch |
|---|---:|---:|---:|
| User activity | 10 | 10 | 0 |
| Booking | 10 | 10 | 0 |
| Subscription | 10 | 10 | 0 |
| Attendance | 10 | 10 | 0 |

Booking value reconciliation:

```text
Silver confirmed: 8,120,000 VND
Gold confirmed:   8,120,000 VND
Silver refunded:    250,000 VND
Gold refunded:      250,000 VND
Gold net proxy:   7,870,000 VND
```

Customer 360: 36 rows, 36 distinct customer IDs, 0 duplicate grain.

## KPI snapshot

```text
Activity events:                  10
Play events:                       2
Completion events:                 0
Observed position seconds:    27,865.4

Confirmed booking events:          8
Refunded booking events:           1
Failed booking events:             1
Confirmed tickets for live events:15

Checked in:                        9
No show:                           1

Subscription started:              4
Subscription renewed:              3
Subscription cancelled:            1
MRR event value proxy:        943,000 VND

Customer 360 rows:                36
Customers with activity:          10
Customers with confirmed booking:  8
Customers with check-in:           9
Active subscription proxy:         9
```

## Late data và giới hạn

Tất cả 40 Silver events đến sau event time từ 802 đến 830 giây vì producer batch được chạy trước processor. Không có negative latency. Full Gold refresh vẫn phân bổ theo `occurred_at` UTC, nên late records nằm đúng event date.

Kết quả này không chứng minh NFR-01 ≤ 60 giây. Cần một bài test live có producer, processor và Gold refresh chạy đồng thời ở Phase 5/6 nếu muốn nghiệm thu latency.

Booking conversion, net booking value, attendance rate, active subscription và MRR đều là proxy theo định nghĩa tại `gold-metric-definitions.md`; chưa phải business/accounting sign-off.

## Kết luận

Phase 4 đạt exit criteria trong phạm vi PoC: năm Gold products trả lời BR-01 đến BR-05, totals reconcile với Silver, Customer 360 có unique grain, metric semantics và column lineage được ghi rõ, và refresh có audit trail.

