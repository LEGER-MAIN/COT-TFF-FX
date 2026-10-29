# Recomendación semanal (pares swing)

## Para qué sirve

Tras el scoring COT por mercado, el informe añade una sección **Recomendación semanal** que traduce futuros TFF → pares spot/futuros sugeridos para estudio de swing (EURUSD, USDJPY, NZDUSD, GBPJPY, DXY, etc.), agrupados por secciones.

**No es señal de compra automática.** Es un ranking explicable de oportunidades relativas.

## Entradas

- `combined_bias`, `evidence_quality`, confirmación precio (si hay ticker)
- Mapa `swing_pairs` en `cot_system/config/markets.json`
- Universo TFF: **F10** + **F15** (NZD/MXN/BRL/ZAR si aparecen en CFTC) + **USD INDEX (F90 / DXY)**

## Secciones

| Sección | Contenido típico |
|---------|------------------|
| Majors USD | EURUSD, GBPUSD, AUDUSD, USDCAD, USDCHF, USDJPY |
| Crosses | EURGBP, EURJPY, GBPJPY (derivado GBP+JPY) |
| Índice DXY | DXY (`DX-Y.NYB`) |
| Opcionales | NZDUSD, USDMXN, USDBRL, USDZAR |

## COT-backed vs price-only

| `coverage` | Significado |
|------------|-------------|
| `direct` | Un mercado COT mapea 1:1 al par (`cot_backed=true`) |
| `derived` | Sesgo compuesto de varios COT (p. ej. GBPJPY); sigue siendo COT-backed |
| `price_only` | Sin COT en archivo; solo precio (ninguno por defecto en el mapa actual) |

Si el mercado F15 no viene en el zip CFTC de esa semana, el par aparece con aviso “sin dato COT”.

## Cómo leer cada fila

| Campo | Lectura |
|-------|---------|
| `priority` | **Prioridad alta / media / baja** (español) |
| `pair_bias` | Sesgo del **par** (−100…+100). En USDxxx con futuros de la divisa cotizada se **invierte** (p. ej. JPY alcista → USDJPY bajista) |
| `evidence_quality` | Calidad del/los mercados COT fuente (0…100) — no probabilidad |
| `opportunity_score` | Ranking: \|sesgo\| × calidad × factor precio |
| `por_que` | Resumen en español |
| `riesgo` | Umbrales provisionales, divergencias, correlación |
| `correlation_warnings` | Evitar duplicar (p. ej. USDJPY + GBPJPY en `usd_jpy_block`) |
| `disclaimer` | Siempre: no es señal de compra automática |

## Dónde está en el informe

- HTML: ancla `#recomendacion-semanal` (después del panel de sesgo/calidad)
- HTML: sección `#recomendacion-semanal` · JSON: `weekly_recommendations`
- JSON: `weekly_recommendations`
- CSV procesado: `cot_system/data/processed/fx_tff_weekly.csv`

## Esto NO es señal de compra/venta

Usar solo como lista de estudio semanal junto a precio, riesgo y reglas propias. Umbrales de prioridad viven en `markets.json` → `weekly_recommendation` (provisionales).
