# Guía COT por apartado — índice

Documentación en español para leer cada bloque del sistema de evaluación cuantitativa COT (TFF FX + **USD INDEX / DXY**): **para qué sirve** y **qué significa cada resultado** en ese lugar.

**Universo:** FX **F10** + **F15** (NZD/MXN/BRL/ZAR si están en CFTC) + **USD INDEX** (**F90** / `098662`, DXY). Scoring `0.3-provisional`. Incluye **recomendación semanal** de pares swing.

**Esto no es una señal de compra/venta.** El COT mide posicionamiento reportado. El sesgo orienta la evidencia; la calidad mide consistencia — no probabilidad de que el precio suba o baje.

## Cómo usar esta guía

1. Empieza por el [hub](../guia-cot.md) si quieres el acceso rápido al informe HTML.
2. Lee el apartado que corresponda a la columna o panel del informe.
3. Cuando veas **PROVISIONAL**, el umbral vive en `cot_system/config/scoring_rules.json` y **no** está calibrado por mercado.

## Apartados

| # | Documento | Criterios / capa | Estado en código |
|---|-----------|------------------|------------------|
| 1 | [Datos y calidad](datos-y-calidad.md) | Fuente TFF, validación §2 | Implementado (F10 + DXY F90) |
| 2 | [Indicadores básicos](indicadores-basicos.md) | Criterios 1–6 | Implementado |
| 3 | [Horizontes históricos](horizontes-historicos.md) | Criterios 7–10 | Implementado |
| 4 | [Grupos participantes](grupos-participantes.md) | Criterios 11–15 | Implementado (LF/AM + OR/NR peso bajo; Dealer/Spread contexto) |
| 5 | [Precio y confirmación](precio-y-confirmacion.md) | Criterios 16–19 | Implementado (Yahoo; DXY=`DX-Y.NYB`; umbrales provisionales) |
| 6 | [Scoring y calidad](scoring-y-calidad.md) | Sesgo + evidencia §4 | Implementado (umbrales provisionales) |
| 7 | [Reglas por horizonte](reglas-por-horizonte.md) | Manual §8 + scoring real | Implementado (COT + blend suave de precio) |
| 8 | [Aceleración, régimen, divergencia](aceleracion-regimen-divergencia.md) | Criterios 20–22 | Implementado |
| 9 | [Informe y alertas](informe-y-alertas.md) | Salida HTML/JSON | Implementado |
| 9b | [Recomendación semanal](recomendacion-semanal.md) | Pares swing por sección | Implementado |
| 9c | [Backtest as-of](backtest-as-of.md) | Semana pasada, sin look-ahead | Implementado (`--as-of`) |
| 10 | [Controles y límites](controles-y-limites.md) | Checklist §12 | Parcial (backtest semanal sí; OOS/PnL no) |

## Fuentes de verdad

| Documento / artefacto | Uso |
|-----------------------|-----|
| [Plan](../cot-plan.md) | Diseño y alcance explícito |
| Manual `docs/COT_Algoritmo.docx` / `internal/cot-algoritmo-full.txt` | Texto fuente |
| `internal/cot-full-coverage-handoff.md` | Cobertura 16–22 + DXY |
| `cot_system/config/{scoring_rules,markets}.json` | Umbrales y tickers reales |
| `cot_system/src/{cot_indicators,price_confirmation,scoring,report}.py` | Comportamiento implementado |
| [Informe HTML latest](../reports/cot_tff_fx_latest.html) | Lectura operativa |

Si el plan y el código discrepan, **esta guía documenta lo que hace el código**.
