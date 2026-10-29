# Guía COT — hub

Acceso corto al sistema de evaluación cuantitativa COT (TFF FX + **USD INDEX / DXY**) y a la guía por apartado.

## Universo

**F10** (AUD, GBP, CAD, EUR, EUR/GBP, EUR/JPY, JPY, CHF) + **F15** cuando figuran en CFTC (NZD, MXN, BRL, ZAR) + **USD INDEX** (**F90** / `098662`, DXY). Precio DXY: Yahoo **`DX-Y.NYB`**.

Tras el scoring, el informe incluye **Recomendación semanal** de pares swing por secciones (Majors USD, Crosses, Índice DXY, Opcionales). Cómo leerla: [guide/recomendacion-semanal.md](guide/recomendacion-semanal.md).

**Backtest semanal:** `python3 main.py --as-of YYYY-MM-DD` (Windows: `EJECUTAR_COT.bat --as-of 2025-06-17`) trunca COT/precio a esa fecha (sin look-ahead) y escribe `reports/cot_tff_fx_backtest_<asof>.{html,xlsx,json}`. Con calendario en el HTML: `EJECUTAR_COT.bat --serve` → `http://127.0.0.1:8765/`. Detalle: [guide/backtest-as-of.md](guide/backtest-as-of.md).

## Qué es / qué no es

El pipeline calcula indicadores de posicionamiento (incl. régimen y C22), confirmación con precio Yahoo cuando hay ticker, un **sesgo direccional** (−100…+100) y una **calidad de evidencia** (0…100).

**No es señal de compra/venta.** La recomendación semanal tampoco. Calidad ≠ probabilidad de que el precio suba o baje. Umbrales: **provisionales** (`scoring_rules.json` version `0.3-provisional`). Spread no es direccional.

## Informe más reciente

- [Informe HTML latest](reports/cot_tff_fx_latest.html)
- También: `reports/cot_tff_fx_latest.json` (HTML only; sin Excel)
- Backtest (ejemplo): `reports/cot_tff_fx_backtest_YYYY-MM-DD.html`

## Guía por apartado

Índice completo: [guide/00-indice.md](guide/00-indice.md)

| Apartado | Archivo |
|----------|---------|
| Datos y calidad | [guide/datos-y-calidad.md](guide/datos-y-calidad.md) |
| Indicadores básicos (1–6) | [guide/indicadores-basicos.md](guide/indicadores-basicos.md) |
| Horizontes históricos (7–10) | [guide/horizontes-historicos.md](guide/horizontes-historicos.md) |
| Grupos participantes (11–15) | [guide/grupos-participantes.md](guide/grupos-participantes.md) |
| Precio y confirmación (16–19) | [guide/precio-y-confirmacion.md](guide/precio-y-confirmacion.md) |
| Scoring y calidad | [guide/scoring-y-calidad.md](guide/scoring-y-calidad.md) |
| Reglas por horizonte | [guide/reglas-por-horizonte.md](guide/reglas-por-horizonte.md) |
| Aceleración / régimen / divergencia (20–22) | [guide/aceleracion-regimen-divergencia.md](guide/aceleracion-regimen-divergencia.md) |
| Informe y alertas | [guide/informe-y-alertas.md](guide/informe-y-alertas.md) |
| Recomendación semanal | [guide/recomendacion-semanal.md](guide/recomendacion-semanal.md) |
| Controles y límites | [guide/controles-y-limites.md](guide/controles-y-limites.md) |
| Backtest as-of | [guide/backtest-as-of.md](guide/backtest-as-of.md) |

## Referencias

- [Plan de implementación](cot-plan.md)
- Handoff cobertura: `internal/cot-full-coverage-handoff.md`
- Manual: `COT_Algoritmo.docx`
- Código: `cot_system/` — `python3 main.py` (cache de precios; `--skip-price` omite 16–19; `--as-of` backtest)
