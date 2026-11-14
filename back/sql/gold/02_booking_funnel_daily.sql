WITH booking AS (
    SELECT
        cast(at_timezone(occurred_at, 'UTC') AS date) AS event_date_utc,
        coalesce(
            json_extract_scalar(payload_json, '$.entertainment_event_id'),
            json_extract_scalar(payload_json, '$.content_id')
        ) AS destination_id,
        CASE
            WHEN json_extract_scalar(payload_json, '$.entertainment_event_id') IS NOT NULL THEN 'live_event'
            ELSE 'content'
        END AS destination_type,
        json_extract_scalar(payload_json, '$.booking_type') AS booking_type,
        json_extract_scalar(payload_json, '$.channel') AS channel,
        upper(currency) AS currency,
        lower(status) AS booking_status,
        coalesce(try_cast(json_extract_scalar(payload_json, '$.quantity') AS bigint), 0) AS quantity,
        coalesce(amount, DECIMAL '0') AS amount
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'booking'
)
SELECT
    event_date_utc,
    destination_type,
    destination_id,
    booking_type,
    channel,
    currency,
    count(*) AS booking_state_events,
    count_if(booking_status = 'initiated') AS initiated_events,
    count_if(booking_status = 'confirmed') AS confirmed_events,
    count_if(booking_status = 'cancelled') AS cancelled_events,
    count_if(booking_status = 'refunded') AS refunded_events,
    count_if(booking_status = 'failed') AS failed_events,
    sum(CASE WHEN booking_status = 'confirmed' THEN quantity ELSE 0 END) AS confirmed_quantity,
    sum(CASE WHEN booking_status = 'refunded' THEN quantity ELSE 0 END) AS refunded_quantity,
    sum(CASE WHEN booking_status = 'confirmed' THEN amount ELSE DECIMAL '0' END) AS confirmed_amount,
    sum(CASE WHEN booking_status = 'refunded' THEN amount ELSE DECIMAL '0' END) AS refunded_amount,
    sum(
        CASE
            WHEN booking_status = 'confirmed' THEN amount
            WHEN booking_status = 'refunded' THEN -amount
            ELSE DECIMAL '0'
        END
    ) AS net_booking_value_proxy,
    round(
        cast(count_if(booking_status = 'confirmed') AS double) / nullif(count(*), 0),
        4
    ) AS confirmation_share_proxy
FROM booking
GROUP BY 1, 2, 3, 4, 5, 6

