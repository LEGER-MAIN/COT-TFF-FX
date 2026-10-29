# Informe y alertas

## Para qué sirve

Entregar, por mercado, una conclusión **explicable**: sesgo, calidad, desglose por grupo/horizonte, contexto Dealer y warnings — sin limitarse a “alcista/bajista”.

Generado por `cot_system/src/report.py` + `main.py`. Artefacto habitual:

- [HTML latest](../reports/cot_tff_fx_latest.html)
- También: `cot_tff_fx_latest.json` (+ copias fechadas). **Solo HTML/JSON** (sin Excel).

## Entradas que usa

- DataFrame de indicadores + `ValidationReport`
- DataFrame scored (`score_markets`) y reglas JSON
- Metadatos: `as_of_date`, fuente CFTC TFF Futures Only

## Cómo leer la salida

### Capas del informe

| Pieza | Contenido |
|-------|-----------|
| Meta | Tipo TFF, fechas, conteos, mismatches, fuente precio, disclaimer |
| Sesgo / calidad | `combined_bias`, label, `evidence_quality`, warnings |
| LF / AM / OR / NR | Netos, percentiles, bias, horizontes, accel, régimen |
| Precio + C22 | Ticker/close, confirmaciones, `c22_weekly_change_agreement` |
| **Recomendación semanal** | Pares swing por sección (prioridad, por qué, riesgo); ver [recomendacion-semanal](recomendacion-semanal.md) |
| Dealer / Spread | Solo contexto |
| Horizontes | Tabla larga mercado × grupo × horizonte (+ precio) |
| Validación | Warnings de datos |

### Campos clave del JSON / panel HTML

| Campo | Cómo leerlo |
|-------|-------------|
| `combined_bias` | −100…+100 (LF+AM + blend OR/NR) |
| `combined_bias_label` | Ver [scoring-y-calidad](scoring-y-calidad.md) |
| `evidence_quality` | 0…100 consistencia — **no** probabilidad |
| `quality_reasons` | Códigos cortos de por qué subió/bajó la calidad |
| `warnings` | Provisionalidad, historial, C22, precio, régimen, extensión… |
| `c22_*` | Gap NN y acuerdo/desacuerdo de Δ semanal LF–AM |
| `price_ticker` / `price_close` | Yahoo mapeado (DXY → `DX-Y.NYB`) |
| `groups[].horizons` | Scores −2…+2, pesos, confirmación precio |
| `dealer_context` / `spread_context` | Contexto; no scoring direccional |
| `provisional_thresholds` | Debe ser `true` mientras no se calibré |
| `disclaimer` | Sesgo ≠ compra/venta; calidad ≠ probabilidad |

## Alertas típicas y significado

| Warning (ejemplo) | Significado | ¿Acción operativa? |
|-------------------|-------------|--------------------|
| Umbrales PROVISIONALES… | Config no calibrada | No tratar números como “listos para trading” |
| Historial corto… | Percentiles/horizontes largos frágiles | Bajar confianza en extremos |
| Percentil 156w no disponible… | Serie &lt; umbral 156w | Contexto anual limitado |
| Horizontes en desacuerdo… | Direcciones mixtas dentro del grupo | Calidad baja / lectura mixta |
| Divergencia LF vs AM… | Sesgos de grupo opuestos | Conflicto entre participantes |
| Percentil extremo + sesgo mismo signo | Extensión/saturación | **No** venta/compra automática |
| Dealer sin dato… | Falta contexto de intermediación | Informativo |
| Warnings de validación (OI, mismatches) | Integridad de datos | Revisar fuente antes de confiar |

## Esto NO es señal de compra/venta

El informe resume evidencia de **posicionamiento reportado**. Cualquier uso operativo requiere precio, reglas de ejecución y validación histórica (fases 6–7 del plan) — aún pendientes.

## Umbrales provisionales

Versionado en `scoring_version` del payload. Si cambia `scoring_rules.json`, regenerar con `cd cot_system && python3 main.py`.
