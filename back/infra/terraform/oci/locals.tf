locals {
  name_prefix = lower(replace("${var.project_name}-${var.environment}", "_", "-"))

  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = var.project_name
    },
    var.freeform_tags,
  )

  create_network = var.deployment_enabled && var.create_network
  private_subnet_id = var.create_network ? try(
    oci_core_subnet.private[0].id,
    null,
  ) : var.existing_private_subnet_id

  bucket_suffixes = toset([
    "artifacts",
    "bronze",
    "checkpoints",
    "gold",
    "logs",
    "silver",
    "warehouse",
  ])

  bucket_name_prefix = coalesce(var.bucket_name_prefix, local.name_prefix)
  bucket_names = {
    for suffix in local.bucket_suffixes :
    suffix => substr("${local.bucket_name_prefix}-${suffix}", 0, 256)
  }

  object_storage_namespace = try(data.oci_objectstorage_namespace.this[0].namespace, null)

  create_managed_kafka = var.deployment_enabled && var.enable_managed_kafka
  create_dataflow      = var.deployment_enabled && var.enable_dataflow
  create_lakehouse     = var.deployment_enabled && var.enable_autonomous_lakehouse
}
