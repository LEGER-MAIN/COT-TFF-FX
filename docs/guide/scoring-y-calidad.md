# Scoring y calidad de la evidencia

## Para qué sirve

Separar dos resultados distintos:

| Resultado | Escala | Significado |
|-----------|--------|------------|
| **Sesgo direccional** (`combined_bias`) | −100 … +100 | Orientación alcista/bajista de la evidencia de posicionamiento |
| **Calidad de la evidencia** (`evidence_quality`) | 0 … 100 | Consistencia / historial / acuerdos — **no** probabilidad de subida/bajada |

Implementado en `cot_system/src/scoring.py` con umbrales de `config/scoring_rules.json` (`provisional: true`, version `0.3-provisional`).

## Entradas que usa

- Snapshot de indicadores (LF + AM; OR/NR complementarios; Dealer contexto)
- Por horizonte: `net_change_nn_*`, `direction_*`, percentiles 52/156, persistencia; si hay precio → `price_position_confirm_*`
- C22 (`group_divergence_snapshot`), régimen reciente, alertas precio×extremo
- Pesos: `horizon_weights`, `group_weights`, `complementary_group_weights` + `complementary_blend_cap`
- Factores: bloques `quality`, `price`, `divergence`, `regime` del JSON

## Puntuación por criterio (−2 … +2)

Cada pieza se mapea así (luego se promedia por horizonte):

### Cambio neto del horizonte (`net_change_nn_*` = % del OI)

| Condición (**PROVISIONAL**) | Score |
|-----------------------------|-------|
| \|Δ\| &lt; `neutral_net_change_oi_pct` (0,5) | 0 |
| Δ ≥ `strong_net_change_oi_pct` (2,0) | +2 |
| Δ &gt; 0 (pero &lt; strong) | +1 |
| Δ ≤ −strong | −2 |
| Δ &lt; 0 (pero &gt; −strong) | −1 |

### Percentil de neto

| Percentil | Score |
|-----------|-------|
| ≥ 90 (`extreme_high`) | +2 |
| ≥ 75 (`high`) | +1 |
| ≤ 10 (`extreme_low`) | −2 |
| ≤ 25 (`low`) | −1 |
| Entre medias | 0 |

- Ventanas cortas/medias: usan `net_percentile_52w`
- Horizonte `annual`: prefiere `net_percentile_156w` si existe
- `normalized_net_percentile_52w` entra solo en `semiannual` y `annual`

### Persistencia

| Condición (`persistence_min_weeks` = 3) | Score |
|-----------------------------------------|-------|
| `consecutive_net_up` ≥ 3 y ≥ down | +1; si ≥ 6 → +2 |
| `consecutive_net_down` ≥ 3 y &gt; up | −1; si ≥ 6 → −2 |
| Resto | 0 |
| Horizonte `weekly` | Persistencia **no** se aplica (`null`) |

### Confirmación de precio (si `price.enabled` y hay ticker)

Tras la media COT del horizonte, blend suave:  
`(1 − 0,25) × media_COT + 0,25 × price_score` — detalle en [precio-y-confirmacion](precio-y-confirmacion.md).

**Percentil alto puntúa “posicionamiento largo-pesado” como evidencia alcista de posicionamiento — no como compra.**

## Agregación

1. Media de piezas COT del horizonte (+ blend precio) → `horizon_score_m2_p2` (−2…+2).
2. Media ponderada por `horizon_weights` × 50 → `group_bias` (−100…+100).
3. Sesgo primario = media ponderada LF/AM; luego blend OR/NR con cap 0,15 → `combined_bias`.

Pesos horizonte (**PROVISIONAL**): semanal 10 %, mensual 15 %, trimestral 25 %, semestral 25 %, anual 25 %.

## Clasificación del sesgo

| Puntuación | `combined_bias_label` / `*_bias_label` |
|------------|----------------------------------------|
| ≥ +60 | `fuertemente_alcista` |
| ≥ +25 | `moderadamente_alcista` |
| &gt; −25 y &lt; +25 | `neutral_o_mixto` |
| ≤ −25 | `moderadamente_bajista` |
| ≤ −60 | `fuertemente_bajista` |

## Calidad de la evidencia (cómo se construye en código)

Partida: **50**. Luego ajustes (clamp 0–100):

| Factor | Efecto aproximado |
|--------|-------------------|
| Historial ≥ 52w | +15 |
| Historial ≥ 26w (&lt;52) | +8 |
| Historial &lt; 26w | −`insufficient_history_penalty` (25) + warning |
| Percentil 156w disponible en primarios | +5 |
| Horizontes alineados (acuerdo ≥ 0,8) | +15 |
| Acuerdo parcial (≥ 0,6) | +8 |
| Horizontes divergentes | −10 + warning |
| LF y AM mismo signo (sesgos \|b\|&gt;5) | +`group_agreement_bonus` (15) |
| LF y AM signos opuestos | −`divergence_penalty` (20) + warning |
| Dealer presente / ausente | razón o warning de contexto |
| C22 gap niveles NN | warning informativo |
| C22 `desacuerdo_cambios` / acuerdos | −8 / +5 |
| OR/NR acuerdan o divergen del primario | +`complementary_agreement_bonus` (5) o warning |
| Precio confirma / diverge (conteo de etiquetas) | +10 / −12 (**PROVISIONAL**) |
| Sin precio mapeado | warning; razón `sin_precio` |
| Régimen reciente (≤ 8 sem.) | warning de contexto |

### Alertas de extensión (dentro de calidad)

Si percentil 52w ≥ 90 y sesgo de grupo &gt; 0 → warning de extensión/saturación (**no señal de venta**).  
Si percentil ≤ 10 y sesgo &lt; 0 → warning de extensión corta (**no señal de compra**).

Siempre se antepone: *“Umbrales PROVISIONALES… no calibrados por mercado.”*

## Esto NO es señal de compra/venta

- Sesgo = orientación de la **evidencia de posicionamiento reportado**
- Calidad ≠ probabilidad de dirección del precio
- Disclaimer fijo en JSON/HTML: no son señales de compra/venta

## Umbrales provisionales

Todos los números de esta página vienen de `scoring_rules.json` y deben revisarse (COT-5) antes de usarlos como input de decisión.
