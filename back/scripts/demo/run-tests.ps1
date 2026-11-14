# Chạy toàn bộ automated tests trong container Python 3.12; không cần cài Python trên máy.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'docker-common.ps1')
$docker = Initialize-Docker

Write-Host 'Chạy automated tests trong container python:3.12-slim...' -ForegroundColor Cyan
# Mount chỉ đọc rồi copy vào container để test không ghi file vào thư mục dự án.
$script = 'mkdir /app && cd /src && tar --exclude=./.venv --exclude="*/__pycache__" -cf - . | tar -xf - -C /app && cd /app && ' +
          'pip install -q --root-user-action=ignore --disable-pip-version-check ".[dev]" && python -m pytest'
& $docker run --rm -v "${root}:/src:ro" python:3.12-slim sh -c $script
exit $LASTEXITCODE
