WITH subscription AS (
    SELECT
        cast(at_timezone(occurred_at, 'UTC') AS date) AS event_date_utc,
        json_extract_scalar(payload_json, '$.plan_id') AS plan_id,
        upper(currency) AS currency,
        lower(status) AS subscription_status,
        coalesce(amount, DECIMAL '0') AS amount
    FROM {{catalog}}.{{silver_schema}}.events
    WHERE event_type = 'subscription'
)
SELECT
    event_date_utc,
    plan_id,
    currency,
    count(*) AS subscription_events,
    count_if(subscription_status = 'started') AS started_events,
    count_if(subscription_status = 'renewed') AS renewed_events,
    count_if(subscription_status = 'upgraded') AS upgraded_events,
    count_if(subscription_status = 'downgraded') AS downgraded_events,
    count_if(subscription_status = 'paused') AS paused_events,
    count_if(subscription_status = 'cancelled') AS cancelled_events,
    count_if(subscription_status = 'expired') AS expired_events,
    sum(
        CASE WHEN subscription_status IN ('started', 'renewed', 'upgraded')
            THEN amount ELSE DECIMAL '0' END
    ) AS mrr_event_value_proxy,
    sum(CASE WHEN subscription_status = 'cancelled' THEN amount ELSE DECIMAL '0' END) AS cancelled_value_context
FROM subscription
GROUP BY 1, 2, 3

