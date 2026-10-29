# Crea un acceso directo .lnk en el Escritorio de Windows hacia run_cot.bat
$ErrorActionPreference = "Stop"
$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bat = Join-Path $LauncherDir "run_cot.bat"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "COT TFF FX.lnk"

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Bat
$Sc.WorkingDirectory = $LauncherDir
$Sc.WindowStyle = 1
$Sc.Description = "COT TFF FX — ejecutar pipeline y abrir informe"
$Sc.Save()

Write-Host "Acceso directo creado:"
Write-Host "  $ShortcutPath"
Write-Host ""
Write-Host "Puedes anclarlo a la barra de tareas: clic derecho en el .lnk → Anclar a la barra de tareas."
