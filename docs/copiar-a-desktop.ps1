# Copia limpia COT -> Escritorio (preserva .venv; usa robocopy si Remove-Item falla)
$ErrorActionPreference = 'Stop'
$src = Join-Path $env:LOCALAPPDATA 'Cursor\AgentStores\cursor_agent_stores\bc-b9693e3f-cdd0-4694-9adf-ed726e6273f3\files'
$dest = Join-Path $env:USERPROFILE 'Desktop\COT-TFF-FX'

if (-not (Test-Path $src)) {
  Write-Error "No Agent Store: $src"
  exit 1
}

$hasHtml = Test-Path (Join-Path $src 'docs\reports\cot_tff_fx_latest.html')
$hasServer = Test-Path (Join-Path $src 'cot_system\report_server.py')
Write-Host "Fuente OK. HTML latest: $hasHtml  report_server: $hasServer"

$venvBackup = Join-Path $env:TEMP ('COT-TFF-FX-venv-backup-' + [guid]::NewGuid().ToString('N'))
$venvSrc = Join-Path $dest 'cot_system\.venv'
$hadVenv = $false
if (Test-Path $venvSrc) {
  Write-Host "Preservando .venv existente..."
  New-Item -ItemType Directory -Force -Path $venvBackup | Out-Null
  Move-Item -Force $venvSrc (Join-Path $venvBackup '.venv')
  $hadVenv = $true
}

$removed = $false
if (Test-Path $dest) {
  try {
    Remove-Item -Recurse -Force $dest
    $removed = $true
  } catch {
    Write-Host "Remove-Item bloqueado; sincronizando con robocopy..."
  }
}
if ($removed -or -not (Test-Path $dest)) {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  Copy-Item -Recurse -Force (Join-Path $src 'cot_system') (Join-Path $dest 'cot_system')
  Copy-Item -Recurse -Force (Join-Path $src 'docs') (Join-Path $dest 'docs')
} else {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  & robocopy (Join-Path $src 'cot_system') (Join-Path $dest 'cot_system') /E /XD .venv /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
  & robocopy (Join-Path $src 'docs') (Join-Path $dest 'docs') /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

if ($hadVenv) {
  $restored = Join-Path $dest 'cot_system\.venv'
  if (Test-Path $restored) {
    Remove-Item -Recurse -Force $restored -ErrorAction SilentlyContinue
  }
  Move-Item -Force (Join-Path $venvBackup '.venv') $restored
  Remove-Item -Recurse -Force $venvBackup -ErrorAction SilentlyContinue
  Write-Host ".venv restaurado."
}

$batSrc = Join-Path $src 'EJECUTAR_COT.bat'
if (-not (Test-Path $batSrc)) {
  $batSrc = Join-Path $src 'cot_system\EJECUTAR_COT.bat'
}
if (Test-Path $batSrc) {
  Copy-Item -Force $batSrc (Join-Path $dest 'EJECUTAR_COT.bat')
}

$abrirSrc = Join-Path $src 'ABRIR_CALENDARIO.bat'
$abrirDest = Join-Path $dest 'ABRIR_CALENDARIO.bat'
if (Test-Path $abrirSrc) {
  Copy-Item -Force $abrirSrc $abrirDest
} else {
  @(
    '@echo off'
    'cd /d "%~dp0"'
    'call "%~dp0EJECUTAR_COT.bat" --serve'
    'exit /b %ERRORLEVEL%'
  ) | Set-Content -Encoding ASCII $abrirDest
}

$html = Join-Path $dest 'docs\reports\cot_tff_fx_latest.html'
$picker = $false
if (Test-Path $html) {
  $picker = [bool](Select-String -Path $html -Pattern 'week-picker' -Quiet -ErrorAction SilentlyContinue)
}

Write-Host "Listo: $dest"
Write-Host "Calendario en HTML: $picker"
Write-Host ''
Write-Host 'IMPORTANTE: no abras el HTML a doble clic (file:// rompe Aplicar).'
Write-Host 'Siguiente:'
Write-Host ("  Doble clic:  {0}\ABRIR_CALENDARIO.bat" -f $dest)
Write-Host ("  O:           {0}\EJECUTAR_COT.bat --serve" -f $dest)
Write-Host '  Navegador:   http://127.0.0.1:8765/'
