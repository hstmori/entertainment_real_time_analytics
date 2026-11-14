# Phase 6A - OCI Lakehouse deployment runbook

## 1. Trạng thái và ranh giới

Phase 6A đã chuẩn bị Infrastructure-as-Code và cấu hình ứng dụng để chuyển từ local PoC sang đích Oracle-native:

```text
OCI Streaming with Apache Kafka
  -> OCI Data Flow Spark Structured Streaming
  -> OCI Object Storage Bronze/Silver/Gold Iceberg
  -> Autonomous AI Lakehouse
  -> Power BI
```

Chưa có tài nguyên cloud nào được tạo. `deployment_enabled = false` là mặc định và các dịch vụ tốn phí có cờ bật riêng. Việc `apply` chỉ được thực hiện sau khi có tenancy, compartment, region, IAM, quota và budget được duyệt.

## 2. Thành phần đã chuẩn bị

| Thành phần | Mã nguồn | Trạng thái |
|---|---|---|
| VCN/subnet private, NAT, service gateway | `infra/terraform/oci/network.tf` | Sẵn sàng để plan |
| Bronze/Silver/Gold và bucket vận hành | `infra/terraform/oci/storage.tf` | Sẵn sàng để plan |
| Logging | `infra/terraform/oci/observability.tf` | Sẵn sàng để plan |
| OCI Streaming with Apache Kafka | `infra/terraform/oci/kafka.tf` | Opt-in, cần kiểm tra quota/version |
| Data Flow private endpoint/application | `infra/terraform/oci/dataflow.tf` | Opt-in, cần PySpark artifact Phase 6B |
| Autonomous AI Lakehouse private | `infra/terraform/oci/autonomous_lakehouse.tf` | Opt-in, cần Vault secret OCID |
| Kafka TLS/SASL cho Python producer/consumer/DLQ | `src/entertainment_pipeline/config.py` | Đã hỗ trợ bằng biến môi trường |
| Bootstrap 5 Kafka topics | `scripts/oci/create-topics.ps1` | Cần bootstrap URL/client config thật |

## 3. Điều kiện trước khi triển khai

1. Có OCI tenancy, target compartment và region đã chốt.
2. Người chạy có quyền tạo Networking, Object Storage, Logging và các dịch vụ được bật.
3. Kiểm tra service limits/quota cho Managed Kafka, Data Flow và Autonomous AI Lakehouse trong region.
4. Chốt budget/cost alert trước khi bật dịch vụ trả phí.
5. Cài Terraform `>= 1.6` hoặc dùng OCI Resource Manager.
6. Dùng OCI config/profile, security token, instance principal hoặc Resource Manager principal; không ghi API private key vào repo.

## 4. Trình tự triển khai có kiểm soát

### Bước A - validate no-op

```powershell
Copy-Item infra/terraform/oci/terraform.tfvars.example infra/terraform/oci/terraform.tfvars
# Thay region và OCID placeholder, giữ deployment_enabled = false.
terraform -chdir=infra/terraform/oci init
terraform -chdir=infra/terraform/oci fmt -check
terraform -chdir=infra/terraform/oci validate
terraform -chdir=infra/terraform/oci plan
```

Kỳ vọng: không tạo resource. Nếu plan có resource thì dừng và kiểm tra lại safety switch.

### Bước B - foundation trước, dịch vụ trả phí sau

Trong `terraform.tfvars`:

```hcl
deployment_enabled             = true
enable_managed_kafka           = false
enable_dataflow                = false
enable_autonomous_lakehouse    = false
```

Chạy plan và apply riêng cho VCN, subnet, gateways, buckets và logging. Kiểm tra:

- Subnet không cấp public IP.
- Buckets là `NoPublicAccess`, versioning `Enabled`.
- Route qua Service Gateway tới Oracle Services Network.
- Không có password/API key trong plan hoặc state.

### Bước C - Managed Kafka

1. Xác nhận `kafka_version`, `kafka_coordination_type`, shape và quota có trong region.
2. Với dev có thể dùng `DEVELOPMENT`; production phải dùng `PRODUCTION` và ít nhất ba broker.
3. Bật `enable_managed_kafka = true`, chạy plan riêng rồi apply.
4. Lấy bootstrap listeners bằng `terraform output kafka_bootstrap_urls`.
5. Tạo Kafka client config ngoài repo, lấy credential từ OCI Vault/secret bundle.
6. Tạo topic:

```powershell
./scripts/oci/create-topics.ps1 `
  -BootstrapServers '<bootstrap-host:port>' `
  -CommandConfig 'C:\secure\kafka-client.properties' `
  -Partitions 3 `
  -ReplicationFactor 3
```

