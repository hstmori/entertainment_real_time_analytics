output "bucket_names" {
  description = "Lakehouse Object Storage buckets by data layer."
  value = {
    for key, bucket in oci_objectstorage_bucket.lakehouse : key => bucket.name
  }
}

output "object_storage_namespace" {
  description = "OCI Object Storage namespace used in oci:// URIs."
  value       = local.object_storage_namespace
}

output "private_subnet_id" {
  description = "Private subnet used by Kafka, Data Flow, and Autonomous AI Lakehouse."
  value       = var.deployment_enabled ? local.private_subnet_id : null
}

output "kafka_cluster_id" {
  description = "Managed Kafka cluster OCID when enabled."
  value       = try(oci_managed_kafka_kafka_cluster.lakehouse[0].id, null)
}

output "kafka_bootstrap_urls" {
  description = "Managed Kafka bootstrap listener URLs when enabled."
  value       = try(oci_managed_kafka_kafka_cluster.lakehouse[0].kafka_bootstrap_urls, [])
}

output "kafka_superuser_secret_id" {
  description = "Vault secret OCID generated for the Managed Kafka superuser. The secret value is not exposed."
  value       = try(oci_managed_kafka_kafka_cluster.lakehouse[0].secret_id, null)
  sensitive   = true
}

output "dataflow_application_id" {
  description = "Data Flow streaming application OCID when enabled."
  value       = try(oci_dataflow_application.streaming[0].id, null)
}

output "autonomous_lakehouse_id" {
  description = "Autonomous AI Lakehouse OCID when enabled."
  value       = try(oci_database_autonomous_database.lakehouse[0].id, null)
}

output "autonomous_private_endpoint" {
  description = "Private Autonomous AI Lakehouse endpoint when enabled."
  value       = try(oci_database_autonomous_database.lakehouse[0].private_endpoint, null)
}
