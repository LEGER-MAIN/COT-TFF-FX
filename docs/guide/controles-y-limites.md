# Controles y límites

## Para qué sirve

Evitar conclusiones incorrectas por datos mal tratados, historial insuficiente o uso del sesgo como si fuera una señal operativa. Checklist del manual §12 + lo que el pipeline **sí** comprueba hoy.

## Entradas que usa

- Dataset tras el loader (`validate_and_enrich`)
- Longitud de serie por mercado (`history_weeks`, conteo de fechas)
- Flags del scoring (`provisional_thresholds`, warnings de calidad)

## Checklist técnico

| Control | Qué significa “OK” | Estado en código |
|---------|--------------------|------------------|
| Integridad temporal | Fechas ordenables; serie cronológica por mercado×grupo | Ordenación en validación/indicadores |
| Validación de cambios | Publicado vs `*_recalc` documentado | Sí — `change_mismatch_rows` + warnings |
| Open Interest | Un OI por mercado×fecha; no sumar grupos | Sí — `oi_duplicate_market_dates` |
| Datos ausentes ≠ cero | NA no se rellena con 0 | Sí — política explícita |
| Historial suficiente | No forzar percentiles sin mín. obs. | Sí — NA si &lt; umbral; warning &lt;52w |
| Sesgo retrospectivo | Solo info disponible a la fecha evaluada | Percentiles rodantes “hasta t”; `--as-of` trunca COT/precio antes de indicadores ([backtest-as-of](backtest-as-of.md)) |
| Fecha de publicación | Usar cuándo el dato era operable | Campo previsto en plan; pipeline usa `report_date` |
| Costes / ejecución | Spreads, slippage en pruebas | **No** (fase backtest) |
| Validación fuera de muestra | Hold-out para calibración | **No** |

## Límites del sistema actual (leer antes de decidir)

| Límite | Implicación |
|--------|-------------|
| TFF only: F10 + F15 (si en CFTC) + DXY (F90) | No Legacy; F15 solo si el archivo CFTC lo trae |
| Precio = Yahoo + cache | Si falla ticker/`--skip-price`, 16–19 omitidos en scoring |
| DXY usa `DX-Y.NYB` | Índice ICE, no continuo `DX=F` (no respondió en Yahoo) |
| Umbrales globales | Mismos % OI / bandas para todos los mercados (**PROVISIONAL**) |
| Ventanas solapadas | Los 5 horizontes no son evidencia independiente |
| OR/NR peso bajo acotado | Cap 0,15; Spread sigue no direccional |
| Calidad alta + sesgo fuerte | Sigue sin ser probabilidad ni orden |
| Backtest semanal as-of sí; OOS/PnL no | `--as-of` sin look-ahead; calibración hold-out y costes siguen pendientes |

## Cómo leer “fallos” de control en el informe

| Señal | Lectura |
|-------|---------|
| `oi_duplicate_market_dates` &gt; 0 | No confiar en NN/% OI hasta corregir |
| `change_mismatch_rows` &gt; 0 | Revisar; puede ser benigno (1ª semana) o revisión CFTC |
| `missing_position_cells` &gt; 0 | Hay NA reales — no interpretar como flat |
| `provisional_thresholds: true` | Sesgo/calidad son hipótesis de diseño |
| Historial &lt; 26–52w en calidad | Penalización + warnings — extremos poco fiables |

## Esto NO es señal de compra/venta

Superar los controles de datos autoriza **confiar en la aritmética**, no a operar la etiqueta de sesgo. Precio Yahoo ya entra en scoring (provisional). El backtest `--as-of` reproduce el informe de una semana pasada sin look-ahead; sigue pendiente validación fuera de muestra / PnL.

## Umbrales provisionales ligados a controles

`min_history_weeks_for_percentile`, `min_history_weeks_for_156w`, `quality.min_weeks_full_credit`, `insufficient_history_penalty` — todos en `scoring_rules.json`.