Không truyền password trực tiếp trên command line.

### Bước D - kiểm tra producer với TLS/SASL

Inject secret vào environment của runtime:

```text
KAFKA_BOOTSTRAP_SERVERS
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM
KAFKA_SASL_USERNAME
KAFKA_SASL_PASSWORD
KAFKA_SSL_CA_LOCATION
```

Chạy dry-run trước, sau đó publish một batch nhỏ và đối chiếu offsets từng topic. Không ghi các biến này vào `.env` được commit, log hoặc tài liệu nghiệm thu.

### Bước E - Data Flow

Phase 6B cần đóng gói processor thành PySpark Structured Streaming và upload entry point/dependency archive vào bucket `artifacts`. Sau đó:

1. Điền `dataflow_application_file_uri` bằng URI `oci://...`.
2. Điền `dataflow_dns_zones` từ bootstrap FQDN của Managed Kafka.
3. Review và tạo IAM policies theo `infra/terraform/oci/iam-policy-template.txt`.
4. Bật `enable_dataflow = true`, plan/apply riêng.
5. Chạy job với checkpoint trong bucket `checkpoints`; xác nhận restart không làm trùng Silver.

Terraform chỉ tạo application definition; không tự chạy streaming job để tránh phát sinh compute ngoài ý muốn.

### Bước F - Autonomous AI Lakehouse

1. Tạo ADMIN password trong OCI Vault bằng Console/CLI an toàn.
2. Chỉ điền secret OCID vào `autonomous_admin_secret_id`; không điền secret value.
3. Xác nhận workload `LH`, ECPU/storage, license model và private subnet.
4. Bật `enable_autonomous_lakehouse = true`, plan/apply riêng.
5. Tạo credential/policy cho Autonomous AI Lakehouse đọc Iceberg metadata/data trong Object Storage.
6. Query thử từng bảng Gold, đối chiếu totals với kết quả Phase 4.

### Bước G - Power BI

1. Cài Oracle Client for Microsoft Tools/ODP.NET phù hợp trên Desktop hoặc gateway host.
2. Kết nối Power BI tới Autonomous AI Lakehouse private endpoint qua VPN/FastConnect/gateway.
3. Thay nguồn CSV Import bằng Oracle connector trong một nhánh PBIP riêng; giữ nguyên DAX/business semantics.
4. Chọn Import + incremental refresh cho báo cáo lịch sử, hoặc DirectQuery nếu SLA và tải đã được benchmark.
5. Reconcile lại 31 KPI đã được kiểm tra ở Phase 5 trước khi thay nguồn chính thức.

## 5. Nghiệm thu cloud

- 5 topic tồn tại, producer publish và consumer/Data Flow đọc thành công qua TLS/SASL.
- Bronze có lineage topic/partition/offset; Silver duplicate rate bằng 0.
- DLQ có 100% trace cho invalid fixtures.
- Restart/replay test đạt như local PoC.
- Gold totals reconcile với Silver và baseline Phase 4.
- Autonomous AI Lakehouse query được Iceberg Gold.
- Power BI refresh/DirectQuery thành công và 31 KPI reconcile.
- Đo P50/P95/P99 event-to-query và event-to-visual; NFR-01 chỉ đạt khi P95 không quá 60 giây.
- Có alerts cho consumer lag, Data Flow failure, DLQ volume, Iceberg commit, storage và Autonomous health.

## 6. Những việc chưa được tự động hóa trong Phase 6A

- Tạo OCI tenancy/compartment và phê duyệt IAM/quota/budget.
- Apply Terraform vào tenancy thật.
- PySpark Structured Streaming artifact cho Data Flow.
- Vault secret value và Kafka superuser lifecycle.
- Autonomous external Iceberg credentials/catalog objects.
- Power BI gateway/VPN/FastConnect và thay source PBIP.
- Benchmark latency/capacity/cost production.

Các phần này cần thông tin và quyền của môi trường đích; không thể xác nhận chỉ bằng local code.

## 7. Tài liệu Oracle chính thức

- Managed Kafka Terraform resource: <https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/managed_kafka_kafka_cluster.html>
- Data Flow application Terraform resource: <https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/dataflow_application.html>
- Data Flow resource principal policies: <https://docs.oracle.com/en-us/iaas/Content/data-flow/using/resource-principal-policies.htm>
- Object Storage bucket Terraform resource: <https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/objectstorage_bucket.html>
- Autonomous AI Database Terraform resource: <https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/database_autonomous_database.html>
