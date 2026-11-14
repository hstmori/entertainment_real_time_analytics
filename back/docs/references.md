# Tài liệu kỹ thuật tham chiếu

Các nguồn chính thức dùng để chốt bộ khung ngày 2026-11-06:

- [Apache Kafka Docker image documentation](https://kafka.apache.org/documentation/#docker)
- [Apache Kafka downloads and Docker tags](https://kafka.apache.org/community/downloads/)
- [Apache Kafka official Docker examples](https://github.com/apache/kafka/tree/trunk/docker/examples)
- [Apache Iceberg Spark quickstart with REST catalog and object storage](https://iceberg.apache.org/spark-quickstart/)
- [Apache Iceberg REST catalog specification](https://iceberg.apache.org/docs/latest/rest-catalog/)
- [Trino object storage overview](https://trino.io/docs/current/object-storage.html)
- [Trino S3-compatible storage configuration](https://trino.io/docs/current/object-storage/file-system-s3.html)
- [Trino Iceberg catalog/metastore configuration](https://trino.io/docs/current/object-storage/metastores.html)
- [RustFS container deployment](https://docs.rustfs.com/en/installation/container/docker/)
- [RustFS official repository](https://github.com/rustfs/rustfs)
- [Apache Iceberg tracking issue: replace withdrawn MinIO images with RustFS](https://github.com/apache/iceberg/issues/18246)
- [Confluent Kafka Python client documentation](https://docs.confluent.io/kafka-clients/python/current/index.html)
- [confluent-kafka package release history](https://pypi.org/project/confluent-kafka/)
- [jsonschema package release history](https://pypi.org/project/jsonschema/)
- [pytest changelog](https://docs.pytest.org/en/latest/changelog.html)
- [Trino Python client](https://pypi.org/project/trino/)
- [Trino Iceberg connector](https://trino.io/docs/current/connector/iceberg.html)
- [Trino client protocol](https://trino.io/docs/current/client/client-protocol.html)
- [Confluent Python manual offset commits](https://docs.confluent.io/kafka-clients/python/current/index.html)
- [Trino CREATE TABLE AS](https://trino.io/docs/current/sql/create-table-as.html)
- [Trino ALTER TABLE / RENAME](https://trino.io/docs/current/sql/alter-table.html)
- [Trino JSON functions](https://trino.io/docs/current/functions/json.html)
- [OCI Streaming with Apache Kafka overview](https://docs.oracle.com/en-us/iaas/Content/kafka/overview.htm)
- [OCI Managed Kafka Terraform resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/managed_kafka_kafka_cluster.html)
- [OCI Data Flow streaming applications](https://docs.oracle.com/en-us/iaas/Content/data-flow/using/streaming-get-started.htm)
- [OCI Data Flow Terraform application resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/dataflow_application.html)
- [OCI Data Flow resource principal policies](https://docs.oracle.com/en-us/iaas/Content/data-flow/using/resource-principal-policies.htm)
- [OCI Object Storage Terraform bucket resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/objectstorage_bucket.html)
- [Autonomous AI Lakehouse external Iceberg queries](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/query-external-data-apache-iceberg.html)
- [Autonomous AI Database Terraform resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/database_autonomous_database.html)
- [Power BI connection to Autonomous AI Database](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/connecting-ocmt.html)

Lưu ý: image version phải được kiểm tra lại trước khi production hóa. `apache/iceberg-rest-fixture` là fixture cho local test; không dùng làm production metadata catalog. MinIO vẫn là một ý tưởng kiến trúc trong đề gốc, nhưng public Community Edition images không còn khả dụng ở thời điểm smoke test.

