# Precio y confirmación (criterios 16–19)

## Estado

**Implementado** en `cot_system/src/price_confirmation.py` (scoring `0.3-provisional`). Precios semanales de **Yahoo Finance** (chart API vía curl + cache en `cot_system/data/price/`). Alineación a `report_date` con `merge_asof` hacia atrás. Omitible con `--skip-price`.

Umbrales en `scoring_rules.json` → bloque `price` (**PROVISIONAL**).

## Para qué sirve

Cruzar posicionamiento COT con el precio del instrumento mapeado para: tendencia por horizonte, confirmación/divergencia, alerta de extensión y lectura OI×precio — sin convertir divergencias en reversión automática.

## Entradas que usa

| Entrada | Detalle |
|---------|---------|
| Tickers | `config/markets.json` → `price_source.tickers` |
| Panel semanal | Cache CSV por ticker + `fx_dx_weekly_panel.csv` |
| Dirección neta COT | `direction_{h}` (criterio 7) |
| Percentil / OI | `net_percentile_52w`, `oi_change_label` |
| Horizontes | Mismos 1 / 4 / 13 / 26 / 52 |

### Mapa de tickers (código)

| Mercado COT | Yahoo |
|-------------|-------|
| AUD, GBP, CAD, EUR, JPY, CHF | `6A/B/C/E/J/S=F` (futuros CME) |
| EUR/GBP, EUR/JPY | `RP=F`, `RY=F` |
| **USD INDEX (DXY, F90 / 098662)** | **`DX-Y.NYB`** (índice ICE; `DX=F` no respondió en Yahoo) |

Precio a nivel de mercado (duplicado por `trader_group` para el join). Si no hay ticker o falla la descarga → `price_available=false` y criterios 16–19 omitidos en scoring (warning).

## Criterio 16 — Tendencia del precio

**Fórmula:** `price_return_{h}` = (close_t / close_{t−weeks} − 1) × 100.

| Etiqueta (`price_direction_{h}`) | Condición (**PROVISIONAL**) |
|----------------------------------|------------------------------|
| `sube` | retorno % ≥ `sideways_abs_return_pct` (0,5) |
| `baja` | retorno % ≤ −0,5 |
| `lateral` | \|retorno %\| &lt; 0,5 |

## Criterio 17 — Confirmación precio × posicionamiento

Compara `direction_{h}` (neto) con `price_direction_{h}` → `price_position_confirm_{h}`:

| Neto | Precio | Etiqueta |
|------|--------|----------|
| alcista | sube | `confirmacion_alcista_potencial` |
| bajista | baja | `confirmacion_bajista_potencial` |
| alcista | baja | `divergencia_neto_sube_precio_baja` |
| bajista | sube | `divergencia_neto_baja_precio_sube` |
| (cualquier) | lateral | `precio_lateral_sin_confirmacion` |
| neutral / ausente | — | sin etiqueta |

**Divergencia ≠ señal de reversión automática.**

### Cómo entra al scoring

Si `price.enabled` y hay precio: el score del horizonte mezcla  
`(1 − confirm_weight_in_horizon) × media_COT + confirm_weight × price_score`, con `confirm_weight_in_horizon` = **0,25** (**PROVISIONAL**).

| Etiqueta confirm | `price_score` (−2…+2) |
|------------------|------------------------|
| `confirmacion_alcista_potencial` | +1 |
| `confirmacion_bajista_potencial` | −1 |
| `divergencia_neto_sube_precio_baja` | −1 (penalización suave) |
| `divergencia_neto_baja_precio_sube` | +1 (ajuste suave opuesto) |
| lateral / mixta / otra | 0 |

En calidad: más confirmaciones que divergencias → +`quality_confirm_bonus` (10); más divergencias → −`quality_diverge_penalty` (12) + warning.

## Criterio 18 — Extremo de posicionamiento y precio

Columna `price_extreme_alert` (alerta, **no** orden):

| Condición | Etiqueta |
|-----------|----------|
| percentil 52w ≥ `extension_percentile` (90), neto &gt; 0, precio mensual `sube` | `extremo_largo_con_precio_subiendo_alerta_extension` |
| percentil ≤ 10, neto &lt; 0, precio mensual `baja` | `extremo_corto_con_precio_bajando_alerta_extension` |

Siguen existiendo warnings de extensión **solo por percentil+sesgo** en calidad (sin exigir precio).

## Criterio 19 — OI y precio

`oi_price_reading` = `precio_{dir}_oi_{oi_label}` usando dirección de precio **mensual** y `oi_change_label` semanal (p. ej. `precio_sube_oi_aumenta`).

Lectura complementaria; **sin** dirección compradora/vendedora inequívoca. No entra como score −2…+2 propio.

## Esto NO es señal de compra/venta

Confirmación, divergencia y alertas de extensión son **etiquetas de evidencia**. El blend de precio en el horizonte es suave y provisional.

## Umbrales provisionales

Bloque `price` en `scoring_rules.json`: `sideways_abs_return_pct`, `confirm_weight_in_horizon`, bonus/penalización de calidad, `extension_percentile`. Calibración por mercado pendiente.
