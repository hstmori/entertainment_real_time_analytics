param(
    [switch]$RequireTerraform
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stackPath = Join-Path $repoRoot "infra\terraform\oci"

$requiredFiles = @(
    "versions.tf",
    "variables.tf",
    "network.tf",
    "storage.tf",
    "kafka.tf",
    "dataflow.tf",
    "autonomous_lakehouse.tf",
    "outputs.tf",
    "terraform.tfvars.example"
)

$missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $stackPath $_)) })
if ($missing.Count -gt 0) {
    throw "Missing OCI IaC files: $($missing -join ', ')"
}

$ignoreFile = Join-Path $stackPath ".gitignore"
$ignoreText = Get-Content -LiteralPath $ignoreFile -Raw
foreach ($requiredPattern in @(".terraform/", "*.tfstate", "*.tfplan", "terraform.tfvars")) {
    if (-not $ignoreText.Contains($requiredPattern)) {
        throw "Terraform .gitignore is missing required pattern: $requiredPattern"
    }
}

$passwordAssignments = @(Get-ChildItem -LiteralPath $stackPath -Filter "*.tf" -File | Select-String -Pattern "admin_password\s*=|sasl_password\s*=")
if ($passwordAssignments.Count -gt 0) {
    throw "Plain password assignment found in Terraform source. Use OCI Vault secret OCIDs instead."
}

$terraform = Get-Command terraform -ErrorAction SilentlyContinue
if (-not $terraform) {
    if ($RequireTerraform) {
        throw "Terraform is required but was not found in PATH."
    }
    Write-Warning "Structural and secret-safety checks passed; Terraform is not installed, so fmt/validate were skipped."
    exit 0
}

& $terraform.Source -chdir=$stackPath fmt -check -recursive
if ($LASTEXITCODE -ne 0) { throw "terraform fmt -check failed." }

& $terraform.Source -chdir=$stackPath init -backend=false -input=false
if ($LASTEXITCODE -ne 0) { throw "terraform init -backend=false failed." }

& $terraform.Source -chdir=$stackPath validate
if ($LASTEXITCODE -ne 0) { throw "terraform validate failed." }

Write-Output "OCI Terraform fmt/validate and secret-safety checks passed."
