@echo off
REM Thin redirect → EJECUTAR_COT.bat --serve
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0EJECUTAR_COT.bat" --serve
exit /b %ERRORLEVEL%
