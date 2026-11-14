WITH journey AS (
SELECT
    event_id,
    customer_id,
    occurred_at,
    cast(at_timezone(occurred_at, 'UTC') AS date) AS event_date_utc,
    date_trunc('hour', at_timezone(occurred_at, 'UTC')) AS event_hour_utc,
    event_type,
    CASE event_type
        WHEN 'user_activity' THEN 'Content'
        WHEN 'booking' THEN 'Booking'
        WHEN 'event_attendance' THEN 'Attendance'
        WHEN 'subscription' THEN 'Subscription'
        ELSE event_type
    END AS domain,
    status AS action,
    source,
    json_extract_scalar(payload_json, '$.session_id') AS session_id,
    json_extract_scalar(payload_json, '$.device_type') AS device_type,
    json_extract_scalar(payload_json, '$.content_id') AS content_id,
    json_extract_scalar(payload_json, '$.search_term') AS search_term,
    json_extract_scalar(payload_json, '$.booking_id') AS booking_id,
    json_extract_scalar(payload_json, '$.booking_type') AS booking_type,
    json_extract_scalar(payload_json, '$.channel') AS channel,
    coalesce(
        json_extract_scalar(payload_json, '$.entertainment_event_id'),
        json_extract_scalar(payload_json, '$.content_id')
    ) AS destination_id,
    json_extract_scalar(payload_json, '$.entertainment_event_id') AS entertainment_event_id,
    json_extract_scalar(payload_json, '$.plan_id') AS plan_id,
    coalesce(try_cast(json_extract_scalar(payload_json, '$.quantity') AS bigint), 0) AS quantity,
    amount,
    currency,
    CASE
        WHEN event_type = 'booking' AND status = 'confirmed' THEN coalesce(amount, DECIMAL '0')
        WHEN event_type = 'booking' AND status = 'refunded' THEN -coalesce(amount, DECIMAL '0')
        ELSE DECIMAL '0'
    END AS booking_value_impact_proxy,
    CASE WHEN event_type = 'subscription' THEN coalesce(amount, DECIMAL '0') ELSE DECIMAL '0' END AS subscription_value_context,
    1 AS event_count
FROM {{catalog}}.{{silver_schema}}.events
WHERE customer_id IS NOT NULL
)
SELECT *
FROM journey

