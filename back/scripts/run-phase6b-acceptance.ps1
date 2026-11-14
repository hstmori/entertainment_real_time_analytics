[CmdletBinding()]
param(
    [ValidateRange(4, 400)]
    [int]$EventCount = 40,

    [ValidateRange(1, 100)]
    [double]$RatePerSecond = 10,

    [ValidateRange(1, 600)]
    [double]$SlaSeconds = 60
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dockerPath = Join-Path $env:USERPROFILE "AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
if (-not (Test-Path -LiteralPath $dockerPath)) {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCommand) { throw "Docker CLI was not found." }
    $dockerPath = $dockerCommand.Source
}
$dockerBin = Split-Path -Parent $dockerPath
$env:PATH = "$dockerBin;$env:PATH"

function Invoke-DockerCapture {
    param([string[]]$Arguments)
    # Windows PowerShell 5.1 treats docker's stderr progress lines as terminating errors under 'Stop';
    # rely on the exit code instead.
    $ErrorActionPreference = "Continue"
    $output = @(& $dockerPath @Arguments 2>&1 | ForEach-Object { "$_" })
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')`n$($output -join [Environment]::NewLine)"
    }
    return $output
}

function Get-JsonLine {
    param([object[]]$Output)
    $line = $Output | Where-Object { "$_".TrimStart().StartsWith("{") } | Select-Object -Last 1
    if (-not $line) { throw "Command did not return a JSON result." }
    return ("$line" | ConvertFrom-Json)
}

function Save-Json {
    param([object]$Value, [string]$Path)
    $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding utf8
}

Push-Location $repoRoot
$processorContainer = $null
try {
    & (Join-Path $repoRoot "scripts\stack.ps1") up
    & (Join-Path $repoRoot "scripts\stack.ps1") build event-producer stream-processor gold-builder powerbi-exporter event-producer-test

    # On a fresh machine Trino needs a while after `up`; wait for topics and a working query first.
    $ErrorActionPreference = "Continue"
    & $dockerPath compose wait kafka-init object-store-init *> $null
    $trinoDeadline = (Get-Date).AddMinutes(4)
    do {
        & $dockerPath compose exec -T trino trino --execute "SELECT 1" *> $null
        $trinoReady = $LASTEXITCODE -eq 0
        if (-not $trinoReady) { Start-Sleep -Seconds 3 }
    } while (-not $trinoReady -and (Get-Date) -lt $trinoDeadline)
    $ErrorActionPreference = "Stop"
    if (-not $trinoReady) { throw "Trino was not ready within 4 minutes." }

    $runStamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $seed = [int]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() % [int]::MaxValue)
    $correlationId = [guid]::NewGuid().ToString()
    $consumerGroup = "entertainment-phase6b-$runStamp"
    $processorContainer = "entertainment-phase6b-processor-$runStamp".ToLowerInvariant()
    $artifactDir = Join-Path $repoRoot "artifacts\acceptance\$runStamp"
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

    $processorId = Invoke-DockerCapture @(
        "compose", "run", "--no-deps", "-d", "--name", $processorContainer,
        "-e", "KAFKA_CONSUMER_GROUP=$consumerGroup",
        "-e", "KAFKA_AUTO_OFFSET_RESET=latest",
        "stream-processor",
        "--batch-size", "10",
        "--flush-interval", "1",
        "--poll-timeout", "0.2",
        "--max-messages", "$EventCount",
        "--idle-exit-seconds", "30"
    )
    Start-Sleep -Seconds 5
    $baseTime = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")

    $producerOutput = Invoke-DockerCapture @(
        "compose", "run", "--no-deps", "--rm", "event-producer",
        "--count", "$EventCount",
        "--rate", "$RatePerSecond",
        "--seed", "$seed",
        "--base-time", $baseTime,
        "--correlation-id", $correlationId,
        "--sample-limit", "0"
    )
    $producer = Get-JsonLine $producerOutput

    $processorExit = (Invoke-DockerCapture @("wait", $processorContainer) | Select-Object -Last 1).Trim()
    $processorLogs = Invoke-DockerCapture @("logs", $processorContainer)
    if ($processorExit -ne "0") {
        throw "Stream processor exited with code $processorExit.`n$($processorLogs -join [Environment]::NewLine)"
    }
    $processor = Get-JsonLine $processorLogs

    $probeBase = @(
        "compose", "run", "--no-deps", "--rm", "--entrypoint", "python",
        "gold-builder", "-m", "entertainment_pipeline.acceptance_probe",
        "--correlation-id", $correlationId,
        "--expected-count", "$EventCount",
        "--sla-seconds", "$SlaSeconds"
    )
    $silverProbe = Get-JsonLine (Invoke-DockerCapture $probeBase)
    Save-Json $silverProbe (Join-Path $artifactDir "silver-latency.json")

    $goldOutput = Invoke-DockerCapture @(
        "compose", "run", "--no-deps", "--rm", "gold-builder",
        "--sql-dir", "/app/sql/gold"
    )
    $gold = Get-JsonLine $goldOutput
    Save-Json $gold (Join-Path $artifactDir "gold-refresh.json")

    $goldProbe = Get-JsonLine (Invoke-DockerCapture $probeBase)
    Save-Json $goldProbe (Join-Path $artifactDir "gold-query-upper-bound.json")

    $exportOutput = Invoke-DockerCapture @(
        "compose", "run", "--no-deps", "--rm", "powerbi-exporter"
    )
    $export = Get-JsonLine $exportOutput
    Save-Json $export (Join-Path $artifactDir "powerbi-export.json")

    $exportProbe = Get-JsonLine (Invoke-DockerCapture $probeBase)
    Save-Json $exportProbe (Join-Path $artifactDir "export-upper-bound.json")

    $testOutput = Invoke-DockerCapture @(
        "compose", "run", "--no-deps", "--rm", "event-producer-test", "-q"
    )

    $summary = [ordered]@{
        status = if ($silverProbe.status -eq "passed") { "passed" } else { "failed" }
        run_stamp = $runStamp
        correlation_id = $correlationId
        consumer_group = $consumerGroup
        event_count = $EventCount
        rate_per_second = $RatePerSecond
        seed = $seed
        base_time = $baseTime
        producer = $producer
        processor = $processor
        silver_latency = $silverProbe
        gold_refresh = $gold
        gold_query_upper_bound = $goldProbe
        powerbi_export = $export
        export_upper_bound = $exportProbe
        automated_test_output = @($testOutput)
    }
    Save-Json $summary (Join-Path $artifactDir "acceptance-summary.json")
    $summary | ConvertTo-Json -Depth 12

    if ($summary.status -ne "passed") { exit 1 }
}
finally {
    if ($processorContainer) {
        $ErrorActionPreference = "Continue"
        & $dockerPath rm -f $processorContainer 2>$null | Out-Null
    }
    Pop-Location
}
