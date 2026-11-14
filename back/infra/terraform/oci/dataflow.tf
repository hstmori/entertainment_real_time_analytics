resource "oci_dataflow_private_endpoint" "lakehouse" {
  count = local.create_dataflow ? 1 : 0

  compartment_id = var.compartment_ocid
  description    = "Private endpoint for Data Flow access to Managed Kafka and private Oracle services"
  display_name   = "${local.name_prefix}-dataflow-endpoint"
  dns_zones      = var.dataflow_dns_zones
  freeform_tags  = local.common_tags
  max_host_count = 256
  subnet_id      = local.private_subnet_id

  depends_on = [terraform_data.deployment_guard]
}

resource "oci_dataflow_application" "streaming" {
  count = local.create_dataflow ? 1 : 0

  archive_uri                = var.dataflow_archive_uri
  compartment_id             = var.compartment_ocid
  description                = "Kafka to Bronze/Silver Iceberg streaming pipeline"
  display_name               = "${local.name_prefix}-streaming"
  driver_shape               = var.dataflow_driver_shape
  executor_shape             = var.dataflow_executor_shape
  file_uri                   = var.dataflow_application_file_uri
  freeform_tags              = local.common_tags
  language                   = "PYTHON"
  logs_bucket_uri            = "oci://${oci_objectstorage_bucket.lakehouse["logs"].name}@${local.object_storage_namespace}/"
  num_executors              = var.dataflow_num_executors
  private_endpoint_id        = oci_dataflow_private_endpoint.lakehouse[0].id
  spark_version              = var.dataflow_spark_version
  terminate_runs_on_deletion = true
  type                       = "STREAMING"

  application_log_config {
    log_group_id = oci_logging_log_group.lakehouse[0].id
    log_id       = oci_logging_log.dataflow[0].id
  }

  driver_shape_config {
    memory_in_gbs = var.dataflow_driver_memory_gb
    ocpus         = var.dataflow_driver_ocpus
  }

  executor_shape_config {
    memory_in_gbs = var.dataflow_executor_memory_gb
    ocpus         = var.dataflow_executor_ocpus
  }

  depends_on = [terraform_data.deployment_guard]
}
