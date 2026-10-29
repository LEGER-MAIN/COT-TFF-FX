# cot_system

Código del pipeline. Punto de entrada del usuario: **[`../EJECUTAR_COT.bat`](../EJECUTAR_COT.bat)** y **[`../README.md`](../README.md)**.

```bash
python3 main.py
python3 main.py --as-of 2025-06-17
python3 report_server.py
python3 -m pytest tests -q
```

Salidas HTML/JSON → `../docs/reports/`. Universo: ver `config/markets.json` (sin MXN/ZAR/CNH).
