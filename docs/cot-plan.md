# Plan del sistema COT — evaluación cuantitativa

Documento de trabajo derivado del *Manual técnico del sistema COT para futura automatización con Python*. Objetivo: convertir ese manual en un plan accionable para construir juntos el algoritmo/sistema.

**Alcance de este plan:** lo que el manual define de forma explícita. Donde el texto es incompleto, provisional o deja una elección abierta, se marca como **[ABIERTO]**.

---

## 1. Objetivo y alcance

### Qué es el sistema

Un sistema de evaluación cuantitativa, estructurado y programable que:

1. Recibe informes COT históricos.
2. Calcula indicadores.
3. Asigna puntuaciones.
4. Compara horizontes temporales.
5. Genera una conclusión objetiva **por mercado**.

### Arquitectura en cuatro capas

| Capa | Qué hace |
|------|----------|
| **Datos** | Qué posiciones reporta realmente el COT |
| **Indicadores** | Cálculos matemáticos derivados de esos datos |
| **Evaluación** | Reglas para clasificar el posicionamiento |
| **Decisión** | Interpretación final: confirmaciones, contradicciones y riesgos |

### Qué *no* es el sistema

- **No** confunde posición neta alcista con señal de compra inmediata.
- El COT mide **posicionamiento reportado**; las señales operativas deben validarse con el **precio** y probarse **históricamente**.
- Un percentil alto o un sesgo “fuertemente alcista” **no** equivalen a una orden de entrada.

### Flujo funcional

```
Datos COT → Indicadores → Evaluación por horizonte → Puntuación y validación → Informe final
```

Salida esperada: sesgo direccional + calidad de la evidencia + explicaciones + alertas — no un “comprar/vender” automático.

---

## 2. Modelo de datos

### 2.1 Tipo de informe (decisión previa)

La tabla de referencia del manual usa categorías **Traders in Financial Futures (TFF)**. Estas **no** son intercambiables con el informe **Legacy** (comerciales / no comerciales).

El sistema debe **identificar el tipo de informe** antes de interpretar datos.

| Categoría TFF | Interpretación general | Uso en el modelo |
|---------------|------------------------|------------------|
| Dealer / Intermediary | Intermediarios y dealers | Contexto de intermediación y cobertura |
| Asset Manager / Institutional | Gestores institucionales | Posicionamiento institucional |
| Leveraged Funds | Fondos apalancados | Posicionamiento especulativo |
| Other Reportables | Otros reportables | Confirmación complementaria |
| Nonreportable | Por debajo de umbrales de reporte | Contexto residual |

**[ABIERTO]** ¿Modelo centrado en TFF (LF + AM principales) o también Legacy (Commercials / Non-Commercials)? Ver §6.

### 2.2 Campos a persistir

Conservar datos originales sin modificarlos; añadir columnas calculadas después.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `market` | Texto | Mercado o contrato de futuros |
| `report_type` | Texto | TFF, Legacy u otra clasificación |
| `report_date` | Fecha | Fecha de posicionamiento reportado |
| `publication_date` | Fecha | Fecha de publicación, si está disponible |
| `trader_group` | Texto | Categoría de participante |
| `long_positions` | Entero | Total de posiciones largas |
| `long_change` | Entero | Cambio reportado en Long |
| `short_positions` | Entero | Total de posiciones cortas |
| `short_change` | Entero | Cambio reportado en Short |
| `spreading_positions` | Entero | Posiciones Spread |
| `spread_change` | Entero | Cambio en Spread |
| `open_interest_total` | Entero | Interés abierto total del mercado |
| `source` | Texto | Fuente del registro |

### 2.3 Reglas de calidad de datos

1. Conservar cambios semanales del informe **y** recalcularlos para verificar integridad.
2. **No usar cero para dato ausente.** Cero = no hay posiciones reportadas; ausente = información no disponible.
3. Open Interest total: **una sola vez** por mercado, contrato y fecha. **No sumar** OI de todos los participantes.
4. Controles previos a confiar en resultados (checklist del manual): integridad temporal; validación de cambios vs. diferencias consecutivas; OI no duplicado; ausentes ≠ cero; historial suficiente para percentiles; sin sesgo retrospectivo; respetar fecha de publicación en simulaciones; costes/ejecución en pruebas operativas; validación fuera de muestra.

