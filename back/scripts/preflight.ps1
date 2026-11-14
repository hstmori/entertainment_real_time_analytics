[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$issues = [System.Collections.Generic.List[string]]::new()

Write-Host 'Checking local prerequisites...'

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerPath = if ($dockerCommand) {
    $dockerCommand.Source
} else {
    $localDockerPath = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    $standardDockerPath = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $localDockerPath) {
        $localDockerPath
    } elseif (Test-Path -LiteralPath $standardDockerPath) {
        $standardDockerPath
    }
}

if (-not $dockerPath) {
    $issues.Add('Docker CLI was not found. Install/start Docker Desktop with Compose v2.')
} else {
    try {
        $clientVersion = & $dockerPath version --format '{{.Client.Version}}' 2>$null
        $serverVersion = & $dockerPath version --format '{{.Server.Version}}' 2>$null
        Write-Host "Docker client: $clientVersion"
        Write-Host "Docker server: $serverVersion"
    } catch {
        $issues.Add('Docker CLI exists, but the Docker engine is not reachable.')
    }

    try {
        $composeVersion = & $dockerPath compose version --short 2>$null
        Write-Host "Docker Compose: $composeVersion"
    } catch {
        $issues.Add('Docker Compose v2 is unavailable.')
    }
}

if (-not (Test-Path -LiteralPath '.env')) {
    Write-Warning 'No .env file found. Copy .env.example to .env before starting the stack.'
}

$ports = 29092, 9000, 9001, 8181, 8080
foreach ($port in $ports) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Warning "Port $port is already in use. Override it in .env if it is not this project."
    }
}

if ($issues.Count -gt 0) {
    foreach ($issue in $issues) {
        Write-Error $issue
    }
    exit 1
}

Write-Host 'Preflight passed.' -ForegroundColor Green

