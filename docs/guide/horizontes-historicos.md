# Horizontes históricos (criterios 7–10)

## Para qué sirve

Pasar de una foto semanal a **estructura**: cómo cambió el neto en ventanas largas, si está en extremo relativo (percentiles) y si el desplazamiento es persistente o aislado.

Ventanas en `scoring_rules.json` → `horizons_weeks` (observaciones semanales aproximadas):

| Horizonte | Semanas (código) | Uso |
|-----------|------------------|-----|
| `weekly` | 1 | Cambio reciente |
| `monthly` | 4 | Confirmación corto plazo |
| `quarterly` | 13 | Estructura intermedia |
| `semiannual` | 26 | Posicionamiento estructural |
| `annual` | 52 | Extremos relativos del año |

Las ventanas se **superponen**: no son cinco pruebas independientes.

## Entradas que usa

- Serie semanal de `net_position` y `normalized_net_pct` por mercado × grupo
- OI actual para normalizar el cambio de horizonte
- `neutral_net_change_oi_pct` (**PROVISIONAL**, default 0,5) para etiqueta `direction_*`
- Mínimos de historial: `min_history_weeks_for_percentile` (10), `min_history_weeks_for_156w` (40)

## Criterio 7 — Variación neta acumulada

Por horizonte `h`:

| Campo | Significado |
|-------|-------------|
| `net_start_{h}` | Neto hace `weeks` observaciones |
| `net_change_{h}` | Neto actual − neto inicio |
| `net_change_nn_{h}` | Ese cambio / OI actual × 100 |
| `direction_{h}` | Ver tabla |

| `direction_*` | Condición en código |
|---------------|---------------------|
| `neutral` | \|cambio\| / OI × 100 &lt; `neutral_net_change_oi_pct` (o cambio 0) |
| `alcista` | Cambio neto positivo y relevante vs umbral |
| `bajista` | Cambio neto negativo y relevante |

**Esto NO es señal de compra/venta.** “Alcista” aquí = el **posicionamiento neto** se desplazó hacia más Long relativo, no una orden.

## Criterio 8 — Percentil histórico del neto

**Fórmula empírica (código):**  
\( P_t = 100 \times \#\{N_i &lt; N_t\} / M \) en ventana rodante que **incluye** la observación actual. Empates (`=`) no cuentan como “menores”.

| Columna | Ventana | Mín. obs. |
|---------|---------|-----------|
| `net_percentile_52w` | 52 | `min_history_weeks_for_percentile` |
| `net_percentile_156w` | 156 | `min_history_weeks_for_156w` |

Bandas de lectura (plan / config `percentile_bands`):

| Percentil | Lectura |
|-----------|---------|
| 0–10 | Cerca de mínimos del período (`extreme_low`) |
| 10–25 | Zona relativamente baja (`low`) |
| 25–75 | Zona intermedia |
| 75–90 | Zona relativamente alta (`high`) |
| 90–100 | Cerca de máximos (`extreme_high`) |

**Percentil alto ≠ compra** — puede ser saturación / extensión.

Si no hay historial suficiente → NA (no se inventa el percentil).

## Criterio 9 — Percentil de la NN

| Columna | Significado |
|---------|-------------|
| `normalized_net_percentile_52w` | Percentil de NN en 52w |
| `normalized_net_percentile_156w` | Idem 156w |

Si neto y NN están ambos elevados → evidencia de posicionamiento alto en absoluto y relativo al tamaño del mercado.

## Criterio 10 — Persistencia

| Campo | Significado |
|-------|-------------|
| `consecutive_net_up` | Semanas seguidas con Δ neto &gt; 0 (cero o NA rompe la racha) |
| `consecutive_net_down` | Semanas seguidas con Δ neto &lt; 0 |
| `positive_net_change_ratio_{h}` | Fracción de semanas con Δ neto &gt; 0 en la ventana |
| `negative_net_change_ratio_{h}` | Fracción con Δ neto &lt; 0 |

En `weekly`, el ratio es 1/0 según el signo de esa única observación.

La persistencia **no garantiza** continuidad futura; distingue variación aislada vs desplazamiento prolongado.

## Umbrales provisionales

Todo lo numérico de dirección/neutral y mínimos de percentil está en `scoring_rules.json` (`provisional: true`). Calibración por mercado: pendiente (COT-5).
