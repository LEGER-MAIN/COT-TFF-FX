"""Self-contained HTML (+ JSON) reports for FX TFF COT (indicators + provisional scoring)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .cot_indicators import latest_snapshot, market_summary
from .data_validation import ValidationReport
from .scoring import scored_to_json_payload
from .timeframes import HORIZON_ORDER


def _short_market(name: str) -> str:
    return name.split(" - ")[0].strip()


def _wrap_tbl_scroll(table_markup: str) -> str:
    """Wrap a wide <table> so it gets synced horizontal scrollbars (top + bottom)."""
    return (
        '<div class="tbl-scroll-wrap">'
        '<div class="tbl-scroll-top" aria-hidden="true">'
        '<div class="tbl-scroll-top-inner"></div></div>'
        f'<div class="tbl-scroll-main">{table_markup}</div>'
        "</div>"
    )


def _tbl_scroll_js() -> str:
    """Sync top/bottom horizontal scroll; hide top bar when table fits."""
    return """
<script>
(function () {
  function wire(wrap) {
    var top = wrap.querySelector(".tbl-scroll-top");
    var main = wrap.querySelector(".tbl-scroll-main");
    var inner = wrap.querySelector(".tbl-scroll-top-inner");
    var table = main && main.querySelector("table");
    if (!top || !main || !inner || !table) return;
    var syncing = false;
    function sizeTop() {
      inner.style.width = table.scrollWidth + "px";
      var need = table.scrollWidth > main.clientWidth + 1;
      wrap.classList.toggle("needs-hscroll", need);
      if (!need) {
        top.scrollLeft = 0;
        main.scrollLeft = 0;
      }
    }
    top.addEventListener("scroll", function () {
      if (syncing) return;
      syncing = true;
      main.scrollLeft = top.scrollLeft;
      syncing = false;
    });
    main.addEventListener("scroll", function () {
      if (syncing) return;
      syncing = true;
      top.scrollLeft = main.scrollLeft;
      syncing = false;
    });
    sizeTop();
    if (typeof ResizeObserver !== "undefined") {
      var ro = new ResizeObserver(sizeTop);
      ro.observe(main);
      ro.observe(table);
    }
    window.addEventListener("resize", sizeTop);
  }
  function init() {
    document.querySelectorAll(".tbl-scroll-wrap").forEach(wire);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
</script>
"""


def _bias_class_css(label: str | None) -> str:
    if not label:
        return ""
    if "fuertemente_alcista" in label:
        return "bias-strong-up"
    if "moderadamente_alcista" in label:
        return "bias-up"
    if "fuertemente_bajista" in label:
        return "bias-strong-down"
    if "moderadamente_bajista" in label:
        return "bias-down"
    return "bias-neutral"


def _weekly_html_section(weekly: pd.DataFrame | None) -> str:
    if weekly is None or weekly.empty:
        return ""
    from .weekly_recommendations import SECTION_ORDER

    blocks: list[str] = []
    blocks.append(
        """
  <section class="market weekly" id="recomendacion-semanal">
    <h2>Recomendación semanal</h2>
    <p class="sub">Pares swing agrupados por sección tras el scoring COT.
    Prioridad según |sesgo|, calidad de evidencia y confirmación de precio.
    Avisos si hay exposición correlacionada (p. ej. USDJPY + GBPJPY).
    <strong>No es señal de compra automática.</strong></p>
"""
    )
    show_cols = [
        "rank_in_section",
        "symbol",
        "priority",
        "pair_bias",
        "pair_bias_label",
        "evidence_quality",
        "opportunity_score",
        "direction_hint",
        "price_confirm_state",
        "coverage",
        "cot_backed",
        "por_que",
        "riesgo",
        "correlation_warnings",
    ]

    def _tbl(df: pd.DataFrame) -> str:
        show = df.copy()
        for c in show.columns:
            if show[c].dtype.kind == "f":
                show[c] = pd.to_numeric(show[c], errors="coerce").round(2)
        # Allow wrapping on long Spanish text columns
        html_tbl = show.to_html(
            index=False, na_rep="—", classes="tbl weekly-tbl", border=0, escape=True
        )
        return _wrap_tbl_scroll(html_tbl)

    ordered_sections = [s for s in SECTION_ORDER if s in set(weekly["section"].tolist())]
    extra = [s for s in weekly["section"].unique() if s not in ordered_sections]
    for sec in ordered_sections + extra:
        part = weekly.loc[weekly["section"] == sec].sort_values(
            ["rank_in_section", "opportunity_score"], ascending=[True, False]
        )
        label = html.escape(str(part["section_label"].iloc[0]) if "section_label" in part else sec)
        cols = [c for c in show_cols if c in part.columns]
        blocks.append(f"    <h3>{label}</h3>\n    {_tbl(part[cols])}\n")

    blocks.append("  </section>\n")
    return "".join(blocks)


def _backtest_html_section(backtest: dict[str, Any] | None) -> str:
    if not backtest:
        return ""
    req = html.escape(str(backtest.get("requested_as_of") or ""))
    eff = html.escape(str(backtest.get("effective_as_of") or ""))
    note = html.escape(
        str(
            backtest.get("note_es")
            or "Solo datos hasta esta semana (sin look-ahead)."
        )
    )
    return f"""
  <section class="market" id="backtest-as-of">
    <h2>Backtest · as-of</h2>
    <p class="sub">Modo retrospectivo — mismos scoring y recomendación semanal que el informe en vivo.</p>
    <div class="meta">
      <div><span>As-of solicitado</span><strong>{req}</strong></div>
      <div><span>Semana COT efectiva</span><strong>{eff}</strong></div>
      <div><span>Look-ahead</span><strong>ninguno</strong></div>
    </div>
    <p><strong>Solo datos hasta esta semana.</strong> {note}</p>
    <p>Filtro: <code>report_date &lt;= as-of</code> y <code>price_date &lt;= as-of</code>
    aplicados <em>antes</em> de indicadores, percentiles, scoring y pares swing.</p>
  </section>
"""


def _week_picker_section(
    validation: ValidationReport,
    backtest: dict[str, Any] | None = None,
) -> str:
    """Dual-month Sun–Sat week calendar → Saturday as --as-of."""
    from .week_calendar import calendar_html_section

    initial = None
    if backtest and backtest.get("requested_as_of"):
        initial = str(backtest["requested_as_of"])
    elif validation.as_of_date:
        initial = str(validation.as_of_date)
    return calendar_html_section(initial_as_of=initial)


def write_html(
    indicators: pd.DataFrame,
    validation: ValidationReport,
    path: Path,
    scored: pd.DataFrame | None = None,
    rules: dict[str, Any] | None = None,
    price_meta: dict[str, Any] | None = None,
    weekly: pd.DataFrame | None = None,
    backtest: dict[str, Any] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    latest = latest_snapshot(indicators)
    summary = market_summary(latest)

    warnings_html = ""
    if validation.warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in validation.warnings)
        warnings_html = f'<div class="warn"><h2>Advertencias de calidad de datos</h2><ul>{items}</ul></div>'
    else:
        warnings_html = '<div class="ok"><p>Sin advertencias críticas de calidad de datos.</p></div>'

    backtest_section = _backtest_html_section(backtest)
    week_picker_section = _week_picker_section(validation, backtest)
    from .week_calendar import calendar_css

    title_suffix = " — Backtest" if backtest else ""
    header_extra = (
        " <strong>Informe de backtest</strong> (histórico truncado a as-of)."
        if backtest
        else ""
    )

    def table_html(df: pd.DataFrame, float_cols: list[str] | None = None) -> str:
        show = df.copy()
        if "report_date" in show.columns:
            show["report_date"] = pd.to_datetime(show["report_date"]).dt.strftime("%Y-%m-%d")
        if "as_of_date" in show.columns:
            show["as_of_date"] = pd.to_datetime(show["as_of_date"]).dt.strftime("%Y-%m-%d")
        if "market" in show.columns:
            show["market"] = show["market"].map(_short_market)
        float_cols = float_cols or [
            c
            for c in show.columns
            if show[c].dtype.kind == "f" or str(show[c].dtype) in ("Float64", "float64")
        ]
        for c in float_cols:
            if c in show.columns:
                show[c] = pd.to_numeric(show[c], errors="coerce").round(2)
        raw = show.to_html(index=False, na_rep="—", classes="tbl", border=0, escape=True)
        return _wrap_tbl_scroll(raw)

    # Scoring board
    scoring_section = ""
    market_score_sections: list[str] = []
    if scored is not None and not scored.empty:
        board_cols = [
            c
            for c in [
                "market",
                "combined_bias",
                "combined_bias_label",
                "evidence_quality",
                "LF_bias",
                "AM_bias",
                "OR_bias",
                "NR_bias",
                "LF_pctl_52w",
                "AM_pctl_52w",
                "c22_weekly_change_agreement",
                "price_ticker",
                "price_close",
                "dealer_nn_pct",
            ]
            if c in scored.columns
        ]
        provisional_banner = ""
        if rules and rules.get("provisional"):
            provisional_banner = (
                '<div class="warn"><strong>Umbrales provisionales.</strong> '
                "Sesgo (−100…+100) y calidad (0…100) usan reglas en "
                "<code>config/scoring_rules.json</code>. "
                "No son señales de compra/venta ni probabilidades.</div>"
            )
        scoring_section = f"""
  {provisional_banner}
  <section class="market">
    <h2>Sesgo direccional + calidad de evidencia</h2>
    <p class="sub">Foco LF + Asset Managers; Other/Nonreportable peso complementario bajo; Dealers y Spread solo contexto. Precio Yahoo si está mapeado. Horizontes ponderados (sem/1m/3m/6m/1y).</p>
    {table_html(scored[board_cols])}
  </section>
"""
        for _, row in scored.iterrows():
            title = html.escape(_short_market(str(row["market"])))
            full = html.escape(str(row["market"]))
            label = row.get("combined_bias_label")
            css = _bias_class_css(None if pd.isna(label) else str(label))
            bias = row.get("combined_bias")
            quality = row.get("evidence_quality")
            warns = [
                w.strip() for w in str(row.get("warnings") or "").split("|") if w.strip()
            ]
            warn_block = ""
            if warns:
                warn_block = "<ul class='mwarn'>" + "".join(
                    f"<li>{html.escape(w)}</li>" for w in warns
                ) + "</ul>"

            # Horizon mini-table from group detail
            hz_rows = []
            for sg in row.get("_groups_detail") or []:
                tg = sg.get("trader_group")
                for h in HORIZON_ORDER:
                    hd = sg.get("horizons", {}).get(h, {})
                    hz_rows.append(
                        {
                            "grupo": tg,
                            "horizonte": h,
                            "direccion": hd.get("direction"),
                            "Δ neto": hd.get("net_change"),
                            "Δ neto/OI %": hd.get("net_change_nn_pct"),
                            "precio %": hd.get("price_return_pct"),
                            "precio dir": hd.get("price_direction"),
                            "confirmación": hd.get("price_position_confirm"),
                            "score (−2…+2)": hd.get("horizon_score_m2_p2"),
                        }
                    )
            hz_html = table_html(pd.DataFrame(hz_rows)) if hz_rows else "<p>—</p>"

            lf_bias = row.get("LF_bias")
            am_bias = row.get("AM_bias")
            or_bias = row.get("OR_bias")
            nr_bias = row.get("NR_bias")
            dealer_nn = row.get("dealer_nn_pct")
            c22 = row.get("c22_weekly_change_agreement")
            px_t = row.get("price_ticker")
            px_c = row.get("price_close")
            def _fmt(v, nd=None):
                if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
                    return "—"
                if nd is not None:
                    try:
                        return str(round(float(v), nd))
                    except (TypeError, ValueError):
                        return str(v)
                return str(v)

            market_score_sections.append(
                f"""
  <section class="market {css}">
    <h2>{title}</h2>
    <p class="sub">{full}</p>
    <div class="meta">
      <div><span>Sesgo combinado</span><strong>{html.escape(_fmt(bias))}</strong>
        <em>{html.escape(_fmt(label) if label is not None and not (isinstance(label, float) and pd.isna(label)) else '')}</em></div>
      <div><span>Calidad evidencia</span><strong>{html.escape(_fmt(quality))}</strong>/100</div>
      <div><span>LF bias</span><strong>{html.escape(_fmt(lf_bias))}</strong></div>
      <div><span>AM bias</span><strong>{html.escape(_fmt(am_bias))}</strong></div>
      <div><span>OR / NR bias</span><strong>{html.escape(_fmt(or_bias))} / {html.escape(_fmt(nr_bias))}</strong></div>
      <div><span>C22 Δ LF–AM</span><strong>{html.escape(_fmt(c22))}</strong></div>
      <div><span>Precio</span><strong>{html.escape(_fmt(px_t))}</strong>
        <em>{html.escape(_fmt(px_c, 4))}</em></div>
      <div><span>Dealer NN% (ctx)</span><strong>{html.escape(_fmt(dealer_nn, 2))}</strong></div>
    </div>
    {warn_block}
    <h3>Desglose por horizonte</h3>
    {hz_html}
  </section>
"""
            )

    # Per-market latest indicator tables
    market_sections = []
    for market, g in latest.groupby("market", sort=True):
        title = html.escape(_short_market(str(market)))
        full = html.escape(str(market))
        cols = [
            "trader_group",
            "net_position",
            "normalized_net_pct",
            "delta_net_weekly",
            "delta_net_label",
            "accum_liq_pattern",
            "open_interest_total",
            "oi_change_pct",
            "pct_oi_long_calc",
            "pct_oi_short_calc",
            "net_percentile_52w",
            "net_percentile_156w",
            "consecutive_net_up",
            "consecutive_net_down",
            "net_change_accel_label",
            "spreading_positions",
            "spread_change_label",
            "weeks_since_regime_cross",
            "regime_direction",
            "price_close",
            "price_direction_monthly",
            "price_position_confirm_monthly",
        ]
        body = table_html(g[[c for c in cols if c in g.columns]])
        market_sections.append(
            f'<section class="market"><h2>{title} — indicadores</h2>'
            f'<p class="sub">{full}</p>{body}</section>'
        )

    markets_list = ", ".join(
        html.escape(_short_market(m)) for m in sorted(indicators["market"].unique())
    )
    ver = html.escape(str((rules or {}).get("version", "n/a")))
    px_note = html.escape(
        str((price_meta or {}).get("source") or (price_meta or {}).get("provider") or "sin precio")
    )

    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>COT TFF FX + DXY — Informe{title_suffix}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
  :root {{
    --bg: #eef2f0;
    --ink: #1a2220;
    --accent: #0d5c4d;
    --warn: #7a3e12;
    --line: #c5d0cb;
    --card: #fbfcfb;
    --up: #0d5c4d;
    --down: #8b2e2e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    color: var(--ink);
    background:
      radial-gradient(1100px 480px at 8% -8%, #cfe6df 0%, transparent 55%),
      radial-gradient(800px 360px at 100% 0%, #d9e2ea 0%, transparent 50%),
      var(--bg);
    line-height: 1.45;
  }}
  header {{
    padding: 2.2rem 1.5rem 1.2rem;
    border-bottom: 1px solid var(--line);
  }}
  header h1 {{
    margin: 0 0 .35rem;
    font-size: clamp(1.6rem, 3vw, 2.2rem);
    letter-spacing: -0.02em;
    color: var(--accent);
  }}
  header p {{ margin: .2rem 0; max-width: 72ch; }}
  main {{ padding: 1.25rem 1.5rem 3rem; max-width: 1200px; margin: 0 auto; }}
  .meta {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: .75rem;
    margin: 1rem 0 1.25rem;
  }}
  .meta div {{
    background: var(--card);
    border: 1px solid var(--line);
    padding: .75rem .9rem;
  }}
  .meta span {{ display:block; font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; opacity: .7; }}
  .meta strong {{ font-size: 1.05rem; }}
  .meta em {{ display:block; font-style: normal; font-size: .8rem; opacity: .75; margin-top: .15rem; }}
  .warn {{ background: #fff1e4; border: 1px solid #e0b48a; padding: .9rem 1rem; margin-bottom: 1.25rem; color: var(--warn); }}
  .ok {{ background: #e8f4ef; border: 1px solid #9fc9b8; padding: .7rem 1rem; margin-bottom: 1.25rem; }}
  section.market {{
    margin: 1.5rem 0;
    background: var(--card);
    border: 1px solid var(--line);
    padding: 1rem;
  }}
  section.market h2 {{ margin: 0; color: var(--accent); }}
  section.market h3 {{ margin: 1rem 0 .4rem; font-size: 1rem; }}
  section.bias-strong-up {{ border-left: 4px solid var(--up); }}
  section.bias-up {{ border-left: 4px solid #3a8f78; }}
  section.bias-strong-down {{ border-left: 4px solid var(--down); }}
  section.bias-down {{ border-left: 4px solid #b05a5a; }}
  section.bias-neutral {{ border-left: 4px solid #8a9290; }}
  .sub {{ margin: .15rem 0 0.8rem; font-size: .85rem; opacity: .75; }}
  ul.mwarn {{ margin: .4rem 0 1rem; padding-left: 1.2rem; color: var(--warn); font-size: .9rem; }}
  .tbl-scroll-wrap {{ margin: .25rem 0 .75rem; }}
  .tbl-scroll-top {{
    display: none;
    overflow-x: auto;
    overflow-y: hidden;
    height: 14px;
    margin-bottom: 2px;
  }}
  .tbl-scroll-wrap.needs-hscroll .tbl-scroll-top {{ display: block; }}
  .tbl-scroll-top-inner {{ height: 1px; pointer-events: none; }}
  .tbl-scroll-main {{ overflow-x: auto; }}
  table.tbl {{
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: .88rem;
  }}
  table.tbl th, table.tbl td {{
    border-bottom: 1px solid var(--line);
    padding: .45rem .5rem;
    text-align: left;
    white-space: nowrap;
  }}
  table.tbl th {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .03em; }}
  table.weekly-tbl td {{ white-space: normal; max-width: 28rem; vertical-align: top; }}
  section.weekly h3 {{ margin: 1.1rem 0 .35rem; color: var(--ink); font-size: 1.05rem; }}
  .prio-alta {{ color: var(--accent); font-weight: 600; }}
  footer {{ padding: 1rem 1.5rem 2rem; font-size: .85rem; opacity: .75; }}
  {calendar_css()}
</style>
</head>
<body>
<header>
  <h1>COT · TFF FX + USD INDEX (DXY){title_suffix}</h1>
  <p>Indicadores (Criterios 1–10, 15–22) y scoring dual provisional
  (sesgo −100…+100 + calidad 0…100). Fuente CFTC Futures Only (F10 + F15 si hay + USD INDEX F90).
  Precio: {px_note}. Posicionamiento reportado; <strong>no es señal de compra/venta</strong>.
  Incluye <a href="#recomendacion-semanal">recomendación semanal</a> de pares swing
  y <a href="#week-picker">calendario semanal</a> para regenerar backtest.{header_extra}</p>
</header>
<main>
  <div class="meta">
    <div><span>As-of</span><strong>{html.escape(str(validation.as_of_date))}</strong></div>
    <div><span>Desde</span><strong>{html.escape(str(validation.min_date))}</strong></div>
    <div><span>Mercados</span><strong>{validation.n_markets}</strong></div>
    <div><span>Semanas</span><strong>{validation.n_dates}</strong></div>
    <div><span>Filas</span><strong>{validation.n_rows}</strong></div>
    <div><span>Scoring</span><strong>{ver}</strong></div>
  </div>
  {week_picker_section}
  {backtest_section}
  {warnings_html}
  {scoring_section}
  {_weekly_html_section(weekly)}
  {''.join(market_score_sections)}
  <section class="market">
    <h2>Resumen indicadores — Leveraged Funds &amp; Asset Managers</h2>
    <p class="sub">Mercados: {markets_list}</p>
    {table_html(summary)}
  </section>
  {''.join(market_sections)}
</main>
<footer>
  Fuente: CFTC <code>fut_fin_txt_YYYY.zip</code> (Traders in Financial Futures, Futures Only).
  Universo: F10 + F15 (NZD/BRL) + <strong>USD INDEX</strong> (ICE, F90 / 098662);
  excluidos MXN / ZAR / CNH vía <code>exclude_markets</code>.
  Generado por <code>cot_system/main.py</code>.
  Validación: OI duplicados={validation.oi_duplicate_market_dates};
  mismatches de cambio={validation.change_mismatch_rows}.
  Umbrales: <code>config/scoring_rules.json</code> (provisional={html.escape(str(bool((rules or {}).get('provisional', True))))}).
</footer>
{_tbl_scroll_js()}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")

    side = path.with_suffix(".json")
    if scored is not None and rules is not None:
        payload = scored_to_json_payload(
            scored, validation.to_dict(), rules, price_meta=price_meta, weekly=weekly
        )
        payload["markets_list"] = sorted(indicators["market"].unique().tolist())
        payload["latest_summary"] = json.loads(
            summary.assign(
                report_date=pd.to_datetime(summary["report_date"]).dt.strftime("%Y-%m-%d")
            ).to_json(orient="records")
        )
    else:
        payload = {
            "report_type": "TFF",
            "as_of_date": validation.as_of_date,
            "min_date": validation.min_date,
            "markets": sorted(indicators["market"].unique().tolist()),
            "validation": validation.to_dict(),
            "latest_summary": json.loads(
                summary.assign(
                    report_date=pd.to_datetime(summary["report_date"]).dt.strftime("%Y-%m-%d")
                ).to_json(orient="records")
            ),
        }
    if backtest:
        payload["backtest"] = backtest
        payload["mode"] = backtest.get("mode", "backtest")
    side.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path
