@echo off
REM Thin redirect → raiz del proyecto\EJECUTAR_COT.bat
setlocal EnableExtensions
cd /d "%~dp0..\.."
call "%~dp0..\..\EJECUTAR_COT.bat" %*
exit /b %ERRORLEVEL%
