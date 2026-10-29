# Indicadores básicos (criterios 1–6)

## Para qué sirve

Traducir Long / Short / OI de cada grupo en métricas semanales comparables: neto, neto normalizado, dirección del cambio, patrón acumulación/liquidación, variación de OI y participación relativa.

Implementado en `cot_system/src/cot_indicators.py`.

## Entradas que usa

- Serie validada: `long_positions`, `short_positions`, cambios usados (`long_change_used` / `short_change_used`), `spreading_positions`, `open_interest_total`
- Grano: mercado × `trader_group` × `report_date`

## Criterio 1 — Posición neta

**Fórmula:** \( N_t = Long_t - Short_t \) → columna `net_position`.

| Etiqueta (`net_class`) | Significado |
|------------------------|------------|
| `neto_positivo` | Predominio Long |
| `neto_negativo` | Predominio Short |
| `neto_cercano_a_cero` | Exactamente 0 en el dato |

**Esto NO es señal de compra/venta.** Un neto positivo solo describe posicionamiento reportado; la magnitud relativa se evalúa con el criterio 2 y percentiles.

## Criterio 2 — Posición neta normalizada (NN)

**Fórmula:** \( NN_t = N_t / OI_t \times 100 \) → `normalized_net_pct`.

| Lectura | Significado |
|---------|-------------|
| Valor % | Neto del grupo como fracción del OI total del mercado |
| Comparación | Contra el **historial del mismo mercado y grupo**, no contra un umbral universal |

Si OI es 0 o ausente → `normalized_net_pct` = NA.

## Criterio 3 — Variación semanal del neto

**Fórmula:** `delta_net_weekly` = ΔLong − ΔShort (con cambios usados).

| Etiqueta (`delta_net_label`) | Significado |
|------------------------------|------------|
| `mejora_alcista` | Δ neto &gt; 0 (el grupo quedó más netamente largo / menos corto) |
| `deterioro_bajista` | Δ neto &lt; 0 |
| `sin_cambio_neto` | Δ neto = 0 |

Expresa **dirección**, no intensidad. Ejemplo del manual: cierre fuerte de shorts puede mejorar el neto sin “compras nuevas”.

## Criterio 4 — Acumulación vs liquidación

Booleanos: `long_increase`, `short_increase`, `long_reduction`, `short_reduction` (+ cantidades).

| Patrón (`accum_liq_pattern`) | Δ Long | Δ Short | Lectura |
|------------------------------|--------|---------|---------|
| `nuevos_long_y_cierre_short` | + | − | Más largos y menos cortos |
| `aumentan_ambas` | + | + | Crecen ambos lados |
| `se_reducen_ambas` | − | − | Se reducen ambos |
| `menos_long_y_mas_short` | − | + | Menos largos y más cortos |
| `sin_cambio` | 0 | 0 | Sin movimiento |
| `mixta_o_unilateral` | otro | otro | Un lado cero / mixto |

**Regla:** ↑ Long ≠ prueba de “dinero nuevo” en sentido estricto.

## Criterio 5 — Open Interest total

| Campo | Significado |
|-------|-------------|
| `oi_change_abs` | \( OI_t - OI_{t-1} \) |
| `oi_change_pct` | Variación % |
| `oi_change_label` | Ver tabla |

| Etiqueta | Condición (código) |
|----------|---------------------|
| `aumenta` | %Δ OI &gt; 0,1 |
| `disminuye` | %Δ OI &lt; −0,1 |
| `estable` | \|%Δ OI\| ≤ 0,1 |

El OI **solo** no tiene sesgo alcista/bajista. La combinación con precio (criterio 19) aún no está codificada.

## Criterio 6 — % del OI por grupo

| Campo | Significado |
|-------|-------------|
| `pct_oi_long_calc` / `pct_oi_short_calc` / `pct_oi_spread_calc` | Calculados: posiciones / OI × 100 |
| `pct_oi_gross_calc` | (Long+Short+Spread) / OI × 100 |
| `pct_oi_*_reported` (loader) | Si la fuente trae %, se conservan para contraste |

No sustituyen neto ni variación semanal.

## Umbrales provisionales

- Epsilon OI “estable”: **0,1 %** (fijo en código de etiquetas, no en JSON).
- No hay umbral universal de NN “alto/bajo” en esta capa; eso entra vía percentiles y scoring.
