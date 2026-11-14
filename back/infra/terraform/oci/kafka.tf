locals {
  kafka_properties = merge(
    {
      "auto.create.topics.enable" = "false"
      "compression.type"          = "producer"
      "delete.topic.enable"       = "false"
      "min.insync.replicas"       = var.kafka_cluster_type == "PRODUCTION" ? "2" : "1"
    },
    var.kafka_config_properties,
  )
}

resource "oci_managed_kafka_kafka_cluster_config" "lakehouse" {
  count = local.create_managed_kafka ? 1 : 0

  compartment_id = var.compartment_ocid
  display_name   = "${local.name_prefix}-kafka-config"
  freeform_tags  = local.common_tags

  latest_config {
    properties     = local.kafka_properties
    version_number = 1
  }
}

resource "oci_managed_kafka_kafka_cluster" "lakehouse" {
  count = local.create_managed_kafka ? 1 : 0

  cluster_config_id      = oci_managed_kafka_kafka_cluster_config.lakehouse[0].id
  cluster_config_version = 1
  cluster_type           = var.kafka_cluster_type
  compartment_id         = var.compartment_ocid
  coordination_type      = var.kafka_coordination_type
  display_name           = "${local.name_prefix}-kafka"
  freeform_tags          = local.common_tags
  kafka_version          = var.kafka_version

  access_subnets {
    subnets = [local.private_subnet_id]
  }

  broker_shape {
    node_count          = var.kafka_broker_count
    node_shape          = var.kafka_broker_shape
    ocpu_count          = var.kafka_broker_ocpus
    storage_size_in_gbs = var.kafka_broker_storage_gb
  }

  timeouts {
    create = "60m"
    delete = "60m"
    update = "60m"
  }

  depends_on = [terraform_data.deployment_guard]
}