---

## 3. Criterios / fórmulas a implementar

Todos los horizontes se construyen desde la **misma serie semanal**. Nombrar cada criterio y qué implementar.

### Criterio 1 — Posición neta (Net Position)

- **Fórmula:** \( N_t = Long_t - Short_t \)
- **Clasificación:** neto positivo / negativo / cercano a cero.
- **Implementar:** no usar solo el signo; un +100 puede ser irrelevante en un mercado y crítico en otro → pasar siempre a Criterio 2.

### Criterio 2 — Posición neta normalizada (NN)

- **Fórmula:** \( NN_t = \frac{N_t}{OI_t} \times 100 \)
- **Ejemplo del manual:** Long 18 063, Short 14 880, OI 100 000 → NN = 3,183 %.
- **Implementar:** comparar % con historial del **mismo mercado y grupo**. **No** umbral universal (p. ej. 5 % para todos).

### Criterio 3 — Variación semanal de la posición neta

- **Idea:** si el grupo se volvió más alcista o más bajista en la semana.
- **Ejemplo:** ΔLong −945, ΔShort −2 052 → mejora neta +1 107 (cierre de cortos más fuerte, no “1 107 compras nuevas”).
- **Etiquetas:** mejora alcista / deterioro bajista / sin cambio neto (dirección, no intensidad).
- **Implementar:** intensidad vía variaciones históricas del mismo mercado.

### Criterio 4 — Acumulación frente a liquidación

| Δ Long | Δ Short | Interpretación |
|--------|---------|----------------|
| + | − | Nuevos Long y cierre de Short |
| + | + | Aumentan ambas |
| − | − | Se reducen ambas |
| − | + | Menos Long y más Short |

- **Indicadores por grupo:** `long_increase`, `short_increase`, `long_reduction`, `short_reduction` (booleanos + cantidades).
- **Regla:** aumento de Long ≠ prueba de “dinero nuevo” en sentido estricto.

### Criterio 5 — Open Interest total

- Guardar variación absoluta y \( \%\Delta OI_t = \frac{OI_t - OI_{t-1}}{OI_{t-1}} \times 100 \).
- Lecturas: aumenta / disminuye / estable.
- OI **solo** no tiene sesgo alcista/bajista; combinar con neto, Δ Long/Short y precio.
- Validación: OI una vez por mercado/fecha.

### Criterio 6 — % del Open Interest por grupo

- Calcular participación relativa por categoría.
- Si la fuente trae %, conservarlos y contrastarlos con los calculados.
- No sustituyen neto ni variación semanal.

### Horizontes (base de Criterios 7–10 y reglas de §8)

| Horizonte | Ventana aprox. | Uso |
|-----------|----------------|-----|
| Semanal | 1 obs. | Cambio reciente |
| Mensual | 4–5 obs. | Confirmación corto plazo |
| Trimestral | 13 obs. | Estructura intermedia |
| Semestral | 26 obs. | Posicionamiento estructural |
| Anual | 52 obs. | Extremos relativos del año |

Preferir fechas reales de informe y ventanas temporales; los conteos son aproximaciones.

### Criterio 7 — Variación neta acumulada (por horizonte)

- Comparar neto actual vs. neto al inicio de la ventana.
- Guardar por grupo/horizonte: `net_start`, `net_current`, `net_change_horizon`, `net_change_normalized`, `direction` (alcista / bajista / neutral según reglas configuradas).
- **[ABIERTO]** Umbrales exactos de “neutral” / relevancia: el manual dice “según las reglas configuradas” sin fijarlos todos.

### Criterio 8 — Percentil histórico de la posición neta

