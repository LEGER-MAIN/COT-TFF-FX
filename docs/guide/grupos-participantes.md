# Grupos participantes (criterios 11–15)

## Para qué sirve

No todos los participantes se leen igual. El modelo separa **grupos principales** (núcleo del sesgo), **complementarios** (peso bajo acotado) y **contexto** (Dealer / Spread; sin sesgo por signo).

Config actual (`scoring_rules.json`, version `0.3-provisional`):

| Rol | Grupos | Peso |
|-----|--------|------|
| Primarios | Leveraged Funds, Asset Manager / Institutional | 0,55 / 0,45 (**PROVISIONAL**) |
| Complementarios | Other Reportables, Nonreportable | 0,08 / 0,05; blend cap **0,15** (**PROVISIONAL**) |
| Contexto | Dealer / Intermediary | No puntúa por signo del neto |
| Spread (crit. 15) | Por grupo, columnas de contexto | **No** entra en neto ni en sesgo |

### Cómo se combina el sesgo de mercado

1. Media ponderada LF+AM → sesgo primario.  
2. Si hay OR/NR con bias: media ponderada complementaria.  
3. `combined = (1 − cap) × primario + cap × complementario`, con `cap = min(complementary_blend_cap, …)`.

## Entradas que usa

- Indicadores 1–10 + 15 + 20–21 (+ precio 16–19 si hay) por `trader_group`
- Snapshot más reciente (`latest_snapshot`)
- Scoring: primarios y complementarios → `score_group_row`; Dealer → `dealer_*`; C22 vía `group_divergence_snapshot`

## Criterio 11 — Leveraged Funds (LF)

Grupo principal especulativo. En el informe: columnas `LF_*` (neto, NN, percentiles, persistencia, accel, bias, régimen, etc.).

### Etiquetas del manual vs código

El manual propone etiquetas narrativas (alcista en desarrollo, extendido, …). **El código no emite esas cinco**; usa la clasificación de sesgo compartida:

| `*_bias_label` | Rango (**PROVISIONAL**) |
|----------------|-------------------------|
| `fuertemente_alcista` | ≥ +60 |
| `moderadamente_alcista` | ≥ +25 y &lt; +60 |
| `neutral_o_mixto` | &gt; −25 y &lt; +25 |
| `moderadamente_bajista` | ≤ −25 y &gt; −60 |
| `fuertemente_bajista` | ≤ −60 |

**Neto positivo solo no activa “compra”.**

## Criterio 12 — Asset Managers / Institutional (AM)

Mismo esquema con prefijo `AM_`. Evaluación separada de LF; núcleo del sesgo de mercado con pesos 0,55/0,45.

Acuerdo de dirección (calidad + C22): ver [aceleracion-regimen-divergencia](aceleracion-regimen-divergencia.md).

## Criterio 13 — Dealers / Intermediaries

| Campo | Significado |
|-------|-------------|
| `dealer_net` / `dealer_nn_pct` / `dealer_delta_weekly` | Contexto |
| `dealer_spread` | Spread del Dealer si existe |
| Nota | No entra en sesgo direccional automático |

**No** se asigna alcista/bajista automático por el signo del neto del Dealer.

## Criterio 14 — Other Reportables y Nonreportable

| Estado | Detalle |
|--------|---------|
| Datos | Loader TFF incluye ambos |
| Scoring | **Sí** — pesos `complementary_group_weights` 0,08 / 0,05 |
| Blend | Cap `complementary_blend_cap` = 0,15 sobre el sesgo primario |
| Informe | Prefijos `OR_*` / `NR_*` |
| Calidad | Bonus si acuerdan el signo primario; warning si divergen |

Pesos: hipótesis iniciales (**PROVISIONAL**); Jefferson puede ajustar en JSON.

## Criterio 15 — Spread

| Campo | Lectura |
|-------|---------|
| `spreading_positions` / `spread_oi_pct` | Nivel y % OI |
| `spread_change_used` | Cambio (recalc preferido) |
| `spread_change_label` | `spread_aumenta` / `spread_disminuye` / `spread_sin_cambio` |
| `spread_context_note` | `spread_no_direccional` |

**No** se suma al neto direccional ni al sesgo. Bloque `spread_context` en HTML/JSON.

## Esto NO es señal de compra/venta

El sesgo combina evidencia de posicionamiento (y, si hay, blend suave de precio). No es orden ni predicción de precio.

## Umbrales provisionales

`group_weights`, `complementary_group_weights`, `complementary_blend_cap`, bandas de sesgo y ±5 de “sesgo claro” en calidad.
