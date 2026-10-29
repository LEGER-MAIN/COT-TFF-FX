# Aceleración, régimen y divergencia (criterios 20–22)

## Para qué sirve

Añadir profundidad más allá de “el neto sube o baja”: si el cambio **acelera**, si hubo **cruce de signo** (régimen) y si LF y AM **coinciden o divergen** (niveles NN vs cambios semanales, por separado).

## Entradas que usa

| Criterio | Entradas | Estado |
|----------|----------|--------|
| 20 | `delta_net_weekly`, lookback y umbral en JSON | **Implementado** |
| 21 | Signo de `net_position` semana a semana | **Implementado** (`cot_indicators`) |
| 22 | NN y Δ neto semanal LF vs AM | **Implementado** (`group_divergence_snapshot`) |

## Criterio 20 — Aceleración del cambio neto

Compara la magnitud del Δ neto semanal actual con la media de magnitudes de las semanas previas.

| Parámetro (**PROVISIONAL**) | Default |
|-----------------------------|---------|
| `acceleration_lookback_weeks` | 4 |
| `acceleration_ratio_threshold` | 1,5 |

**Fórmula (código):**  
`ratio = |Δ_t| / media(|Δ| de lookback desplazado 1 semana)`.

| Etiqueta (`net_change_accel_label` / `LF_accel` / `AM_accel`) | Condición |
|--------------------------------------------------------------|-----------|
| `acelerando` | ratio ≥ 1,5 |
| `desacelerando` | ratio ≤ 1/1,5 (≈ 0,667) |
| `estable` | entre ambos |
| ausente | Sin historial / media 0 |

**Esto NO es señal de compra/venta.** Aceleración del posicionamiento ≠ dirección del precio. La etiqueta **no** entra en `group_bias` (solo se reporta).

## Criterio 21 — Cambio de régimen

Detecta cruce de signo del neto (ambos lados ≠ 0 y `sign(prev) ≠ sign(cur)`).

| Campo | Significado |
|-------|-------------|
| `regime_cross_flag` | True en la semana del cruce |
| `regime_net_before` / `regime_net_after` | Neto antes/después |
| `regime_direction` | `cruzo_a_neto_positivo` o `cruzo_a_neto_negativo` |
| `weeks_since_regime_cross` | Semanas desde el último cruce (0 = semana del cruce) |

En el JSON de grupo: objeto `regime` con nota fija: *“Cruce de signo del neto; no es señal de entrada por sí solo.”*

### Calidad / alertas

Si `weeks_since` ≤ `quality.regime_recent_weeks` (8, **PROVISIONAL**) en un grupo primario → warning de régimen reciente (contexto, no entrada automática).

Precio antes/después del cruce: **no** registrado aún como campos dedicados (el plan lo menciona; el código actual no lo calcula).

## Criterio 22 — Divergencia entre grupos (LF vs AM)

Función `group_divergence_snapshot` — **dos lecturas separadas** (no confundirlas):

### A) Gap de niveles NN

| Campo | Significado |
|-------|-------------|
| `c22_nn_level_gap_pct` | \|NN_LF − NN_AM\| |
| `c22_nn_levels_diverge` | True si gap ≥ `divergence.nn_level_gap_pct` (5,0 **PROVISIONAL**) |

Gap de nivel → warning informativo en calidad (`C22_gap_niveles_NN`); **no** implica por sí solo desacuerdo de cambios.

### B) Acuerdo de cambios semanales

Δ neto / OI × 100 por grupo; umbral `divergence.change_disagree_oi_pct` (0,5 **PROVISIONAL**).

| `c22_weekly_change_agreement` | Condición | Efecto en calidad |
|-------------------------------|-----------|-------------------|
| `acuerdo_mejora` | Ambos Δ NN &gt; umbral | +5 |
| `acuerdo_deterioro` | Ambos Δ NN &lt; −umbral | +5 |
| `desacuerdo_cambios` | Signos opuestos y relevantes | −8 + warning |
| `ambos_cambios_neutrales` | Ambos \|Δ NN\| &lt; umbral | — |
| `mixto_un_lado_neutral` | Un lado relevante, el otro no | — |

Además sigue el acuerdo/desacuerdo de **sesgos de grupo** LF vs AM (±5 hardcodeado) con bonus/penalización `group_agreement_bonus` / `divergence_penalty`.

## Esto NO es señal de compra/venta

Régimen y C22 son contexto de posicionamiento. Un cruce de cero o un desacuerdo LF–AM **no** es orden de entrada/salida.

## Umbrales provisionales

`acceleration_*`, `divergence.*`, `quality.regime_recent_weeks` en `scoring_rules.json`. Umbral ±5 de “sesgo claro” para acuerdo LF/AM sigue hardcodeado en `scoring.py`.
