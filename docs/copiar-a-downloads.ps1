# Copia limpia COT -> Descargas (incluye calendario HTML + report_server)
$src = Join-Path $env:LOCALAPPDATA "Cursor\AgentStores\cursor_agent_stores\bc-b9693e3f-cdd0-4694-9adf-ed726e6273f3\files"
$dest = Join-Path $env:USERPROFILE "Downloads\COT-TFF-FX"
if (-not (Test-Path $src)) { Write-Error "No encuentro Agent Store: $src"; exit 1 }
$hasPicker = Test-Path (Join-Path $src "docs\reports\cot_tff_fx_latest.html")
$hasServer = Test-Path (Join-Path $src "cot_system\report_server.py")
Write-Host "Fuente OK. HTML latest:" $hasPicker " report_server:" $hasServer
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $src "cot_system") (Join-Path $dest "cot_system")
Copy-Item -Recurse -Force (Join-Path $src "docs") (Join-Path $dest "docs")
if (Test-Path (Join-Path $src "EJECUTAR_COT.bat")) {
  Copy-Item -Force (Join-Path $src "EJECUTAR_COT.bat") (Join-Path $dest "EJECUTAR_COT.bat")
} elseif (Test-Path (Join-Path $dest "cot_system\EJECUTAR_COT.bat")) {
  Copy-Item -Force (Join-Path $dest "cot_system\EJECUTAR_COT.bat") (Join-Path $dest "EJECUTAR_COT.bat")
}
$abrirSrc = Join-Path $src "ABRIR_CALENDARIO.bat"
if (Test-Path $abrirSrc) {
  Copy-Item -Force $abrirSrc (Join-Path $dest "ABRIR_CALENDARIO.bat")
} else {
  @"
@echo off
cd /d "%~dp0"
call "%~dp0EJECUTAR_COT.bat" --serve
exit /b %ERRORLEVEL%
"@ | Set-Content -Encoding ASCII (Join-Path $dest "ABRIR_CALENDARIO.bat")
}
$html = Join-Path $dest "docs\reports\cot_tff_fx_latest.html"
$picker = Select-String -Path $html -Pattern "week-picker" -Quiet -ErrorAction SilentlyContinue
Write-Host "Destino: $dest"
Write-Host "Calendario en HTML:" $picker
Write-Host ""
Write-Host "IMPORTANTE — NO abras el HTML a doble clic (file:// rompe Aplicar)."
Write-Host "Siguiente:"
Write-Host "  Doble clic:  $dest\ABRIR_CALENDARIO.bat"
Write-Host "  O:           $dest\EJECUTAR_COT.bat --serve"
Write-Host "  Navegador:   http://127.0.0.1:8765/"
