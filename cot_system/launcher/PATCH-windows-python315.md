# Patch — Windows: App Control + Python 3.15 (pandas DLL)

## Qué pasaba
Tras alinear pip y el launcher al mismo `python.exe`, Jefferson seguía fallando:

```
ImportError: DLL load failed … Application Control policy has blocked this file
```

Causa: **WDAC / Application Control** bloquea las DLLs nativas de **pandas/numpy** bajo Python 3.15 (`pythoncore-3.15-64`). No es un “falta pip”: el wheel se instala pero el import muere al cargar el binario.

**Python 3.15 + App Control = no soportado** para este pipeline.

## Qué cambió (esta entrega)
| Archivo | Cambio |
|---------|--------|
| `launcher/run_cot_windows.ps1` | **Nuevo:** prefiere `py -3.12/3.11/3.10`, crea `cot_system/.venv`, pip, `main.py`, abre HTML; mensaje claro en español si App Control |
| `launcher/run_cot.bat` | Llama al `.ps1` (doble clic) |
| `launcher/bootstrap.ps1` | Reenvía a `run_cot_windows.ps1` |
| `requirements.txt` | Pines pandas/numpy compatibles con wheels 3.12; pyarrow opcional |
| `main.py --from-csv-only` | Regenera Excel/HTML sin pandas (`csv` + `openpyxl`) |
| `src/report_lite.py` + `src/appcontrol_help.py` | Fallback + texto de arreglo |

## Qué hacer en el PC de Jefferson
1. Re-copiar el store a Downloads (`docs/copiar-a-downloads.ps1`).
2. Instalar **Python 3.12** desde python.org (Add to PATH) si no lo tiene.
3. Doble clic: `Downloads\COT-TFF-FX\cot_system\launcher\run_cot.bat`

No hace falta 3.15. Si solo hay CSV procesados y pandas sigue bloqueado:  
`python main.py --from-csv-only`
