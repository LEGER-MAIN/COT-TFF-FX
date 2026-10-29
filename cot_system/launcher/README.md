# Launcher (interno)

El usuario debe usar **[`../../EJECUTAR_COT.bat`](../../EJECUTAR_COT.bat)** en la raíz del proyecto.

Este directorio contiene la implementación Windows (`run_cot_windows.ps1`) que el BAT invoca: venv 3.12, pins pandas/numpy, pipeline y servidor `http://127.0.0.1:8765/`.

`run_cot.bat` aquí es un redirect al BAT raíz. Wrappers Unix: `run_cot.sh` / `run_cot.command`.

Si App Control bloquea DLLs: ver `PATCH-windows-python315.md` o `EJECUTAR_COT.bat --from-csv-only`.
