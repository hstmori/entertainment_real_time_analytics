# OCI Lakehouse Terraform foundation

This stack prepares the Oracle-native deployment target for the local PoC:

```text
OCI Streaming with Apache Kafka
  -> OCI Data Flow (Spark Structured Streaming)
  -> OCI Object Storage (Bronze / Silver / Gold Iceberg)
  -> Autonomous AI Lakehouse
  -> Power BI
```

## Safety model

- `deployment_enabled` defaults to `false`, so the first plan is a no-op.
- Managed Kafka, Data Flow, and Autonomous AI Lakehouse each have a separate opt-in flag.
- The stack never accepts an Autonomous ADMIN password. It accepts only a Vault secret OCID.
- API keys, private keys, passwords, `terraform.tfvars`, state, and plan files are ignored. The provider lock file is intentionally versionable for reproducible installs.
- Use OCI Resource Manager or another encrypted remote-state backend before production use.

## Included resources

- Optional private VCN and subnet with NAT and Oracle Services Network gateways.
- Private security rules for Kafka TLS and Oracle SQL Net TLS.
- Versioned, non-public Object Storage buckets for artifacts, Bronze, Silver, Gold, checkpoints, logs, and Spark warehouse.
- OCI Logging group and Data Flow custom log.
- Optional OCI Streaming with Apache Kafka cluster and cluster configuration.
- Optional Data Flow private endpoint and streaming application definition.
- Optional private Autonomous AI Lakehouse (`db_workload = "LH"`).

## First validation

```powershell
Copy-Item infra/terraform/oci/terraform.tfvars.example infra/terraform/oci/terraform.tfvars
# Replace placeholder OCIDs but keep deployment_enabled = false.
terraform -chdir=infra/terraform/oci init
terraform -chdir=infra/terraform/oci fmt -check
terraform -chdir=infra/terraform/oci validate
terraform -chdir=infra/terraform/oci plan -out foundation.tfplan
```

Review the no-op plan, then follow `docs/phase-6a-oci-deployment.md`. Never enable all paid services in one first apply. Provision and verify foundation, Kafka, Data Flow, and Autonomous AI Lakehouse in separate reviewed plans.

## Authentication

The provider block contains only the OCI region. Authenticate with one of OCI's supported provider mechanisms, such as an OCI config profile for local administration or Resource Manager principal authentication. Do not add credentials to these `.tf` files.

## Regional values

Kafka and Spark versions, VM shapes, service quotas, and availability vary by region. The example values are reviewable starting values, not an assertion that every value is available in every tenancy. Confirm them before changing `deployment_enabled` to `true`.
