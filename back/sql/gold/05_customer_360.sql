WITH observation AS (
    SELECT max(occurred_at) AS snapshot_at
    FROM {{catalog}}.{{silver_schema}}.events
),
spine AS (
    SELECT
        customer_id,
        min(occurred_at) AS first_seen_at,
        max(occurred_at) AS last_seen_at,
        count(*) AS total_events,
        count(DISTINCT event_type) AS domain_count
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE customer_id IS NOT NULL
    GROUP BY 1
),
activity AS (
    SELECT
        customer_id,
        count(*) AS activity_events,
        count(DISTINCT cast(at_timezone(occurred_at, 'UTC') AS date)) AS active_days,
        count(DISTINCT json_extract_scalar(payload_json, '$.session_id')) AS sessions,
        count(DISTINCT json_extract_scalar(payload_json, '$.content_id')) AS distinct_content,
        count_if(status = 'play') AS play_events,
        count_if(status = 'complete') AS completion_events,
        count_if(status = 'search') AS search_events,
        max(occurred_at) AS last_activity_at
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'user_activity'
    GROUP BY 1
),
content_rank AS (
    SELECT
        customer_id,
        json_extract_scalar(payload_json, '$.content_id') AS content_id,
        count(*) AS content_events,
        row_number() OVER (
            PARTITION BY customer_id
            ORDER BY count(*) DESC, json_extract_scalar(payload_json, '$.content_id')
        ) AS content_rank
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'user_activity'
      AND json_extract_scalar(payload_json, '$.content_id') IS NOT NULL
    GROUP BY 1, 2
),
favorite AS (
    SELECT customer_id, content_id AS favorite_content_id, content_events AS favorite_content_events
    FROM content_rank
    WHERE content_rank = 1
),
booking AS (
    SELECT
        customer_id,
        count(*) AS booking_state_events,
        count_if(status = 'initiated') AS initiated_bookings,
        count_if(status = 'confirmed') AS confirmed_bookings,
        count_if(status = 'refunded') AS refunded_bookings,
        count_if(status = 'failed') AS failed_bookings,
        sum(
            CASE WHEN status = 'confirmed'
                THEN coalesce(try_cast(json_extract_scalar(payload_json, '$.quantity') AS bigint), 0)
                ELSE 0
            END
        ) AS confirmed_tickets,
        sum(
            CASE
                WHEN status = 'confirmed' THEN coalesce(amount, DECIMAL '0')
                WHEN status = 'refunded' THEN -coalesce(amount, DECIMAL '0')
                ELSE DECIMAL '0'
            END
        ) AS net_booking_value_proxy,
        max(occurred_at) AS last_booking_at
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'booking'
    GROUP BY 1
),
attendance AS (
    SELECT
        customer_id,
        count(*) AS attendance_records,
        count_if(status = 'checked_in') AS checked_in_events,
        count_if(status = 'no_show') AS no_show_events,
        round(
            cast(count_if(status = 'checked_in') AS double) / nullif(count(*), 0),
            4
        ) AS attendance_rate_proxy,
        max(occurred_at) AS last_attendance_at
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'event_attendance'
    GROUP BY 1
),
subscription AS (
    SELECT
        customer_id,
        count(*) AS subscription_events,
        max(occurred_at) AS last_subscription_event_at
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'subscription'
    GROUP BY 1
),
subscription_rank AS (
    SELECT
        customer_id,
        status AS latest_subscription_status,
        json_extract_scalar(payload_json, '$.plan_id') AS latest_plan_id,
        occurred_at AS latest_subscription_at,
        row_number() OVER (PARTITION BY customer_id ORDER BY occurred_at DESC, event_id DESC) AS recency_rank
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'subscription'
),
latest_subscription AS (
    SELECT customer_id, latest_subscription_status, latest_plan_id, latest_subscription_at
    FROM subscription_rank
    WHERE recency_rank = 1
),
profile AS (
    SELECT
        s.customer_id,
        s.first_seen_at,
        s.last_seen_at,
        date_diff(
            'day',
            cast(at_timezone(s.first_seen_at, 'UTC') AS date),
            cast(at_timezone(s.last_seen_at, 'UTC') AS date)
        ) + 1 AS observed_days,
        date_diff(
            'day',
            cast(at_timezone(s.last_seen_at, 'UTC') AS date),
            cast(at_timezone(o.snapshot_at, 'UTC') AS date)
        ) AS recency_days,
        s.total_events,
        s.domain_count,
        coalesce(a.activity_events, 0) AS activity_events,
        coalesce(a.active_days, 0) AS active_days,
        coalesce(a.sessions, 0) AS sessions,
        coalesce(a.distinct_content, 0) AS distinct_content,
        coalesce(a.play_events, 0) AS play_events,
        coalesce(a.completion_events, 0) AS completion_events,
        coalesce(a.search_events, 0) AS search_events,
        a.last_activity_at,
        f.favorite_content_id,
        coalesce(f.favorite_content_events, 0) AS favorite_content_events,
        coalesce(b.booking_state_events, 0) AS booking_state_events,
        coalesce(b.initiated_bookings, 0) AS initiated_bookings,
        coalesce(b.confirmed_bookings, 0) AS confirmed_bookings,
        coalesce(b.refunded_bookings, 0) AS refunded_bookings,
        coalesce(b.failed_bookings, 0) AS failed_bookings,
        coalesce(b.confirmed_tickets, 0) AS confirmed_tickets,
        coalesce(b.net_booking_value_proxy, DECIMAL '0') AS net_booking_value_proxy,
        b.last_booking_at,
        coalesce(t.attendance_records, 0) AS attendance_records,
        coalesce(t.checked_in_events, 0) AS checked_in_events,
        coalesce(t.no_show_events, 0) AS no_show_events,
        t.attendance_rate_proxy,
        t.last_attendance_at,
        coalesce(sub.subscription_events, 0) AS subscription_events,
        ls.latest_subscription_status,
        ls.latest_plan_id,
        ls.latest_subscription_at,
        CASE
            WHEN ls.latest_subscription_status IN ('started', 'renewed', 'upgraded', 'downgraded') THEN true
            ELSE false
        END AS active_subscription_proxy
    FROM spine s
    CROSS JOIN observation o
    LEFT JOIN activity a ON s.customer_id = a.customer_id
    LEFT JOIN favorite f ON s.customer_id = f.customer_id
    LEFT JOIN booking b ON s.customer_id = b.customer_id
    LEFT JOIN attendance t ON s.customer_id = t.customer_id
    LEFT JOIN subscription sub ON s.customer_id = sub.customer_id
    LEFT JOIN latest_subscription ls ON s.customer_id = ls.customer_id
)
SELECT
    *,
    CASE
        WHEN domain_count >= 3 THEN 'Omnichannel'
        WHEN active_subscription_proxy THEN 'Active subscriber'
        WHEN confirmed_bookings > 0 OR checked_in_events > 0 THEN 'Buyer / attendee'
        WHEN activity_events > 0 THEN 'Content engaged'
        ELSE 'Other observed'
    END AS customer_segment_proxy
FROM profile

