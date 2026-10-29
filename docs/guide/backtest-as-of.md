# Backtest semanal (as-of)

## Para qué sirve

Repetir el **mismo** scoring y la **misma** recomendación semanal de pares swing que el informe en vivo, pero fijando una fecha de corte en el pasado. Sirve para revisar qué habría dicho el sistema en esa semana **sin mirar datos posteriores**.

## Calendario en el HTML (recomendado en Windows)

El informe HTML incluye un **calendario semanal** estilo Forex Factory (domingo–sábado). Los datos COT se publican el **viernes**; el fin de semana del sistema es el **sábado**, que se usa como `--as-of`.

1. Arranca el servidor local (stdlib, sin Flask):

```text
ABRIR_CALENDARIO.bat
REM equivalente: EJECUTAR_COT.bat --serve
# NO abras el HTML a doble clic — usa http://127.0.0.1:8765/
```

También: `launcher\run_cot.bat --serve` o `python report_server.py` desde `cot_system/`.

2. Se abre el navegador en `http://127.0.0.1:8765/` (informe latest con calendario). Página solo calendario: `/cot_week_picker.html`.

3. Elige la semana (clic en cualquier día → se resalta Sun–Sat; el sábado queda seleccionado). Atajos: **Esta semana**, **Semana pasada**, etc.

4. Pulsa **Aplicar · regenerar informe**. El servidor ejecuta `main.py --as-of <sábado>` y redirige a `cot_tff_fx_backtest_<asof>.html`.

Sin servidor, el botón Aplicar muestra pasos claros (y banner si es `file://`). **No regeneres desde doble clic al HTML** — usa `ABRIR_CALENDARIO.bat` o CLI `--as-of`.

## Cómo ejecutarlo (CLI)

Desde `cot_system/`:

```bash
python3 main.py --as-of 2025-06-17
```

Windows (el BAT reenvía argumentos a `main.py`):

```text
EJECUTAR_COT.bat --as-of 2025-06-17
```

También: `launcher\run_cot.bat --as-of 2025-06-17` o el campo **Backtest as-of** del lanzador GUI (`cot_launcher.py`).

La fecha puede ser el fin de semana COT o cualquier día calendario: se normaliza al **sábado** de esa semana Sun–Sat cuando se usa el calendario/servidor; en CLI se usa la última `report_date` **≤** as-of.

## Sin look-ahead (regla dura)

Antes de indicadores, percentiles, scoring y recomendación semanal el pipeline:

1. Trunca COT: `report_date <= as-of`
2. Trunca precios Yahoo: `price_date <= as-of`
3. No actualiza `cot_tff_fx_latest.*` (solo artefactos `backtest_`)

## Salidas

| Archivo | Ruta |
|---------|------|
| HTML | `docs/reports/cot_tff_fx_backtest_<asof>.html` |
| JSON | `docs/reports/cot_tff_fx_backtest_<asof>.json` |
| Calendario companion | `docs/reports/cot_week_picker.html` (lo escribe `report_server.py`) |

El HTML incluye la sección **Backtest · as-of** con el as-of solicitado, la semana COT efectiva y el aviso **«solo datos hasta esta semana»**, más el **calendario semanal** (`#week-picker`).

## Qué NO es

No es calibración fuera de muestra automática ni métrica de PnL. No es señal de compra/venta. `--from-csv-only` no admite `--as-of` (hace falta el pipeline completo con truncado). No hay empaquetado PyInstaller.
