WITH activity AS (
    SELECT
        date_trunc('hour', at_timezone(occurred_at, 'UTC')) AS event_hour_utc,
        customer_id,
        coalesce(json_extract_scalar(payload_json, '$.content_id'), '__NO_CONTENT__') AS content_id,
        json_extract_scalar(payload_json, '$.device_type') AS device_type,
        lower(json_extract_scalar(payload_json, '$.activity_type')) AS activity_type,
        try_cast(json_extract_scalar(payload_json, '$.position_seconds') AS double) AS position_seconds
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'user_activity'
)
SELECT
    event_hour_utc,
    cast(event_hour_utc AS date) AS event_date_utc,
    content_id,
    device_type,
    count(*) AS activity_events,
    count(DISTINCT customer_id) AS active_users,
    count_if(activity_type = 'play') AS play_events,
    count_if(activity_type = 'complete') AS completion_events,
    round(
        cast(count_if(activity_type = 'complete') AS double)
        / nullif(count_if(activity_type = 'play'), 0),
        4
    ) AS completion_per_play_proxy,
    round(sum(coalesce(position_seconds, 0)), 2) AS observed_position_seconds
FROM activity
GROUP BY 1, 2, 3, 4

