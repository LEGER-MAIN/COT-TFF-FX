@echo off
REM COT TFF FX - unico punto de entrada Windows
REM Flujo: venv Python 3.12 - pip pins - main.py - http://127.0.0.1:8765/
REM NO abras el HTML a doble clic (file://). Usa este BAT.
REM
REM Uso:
REM   EJECUTAR_COT.bat
REM   EJECUTAR_COT.bat --serve
REM   EJECUTAR_COT.bat --test
REM   EJECUTAR_COT.bat --as-of 2025-06-17

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "COT=%~dp0cot_system"
set "PS1=%COT%\launcher\run_cot_windows.ps1"
set "VENV_PY=%COT%\.venv\Scripts\python.exe"
set "EXITCODE=0"

if not exist "%COT%\main.py" (
  echo ERROR: no se encuentra cot_system\main.py
  echo   Esperado en: %COT%
  pause
  exit /b 1
)

echo %*| findstr /I /C:"--test" >nul
if !errorlevel! EQU 0 (
  echo COT TFF FX - tests
  if not exist "%PS1%" (
    echo ERROR: falta %PS1%
    pause
    exit /b 1
  )
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -SkipLaunch
  if !errorlevel! NEQ 0 (
    echo Fallo al preparar venv/deps.
    pause
    exit /b 1
  )
  if not exist "%VENV_PY%" (
    echo ERROR: no hay venv en %COT%\.venv
    pause
    exit /b 1
  )
  echo [pytest] cot_system\tests
  pushd "%COT%"
  "%VENV_PY%" -m pytest tests -q
  set EXITCODE=!errorlevel!
  popd
  if !EXITCODE! NEQ 0 pause
  exit /b !EXITCODE!
)

if not exist "%PS1%" (
  echo ERROR: no se encuentra launcher\run_cot_windows.ps1
  echo   %PS1%
  pause
  exit /b 1
)

echo COT TFF FX - lanzando...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set EXITCODE=!errorlevel!
if !EXITCODE! NEQ 0 (
  echo.
  echo Fallo con codigo !EXITCODE!.
  echo Si ves Application Control / DLL load failed:
  echo   1^) Instala Python 3.12  https://www.python.org/downloads/
  echo   2^) Vuelve a ejecutar este .bat
  echo   3^) O: EJECUTAR_COT.bat --from-csv-only
  echo.
  echo HTML siempre via http://127.0.0.1:8765/  - no file://
  echo.
  pause
)
exit /b !EXITCODE!
