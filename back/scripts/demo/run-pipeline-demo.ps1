# Chạy pipeline end-to-end bằng Docker: Kafka -> processor -> Iceberg Bronze/Silver/Gold -> Trino -> CSV Power BI.
[CmdletBinding()]
param(
    [ValidateRange(4, 400)]
    [int]$EventCount = 40
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'docker-common.ps1')
$docker = Initialize-Docker

Write-Host "Chạy pipeline với $EventCount sự kiện. Lần đầu cần tải image Docker (khoảng 5-10 phút)..." -ForegroundColor Cyan
& (Join-Path $root 'scripts\run-phase6b-acceptance.ps1') -EventCount $EventCount | Out-Null
$acceptanceExit = $LASTEXITCODE

$latest = Get-ChildItem -LiteralPath (Join-Path $root 'artifacts\acceptance') -Directory |
    Sort-Object Name | Select-Object -Last 1
$summary = Get-Content -LiteralPath (Join-Path $latest.FullName 'acceptance-summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Host ''
Write-Host '================ KẾT QUẢ PIPELINE ================' -ForegroundColor Cyan
Write-Host ("Trạng thái              : {0}" -f $summary.status.ToUpper())
Write-Host ("Sự kiện gửi vào Kafka   : {0}/{1}" -f $summary.producer.delivered, $summary.event_count)
Write-Host ("Hợp lệ / lỗi (DLQ)      : {0} / {1}" -f $summary.processor.valid, $summary.processor.invalid)
Write-Host ("Trùng event_id ở Silver : {0}" -f $summary.silver_latency.duplicate_event_ids)
Write-Host ("Độ trễ xử lý P95        : {0} ms" -f $summary.silver_latency.processing_latency_ms.p95)
Write-Host ("Event -> Silver P95     : {0} ms (SLA 60.000 ms)" -f $summary.silver_latency.query_upper_bound_latency_ms.p95)
Write-Host ("Bảng Gold đã làm mới    : {0}" -f @($summary.gold_refresh.row_counts.PSObject.Properties).Count)
Write-Host ("Chi tiết                : {0}" -f $latest.FullName)
Write-Host ''
Write-Host 'Stack vẫn đang chạy để bạn khám phá:'
Write-Host '  Trino UI       http://localhost:8080   (user bất kỳ)'
Write-Host '  RustFS console http://localhost:9001   (lakehouse_admin / change-this-local-password)'
Write-Host 'Chạy 4_Stop_Pipeline.bat để tắt và dọn dữ liệu demo.'

if ($acceptanceExit -ne 0 -or $summary.status -ne 'passed') { exit 1 }
