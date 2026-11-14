resource "terraform_data" "deployment_guard" {
  count = var.deployment_enabled ? 1 : 0

  lifecycle {
    precondition {
      condition     = var.create_network || (var.existing_private_subnet_id != null && startswith(var.existing_private_subnet_id, "ocid1.subnet."))
      error_message = "Set existing_private_subnet_id to a subnet OCID when create_network is false."
    }

    precondition {
      condition     = !var.enable_managed_kafka || var.kafka_cluster_type != "PRODUCTION" || var.kafka_broker_count >= 3
      error_message = "PRODUCTION Managed Kafka requires at least three brokers."
    }

    precondition {
      condition     = !var.enable_dataflow || (length(var.dataflow_dns_zones) > 0 && startswith(var.dataflow_application_file_uri, "oci://"))
      error_message = "Data Flow requires at least one DNS zone and an oci:// application file URI."
    }

    precondition {
      condition     = !var.enable_autonomous_lakehouse || (var.autonomous_admin_secret_id != null && startswith(var.autonomous_admin_secret_id, "ocid1.vaultsecret."))
      error_message = "Autonomous AI Lakehouse requires autonomous_admin_secret_id pointing to an OCI Vault secret."
    }
  }
}
