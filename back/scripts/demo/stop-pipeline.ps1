# Tắt stack demo và xóa dữ liệu demo (Docker volumes của project này).
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'docker-common.ps1')
$docker = Initialize-Docker

Push-Location $root
try {
    & $docker compose down -v --remove-orphans
    Write-Host 'Đã tắt pipeline và xóa dữ liệu demo.' -ForegroundColor Green
} finally {
    Pop-Location
}
