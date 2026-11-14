[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$backRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $backRoot

$requiredFiles = @(
    '../README.md',
    '.dockerignore',
    'Dockerfile',
    'docker-compose.yml',
    '.env.example',
    'pyproject.toml',
    'docs/requirements.md',
    'docs/architecture.md',
    'docs/roadmap.md',
    'docs/phase-2-smoke-test-2026-11-06.md',
    'docs/phase-3-smoke-test-2026-11-06.md',
    'docs/phase-3-runbook.md',
    'docs/phase-4-smoke-test-2026-11-06.md',
    'docs/phase-5-code-validation-2026-11-06.md',
    'docs/power-bi.md',
    'docs/customer-360-dashboard.md',
    'docs/customer-360-validation-2026-11-07.md',
    'docs/gold-metric-definitions.md',
    'docs/gold-data-dictionary.md',
    'config/trino/catalog/iceberg.properties',
    'sql/bootstrap/001_create_namespaces.sql',
    'scripts/stack.ps1',
    'src/entertainment_pipeline/contracts.py',
    'src/entertainment_pipeline/generator.py',
    'src/entertainment_pipeline/producer.py',
    'src/entertainment_pipeline/stream_processor.py',
    'src/entertainment_pipeline/lakehouse.py',
    'src/entertainment_pipeline/dead_letter.py',
    'src/entertainment_pipeline/gold_builder.py',
    'src/entertainment_pipeline/powerbi_export.py',
    'scripts/build_pbip.py',
    'scripts/build_customer_dashboard_data.py',
    'scripts/build_portfolio_demo_data.py',
    'scripts/validate_pbip.py',
    'tests/test_generator.py',
    'tests/test_producer_cli.py',
    'tests/test_stream_processor.py',
    'tests/test_lakehouse.py',
    'tests/test_gold_builder.py',
    'tests/test_powerbi_export.py',
    'tests/test_portfolio_demo_data.py',
    'sql/quality/phase3_checks.sql',
    'sql/quality/phase4_reconciliation.sql',
    'sql/gold/01_content_engagement_hourly.sql',
    'sql/gold/02_booking_funnel_daily.sql',
    'sql/gold/03_event_performance.sql',
    'sql/gold/04_subscription_daily.sql',
    'sql/gold/05_customer_360.sql',
    'sql/gold/06_customer_journey.sql',
    '../dashboard/EntertainmentAnalytics.pbip',
    '../dashboard/EntertainmentAnalytics.Report/definition.pbir',
    '../dashboard/EntertainmentAnalytics.SemanticModel/definition.pbism',
    '../dashboard/EntertainmentAnalytics.SemanticModel/definition/database.tmdl'
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Required file is missing: $file"
    }
}
Write-Host "Required files: $($requiredFiles.Count) OK"

$schemaFiles = Get-ChildItem -LiteralPath 'contracts/jsonschema' -Filter '*.schema.json' -File
if ($schemaFiles.Count -ne 5) {
    throw "Expected 5 JSON Schema files; found $($schemaFiles.Count)."
}

foreach ($schemaFile in $schemaFiles) {
    $schema = Get-Content -Raw -Encoding UTF8 -LiteralPath $schemaFile.FullName | ConvertFrom-Json
    if ($schema.'$schema' -ne 'https://json-schema.org/draft/2020-12/schema') {
        throw "Unexpected JSON Schema draft in $($schemaFile.Name)."
    }
    if ($schema.type -ne 'object' -or -not $schema.required) {
        throw "Incomplete object contract in $($schemaFile.Name)."
    }
}
Write-Host "JSON Schemas: $($schemaFiles.Count) syntax/contracts OK"

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

if ($dockerPath) {
    & $dockerPath compose --env-file .env.example config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw 'docker compose config validation failed.'
    }
    Write-Host 'Docker Compose syntax: OK'
} else {
    Write-Warning 'Docker is not installed; skipped docker compose config validation.'
}

Write-Host 'Foundation validation passed.' -ForegroundColor Green

