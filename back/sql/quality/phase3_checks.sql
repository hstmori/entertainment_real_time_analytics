-- Bronze lineage must be unique by Kafka source coordinates.
SELECT
    count(*) AS bronze_rows,
    count(DISTINCT source_topic || ':' || CAST(source_partition AS varchar) || ':' || CAST(source_offset AS varchar)) AS unique_lineage
FROM iceberg.bronze.raw_events;

-- Silver must contain one row per event_id.
SELECT
    count(*) AS silver_rows,
    count(DISTINCT event_id) AS distinct_event_ids,
    count(*) - count(DISTINCT event_id) AS duplicate_rows
FROM iceberg.silver.events;

-- Trace a Silver record back to its exact Kafka coordinate and Bronze payload.
SELECT
    s.event_id,
    s.source_topic,
    s.source_partition,
    s.source_offset,
    b.ingestion_id,
    b.payload_sha256,
    b.ingested_at
FROM iceberg.silver.events s
JOIN iceberg.bronze.raw_events b
    ON s.source_topic = b.source_topic
   AND s.source_partition = b.source_partition
   AND s.source_offset = b.source_offset
ORDER BY b.ingested_at DESC
LIMIT 20;

