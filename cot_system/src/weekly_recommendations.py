"""Recomendación semanal de pares swing a partir del scoring COT + mapa en markets.json.

No es señal de compra automática. Agrupa por secciones, prioriza por sesgo/calidad/
confirmación de precio y avisa de exposición correlacionada.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .data_loader import load_market_config
from .scoring import classify_bias


SECTION_ORDER = ("majors_usd", "crosses", "indice_dxy", "opcionales")

SECTION_LABELS = {
    "majors_usd": "Majors USD",
    "crosses": "Crosses",
    "indice_dxy": "Índice DXY",
    "opcionales": "Opcionales (NZD/BRL)",
}

BIAS_ES = {
    "fuertemente_alcista": "fuertemente alcista",
    "moderadamente_alcista": "moderadamente alcista",
    "neutral_o_mixto": "neutral o mixto",
    "moderadamente_bajista": "moderadamente bajista",
    "fuertemente_bajista": "fuertemente bajista",
}


def _short_market(name: str) -> str:
    return str(name).split(" - ")[0].strip()


def _norm_mkt(name: str) -> str:
    """Normalize CFTC short names (strip XRATE suffix, collapse spaces)."""
    s = str(name).strip().upper().replace(" XRATE", "").replace("  ", " ")
    return s.strip()


def _find_scored_row(scored: pd.DataFrame, market_key: str) -> pd.Series | None:
    """Match config key to scored market by normalized short name (text before ' - ')."""
    key = _norm_mkt(market_key)
    for _, row in scored.iterrows():
        short = _norm_mkt(_short_market(str(row["market"])))
        if short == key:
            return row
    return None


def _price_confirm_summary(row: pd.Series) -> tuple[str, float]:
    """Return (label, factor) from LF/AM monthly/weekly confirm columns if present."""
    labels: list[str] = []
    for prefix in ("LF", "AM"):
        for h in ("weekly", "monthly", "quarterly"):
            col = f"{prefix}_{h}_px_confirm"
            if col in row.index and not pd.isna(row.get(col)):
                labels.append(str(row.get(col)))
    if not labels:
        return "sin_dato_precio", 1.0
    confirms = sum(1 for x in labels if x.startswith("confirmacion_"))
    diverges = sum(1 for x in labels if x.startswith("divergencia_"))
    if confirms > diverges and confirms > 0:
        return "precio_confirma", 1.0
    if diverges > confirms:
        return "precio_diverge", 1.0
    return "precio_mixto_o_lateral", 1.0


def _priority(
    abs_bias: float,
    quality: float,
    price_state: str,
    cfg: dict[str, Any],
) -> str:
    p = cfg.get("priority") or {}
    alta_b = float(p.get("alta_abs_bias_min", 40))
    alta_q = float(p.get("alta_quality_min", 70))
    med_b = float(p.get("media_abs_bias_min", 20))
    med_q = float(p.get("media_quality_min", 55))
    if abs_bias >= alta_b and quality >= alta_q and price_state != "precio_diverge":
        return "Prioridad alta"
    if abs_bias >= med_b and quality >= med_q:
        return "Prioridad media"
    if abs_bias >= 12 or quality >= 60:
        return "Prioridad baja"
    return "Prioridad baja"


def _direction_es(bias: float | None) -> str:
    if bias is None or (isinstance(bias, float) and np.isnan(bias)):
        return "sin sesgo claro"
    if bias > 15:
        return "sesgo alcista del par"
    if bias < -15:
        return "sesgo bajista del par"
    return "sesgo mixto / lateral"


def _why_text(
    symbol: str,
    pair_bias: float,
    label: str | None,
    quality: float,
    price_state: str,
    coverage: str,
    cot_note: str,
) -> str:
    dir_es = _direction_es(pair_bias)
    bias_lab = BIAS_ES.get(label or "", label or "n/d")
    parts = [
        f"{symbol}: {dir_es} (sesgo={pair_bias:.1f}, {bias_lab}).",
        f"Calidad de evidencia COT={quality:.0f}/100.",
        cot_note,
    ]
    if price_state == "precio_confirma":
        parts.append("El precio semanal/mensual tiende a confirmar el posicionamiento.")
    elif price_state == "precio_diverge":
        parts.append("Hay divergencias precio×posicionamiento — bajar convicción operativa.")
    elif price_state == "sin_dato_precio":
        parts.append("Sin confirmación de precio mapeada (solo COT).")
    if coverage == "derived":
        parts.append("Sesgo derivado de varios mercados COT (no contrato dedicado).")
    elif coverage == "price_only":
        parts.append("Cobertura solo precio — sin respaldo COT directo.")
    parts.append("No es señal de compra automática.")
    return " ".join(parts)


def _risk_text(
    symbol: str,
    quality: float,
    price_state: str,
    corr_warnings: list[str],
    provisional: bool,
) -> str:
    risks: list[str] = []
    if provisional:
        risks.append("Umbrales de scoring provisionales (no calibrados).")
    if quality < 60:
        risks.append("Calidad de evidencia moderada/baja.")
    if price_state == "precio_diverge":
        risks.append("Divergencia precio vs COT.")
    if corr_warnings:
        risks.append("Correlación: " + "; ".join(corr_warnings))
    risks.append("Swing: gestionar tamaño, stops y evento macro; no duplicar el mismo factor USD/JPY.")
    return " ".join(risks)


def _resolve_pair_bias(
    pair: dict[str, Any],
    scored: pd.DataFrame,
) -> tuple[float | None, float, str, bool, str, list[str]]:
    """
    Returns (pair_bias, quality, price_state, price_available, cot_note, source_markets).
    """
    sources = pair.get("cot_sources")
    if sources:
        quals: list[float] = []
        px_states: list[str] = []
        px_ok = False
        names: list[str] = []
        found_w = 0.0
        acc = 0.0
        for src in sources:
            key = str(src.get("key") or "")
            row = _find_scored_row(scored, key)
            if row is None:
                continue
            b = row.get("combined_bias")
            if b is None or (isinstance(b, float) and np.isnan(b)):
                continue
            bb = -float(b) if src.get("invert") else float(b)
            w = float(src.get("weight", 1.0))
            acc += bb * w
            found_w += w
            q = row.get("evidence_quality")
            quals.append(float(q) if q is not None and not pd.isna(q) else 0.0)
            st, _ = _price_confirm_summary(row)
            px_states.append(st)
            px_ok = px_ok or bool(row.get("price_available"))
            names.append(_short_market(str(row["market"])))
        if found_w <= 0:
            return None, 0.0, "sin_dato_precio", False, "Sin mercados COT fuente.", []
        pair_bias = acc / found_w
        quality = float(np.mean(quals)) if quals else 0.0
        if any(s == "precio_diverge" for s in px_states):
            price_state = "precio_diverge"
        elif any(s == "precio_confirma" for s in px_states):
            price_state = "precio_confirma"
        elif px_states and all(s == "sin_dato_precio" for s in px_states):
            price_state = "sin_dato_precio"
        else:
            price_state = "precio_mixto_o_lateral"
        note = "Fuentes COT: " + ", ".join(names) + "."
        return pair_bias, quality, price_state, px_ok, note, names

    key = str(pair.get("cot_market_key") or "")
    if not key:
        return None, 0.0, "sin_dato_precio", False, "Par sin mercado COT (price-only).", []
    row = _find_scored_row(scored, key)
    if row is None:
        return None, 0.0, "sin_dato_precio", False, f"Mercado COT '{key}' no está en el universo as-of.", []
    b = row.get("combined_bias")
    if b is None or (isinstance(b, float) and np.isnan(b)):
        pair_bias = None
    else:
        pair_bias = -float(b) if pair.get("bias_invert") else float(b)
    q = row.get("evidence_quality")
    quality = float(q) if q is not None and not pd.isna(q) else 0.0
    price_state, _ = _price_confirm_summary(row)
    px_ok = bool(row.get("price_available"))
    inv = " (invertido vs futuros)" if pair.get("bias_invert") else ""
    note = f"COT directo: {_short_market(str(row['market']))}{inv}."
    return pair_bias, quality, price_state, px_ok, note, [_short_market(str(row["market"]))]


def build_weekly_recommendations(
    scored: pd.DataFrame,
    cfg: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Build ranked weekly swing recommendations DataFrame (one row per configured pair)."""
    cfg = cfg or load_market_config()
    wr = cfg.get("weekly_recommendation") or {}
    pairs = cfg.get("swing_pairs") or []
    boost = float(wr.get("price_confirm_boost", 1.12))
    pen = float(wr.get("price_diverge_penalty", 0.88))
    watch_clusters = set(wr.get("correlation_warning_clusters") or [])
    provisional = True if rules is None else bool(rules.get("provisional", True))
    as_of = None
    if scored is not None and not scored.empty and "as_of_date" in scored.columns:
        as_of = str(scored["as_of_date"].iloc[0])

    # First pass: compute raw rows
    raw: list[dict[str, Any]] = []
    for pair in pairs:
        symbol = str(pair.get("symbol") or "").strip()
        if not symbol:
            continue
        section = str(pair.get("section") or "opcionales")
        section_label = str(pair.get("section_label") or SECTION_LABELS.get(section, section))
        coverage = str(pair.get("coverage") or ("direct" if pair.get("cot_backed", True) else "price_only"))
        cot_backed = bool(pair.get("cot_backed", coverage != "price_only"))
        pair_bias, quality, price_state, px_ok, cot_note, sources = _resolve_pair_bias(pair, scored)
        if pair_bias is None:
            # Keep a visible row so universe gaps are documented
            raw.append(
                {
                    "as_of_date": as_of,
                    "section": section,
                    "section_label": section_label,
                    "symbol": symbol,
                    "spot_or_futures": pair.get("spot_or_futures"),
                    "cot_backed": cot_backed,
                    "coverage": coverage,
                    "pair_bias": None,
                    "pair_bias_label": None,
                    "evidence_quality": quality,
                    "price_available": px_ok,
                    "price_confirm_state": price_state,
                    "priority": "Prioridad baja",
                    "opportunity_score": 0.0,
                    "direction_hint": "sin_dato",
                    "por_que": (
                        f"{symbol}: sin dato COT as-of para mapear el par. "
                        "No es señal de compra automática."
                    ),
                    "riesgo": "Mercado ausente en archivo CFTC o aún no cargado.",
                    "correlation_clusters": "|".join(pair.get("correlation_clusters") or []),
                    "correlation_warnings": "",
                    "cot_sources": ", ".join(sources),
                    "disclaimer": wr.get("disclaimer")
                    or "No es señal de compra automática.",
                }
            )
            continue

        factor = 1.0
        if price_state == "precio_confirma":
            factor = boost
        elif price_state == "precio_diverge":
            factor = pen
        abs_b = abs(float(pair_bias))
        opp = round(abs_b * (quality / 100.0) * factor, 2)
        label = classify_bias(pair_bias, rules) if rules else None
        if label is None and rules is None:
            # minimal classify without full rules
            if pair_bias >= 50:
                label = "fuertemente_alcista"
            elif pair_bias >= 20:
                label = "moderadamente_alcista"
            elif pair_bias <= -50:
                label = "fuertemente_bajista"
            elif pair_bias <= -20:
                label = "moderadamente_bajista"
            else:
                label = "neutral_o_mixto"
        pri = _priority(abs_b, quality, price_state, wr)
        dir_hint = "alcista_par" if pair_bias > 15 else ("bajista_par" if pair_bias < -15 else "mixto")
        raw.append(
            {
                "as_of_date": as_of,
                "section": section,
                "section_label": section_label,
                "symbol": symbol,
                "spot_or_futures": pair.get("spot_or_futures"),
                "cot_backed": cot_backed,
                "coverage": coverage,
                "pair_bias": round(float(pair_bias), 2),
                "pair_bias_label": label,
                "evidence_quality": round(quality, 1),
                "price_available": px_ok,
                "price_confirm_state": price_state,
                "priority": pri,
                "opportunity_score": opp,
                "direction_hint": dir_hint,
                "por_que": _why_text(
                    symbol, float(pair_bias), label, quality, price_state, coverage, cot_note
                ),
                "riesgo": "",  # filled after corr pass
                "correlation_clusters": "|".join(pair.get("correlation_clusters") or []),
                "correlation_warnings": "",
                "cot_sources": ", ".join(sources),
                "disclaimer": wr.get("disclaimer")
                or "No es señal de compra automática.",
                "_clusters": list(pair.get("correlation_clusters") or []),
                "_provisional": provisional,
            }
        )

    # Correlation warnings: high-priority pairs sharing watched clusters
    highish = [
        r
        for r in raw
        if r.get("pair_bias") is not None
        and r.get("priority") in ("Prioridad alta", "Prioridad media")
        and abs(float(r["pair_bias"])) >= 20
    ]
    for r in raw:
        warns: list[str] = []
        clusters = set(r.get("_clusters") or [])
        for other in highish:
            if other["symbol"] == r["symbol"]:
                continue
            shared = clusters & set(other.get("_clusters") or []) & watch_clusters
            if not shared:
                continue
            # Same USD/JPY factor warning
            same_dir = (
                r.get("direction_hint") == other.get("direction_hint")
                and r.get("direction_hint") in ("alcista_par", "bajista_par")
            )
            # For g10_long_usd, also warn if both imply same USD bet via invert logic already in bias
            if shared:
                warns.append(
                    f"Evitar duplicar con {other['symbol']} "
                    f"(clusters: {', '.join(sorted(shared))}"
                    + ("; mismo sentido" if same_dir else "")
                    + ")"
                )
        r["correlation_warnings"] = " | ".join(warns)
        r["riesgo"] = _risk_text(
            r["symbol"],
            float(r.get("evidence_quality") or 0),
            str(r.get("price_confirm_state")),
            warns,
            bool(r.get("_provisional", True)),
        )
        r.pop("_clusters", None)
        r.pop("_provisional", None)

    if not raw:
        return pd.DataFrame()

    out = pd.DataFrame(raw)
    # Rank within section then globally
    pri_rank = {"Prioridad alta": 0, "Prioridad media": 1, "Prioridad baja": 2}
    out["_pri"] = out["priority"].map(lambda x: pri_rank.get(x, 9))
    out["_sec"] = out["section"].map(
        lambda s: SECTION_ORDER.index(s) if s in SECTION_ORDER else 99
    )
    out = out.sort_values(
        ["_sec", "_pri", "opportunity_score"], ascending=[True, True, False]
    ).reset_index(drop=True)
    out["rank_global"] = range(1, len(out) + 1)
    out["rank_in_section"] = out.groupby("section", sort=False).cumcount() + 1
    out = out.drop(columns=["_pri", "_sec"], errors="ignore")
    return out


def weekly_top_n(weekly: pd.DataFrame, n: int = 3) -> list[dict[str, Any]]:
    if weekly is None or weekly.empty:
        return []
    cols = [
        "rank_global",
        "section_label",
        "symbol",
        "priority",
        "pair_bias",
        "pair_bias_label",
        "evidence_quality",
        "opportunity_score",
        "direction_hint",
        "por_que",
        "riesgo",
        "correlation_warnings",
        "cot_backed",
        "coverage",
    ]
    use = [c for c in cols if c in weekly.columns]
    ranked = weekly.sort_values(["rank_global"]).head(n)
    return ranked[use].to_dict(orient="records")


def weekly_to_records(weekly: pd.DataFrame) -> list[dict[str, Any]]:
    if weekly is None or weekly.empty:
        return []
    return weekly.replace({np.nan: None}).to_dict(orient="records")
