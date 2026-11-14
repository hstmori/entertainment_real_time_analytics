# Mở dashboard Power BI từ bất kỳ thư mục nào: trỏ DataRoot về CSV đi kèm rồi mở file .pbip.
[CmdletBinding()]
param(
    # Chỉ cập nhật đường dẫn dữ liệu, không mở Power BI (dùng khi kiểm thử).
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
$backRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$repoRoot = (Resolve-Path (Join-Path $backRoot '..')).Path
$dataRoot = Join-Path $backRoot 'artifacts\powerbi_demo'
$pbip = Join-Path $repoRoot 'dashboard\EntertainmentAnalytics.pbip'
$tmdl = Join-Path $repoRoot 'dashboard\EntertainmentAnalytics.SemanticModel\definition\expressions.tmdl'
$modelBim = Join-Path $repoRoot 'dashboard\model.bim'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$csvCount = @(Get-ChildItem -LiteralPath $dataRoot -Filter '*.csv' -ErrorAction SilentlyContinue).Count
if ($csvCount -ne 16) {
    throw "Không tìm thấy đủ 16 file CSV trong $dataRoot (đang có $csvCount). Hãy giải nén lại toàn bộ gói."
}

# 1. Cập nhật DataRoot trong TMDL (Power BI đọc file này).
$tmdlText = [IO.File]::ReadAllText($tmdl, $utf8)
$pattern = 'expression DataRoot = "([^"]*)"'
$match = [regex]::Match($tmdlText, $pattern)
if (-not $match.Success) { throw "Không tìm thấy DataRoot trong $tmdl" }
$oldRoot = $match.Groups[1].Value
if ($oldRoot -ne $dataRoot) {
    $tmdlText = $tmdlText.Remove($match.Groups[1].Index, $match.Groups[1].Length).Insert($match.Groups[1].Index, $dataRoot)
    [IO.File]::WriteAllText($tmdl, $tmdlText, $utf8)

    # 2. Đồng bộ model.bim (bản dùng cho validator), đường dẫn ở dạng JSON-escaped.
    $bimText = [IO.File]::ReadAllText($modelBim, $utf8)
    $bimText = $bimText.Replace(($oldRoot -replace '\\', '\\'), ($dataRoot -replace '\\', '\\'))
    [IO.File]::WriteAllText($modelBim, $bimText, $utf8)
}
Write-Host "Dữ liệu dashboard: $dataRoot" -ForegroundColor Green

if ($NoLaunch) { return }

try {
    Start-Process -FilePath $pbip
    Write-Host 'Đang mở Power BI Desktop... (lần đầu có thể mất 30-60 giây)' -ForegroundColor Green
    Write-Host 'Nếu dashboard chưa có số liệu, bấm Home > Refresh.'
} catch {
    Write-Host ''
    Write-Host 'Máy chưa cài Power BI Desktop (miễn phí, chỉ chạy trên Windows).' -ForegroundColor Yellow
    Write-Host 'Cài từ Microsoft Store rồi chạy lại file này:'
    Write-Host '  https://apps.microsoft.com/detail/9ntxr16hnw1t'
    $preview = Join-Path $repoRoot 'dashboard\images'
    if (Test-Path -LiteralPath $preview) {
        Write-Host 'Trong lúc chờ, có thể xem ảnh chụp dashboard trong thư mục dashboard_preview.'
        Start-Process -FilePath $preview
    }
}
