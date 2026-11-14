WITH booking AS (
    SELECT
        json_extract_scalar(payload_json, '$.entertainment_event_id') AS entertainment_event_id,
        upper(currency) AS currency,
        count_if(status = 'confirmed') AS confirmed_bookings,
        count_if(status = 'refunded') AS refunded_bookings,
        sum(
            CASE WHEN status = 'confirmed'
                THEN coalesce(try_cast(json_extract_scalar(payload_json, '$.quantity') AS bigint), 0)
                ELSE 0
            END
        ) AS confirmed_tickets,
        sum(
            CASE WHEN status = 'refunded'
                THEN coalesce(try_cast(json_extract_scalar(payload_json, '$.quantity') AS bigint), 0)
                ELSE 0
            END
        ) AS refunded_tickets,
        sum(
            CASE
                WHEN status = 'confirmed' THEN coalesce(amount, DECIMAL '0')
                WHEN status = 'refunded' THEN -coalesce(amount, DECIMAL '0')
                ELSE DECIMAL '0'
            END
        ) AS net_booking_value_proxy,
        min(occurred_at) AS first_booking_event_at,
        max(occurred_at) AS last_booking_event_at
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'booking'
      AND json_extract_scalar(payload_json, '$.entertainment_event_id') IS NOT NULL
    GROUP BY 1, 2
),
attendance AS (
    SELECT
        json_extract_scalar(payload_json, '$.entertainment_event_id') AS entertainment_event_id,
        count(*) AS attendance_records,
        count_if(status = 'checked_in') AS checked_in,
        count_if(status = 'no_show') AS no_show,
        count_if(status = 'rejected') AS rejected,
        min(occurred_at) AS first_attendance_event_at,
        max(occurred_at) AS last_attendance_event_at
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'event_attendance'
    GROUP BY 1
)
SELECT
    coalesce(b.entertainment_event_id, a.entertainment_event_id) AS entertainment_event_id,
    b.currency,
    coalesce(b.confirmed_bookings, 0) AS confirmed_bookings,
    coalesce(b.refunded_bookings, 0) AS refunded_bookings,
    coalesce(b.confirmed_tickets, 0) AS confirmed_tickets,
    coalesce(b.refunded_tickets, 0) AS refunded_tickets,
    coalesce(b.net_booking_value_proxy, DECIMAL '0') AS net_booking_value_proxy,
    coalesce(a.attendance_records, 0) AS attendance_records,
    coalesce(a.checked_in, 0) AS checked_in,
    coalesce(a.no_show, 0) AS no_show,
    coalesce(a.rejected, 0) AS rejected,
    round(cast(a.checked_in AS double) / nullif(a.attendance_records, 0), 4) AS attendance_rate_proxy,
    round(cast(a.no_show AS double) / nullif(a.attendance_records, 0), 4) AS no_show_rate_proxy,
    b.first_booking_event_at,
    b.last_booking_event_at,
    a.first_attendance_event_at,
    a.last_attendance_event_at
FROM booking b
FULL OUTER JOIN attendance a
    ON b.entertainment_event_id = a.entertainment_event_id

