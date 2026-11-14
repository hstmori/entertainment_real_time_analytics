-- Domain totals must reconcile from Silver to Gold.
SELECT
    (SELECT count(*) FROM iceberg.silver.events WHERE event_type = 'user_activity') AS silver_activity,
    (SELECT sum(activity_events) FROM iceberg.gold.content_engagement_hourly) AS gold_activity,
    (SELECT count(*) FROM iceberg.silver.events WHERE event_type = 'booking') AS silver_booking,
    (SELECT sum(booking_state_events) FROM iceberg.gold.booking_funnel_daily) AS gold_booking,
    (SELECT count(*) FROM iceberg.silver.events WHERE event_type = 'subscription') AS silver_subscription,
    (SELECT sum(subscription_events) FROM iceberg.gold.subscription_daily) AS gold_subscription,
    (SELECT count(*) FROM iceberg.silver.events WHERE event_type = 'event_attendance') AS silver_attendance,
    (SELECT sum(attendance_records) FROM iceberg.gold.event_performance) AS gold_attendance;

-- Booking values must reconcile without currency conversion.
SELECT
    sum(CASE WHEN status = 'confirmed' THEN amount ELSE DECIMAL '0' END) AS silver_confirmed,
    sum(CASE WHEN status = 'refunded' THEN amount ELSE DECIMAL '0' END) AS silver_refunded
FROM iceberg.silver.events
WHERE event_type = 'booking';

SELECT
    sum(confirmed_amount) AS gold_confirmed,
    sum(refunded_amount) AS gold_refunded,
    sum(net_booking_value_proxy) AS gold_net_proxy
FROM iceberg.gold.booking_funnel_daily;

-- Customer 360 grain must be unique.
SELECT
    count(*) AS customer_rows,
    count(DISTINCT customer_id) AS distinct_customers,
    count(*) - count(DISTINCT customer_id) AS duplicate_customers
FROM iceberg.gold.customer_360;

-- Customer Journey must preserve one event-grain row for every identified Silver event.
SELECT
    (SELECT count(*) FROM iceberg.silver.events WHERE customer_id IS NOT NULL) AS silver_identified_events,
    (SELECT count(*) FROM iceberg.gold.customer_journey) AS journey_rows,
    (SELECT count(DISTINCT event_id) FROM iceberg.gold.customer_journey) AS journey_distinct_events;

-- Late-arrival profile. This is evidence, not an automatic SLA pass.
SELECT
    count(*) AS events,
    count_if(first_seen_at < occurred_at) AS negative_latency,
    count_if(date_diff('second', occurred_at, first_seen_at) > 60) AS arrived_over_60s,
    min(date_diff('second', occurred_at, first_seen_at)) AS min_latency_seconds,
    max(date_diff('second', occurred_at, first_seen_at)) AS max_latency_seconds
FROM iceberg.silver.events;

-- Refresh audit must contain six records for every successful run.
SELECT run_id, count(*) AS models, min(refreshed_at) AS started_at, max(refreshed_at) AS completed_at
FROM iceberg.gold.refresh_audit
WHERE status = 'SUCCEEDED'
GROUP BY run_id
ORDER BY completed_at DESC;

