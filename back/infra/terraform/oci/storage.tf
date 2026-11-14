resource "oci_objectstorage_bucket" "lakehouse" {
  for_each = var.deployment_enabled ? local.bucket_names : {}

  access_type           = "NoPublicAccess"
  compartment_id        = var.compartment_ocid
  freeform_tags         = merge(local.common_tags, { DataLayer = each.key })
  is_bucket_key_enabled = var.object_storage_kms_key_id != null
  kms_key_id            = var.object_storage_kms_key_id
  name                  = each.value
  namespace             = local.object_storage_namespace
  object_events_enabled = true
  storage_tier          = "Standard"
  versioning            = "Enabled"
}
