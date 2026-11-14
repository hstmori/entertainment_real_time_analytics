resource "oci_logging_log_group" "lakehouse" {
  count = var.deployment_enabled ? 1 : 0

  compartment_id = var.compartment_ocid
  description    = "Central logs for the entertainment lakehouse"
  display_name   = "${local.name_prefix}-logs"
  freeform_tags  = local.common_tags
}

resource "oci_logging_log" "dataflow" {
  count = var.deployment_enabled ? 1 : 0

  display_name       = "${local.name_prefix}-dataflow-application"
  freeform_tags      = local.common_tags
  is_enabled         = true
  log_group_id       = oci_logging_log_group.lakehouse[0].id
  log_type           = "CUSTOM"
  retention_duration = 30
}
