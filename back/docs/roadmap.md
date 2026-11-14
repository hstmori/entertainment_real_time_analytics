# Roadmap triển khai

## Phase 0 - Foundation (đã chuẩn bị)

- Requirements traceability và Definition of Done.
- Kiến trúc local PoC, Oracle/OCI mapping và ADR.
- Docker Compose, Kafka topic bootstrap, RustFS buckets, Iceberg REST và Trino catalog.
- JSON Schema cho bốn domain.
- Preflight/validation scripts.

Exit criteria: cấu trúc và config validate; khi có Docker, toàn bộ service khởi động và Trino nhìn thấy Iceberg catalog.

## Phase 1 - Local platform smoke test (đã hoàn thành 2026-11-06)

1. Cài Docker Desktop/Compose v2.
2. Chạy `scripts/preflight.ps1` và `docker compose up -d`.
3. Kiểm tra năm Kafka topics, ba object-store buckets, REST catalog và Trino.
4. Chạy SQL tạo Bronze/Silver/Gold namespaces.
5. Lưu log bằng chứng smoke test.

Exit criteria: tất cả service healthy; namespace query được qua Trino.

Kết quả thực tế: đạt. Xem [smoke test evidence](smoke-test-2026-11-06.md).

## Phase 2 - Event generation và Kafka ingestion (đã hoàn thành 2026-11-06)

1. Tạo Python package và cấu hình dependency cố định.
2. Sinh dữ liệu giả lập reproducible cho user activity, booking, subscription và attendance.
3. Validate theo JSON Schema trước khi publish.
4. Thêm correlation ID, deterministic seed và throughput controls.
5. Viết unit/integration tests cho contract và partition key.

Exit criteria: produced count khớp consumed count trong smoke test; invalid fixtures bị từ chối đúng.

Kết quả thực tế: đạt. Automated test đạt 9/9; batch live publish/deliver 40/40 và consumer đọc lại đủ 40 sự kiện mới trên bốn topic. Xem [Phase 2 evidence](phase-2-smoke-test-2026-11-06.md).

## Phase 3 - Stream-to-lakehouse (đã hoàn thành 2026-11-06)

1. Consumer group đọc bốn topics.
2. Validate, enrich Kafka metadata, retry và DLQ.
3. Ghi Bronze theo micro-batch để kiểm soát small files.
4. Tạo Silver transformations và idempotent merge/dedupe.
5. Viết replay, restart và duplicate tests.

Exit criteria: lineage topic/partition/offset -> Iceberg record; NFR-02 đến NFR-04 đạt.

Kết quả thực tế: đạt. Consumer restart giữ đủ dữ liệu và lag về 0; Bronze có 80 source lineage duy nhất, Silver có 40 event ID duy nhất và 0 duplicate; invalid record có trace DLQ đầy đủ; replay sang schema độc lập tái tạo đúng 80 Bronze/40 Silver. Xem [Phase 3 evidence](phase-3-smoke-test-2026-11-06.md).

## Phase 4 - Analytical model (đã hoàn thành 2026-11-06)

1. Chốt metric definitions với business.
2. Xây dựng Gold data products và reconciliation queries.
3. Kiểm tra late events, timezone, refund/cancellation và Customer 360 identity rules.
4. Tạo data dictionary và lineage table-level/column-level.

Exit criteria: Gold trả lời BR-01 đến BR-05, các số tổng kiểm tra chéo với Silver.

Kết quả thực tế: đạt ở phạm vi PoC. Năm Gold tables trả lời BR-01 đến BR-05; bốn domain reconcile 10/10 với Silver, financial proxy reconcile tuyệt đối, Customer 360 có 36/36 customer keys duy nhất. Xem [Phase 4 evidence](phase-4-smoke-test-2026-11-06.md) và [metric definitions](gold-metric-definitions.md).

## Phase 5 - Power BI (đã hoàn thành ở phạm vi PoC chức năng 2026-11-06)

1. Chọn DirectQuery hay Import/incremental refresh theo SLA và tải.
2. Tạo semantic model, measures và bốn trang dashboard ưu tiên.
3. Kiểm tra refresh, filter interactions, performance và business definitions.
4. Ghi lại latency thực tế từ event đến visual.

Exit criteria: dashboard refresh thành công, measures được đối chiếu với Trino SQL, latency đạt SLA.

