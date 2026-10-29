# Datos y calidad

## Para qué sirve

Asegurar que el sistema interpreta **posiciones reportadas reales** (no inventadas), con el **tipo de informe correcto** y reglas de integridad antes de calcular indicadores o sesgo.

## Entradas que usa

| Entrada | Origen / detalle |
|---------|------------------|
| Informes TFF Futures Only | CFTC `fut_fin_txt_{YYYY}.zip` + semanal `FinFutWk.txt` |
| Filtro de mercado | `CFTC_SubGroup_Code == F10` **o** USD INDEX (F90 / `098662`) — `config/markets.json` |
| Universo | **9 mercados**: 8 FX F10 + **USD INDEX / DXY** |
| Tipo de informe | **TFF** (no Legacy). Categorías: Dealer, Asset Manager, Leveraged Funds, Other Reportables, Nonreportable |
| Campos base | `market`, `report_date`, `trader_group`, long/short/spread, cambios publicados, `open_interest_total`, % OI reportados si existen |

Pipeline: `data_loader.py` → `data_validation.validate_and_enrich` → indicadores.

## Cómo leer cada resultado

### Tipo de informe

| Valor | Significado |
|-------|-------------|
| TFF | Traders in Financial Futures — grupos financieros (LF, AM, etc.) |
| Legacy | No usado en este pipeline — **no intercambiar** lecturas |

### Campos del informe de validación (`ValidationReport`)

| Campo | Qué significa |
|-------|----------------|
| `as_of_date` / `min_date` | Última y primera fecha de posicionamiento en la serie |
| `n_markets` / `n_dates` / `n_rows` | Cobertura del dataset filtrado FX |
| `oi_duplicate_market_dates` | Pares mercado/fecha con OI distinto entre grupos (debe ser 0) |
| `change_mismatch_rows` | Filas donde el cambio publicado ≠ diferencia entre semanas consecutivas |
| `missing_position_cells` | Celdas NA en long/short/OI (**no** se rellenan con 0) |
| `warnings` | Mensajes humanos (historial corto, mismatches, OI no único, etc.) |

### Cambios recalculados

| Columna | Lectura |
|---------|---------|
| `long_change` / `short_change` | Publicados por CFTC |
| `*_change_recalc` | Diferencia de posiciones semana a semana |
| Preferencia en indicadores | Se usa `*_recalc` si existe; si no, el publicado (`long_change_used` / `short_change_used`) |

Un mismatch no invalida todo el informe: suele deberse a la primera semana de la serie, revisiones CFTC o huecos. Debe documentarse, no ocultarse.

### Open Interest

| Regla | Lectura |
|-------|---------|
| OI único por mercado × fecha | Correcto: mismo total en todas las filas de grupo |
| Sumar OI de todos los grupos | **Incorrecto** — contaría el mercado varias veces |

### Ausente vs cero

| Valor | Significado |
|-------|-------------|
| `0` | El informe reporta cero posiciones / cero cambio |
| Ausente (`null` / NA) | Información no disponible — **no** tratar como cero |

## Esto NO es señal de compra/venta

Tener datos limpios solo permite confiar en el cálculo. Un dataset válido **no** implica dirección operativa.

## Umbrales / notas provisionales

- Aviso de historial corto: mercados con **&lt; 52** semanas de observaciones (percentiles limitados).
- No hay umbral de “calidad de datos” numérico aparte del conteo de warnings y celdas NA.
- Legacy, precios y backtest quedan fuera de esta capa.
