# COT TFF FX — bootstrap Windows (compat).
# Preferido: run_cot_windows.ps1 (venv bajo cot_system/.venv + Python 3.12/3.11/3.10).
# Este script reenvía allí para no mantener dos flujos distintos.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
#   .\bootstrap.ps1 -PythonExe "C:\Path\to\python.exe"
#   .\bootstrap.ps1 -SkipLaunch

param(
    [string]$PythonExe = "",
    [switch]$SkipLaunch,
    [switch]$RecreateVenv,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PipelineArgs
)

$ErrorActionPreference = "Stop"
$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $LauncherDir "run_cot_windows.ps1"

if (-not (Test-Path -LiteralPath $Target)) {
    throw "No existe run_cot_windows.ps1: $Target"
}

Write-Host "bootstrap.ps1 → run_cot_windows.ps1 (venv + prefer 3.12)" -ForegroundColor Cyan

$fwd = @()
if ($PythonExe) { $fwd += @("-PythonExe", $PythonExe) }
if ($SkipLaunch) { $fwd += "-SkipLaunch" }
if ($RecreateVenv) { $fwd += "-RecreateVenv" }
if ($PipelineArgs) { $fwd += $PipelineArgs }

& powershell -NoProfile -ExecutionPolicy Bypass -File $Target @fwd
exit $LASTEXITCODE