Kết quả thực tế: đã chọn Import từ governed Gold CSV exports cho local PoC; tạo 7-table TMDL semantic model, 33 DAX measures, 3 relationships và bốn trang PBIR. Power BI Desktop refresh thành công, cả bốn trang render, slicer interaction hoạt động và 31 KPI chính đối chiếu tuyệt đối với CSV export. Refresh hoàn tất trong cửa sổ quan sát dưới 8 giây, nhưng event-to-visual latency end-to-end chưa được nghiệm thu vì Gold export/Power BI refresh còn chạy thủ công. Xem [Phase 5 PBIP và Desktop evidence](phase-5-code-validation-2026-11-06.md).

### Phase 5B - Customer 360 redesign (source hoàn thành 2026-11-07)

- Mở rộng customer snapshot lên 36 thuộc tính về recency, breadth, engagement, booking, attendance và latest subscription.
- Bổ sung `gold.customer_journey` ở event grain để drill-down toàn bộ hành vi theo customer.
- Tách dữ liệu acceptance và deterministic portfolio demo; demo có 1.200 events, 200 customers và 100 ngày quan sát.
- PBIP hiện có 8 tables, 47 measures, 5 relationships, 5 pages và 69 visuals.
- Hai trang Customer 360/Customer Journey tách rõ portfolio view và single-customer event timeline.

Source/model validation đã đạt. Chưa mở lại Power BI Desktop cho bản 5B, vì vậy layout, interaction và refresh của bản mới vẫn cần người dùng kiểm tra trực tiếp trước khi gắn nhãn Desktop-validated. Xem [Customer 360 dashboard design](customer-360-dashboard.md) và [validation evidence](customer-360-validation-2026-11-07.md).

## Phase 6 - Production hardening

1. TLS/SASL, RBAC, secrets manager và network isolation.
2. Multi-node HA, persistent catalog, backup/restore và disaster recovery.
3. Schema compatibility policy, CI/CD và infrastructure-as-code.
4. Monitoring/alerting, load test, capacity planning và cost model.
5. Chốt mapping sang các dịch vụ Oracle/OCI cụ thể.

Exit criteria: security review, resilience test, operational runbook và production readiness review đạt.

### Phase 6A - OCI deployment foundation (đã chuẩn bị code 2026-11-06, chưa apply)

- Đã tạo Terraform cho private networking, Object Storage, Logging và các resource opt-in cho OCI Streaming with Apache Kafka, Data Flow và Autonomous AI Lakehouse.
- Mặc định `deployment_enabled = false`; ba dịch vụ trả phí đều tắt riêng để tránh tạo resource ngoài ý muốn.
- Đã bổ sung TLS/SASL environment config cho producer, consumer và DLQ publisher.
- Đã tạo topic bootstrap script, IAM policy template, structural tests và deployment runbook.
- Code validation đạt: Terraform fmt/init/validate với OCI provider 8.29.0 và toàn bộ 28/28 automated tests pass.

Chưa thể gọi Phase 6A là triển khai cloud thành công cho đến khi có OCI tenancy/compartment/region, IAM, quota/budget, chạy `terraform plan/apply` và lưu bằng chứng live. Xem [OCI deployment runbook](phase-6a-oci-deployment.md) và [code validation evidence](phase-6a-code-validation-2026-11-06.md).

### Phase 6B - Simulated acceptance (đã hoàn thành 2026-11-06)

- Chạy fresh 40-event batch với producer và processor đồng thời, chia đều bốn domain.
- Delivery/consume đạt 40/40, 0 duplicate event ID, 0 duplicate Kafka coordinate, consumer lag 0.
- P95 event-to-Silver query upper bound đạt 9.268 giây; sau Gold refresh 16.539 giây; sau governed CSV export 20.593 giây, đều dưới mục tiêu 60 giây.
- Gold reconcile 30/30 events trên từng domain, amounts khớp và Customer 360 có 97/97 keys duy nhất.
- Automated tests đạt 33/33 và PBIP source validation tiếp tục pass.

Project được nghiệm thu **trong phạm vi bài test mô phỏng local**. OCI vẫn là deployment blueprint chưa apply; event-to-visual live chưa đo vì Desktop refresh thủ công. Xem [final acceptance report](final-acceptance-report-2026-11-06.md).

