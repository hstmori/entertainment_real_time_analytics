variable "region" {
  description = "OCI region identifier, for example ap-singapore-1."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "region must not be empty."
  }
}

variable "tenancy_ocid" {
  description = "Tenancy OCID. Use terraform.tfvars or TF_VAR_tenancy_ocid; do not hard-code it in source files."
  type        = string
  sensitive   = true

  validation {
    condition     = startswith(var.tenancy_ocid, "ocid1.tenancy.")
    error_message = "tenancy_ocid must be a tenancy OCID."
  }
}

variable "compartment_ocid" {
  description = "Target compartment OCID."
  type        = string
  sensitive   = true

  validation {
    condition     = startswith(var.compartment_ocid, "ocid1.compartment.")
    error_message = "compartment_ocid must be a compartment OCID."
  }
}

variable "deployment_enabled" {
  description = "Master safety switch. No OCI resource is created while false."
  type        = bool
  default     = false
}

variable "project_name" {
  description = "Short project identifier used in resource names and tags."
  type        = string
  default     = "entertainment-lakehouse"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_-]{2,39}$", var.project_name))
    error_message = "project_name must start with a letter and contain 3-40 letters, numbers, hyphens, or underscores."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "stage", "prod"], var.environment)
    error_message = "environment must be one of dev, test, stage, or prod."
  }
}

variable "freeform_tags" {
  description = "Additional OCI free-form tags."
  type        = map(string)
  default     = {}
}

variable "create_network" {
  description = "Create a private VCN/subnet, NAT gateway, and service gateway."
  type        = bool
  default     = true
}

variable "existing_private_subnet_id" {
  description = "Existing private subnet OCID when create_network is false."
  type        = string
  default     = null
}

variable "vcn_cidr" {
  description = "CIDR for the dedicated lakehouse VCN."
  type        = string
  default     = "10.40.0.0/16"
}

variable "private_subnet_cidr" {
  description = "CIDR for Kafka, Data Flow private endpoint, and Autonomous AI Lakehouse."
  type        = string
  default     = "10.40.10.0/24"
}

variable "bucket_name_prefix" {
  description = "Optional tenancy-unique Object Storage bucket prefix. Defaults to project-environment."
  type        = string
  default     = null
}

variable "object_storage_kms_key_id" {
  description = "Optional Vault master encryption key OCID for Object Storage."
  type        = string
  default     = null
  sensitive   = true
}

variable "enable_managed_kafka" {
  description = "Create OCI Streaming with Apache Kafka resources. This can incur material cost."
  type        = bool
  default     = false
}

variable "kafka_cluster_type" {
  description = "DEVELOPMENT permits one broker; PRODUCTION requires at least three."
  type        = string
  default     = "DEVELOPMENT"

  validation {
    condition     = contains(["DEVELOPMENT", "PRODUCTION"], var.kafka_cluster_type)
    error_message = "kafka_cluster_type must be DEVELOPMENT or PRODUCTION."
  }
}

variable "kafka_version" {
  description = "Managed Kafka version available in the target OCI region."
  type        = string
  default     = "3.7.0"
}

variable "kafka_coordination_type" {
  description = "Coordination type supported by the selected Kafka version."
  type        = string
  default     = "ZOOKEEPER"

  validation {
    condition     = contains(["ZOOKEEPER", "KRAFT"], var.kafka_coordination_type)
    error_message = "kafka_coordination_type must be ZOOKEEPER or KRAFT."
  }
}

variable "kafka_broker_count" {
  description = "Number of Managed Kafka broker nodes."
  type        = number
  default     = 1
}

variable "kafka_broker_ocpus" {
  description = "OCPUs per Managed Kafka broker."
  type        = number
  default     = 1
}

variable "kafka_broker_storage_gb" {
  description = "Storage in GB per Managed Kafka broker."
  type        = number
  default     = 50
}

variable "kafka_broker_shape" {
  description = "Optional flexible VM shape for Managed Kafka brokers."
  type        = string
  default     = null
}

variable "kafka_config_properties" {
  description = "Additional Managed Kafka server properties."
  type        = map(string)
  default     = {}
}

variable "enable_dataflow" {
  description = "Create a Data Flow private endpoint and streaming application."
  type        = bool
  default     = false
}

variable "dataflow_dns_zones" {
  description = "DNS zones resolvable through the Data Flow private endpoint. Set from the Managed Kafka bootstrap FQDN."
  type        = list(string)
  default     = []
}

variable "dataflow_application_file_uri" {
  description = "OCI URI of the uploaded PySpark streaming entry point."
  type        = string
  default     = ""
}

variable "dataflow_archive_uri" {
  description = "Optional OCI URI of a zip archive containing Python dependencies."
  type        = string
  default     = null
}

variable "dataflow_spark_version" {
  description = "Spark version available in the target OCI region."
  type        = string
  default     = "3.5.0"
}

variable "dataflow_driver_shape" {
  description = "Data Flow driver shape."
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "dataflow_executor_shape" {
  description = "Data Flow executor shape."
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "dataflow_driver_ocpus" {
  description = "Driver OCPUs for a flexible shape."
  type        = number
  default     = 1
}

variable "dataflow_driver_memory_gb" {
  description = "Driver memory in GB for a flexible shape."
  type        = number
  default     = 16
}

variable "dataflow_executor_ocpus" {
  description = "Executor OCPUs for a flexible shape."
  type        = number
  default     = 1
}

variable "dataflow_executor_memory_gb" {
  description = "Executor memory in GB for a flexible shape."
  type        = number
  default     = 16
}

variable "dataflow_num_executors" {
  description = "Number of Data Flow executors."
  type        = number
  default     = 2
}

variable "enable_autonomous_lakehouse" {
  description = "Create Autonomous AI Lakehouse with private access. This can incur material cost."
  type        = bool
  default     = false
}

variable "autonomous_admin_secret_id" {
  description = "Vault secret OCID containing the Autonomous ADMIN password. Never put the password in tfvars."
  type        = string
  default     = null
  sensitive   = true
}

variable "autonomous_db_name" {
  description = "Autonomous database name."
  type        = string
  default     = "ENTLAKEDEV"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9]{0,13}$", var.autonomous_db_name))
    error_message = "autonomous_db_name must be 1-14 alphanumeric characters and start with a letter."
  }
}

variable "autonomous_compute_count" {
  description = "Autonomous AI Lakehouse ECPU count."
  type        = number
  default     = 2
}

variable "autonomous_storage_gb" {
  description = "Autonomous AI Lakehouse storage in GB."
  type        = number
  default     = 1024
}

variable "autonomous_license_model" {
  description = "LICENSE_INCLUDED or BRING_YOUR_OWN_LICENSE."
  type        = string
  default     = "LICENSE_INCLUDED"

  validation {
    condition     = contains(["LICENSE_INCLUDED", "BRING_YOUR_OWN_LICENSE"], var.autonomous_license_model)
    error_message = "autonomous_license_model must be LICENSE_INCLUDED or BRING_YOUR_OWN_LICENSE."
  }
}
