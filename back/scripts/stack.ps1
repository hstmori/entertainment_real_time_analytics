[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('up', 'down', 'status', 'logs', 'validate', 'exec', 'build', 'run')]
    [string]$Action,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = 'Stop'

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerPath = if ($dockerCommand) {
    $dockerCommand.Source
} else {
    $localDockerPath = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    $userDockerPath = Join-Path $env:USERPROFILE 'AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
    $standardDockerPath = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $localDockerPath) {
        $localDockerPath
    } elseif (Test-Path -LiteralPath $userDockerPath) {
        $userDockerPath
    } elseif (Test-Path -LiteralPath $standardDockerPath) {
        $standardDockerPath
    }
}

if (-not $dockerPath) {
    throw 'Docker CLI was not found. Install Docker Desktop or add docker.exe to PATH.'
}

$dockerBin = Split-Path -Parent $dockerPath
$env:PATH = "$dockerBin;$env:PATH"

switch ($Action) {
    'up' {
        & $dockerPath compose up -d
    }
    'down' {
        & $dockerPath compose down
    }
    'status' {
        & $dockerPath compose ps -a
    }
    'logs' {
        & $dockerPath compose logs --no-color --tail 100 @RemainingArgs
    }
    'validate' {
        & $dockerPath compose config --quiet
    }
    'exec' {
        if (-not $RemainingArgs -or $RemainingArgs.Count -lt 2) {
            throw 'Usage: ./scripts/stack.ps1 exec <service> <command> [arguments]'
        }
        & $dockerPath compose exec -T @RemainingArgs
    }
    'build' {
        if (-not $RemainingArgs) {
            throw 'Usage: ./scripts/stack.ps1 build <service>'
        }
        & $dockerPath compose build @RemainingArgs
    }
    'run' {
        if (-not $RemainingArgs) {
            throw 'Usage: ./scripts/stack.ps1 run <service> [arguments]'
        }
        & $dockerPath compose run --rm @RemainingArgs
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose action '$Action' failed with exit code $LASTEXITCODE."
}

