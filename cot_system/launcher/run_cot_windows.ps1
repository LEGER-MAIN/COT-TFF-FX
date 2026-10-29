# COT TFF FX - Windows launcher (venv + Python 3.12/3.11/3.10)
# Prefers py -3.12 -> 3.11 -> 3.10 (avoids 3.15 + App Control blocking pandas DLLs).
# Creates cot_system/.venv, installs requirements, runs main.py, then serves HTML
# at http://127.0.0.1:8765/ (never open file:// — Aplicar needs HTTP).
# If App Control blocks pandas, falls back to: python main.py --from-csv-only
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\run_cot_windows.ps1
#   .\run_cot_windows.ps1 -SkipLaunch
#   .\run_cot_windows.ps1 -PythonExe "C:\Path\to\python.exe"
#   .\run_cot_windows.ps1 --as-of 2025-06-17
#   .\run_cot_windows.ps1 --serve
#   (from EJECUTAR_COT.bat — args forward to main.py / report_server)

param(
    [string]$PythonExe = "",
    [switch]$SkipLaunch,
    [switch]$RecreateVenv,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PipelineArgs
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CotRoot = Split-Path -Parent $LauncherDir
$ProjectRoot = Split-Path -Parent $CotRoot
$Requirements = Join-Path $CotRoot "requirements.txt"
$MainPy = Join-Path $CotRoot "main.py"
$VenvDir = Join-Path $CotRoot ".venv"
$ReportHtml = Join-Path $ProjectRoot "docs\reports\cot_tff_fx_latest.html"

function Resolve-ReportHtmlFromArgs([string[]]$ArgsList) {
    # If --as-of YYYY-MM-DD was passed, open the dated backtest HTML instead of latest.
    if (-not $ArgsList) { return $ReportHtml }
    for ($i = 0; $i -lt $ArgsList.Count; $i++) {
        $a = [string]$ArgsList[$i]
        if ($a -eq "--as-of" -and ($i + 1) -lt $ArgsList.Count) {
            $d = ([string]$ArgsList[$i + 1]).Trim().Substring(0, [Math]::Min(10, ([string]$ArgsList[$i + 1]).Trim().Length))
            $bt = Join-Path $ProjectRoot ("docs\reports\cot_tff_fx_backtest_{0}.html" -f $d)
            return $bt
        }
        if ($a.StartsWith("--as-of=")) {
            $d = $a.Substring(8).Trim().Substring(0, [Math]::Min(10, $a.Substring(8).Trim().Length))
            $bt = Join-Path $ProjectRoot ("docs\reports\cot_tff_fx_backtest_{0}.html" -f $d)
            return $bt
        }
    }
    return $ReportHtml
}

function Write-Banner {
    Write-Host ""
    Write-Host "=== COT TFF FX - Windows (venv) ===" -ForegroundColor Cyan
    Write-Host "cot_system : $CotRoot"
    Write-Host "venv       : $VenvDir"
    Write-Host ""
}

function Show-AppControlHelp([string]$Detail) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " BLOQUEO Application Control / WDAC (pandas DLL)" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Smart App Control bloquea DLLs nativas de pandas/numpy." -ForegroundColor Yellow
    Write-Host "Esto ocurre tambien con Python 3.12 + venv y con Miniconda." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Que hacer:" -ForegroundColor Cyan
    Write-Host "  1) Desactivar Smart App Control:"
    Write-Host "     Configuracion > Privacidad y seguridad > Seguridad de Windows >"
    Write-Host "     Control de aplicaciones y navegador > Smart App Control > Desactivado"
    Write-Host "     Reinicia el PC y vuelve a ejecutar EJECUTAR_COT.bat"
    Write-Host "  2) Mientras tanto, regenerar informes sin pandas (CSV ya procesados):"
    Write-Host "       py -3.12 `"$CotRoot\main.py`" --from-csv-only"
    Write-Host ""
    if ($Detail) {
        Write-Host "Detalle tecnico:" -ForegroundColor DarkGray
        Write-Host $Detail -ForegroundColor DarkGray
    }
    Write-Host ""
}

function Test-IsAppControlError([string]$Text) {
    if (-not $Text) { return $false }
    $t = $Text.ToLowerInvariant()
    return (
        $t -match "application control" -or
        $t -match "dll load failed" -or
        $t -match "wdac" -or
        $t -match "applocker" -or
        $t -match "blocked this file" -or
        $t -match "bloqueado"
    )
}

function Get-PythonVersionTuple([string]$Exe) {
    try {
        $raw = & $Exe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
        $parts = $raw.Trim().Split(".")
        return ,@(
            [int]$parts[0],
            [int]$parts[1],
            [int]$parts[2]
        )
    } catch {
        return $null
    }
}

function Test-PythonCandidate([string]$Exe) {
    if (-not $Exe) { return $false }
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    $ver = Get-PythonVersionTuple $Exe
    return ($null -ne $ver)
}

function Find-BasePython {
    if ($PythonExe) {
        if (Test-PythonCandidate $PythonExe) {
            return (Resolve-Path -LiteralPath $PythonExe).Path
        }
        throw "PythonExe no es usable: $PythonExe"
    }
    if ($env:COT_PYTHON -and (Test-PythonCandidate $env:COT_PYTHON)) {
        return (Resolve-Path -LiteralPath $env:COT_PYTHON).Path
    }

    $ordered = New-Object System.Collections.Generic.List[string]

    foreach ($arg in @("-3.12", "-3.11", "-3.10")) {
        try {
            $out = & py $arg -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { $ordered.Add($out.Trim()) | Out-Null }
        } catch { }
    }

    $local = $env:LOCALAPPDATA
    if ($local) {
        foreach ($rel in @(
            "Programs\Python\Python312\python.exe",
            "Programs\Python\Python311\python.exe",
            "Programs\Python\Python310\python.exe",
            "Python\pythoncore-3.12-64\python.exe",
            "Python\pythoncore-3.11-64\python.exe",
            "Python\pythoncore-3.10-64\python.exe"
        )) {
            $ordered.Add((Join-Path $local $rel)) | Out-Null
        }
    }

    foreach ($arg in @("-3.13", "-3.14", "-3.15", "-3")) {
        try {
            $out = & py $arg -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { $ordered.Add($out.Trim()) | Out-Null }
        } catch { }
    }
    if ($local) {
        foreach ($rel in @(
            "Python\pythoncore-3.15-64\python.exe",
            "Python\pythoncore-3.14-64\python.exe",
            "Python\pythoncore-3.13-64\python.exe",
            "Programs\Python\Python315\python.exe",
            "Programs\Python\Python314\python.exe",
            "Programs\Python\Python313\python.exe"
        )) {
            $ordered.Add((Join-Path $local $rel)) | Out-Null
        }
    }
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { $ordered.Add($cmd.Source) | Out-Null }
    }

    $seen = @{}
    foreach ($c in $ordered) {
        if (-not $c) { continue }
        $key = $c.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        if (Test-PythonCandidate $c) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }

    throw @"
No se encuentra un Python usable (se busco 3.12 / 3.11 / 3.10 primero).

Instala Python 3.12 desde https://www.python.org/downloads/
marca 'Add python.exe to PATH', o pasa -PythonExe con la ruta completa.
"@
}

function Ensure-Venv([string]$BasePy) {
    $venvPy = Join-Path $VenvDir "Scripts\python.exe"
    if ($RecreateVenv -and (Test-Path -LiteralPath $VenvDir)) {
        Write-Host "RecreateVenv: eliminando $VenvDir" -ForegroundColor Yellow
        Remove-Item -Recurse -Force -LiteralPath $VenvDir
    }
    if (-not (Test-Path -LiteralPath $venvPy)) {
        Write-Host ">>> creando venv con: $BasePy" -ForegroundColor Cyan
        & $BasePy -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            throw "Fallo 'python -m venv'. El interprete tiene el modulo venv?"
        }
    }
    if (-not (Test-Path -LiteralPath $venvPy)) {
        throw "No existe el python del venv: $venvPy"
    }
    return $venvPy
}

function Test-PandasImport([string]$Py) {
    # Temp .py avoids -c quoting / stderr Stop issues on Windows PowerShell 5.1
    $tmp = Join-Path $env:TEMP ("cot_pandas_probe_{0}.py" -f [guid]::NewGuid().ToString("N"))
    @(
        "import sys"
        "try:"
        "    import pandas as pd"
        "    print('OK:' + pd.__file__)"
        "    sys.exit(0)"
        "except Exception as e:"
        "    print('ERR:' + type(e).__name__ + ':' + str(e))"
        "    sys.exit(1)"
    ) | Set-Content -LiteralPath $tmp -Encoding ASCII
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Py $tmp 2>&1 | Out-String
        $exit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    $ok = ($exit -eq 0 -and $out -match "OK:")
    return @{ Ok = $ok; Output = $out.Trim(); ExitCode = $exit }
}

function Install-Requirements([string]$VenvPy) {
    Write-Host ">>> pip upgrade (venv)" -ForegroundColor Cyan
    & $VenvPy -m pip install --upgrade pip setuptools wheel | Out-Null
    Write-Host ">>> pip install -r requirements.txt" -ForegroundColor Cyan
    & $VenvPy -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "pip install fallo (codigo $LASTEXITCODE)."
    }
}

function Start-ReportServer {
    $ServerPy = Join-Path $CotRoot "report_server.py"
    if (-not (Test-Path -LiteralPath $ServerPy)) {
        Write-Host "No existe report_server.py: $ServerPy" -ForegroundColor Yellow
        return $false
    }
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Yellow
    Write-Host "  Abre el informe en:  http://127.0.0.1:8765/" -ForegroundColor Green
    Write-Host "  NO uses file://  (rompe Aplicar). Deja esta ventana abierta." -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Yellow
    Write-Host ""
    try { Start-Process "http://127.0.0.1:8765/" } catch { }
    Push-Location $CotRoot
    try {
        & $VenvPy $ServerPy
        return ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
    }
}

function Invoke-FromCsvOnly([string]$Py) {
    $scored = Join-Path $CotRoot "data\processed\fx_tff_scored.csv"
    if (-not (Test-Path -LiteralPath $scored)) {
        Write-Host "No hay CSV procesado ($scored); no se puede usar --from-csv-only." -ForegroundColor Red
        return 3
    }
    Write-Host ""
    Write-Host ">>> FALLBACK: main.py --from-csv-only (sin pandas; regenera HTML/JSON)" -ForegroundColor Yellow
    Push-Location $CotRoot
    try {
        & $Py $MainPy --from-csv-only
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

# -------------------- main --------------------
Write-Banner

if (-not (Test-Path -LiteralPath $MainPy)) {
    throw "No existe main.py: $MainPy"
}
if (-not (Test-Path -LiteralPath $Requirements)) {
    throw "No existe requirements.txt: $Requirements"
}

# --serve: start report_server.py (week calendar UI) instead of one-shot pipeline
$ServeMode = $false
$ServeArgs = New-Object System.Collections.Generic.List[string]
if ($PipelineArgs) {
    foreach ($a in $PipelineArgs) {
        if ([string]$a -eq "--serve") {
            $ServeMode = $true
            continue
        }
        $ServeArgs.Add([string]$a) | Out-Null
    }
}
if ($ServeMode) {
    $ServerPy = Join-Path $CotRoot "report_server.py"
    if (-not (Test-Path -LiteralPath $ServerPy)) {
        throw "No existe report_server.py: $ServerPy"
    }
    $BasePy = Find-BasePython
    $VenvPy = Ensure-Venv $BasePy
    # Ensure deps so POST /run can execute main.py --as-of
    $probeServe = Test-PandasImport $VenvPy
    if (-not $probeServe.Ok) {
        Write-Host ">>> instalando requirements (para regenerar desde el calendario)" -ForegroundColor Cyan
        Install-Requirements $VenvPy
    }
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  NO abras el HTML a doble clic." -ForegroundColor Yellow
    Write-Host "  file:// rompe el boton Aplicar (Failed to fetch)." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Usa siempre el navegador en:" -ForegroundColor Yellow
    Write-Host "    http://127.0.0.1:8765/" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Se abrira solo. Deja esta ventana abierta (Ctrl+C para parar)." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host ">>> modo --serve: calendario HTML + regenerar backtest" -ForegroundColor Cyan
    Write-Host "    Abriendo http://127.0.0.1:8765/  (Ctrl+C para detener)" -ForegroundColor Green
    # report_server.py also opens the browser after bind; this is a backup kick
    try { Start-Process "http://127.0.0.1:8765/" } catch { }
    Push-Location $CotRoot
    try {
        & $VenvPy $ServerPy @($ServeArgs.ToArray())
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

$BasePy = Find-BasePython
$BaseVer = Get-PythonVersionTuple $BasePy
$BaseVerStr = "{0}.{1}.{2}" -f $BaseVer[0], $BaseVer[1], $BaseVer[2]
Write-Host "Python base: $BasePy ($BaseVerStr)" -ForegroundColor Green

if ($BaseVer[0] -eq 3 -and $BaseVer[1] -ge 13) {
    Write-Host ""
    Write-Host "AVISO: Python $BaseVerStr (>=3.13). En PCs con App Control," -ForegroundColor Yellow
    Write-Host "pandas suele fallar (DLL bloqueada). Preferible 3.12/3.11/3.10." -ForegroundColor Yellow
    Write-Host ""
}

$VenvPy = Ensure-Venv $BasePy
$VenvVer = & $VenvPy -c "import sys; print(sys.version.split()[0])"
Write-Host "venv python: $VenvPy ($VenvVer)" -ForegroundColor Green
Write-Host ""

# Fast path: if pandas already blocked, skip heavy reinstall and use CSV fallback.
$probeEarly = Test-PandasImport $VenvPy
if (-not $probeEarly.Ok -and (Test-IsAppControlError $probeEarly.Output)) {
    Write-Host "App Control bloquea pandas/numpy en este PC (tambien con 3.12 + venv)." -ForegroundColor Yellow
    Write-Host "Detalle: $($probeEarly.Output)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Para pipeline completo (descarga CFTC + indicadores):" -ForegroundColor Cyan
    Write-Host "  Desactiva Smart App Control y reinicia, luego vuelve a ejecutar."
    Write-Host ""

    $litePy = $BasePy
    $code = Invoke-FromCsvOnly $litePy
    if ($code -eq 0) {
        Write-Host ""
        Write-Host "Listo (modo lite / CSV). Arrancando servidor HTML..." -ForegroundColor Green
        Write-Host "NOTA: no se re-descargaron datos CFTC; solo regenero informes." -ForegroundColor DarkYellow
        $VenvPy = $litePy
        Start-ReportServer | Out-Null
        exit 0
    }
    Show-AppControlHelp $probeEarly.Output
    exit 2
}

Install-Requirements $VenvPy

Write-Host ""
Write-Host ">>> verificar pandas en el venv" -ForegroundColor Cyan
$probe = Test-PandasImport $VenvPy
if (-not $probe.Ok) {
    if (Test-IsAppControlError $probe.Output) {
        $code = Invoke-FromCsvOnly $BasePy
        if ($code -eq 0) {
            Write-Host "Listo (modo lite / CSV)." -ForegroundColor Green
            Start-ReportServer | Out-Null
            exit 0
        }
        Show-AppControlHelp $probe.Output
        exit 2
    }
    Write-Host "pandas no importa en el venv:" -ForegroundColor Red
    Write-Host $probe.Output
    Show-AppControlHelp $probe.Output
    exit 1
}
Write-Host $probe.Output -ForegroundColor Green

& $VenvPy -c "import requests; print('deps OK: requests')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Falta requests tras pip." -ForegroundColor Red
    exit 1
}
& $VenvPy -c "import pyarrow" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "(pyarrow opcional: no disponible; el pipeline usara CSV sin Parquet)" -ForegroundColor DarkYellow
}

if ($SkipLaunch) {
    Write-Host "SkipLaunch: venv listo. Ejecuta:" -ForegroundColor Green
    Write-Host ("  {0} {1}" -f $VenvPy, $MainPy)
    exit 0
}

Write-Host ""
Write-Host ">>> ejecutando pipeline (main.py)" -ForegroundColor Cyan
$fwd = @()
if ($PipelineArgs) { $fwd = $PipelineArgs }

Push-Location $CotRoot
try {
    & $VenvPy $MainPy @fwd
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($code -ne 0) {
    Write-Host ""
    Write-Host "Pipeline termino con codigo $code." -ForegroundColor Red
    $probe2 = Test-PandasImport $VenvPy
    if (-not $probe2.Ok -and (Test-IsAppControlError $probe2.Output)) {
        $code = Invoke-FromCsvOnly $BasePy
        if ($code -eq 0) {
            Write-Host "Listo (fallback CSV tras fallo de pandas)." -ForegroundColor Green
            Start-ReportServer | Out-Null
            exit 0
        }
        Show-AppControlHelp $probe2.Output
    }
    exit $code
}

Write-Host ""
Write-Host "Pipeline OK. Arrancando servidor en http://127.0.0.1:8765/" -ForegroundColor Green
Start-ReportServer | Out-Null
exit 0
