# Reglas por horizonte

## Para qué sirve

El manual (§8) define **qué evaluar** en cada ventana. El motor aplica un **score numérico compartido** (Δ neto/OI + percentil + persistencia selectiva + blend suave de confirmación de precio) con pesos distintos. Esta página traduce ambas capas.

## Entradas que usa

- Columnas `direction_{h}`, `net_change_{h}`, `net_change_nn_{h}`, scores en `horizons` del JSON
- Pesos `horizon_weights`
- Precio (si mapeado): `price_return_{h}`, `price_direction_{h}`, `price_position_confirm_{h}`

## Qué hace el código en cada horizonte

Para cada `h` ∈ weekly / monthly / quarterly / semiannual / annual:

| Pieza | ¿Entra? |
|-------|---------|
| Score de `net_change_nn_{h}` | Sí |
| Score de percentil neto (52w; 156w en annual si hay) | Sí |
| Score de percentil NN 52w | Solo semiannual y annual |
| Score de persistencia | Todos excepto weekly |
| Confirmación precio × neto | Sí, si `price_available` (peso 0,25 **PROVISIONAL**) |
| OI del checklist §8 | Indicador sí; no score propio por horizonte |

Resultado: `horizon_score_m2_p2` y `direction` (etiqueta del criterio 7).

| `direction` | Lectura operativa |
|-------------|-------------------|
| `alcista` | Cambio neto del horizonte relevante hacia más Long |
| `bajista` | Cambio neto relevante hacia más Short |
| `neutral` | Cambio pequeño vs `neutral_net_change_oi_pct` |
| ausente | Sin datos suficientes para esa ventana |

## Checklist del manual vs estado

### Semanal — objetivo: cambio reciente

| Evaluación del plan | En código |
|---------------------|-----------|
| Δ neto positivo/negativo | Sí (`direction_weekly`, score Δ) |
| Magnitud vs historial | Proxy: umbrales fijos % OI (**PROVISIONAL**), no percentil de cambios históricos aún |
| Distinguir ↑Long vs ↓Short | Sí en indicadores (`accum_liq_pattern`), **no** en el score del horizonte |
| Precio confirma o divergencia | Sí (`price_position_confirm_weekly` + blend) |

### Mensual — objetivo: continuidad

| Evaluación del plan | En código |
|---------------------|-----------|
| Neto vs ~1 mes | Sí (`net_change_monthly`) |
| Proporción de semanas con mejora | Calculada (`positive_net_change_ratio_monthly`); **no** entra al score |
| OI expandió/contrajo | Indicador OI semanal existe; **no** en score de horizonte |
| Confirmación / deterioro / mixta | Proxy vía `direction` + score, sin etiqueta “confirmación” |

### Trimestral — objetivo: estructura

| Evaluación del plan | En código |
|---------------------|-----------|
| Δ neto ~13 semanas | Sí |
| Percentil del neto | Sí (52w como estructura) |
| Persistencia | Sí (entra al score) |
| Contrastar LF vs AM | A nivel mercado (calidad / sesgos), no score trimestral separado |

### Semestral — objetivo: estructura / saturación

| Evaluación del plan | En código |
|---------------------|-----------|
| Percentil / extremos | Percentil 52w + NN 52w en score |
| Aceleración | Calculada (crit. 20); visible en informe, **no** en score de horizonte |
| Divergencias prolongadas con precio | Etiquetas C17 por horizonte; no hay “prolongada” como flag aparte |

### Anual — objetivo: contexto histórico

| Evaluación del plan | En código |
|---------------------|-----------|
| Percentil 52 y 156 | 156 preferido en score annual si existe |
| Cambios de régimen | Sí (crit. 21); warning si reciente |
| Distinguir extremo vs reversión confirmada | Alertas extensión (± precio); sin módulo de reversión automática |

## Cómo leer el desglose en el informe

En HTML/JSON (horizontes por grupo):

| Campo | Significado |
|-------|-------------|
| `horizon_score_m2_p2` | Evidencia de ese horizonte (−2…+2) |
| `weight` | Peso en el sesgo de grupo |
| `net_change_nn_pct` | Intensidad del desplazamiento / OI |
| `price_return_pct` / `price_direction` / `price_position_confirm` | Criterios 16–17 si hay Yahoo |

**Esto NO es señal de compra/venta.** Un horizonte “alcista” describe el desplazamiento del posicionamiento en esa ventana.

## Umbrales provisionales

`neutral_net_change_oi_pct`, `strong_net_change_oi_pct`, pesos y bandas de percentil — todos en `scoring_rules.json`.
