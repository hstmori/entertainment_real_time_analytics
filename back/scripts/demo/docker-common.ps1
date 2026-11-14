# Tìm docker.exe và bảo đảm Docker engine đang chạy (tự mở Docker Desktop nếu cần).

function Initialize-Docker {
    # docker info ghi stderr khi engine tắt; không để PowerShell 5.1 coi đó là lỗi dừng script.
    $ErrorActionPreference = 'Continue'
    $candidates = @(
        (Get-Command docker -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'),
        'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $docker = $candidates | Select-Object -First 1
    if (-not $docker) {
        throw 'Chưa cài Docker Desktop. Tải tại https://www.docker.com/products/docker-desktop/ rồi chạy lại.'
    }
    $env:PATH = "$(Split-Path -Parent $docker);$env:PATH"
    # Tên Compose riêng cho bản demo để không đụng Docker volumes của bản phát triển.
    if (-not $env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME = 'rtdp-demo' }

    & $docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        $desktop = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
            'C:\Program Files\Docker\Docker\Docker Desktop.exe'
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $desktop) { throw 'Docker engine chưa chạy. Hãy mở Docker Desktop rồi chạy lại.' }
        Write-Host 'Đang khởi động Docker Desktop...' -ForegroundColor Cyan
        Start-Process -FilePath $desktop
        $deadline = (Get-Date).AddMinutes(4)
        do {
            Start-Sleep -Seconds 3
            & $docker info *> $null
        } while ($LASTEXITCODE -ne 0 -and (Get-Date) -lt $deadline)
        if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop chưa sẵn sàng sau 4 phút. Mở Docker Desktop thủ công rồi chạy lại.' }
    }
    return $docker
}
