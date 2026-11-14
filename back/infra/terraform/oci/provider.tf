provider "oci" {
  region = var.region
}

data "oci_objectstorage_namespace" "this" {
  count          = var.deployment_enabled ? 1 : 0
  compartment_id = var.tenancy_ocid
}