- Versión sencilla (52 obs.): \( P_t = 100 \times \frac{\#(N_i < N_t)}{M} \)
- Bandas: 0–10 / 10–25 / 25–75 / 75–90 / 90–100.
- También percentil **156 semanas** (~3 años) si hay historial.
- Percentil alto ≠ compra; puede ser saturación.
- **[ABIERTO]** Tratamiento consistente de empates y datos ausentes.

### Criterio 9 — Percentil de la posición neta normalizada

- Guardar `net_percentile_52w` y `normalized_net_percentile_52w`.
- Ambos elevados → evidencia de posicionamiento alto en absoluto y relativo al mercado.

### Criterio 10 — Persistencia del posicionamiento

- `consecutive_net_up`, `consecutive_net_down`
- `positive_net_change_ratio`, `negative_net_change_ratio` en la ventana
- Distingue variación aislada vs. desplazamiento prolongado; **no** garantiza continuidad.

### Criterio 11 — Leveraged Funds (grupo principal especulativo)

Indicadores: neto actual; cambio neto semanal/mensual/trimestral; percentiles 52/156; evolución OI; persistencia; divergencia vs. precio.

Etiquetas (con umbrales definidos y reproducibles):

- Alcista en desarrollo  
- Alcista extendido  
- Deterioro alcista  
- Cambio hacia bajista  
- Bajista extendido  

Neto positivo solo **no** activa “compra”. **[ABIERTO]** Valores numéricos exactos de umbrales por mercado/grupo.

### Criterio 12 — Asset Managers / Institutional

Separado de LF. Indicadores: neto y NN; variación mensual/trimestral; percentil; persistencia; diferencia de dirección vs. LF.

- Ambos Δ netos positivos → confirmación alcista potencial entre grupos.  
- Ambos negativos → confirmación bajista potencial.  
- Uno mejora y otro empeora → señal mixta.  

No asumir que AM predicen mejor el largo plazo sin validación por mercado.

### Criterio 13 — Dealers / Intermediaries

Uso: contexto, divergencia entre categorías, estructura de mercado. **No** puntuar automáticamente alcista/bajista por signo del neto.

### Criterio 14 — Other Reportables y Nonreportable

Complementarios: neto, cambio semanal, tendencia mensual, percentil si hay datos, coincidencia/divergencia con grupos principales. Ponderación inicial **inferior** a los dos grupos principales. **[ABIERTO]** Pesos exactos iniciales no cuantificados en el manual (solo “inferior”).

### Criterio 15 — Spread

Analizar por separado. **No** sumar al neto direccional. Registro de cambio de Spread = contexto; no señal alcista/bajista sin info de vencimientos/estructura.

### Criterio 16 — Tendencia del precio

Rendimiento por horizonte (preferir % para comparar mercados). Clasificación: sube / baja / lateral (umbral **[ABIERTO]**). Fuente de precios alineada al **futuro** analizado, no al spot por defecto.

### Criterio 17 — Confirmación precio × posicionamiento

Cuatro combinaciones por horizonte: confirmación alcista/bajista potencial; divergencia neto↑ precio↓; divergencia neto↓ precio↑. Divergencia ≠ señal de reversión automática.

### Criterio 18 — Posicionamiento extremo y precio

Separado del sesgo direccional. Ejemplo: neto positivo + percentil 97 + precio subiendo → alerta de extensión/riesgo de liquidación, **no** venta automática. Reversión requiere además deterioro persistente del neto, cambio de precio u otro criterio definido.

### Criterio 19 — Open Interest y precio

Combinaciones precio↑/↓ × OI↑/↓ como lectura complementaria. Sin dirección compradora/vendedora inequívoca (cada contrato tiene ambas partes).

### Criterio 20 — Aceleración del cambio neto

Si la magnitud de la variación semanal del neto aumenta o disminuye. Distinto de dirección del precio.

### Criterio 21 — Cambio de régimen

Detectar cruce de signo del neto. Registrar: fecha del cruce, neto anterior/actual, tiempo desde el cruce, dirección, precio antes/después. No es señal de entrada por sí solo.

### Criterio 22 — Divergencia entre grupos

Comparar niveles NN de LF vs. AM **y**, por separado, acuerdo/desacuerdo de **cambios**. No confundir diferencia de niveles con desacuerdo de cambios semanales.

---

## 4. Capas de puntuación, validación e informe

### 4.1 Dos resultados separados

| Resultado | Escala | Significado |
|-----------|--------|-------------|
| **Sesgo direccional** | −2…+2 por criterio; combinado −100…+100 | Orientación alcista/bajista de la evidencia |
| **Calidad de la evidencia** | 0…100 | Consistencia y confirmaciones — **no** probabilidad de subida/bajada |

Evita que una señal extrema pero contradictoria obtenga “alta confianza” automática.

### 4.2 Puntuación direccional por criterio (−2 … +2)

| Valor | Significado |
|-------|-------------|
| +2 / +1 | Evidencia alcista fuerte / moderada |
| 0 | Neutral, mixta o no disponible |
| −1 / −2 | Evidencia bajista moderada / fuerte |

Umbrales calibrados **por mercado y grupo**, p. ej. percentiles de cambios históricos **solo con datos disponibles hasta la fecha evaluada** (sin look-ahead).

### 4.3 Pesos iniciales por horizonte (hipótesis de diseño, no optimizados)

| Horizonte | Peso |
|-----------|------|
| Semanal | 10 % |
| Mensual | 15 % |
| Trimestral | 25 % |
| 6 meses | 25 % |
| 1 año | 25 % |

Puntuación combinada ponderada; escala −100…+100 vía normalización ×50. **Precaución:** ventanas se superponen → las cinco puntuaciones **no** son pruebas independientes.

### 4.4 Clasificación final del sesgo (umbrales provisionales)

| Puntuación | Clasificación |
|------------|---------------|
| +60 … +100 | Fuertemente alcista |
| +25 … &lt; +60 | Moderadamente alcista |
| −25 … &lt; +25 | Neutral o mixto |
| &gt; −60 … −25 | Moderadamente bajista |
| −100 … −60 | Fuertemente bajista |

Comprobar utilidad con pruebas históricas; no tratarlos como probabilidades de éxito.

### 4.5 Calidad de la evidencia (factores)

Disponibilidad/calidad de datos; consistencia de cambios semanales; acuerdo entre horizontes; confirmación entre grupos; confirmación del precio; ausencia de contradicciones importantes.

### 4.6 Reglas de decisión por horizonte (hipótesis iniciales)

Resumen de lo que el motor debe evaluar en cada ventana (detalle completo en el manual §8):

- **Semanal:** Δ neto relevante vs. historial; distinguir ↑Long vs. ↓Short (y simétrico bajista); precio confirma o se registra divergencia.
- **Mensual:** continuidad vs. ~1 mes; proporción de semanas con mejora; OI expandió/contrajo; confirmación / deterioro / mixta.
- **Trimestral:** Δ neto ~13 semanas; percentil; persistencia; contrastar LF vs. AM.
- **Semestral:** percentil ~26 semanas; aproximación a extremos; aceleración/desaceleración; divergencias prolongadas con precio.
- **Anual:** percentiles 52 y 156; cambios de régimen; ciclos anteriores; distinguir extremo de posicionamiento vs. reversión confirmada.

### 4.7 Informe final

No basta con “alcista/bajista”: explicar **por qué**. Salida estructurada (JSON) con `market`, `report_type`, `as_of_date`, bloques por timeframe, `combined_bias`, `evidence_quality`, `warnings`. Valores `null` = aún no calculados; **nunca** inventar cifras.

Módulos Python sugeridos por el manual: `data_loader`, `data_validation`, `cot_indicators`, `timeframes`, `scoring`, `price_confirmation`, `report`; pesos/umbrales en `config/scoring_rules.json`.

Estructura de carpetas propuesta:

```
cot_system/
├── data/{raw,processed,price}/
├── config/scoring_rules.json
├── src/{data_loader,data_validation,cot_indicators,timeframes,scoring,price_confirmation,report}.py
├── tests/{test_indicators,test_scoring}.py
└── main.py
```

---

## 5. Fases de implementación (Python) — MVP → sistema completo

Orden del manual: **no** programar todas las variables a la vez. Verificar por fases.

| Fase | Qué construir | Criterio para avanzar |
|------|---------------|------------------------|
| **1** | Importación y limpieza | Datos se leen y validan |
| **2** | Neto, cambios y OI | Fórmulas coinciden con origen |
| **3** | Ventanas históricas | Cinco horizontes con fechas correctas |
| **4** | Percentiles y persistencia | Cálculos OK con historial suficiente |
| **5** | Puntuación | Cada resultado explicable por reglas |
| **6** | Confirmación del precio | Fechas y contratos comparables |
| **7** | Backtesting | Histórico + fuera de muestra |
| **8** | Informe automatizado | Resultados reproducibles y alertas verificables |

**Recomendación del manual:** empezar por **fases 1–4**; luego motor de puntuación auditable.

### Hitos concretos para el primer tramo (MVP técnico)

1. **Hito A — Fuente y esquema:** elegir fuente COT + mercados piloto; esquema de tablas con campos §2.2; `report_type` explícito.
2. **Hito B — Loader + validación:** `data_loader` + `data_validation` (fechas, duplicados, ausentes ≠ 0, cambios recalculados vs. publicados, OI único por fecha).
3. **Hito C — Indicadores base:** Criterios 1–6 en `cot_indicators` con tests unitarios contra filas conocidas del informe.
4. **Hito D — Horizontes:** Criterio 7 + marco de ventanas (1 / 4–5 / 13 / 26 / 52) por fechas reales.
5. **Hito E — Extremos y persistencia:** Criterios 8–10 (52w; 156w si hay datos); tests de empates/ausentes documentados.
6. **Después (fases 5–8):** scoring_rules.json, etiquetas por grupo (11–15), precio (16–19), aceleración/régimen/divergencia (20–22), backtest, informe JSON.

---

## 6. Decisiones abiertas que Jefferson debe fijar antes de codificar

| # | Decisión | Por qué importa |
|---|----------|-----------------|
| 1 | **Fuente de datos COT** (CFTC directa, proveedor, CSV/Excel propio, etc.) | Define loader, campos y frecuencia |
| 2 | **Mercados / contratos piloto** (lista corta vs. universo amplio) | Calibración y tests |
| 3 | **Tipo de informe: TFF vs. Legacy (o ambos)** | Organización de grupos, pesos y reglas — el manual lo marca como decisión importante |
| 4 | **Grupos principales** (¿LF + AM como foco TFF?) | Pesos y divergencias entre grupos |
| 5 | **Lenguaje/stack** (manual asume Python; ¿confirmar?) | Repo, libs, despliegue |
| 6 | **Backtest histórico vs. informe live semanal** (prioridad inicial) | Diseño de fechas de publicación y producto |
| 7 | **Fuente de precios** alineada al futuro (no spot por defecto) | Fase 6 |
| 8 | **Umbrales numéricos** (neutral, relevancia semanal, lateral de precio, etiquetas LF, pesos Other/Nonreportable) | Muchos son hipótesis a calibrar |
| 9 | **Tratamiento de empates/ausentes en percentiles** | Reproducibilidad del Criterio 8 |
| 10 | **Formato de entrega del informe** (solo JSON, tablas, gráficos, alertas) | Alcance de la fase 8 |

---

## 7. Próximo paso recomendado (esta semana)

**Empezar juntos la Fase 1 del MVP**, sin saltar a scoring ni a señales:

1. Jefferson responde las decisiones **1–4 y 5** de la tabla (§6), especialmente **fuente + mercados piloto + TFF vs. Legacy**.
2. En la misma semana: esqueleto `cot_system/` + `data_loader` / `data_validation` + un mercado de prueba con datos reales o muestra controlada.
3. Criterio de éxito de la semana: un dataset limpio, validado, con cambios recalculados documentados y OI correcto — listo para Fase 2 (neto / NN / Δ / acumulación).

Hasta que 1–4 estén claros, **no** conviene invertir en motor de puntuación ni backtest.

---

## Referencia

- Manual fuente: `docs/COT_Algoritmo.docx`
- Texto extraído: `internal/cot-algoritmo-full.txt`
