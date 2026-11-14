resource "oci_database_autonomous_database" "lakehouse" {
  count = local.create_lakehouse ? 1 : 0

  compartment_id              = var.compartment_ocid
  compute_count               = var.autonomous_compute_count
  compute_model               = "ECPU"
  data_storage_size_in_gb     = var.autonomous_storage_gb
  db_name                     = var.autonomous_db_name
  db_workload                 = "LH"
  display_name                = "${local.name_prefix}-autonomous-lakehouse"
  freeform_tags               = local.common_tags
  is_auto_scaling_enabled     = true
  is_mtls_connection_required = true
  license_model               = var.autonomous_license_model
  private_endpoint_label      = replace(local.name_prefix, "-", "")
  secret_id                   = var.autonomous_admin_secret_id
  source                      = "NONE"
  subnet_id                   = local.private_subnet_id

  depends_on = [terraform_data.deployment_guard]
}
