# COT TFF FX

**ES** · Pipeline Python para *Traders in Financial Futures* (CFTC) sobre FX + USD INDEX (DXY).  
Salidas: **HTML + JSON** (sin Excel). Calendario semanal y backtest as-of sin look-ahead.

**EN** · Python pipeline for CFTC TFF FX + DXY. Outputs: **HTML + JSON** only. Week calendar + as-of backtest (no look-ahead).

> No es señal de compra/venta. Sesgo ≠ entrada; calidad ≠ probabilidad.

---

## Layout

```text
EJECUTAR_COT.bat          ← único punto de entrada Windows
ABRIR_CALENDARIO.bat      ← redirect → EJECUTAR_COT.bat --serve
cot_system/
  main.py                 pipeline
  report_server.py        http://127.0.0.1:8765/
  requirements.txt        pandas 2.2.3 / numpy 2.2.6 (Windows SAC)
  config/markets.json     universo + swing pairs
  src/                    indicadores, scoring, weekly, as-of, HTML
  tests/                  fixtures + golden + pytest
  data/                   raw / processed / price
docs/
  guide/                  guía por apartado
  reports/                HTML + JSON generados
  guia-cot.md
```

Universo: F10 + F15 (**NZD, BRL**) + DXY. **Excluidos:** MEXICAN PESO, SO AFRICAN RAND, USD/CHINESE RENMINBI-OFFSHORE (y pares USDMXN / USDZAR / USDCNH).

---

## Windows (recomendado)

Doble clic en la raíz:

```text
EJECUTAR_COT.bat
```

1. Busca Python **3.12** (luego 3.11 / 3.10)  
2. Crea `cot_system\.venv` e instala pins  
3. Ejecuta el pipeline  
4. Abre **http://127.0.0.1:8765/** (deja la ventana abierta; **no** abras el HTML a doble clic)

| Comando | Efecto |
|---------|--------|
| `EJECUTAR_COT.bat` | Pipeline + servidor HTML |
| `EJECUTAR_COT.bat --serve` | Solo calendario / servidor |
| `EJECUTAR_COT.bat --test` | pytest |
| `EJECUTAR_COT.bat --as-of 2025-06-17` | Backtest as-of |
| `EJECUTAR_COT.bat --skip-price` | Sin Yahoo |
| `EJECUTAR_COT.bat --from-csv-only` | Regenera HTML desde CSV (sin pandas) |

`ABRIR_CALENDARIO.bat` y `cot_system\EJECUTAR_COT.bat` son redirects al BAT de la raíz.

---

## Linux / macOS

```bash
cd cot_system
python3 -m pip install -r requirements.txt
python3 main.py
python3 main.py --as-of 2025-06-17
python3 report_server.py          # http://127.0.0.1:8765/
python3 -m pytest tests -q        # o: EJECUTAR_COT.bat --test en Windows
```

---

## Tests

Fixtures + resultados esperados en `cot_system/tests/fixtures/` y `cot_system/tests/golden/`.

```bash
cd cot_system && python3 -m pytest tests -q
# Windows: EJECUTAR_COT.bat --test
```

---

## Fuente

| Qué | Detalle |
|-----|---------|
| CFTC TFF Futures Only | `fut_fin_txt_{YYYY}.zip` |
| Semanal | `FinFutWk.txt` |
| Precio | Yahoo weekly (`config/markets.json`) |

Guía: [`docs/guia-cot.md`](docs/guia-cot.md) · Backtest: [`docs/guide/backtest-as-of.md`](docs/guide/backtest-as-of.md)
