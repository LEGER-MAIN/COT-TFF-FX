"""Provisional dual scoring: directional bias (−100…+100) + evidence quality (0…100).

Not buy/sell signals. Thresholds live in config/scoring_rules.json and are marked provisional.
Dealers are context only — never auto-scored bullish/bearish by net sign.
Spread is non-directional context. Other Reportables / Nonreportable = complementary low weight.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .cot_indicators import group_divergence_snapshot, latest_snapshot
from .timeframes import HORIZON_ORDER, load_scoring_rules


def classify_bias(score: float | None, rules: dict[str, Any]) -> str | None:
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return None
    bc = rules["bias_classification"]
    s = float(score)
    if s >= bc["strongly_bullish_min"]:
        return "fuertemente_alcista"
    if s >= bc["moderately_bullish_min"]:
        return "moderadamente_alcista"
    if s <= bc["strongly_bearish_max"]:
        return "fuertemente_bajista"
    if s <= bc["moderately_bearish_max"]:
        return "moderadamente_bajista"
    return "neutral_o_mixto"


def _score_horizon_change(nn_chg: float | None, rules: dict[str, Any]) -> int | None:
    """Map horizon net-change (% of OI) to −2…+2."""
    if nn_chg is None or (isinstance(nn_chg, float) and np.isnan(nn_chg)):
        return None
    neut = float(rules["neutral_net_change_oi_pct"])
    strong = float(rules["strong_net_change_oi_pct"])
    v = float(nn_chg)
    if abs(v) < neut:
        return 0
    if v >= strong:
        return 2
    if v > 0:
        return 1
    if v <= -strong:
        return -2
    return -1


def _score_percentile(pctl: float | None, rules: dict[str, Any]) -> int | None:
    """High percentile of net = long-heavy positioning (bullish positioning evidence, not a buy)."""
    if pctl is None or (isinstance(pctl, float) and np.isnan(pctl)):
        return None
    bands = rules["percentile_bands"]
    p = float(pctl)
    if p >= bands["extreme_high"]:
        return 2
    if p >= bands["high"]:
        return 1
    if p <= bands["extreme_low"]:
        return -2
    if p <= bands["low"]:
        return -1
    return 0


def _score_persistence(up: int | None, down: int | None, rules: dict[str, Any]) -> int | None:
    need = int(rules["persistence_min_weeks"])
    if up is None and down is None:
        return None
    u = int(up or 0)
    d = int(down or 0)
    if u >= need and u >= d:
        return 1 if u < need * 2 else 2
    if d >= need and d > u:
        return -1 if d < need * 2 else -2
    return 0


def _score_price_confirm(label: str | None) -> int | None:
    if not label or (isinstance(label, float) and pd.isna(label)):
        return None
    s = str(label)
    if s == "confirmacion_alcista_potencial":
        return 1
    if s == "confirmacion_bajista_potencial":
        return -1
    if s == "divergencia_neto_sube_precio_baja":
        return -1  # soft penalty vs net-only bullish reading
    if s == "divergencia_neto_baja_precio_sube":
        return 1  # soft opposite
    return 0


def _mean_int(scores: list[int | None]) -> float | None:
    vals = [s for s in scores if s is not None]
    if not vals:
        return None
    return float(np.mean(vals))


def score_group_row(row: pd.Series, rules: dict[str, Any]) -> dict[str, Any]:
    """Score one market × trader_group latest row → horizon breakdown + group bias."""
    weights = rules["horizon_weights"]
    pcfg = rules.get("price") or {}
    price_w = float(pcfg.get("confirm_weight_in_horizon", 0.25))
    use_price = bool(pcfg.get("enabled", True)) and bool(row.get("price_available"))
    horizon_detail: dict[str, Any] = {}
    weighted = 0.0
    w_sum = 0.0

    p52 = row.get("net_percentile_52w")
    p156 = row.get("net_percentile_156w")
    nn_p52 = row.get("normalized_net_percentile_52w")

    persist = _score_persistence(
        None if pd.isna(row.get("consecutive_net_up")) else int(row["consecutive_net_up"]),
        None if pd.isna(row.get("consecutive_net_down")) else int(row["consecutive_net_down"]),
        rules,
    )

    for h in HORIZON_ORDER:
        nn_col = f"net_change_nn_{h}"
        dir_col = f"direction_{h}"
        nn_chg = row.get(nn_col)
        nn_chg_f = None if pd.isna(nn_chg) else float(nn_chg)

        pctl = p52
        if h == "annual" and p156 is not None and not pd.isna(p156):
            pctl = p156
        pctl_score = _score_percentile(None if pd.isna(pctl) else float(pctl), rules)
        nn_pctl_score = (
            _score_percentile(None if pd.isna(nn_p52) else float(nn_p52), rules)
            if h in ("semiannual", "annual")
            else None
        )

        chg_score = _score_horizon_change(nn_chg_f, rules)
        pers_score = persist if h != "weekly" else None

        confirm_label = row.get(f"price_position_confirm_{h}")
        price_score = _score_price_confirm(confirm_label) if use_price else None

        # Base pieces (COT); optionally blend soft price confirm score
        pieces = [chg_score, pctl_score, nn_pctl_score, pers_score]
        h_mean = _mean_int(pieces)
        if h_mean is not None and price_score is not None:
            h_mean = (1.0 - price_w) * h_mean + price_w * float(price_score)

        if h_mean is not None:
            w = float(weights.get(h, 0.0))
            weighted += h_mean * w
            w_sum += w

        horizon_detail[h] = {
            "net_change": None if pd.isna(row.get(f"net_change_{h}")) else float(row[f"net_change_{h}"]),
            "net_change_nn_pct": nn_chg_f,
            "direction": row.get(dir_col),
            "price_return_pct": (
                None
                if pd.isna(row.get(f"price_return_{h}"))
                else round(float(row[f"price_return_{h}"]), 4)
            ),
            "price_direction": (
                None if pd.isna(row.get(f"price_direction_{h}")) else row.get(f"price_direction_{h}")
            ),
            "price_position_confirm": (
                None if pd.isna(confirm_label) else confirm_label
            ),
            "criterion_scores": {
                "net_change": chg_score,
                "percentile_net": pctl_score,
                "percentile_nn": nn_pctl_score,
                "persistence": pers_score,
                "price_confirm": price_score,
            },
            "horizon_score_m2_p2": None if h_mean is None else round(h_mean, 3),
            "weight": float(weights.get(h, 0.0)),
        }

    group_bias = None if w_sum <= 0 else round((weighted / w_sum) * 50.0, 2)

    regime = {
        "cross_flag": bool(row.get("regime_cross_flag"))
        if not pd.isna(row.get("regime_cross_flag"))
        else False,
        "direction": None
        if pd.isna(row.get("regime_direction"))
        else row.get("regime_direction"),
        "weeks_since": None
        if pd.isna(row.get("weeks_since_regime_cross"))
        else int(row["weeks_since_regime_cross"]),
        "net_before": None
        if pd.isna(row.get("regime_net_before"))
        else float(row["regime_net_before"]),
        "net_after": None
        if pd.isna(row.get("regime_net_after"))
        else float(row["regime_net_after"]),
        "note": "Cruce de signo del neto; no es señal de entrada por sí solo.",
    }

    spread = {
        "spreading_positions": None
        if pd.isna(row.get("spreading_positions"))
        else float(row["spreading_positions"]),
        "spread_oi_pct": None
        if pd.isna(row.get("spread_oi_pct"))
        else round(float(row["spread_oi_pct"]), 4),
        "spread_change": None
        if pd.isna(row.get("spread_change_used"))
        else float(row["spread_change_used"]),
        "spread_change_label": None
        if pd.isna(row.get("spread_change_label"))
        else row.get("spread_change_label"),
        "note": "Contexto no direccional; no se suma al neto ni al sesgo.",
    }

    return {
        "market": row["market"],
        "trader_group": row["trader_group"],
        "report_date": str(pd.Timestamp(row["report_date"]).date()),
        "net_position": None if pd.isna(row.get("net_position")) else float(row["net_position"]),
        "normalized_net_pct": None
        if pd.isna(row.get("normalized_net_pct"))
        else round(float(row["normalized_net_pct"]), 4),
        "net_percentile_52w": None if pd.isna(p52) else round(float(p52), 2),
        "net_percentile_156w": None if pd.isna(p156) else round(float(p156), 2),
        "normalized_net_percentile_52w": None if pd.isna(nn_p52) else round(float(nn_p52), 2),
        "consecutive_net_up": None
        if pd.isna(row.get("consecutive_net_up"))
        else int(row["consecutive_net_up"]),
        "consecutive_net_down": None
        if pd.isna(row.get("consecutive_net_down"))
        else int(row["consecutive_net_down"]),
        "net_change_accel_label": row.get("net_change_accel_label"),
        "history_weeks": None if pd.isna(row.get("history_weeks")) else int(row["history_weeks"]),
        "price_available": bool(row.get("price_available"))
        if not pd.isna(row.get("price_available"))
        else False,
        "price_close": None if pd.isna(row.get("price_close")) else float(row["price_close"]),
        "price_ticker": None if pd.isna(row.get("price_ticker")) else row.get("price_ticker"),
        "price_extreme_alert": None
        if pd.isna(row.get("price_extreme_alert"))
        else row.get("price_extreme_alert"),
        "oi_price_reading": None
        if pd.isna(row.get("oi_price_reading"))
        else row.get("oi_price_reading"),
        "regime": regime,
        "spread_context": spread,
        "group_bias": group_bias,
        "group_bias_label": classify_bias(group_bias, rules),
        "horizons": horizon_detail,
    }


def _evidence_quality(
    market_rows: list[dict[str, Any]],
    dealer_row: pd.Series | None,
    rules: dict[str, Any],
    divergence: dict[str, Any] | None = None,
    complementary_rows: list[dict[str, Any]] | None = None,
) -> tuple[float, list[str], list[str]]:
    """Return (quality 0–100, reasons, warnings)."""
    qcfg = rules["quality"]
    pcfg = rules.get("price") or {}
    reasons: list[str] = []
    warnings: list[str] = []
    score = 50.0

    if not market_rows:
        return 0.0, ["sin_grupos_primarios"], ["Sin datos de LF/AM para puntuar."]

    hist = [r.get("history_weeks") or 0 for r in market_rows]
    min_hist = min(hist) if hist else 0
    full = int(qcfg["min_weeks_full_credit"])
    if min_hist >= full:
        score += 15
        reasons.append(f"historial>={full}w")
    elif min_hist >= 26:
        score += 8
        reasons.append("historial_parcial_26w+")
    else:
        score -= float(qcfg["insufficient_history_penalty"])
        warnings.append(
            f"Historial corto ({min_hist} semanas); percentiles y horizontes largos menos fiables."
        )
        reasons.append("historial_insuficiente")

    has_156 = all(r.get("net_percentile_156w") is not None for r in market_rows)
    if has_156:
        score += 5
        reasons.append("percentil_156w_disponible")
    else:
        warnings.append(
            "Percentil 156w no disponible o incompleto (historial < umbral configurado)."
        )

    agree_ratios = []
    for r in market_rows:
        dirs = []
        for h, detail in r.get("horizons", {}).items():
            d = detail.get("direction")
            hs = detail.get("horizon_score_m2_p2")
            if d in ("alcista", "bajista") and hs is not None and hs != 0:
                dirs.append(1 if d == "alcista" else -1)
        if dirs:
            maj = 1 if sum(dirs) >= 0 else -1
            agree = sum(1 for x in dirs if x == maj) / len(dirs)
            agree_ratios.append(agree)
    if agree_ratios:
        mean_agree = float(np.mean(agree_ratios))
        thr = float(qcfg["horizon_agreement_full_credit"])
        if mean_agree >= thr:
            score += 15
            reasons.append("horizontes_alineados")
        elif mean_agree >= 0.6:
            score += 8
            reasons.append("horizontes_parcialmente_alineados")
        else:
            score -= 10
            warnings.append("Horizontes en desacuerdo dentro de un grupo primario.")
            reasons.append("horizontes_divergentes")

    biases = [r.get("group_bias") for r in market_rows if r.get("group_bias") is not None]
    if len(biases) >= 2:
        signs = [1 if b > 5 else (-1 if b < -5 else 0) for b in biases]
        if 0 not in signs and len(set(signs)) == 1:
            score += float(qcfg["group_agreement_bonus"])
            reasons.append("LF_AM_acuerdo_direccion")
        elif set(signs) == {1, -1}:
            score -= float(qcfg["divergence_penalty"])
            warnings.append(
                "Divergencia LF vs Asset Managers: direcciones opuestas en sesgo de grupo."
            )
            reasons.append("LF_AM_divergencia")
        else:
            reasons.append("LF_AM_mixto_o_neutral")

    # Criterion 22 detail (levels vs weekly changes)
    if divergence and divergence.get("available"):
        if divergence.get("nn_levels_diverge"):
            warnings.append(
                f"C22 niveles: gap NN LF–AM={divergence.get('nn_level_gap_pct')} pts "
                "(diferencia de nivel, no implica desacuerdo de cambios)."
            )
            reasons.append("C22_gap_niveles_NN")
        agr = divergence.get("weekly_change_agreement")
        if agr == "desacuerdo_cambios":
            score -= 8
            warnings.append("C22 cambios: LF y AM en desacuerdo en Δ neto semanal.")
            reasons.append("C22_desacuerdo_cambios")
        elif agr in ("acuerdo_mejora", "acuerdo_deterioro"):
            score += 5
            reasons.append(f"C22_{agr}")

    # Complementary groups soft agreement with primary combined sign
    if complementary_rows and biases:
        primary_sign = 1 if np.mean(biases) > 5 else (-1 if np.mean(biases) < -5 else 0)
        comp_biases = [r.get("group_bias") for r in complementary_rows if r.get("group_bias") is not None]
        if primary_sign != 0 and comp_biases:
            comp_signs = [1 if b > 5 else (-1 if b < -5 else 0) for b in comp_biases]
            if all(s == primary_sign for s in comp_signs if s != 0):
                score += float(qcfg.get("complementary_agreement_bonus", 5))
                reasons.append("Other_Nonrep_acuerdan_direccion_primaria")
            elif any(s == -primary_sign for s in comp_signs):
                warnings.append(
                    "Other Reportables / Nonreportable divergen del sesgo primario (peso complementario)."
                )
                reasons.append("Other_Nonrep_divergen")

    # Price confirmation quality (Criteria 16–19)
    price_rows = [r for r in market_rows if r.get("price_available")]
    if price_rows:
        confirms = 0
        diverges = 0
        n_labels = 0
        for r in price_rows:
            for h, detail in r.get("horizons", {}).items():
                lab = detail.get("price_position_confirm")
                if not lab:
                    continue
                n_labels += 1
                if str(lab).startswith("confirmacion_"):
                    confirms += 1
                elif str(lab).startswith("divergencia_"):
                    diverges += 1
        if n_labels:
            if confirms >= diverges and confirms > 0:
                score += float(pcfg.get("quality_confirm_bonus", 10))
                reasons.append("precio_confirma_posicionamiento")
            elif diverges > confirms:
                score -= float(pcfg.get("quality_diverge_penalty", 12))
                warnings.append(
                    "Divergencias precio × posicionamiento en uno o más horizontes (no = reversión automática)."
                )
                reasons.append("precio_diverge_posicionamiento")
        for r in price_rows:
            alert = r.get("price_extreme_alert")
            if alert:
                warnings.append(f"{r['trader_group']}: {alert}")
    else:
        warnings.append(
            "Precio no disponible o no mapeado para este mercado; Criterios 16–19 omitidos en scoring."
        )
        reasons.append("sin_precio")

    # Recent regime cross note
    regime_w = int(qcfg.get("regime_recent_weeks", 8))
    for r in market_rows:
        reg = r.get("regime") or {}
        ws = reg.get("weeks_since")
        if ws is not None and ws <= regime_w:
            warnings.append(
                f"{r['trader_group']}: cambio de régimen hace {ws} sem. "
                f"({reg.get('direction')}); contexto, no entrada automática."
            )
            reasons.append("regimen_reciente")

    ext_p = float(qcfg["extension_warning_percentile"])
    for r in market_rows:
        p = r.get("net_percentile_52w")
        bias = r.get("group_bias")
        if p is not None and p >= ext_p and bias is not None and bias > 0:
            warnings.append(
                f"{r['trader_group']}: percentil neto 52w={p:.0f} (extremo) con sesgo positivo — "
                "alerta de extensión/saturación, no señal de venta."
            )
        if p is not None and p <= (100 - ext_p) and bias is not None and bias < 0:
            warnings.append(
                f"{r['trader_group']}: percentil neto 52w={p:.0f} (extremo bajo) con sesgo negativo — "
                "alerta de extensión corta, no señal de compra."
            )

    if dealer_row is not None and not pd.isna(dealer_row.get("net_position")):
        reasons.append("dealer_contexto_disponible")
    else:
        warnings.append("Dealer / Intermediary sin dato en el snapshot (solo contexto).")

    score = float(max(0.0, min(100.0, round(score, 1))))
    return score, reasons, warnings


def score_markets(
    indicators: pd.DataFrame,
    rules: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Build one scored row per market from latest LF + AM (+ complementary + Dealer/Spread context).
    Returns a flat DataFrame suitable for Excel/HTML.
    """
    if rules is None:
        rules = load_scoring_rules()
    latest = latest_snapshot(indicators)
    primary = set(rules.get("primary_groups") or ["Leveraged Funds", "Asset Manager / Institutional"])
    complementary = set(rules.get("complementary_groups") or ["Other Reportables", "Nonreportable"])
    gweights = rules.get("group_weights") or {}
    cweights = rules.get("complementary_group_weights") or {}
    blend_cap = float(rules.get("complementary_blend_cap", 0.15))

    records: list[dict[str, Any]] = []
    for market, g in latest.groupby("market", sort=True):
        prim_rows: list[dict[str, Any]] = []
        comp_rows: list[dict[str, Any]] = []
        dealer = None
        scored_groups: list[dict[str, Any]] = []
        for _, row in g.iterrows():
            tg = row["trader_group"]
            if tg in primary:
                sg = score_group_row(row, rules)
                scored_groups.append(sg)
                prim_rows.append(sg)
            elif tg in complementary:
                sg = score_group_row(row, rules)
                scored_groups.append(sg)
                comp_rows.append(sg)
            elif tg == "Dealer / Intermediary":
                dealer = row

        # Primary combined bias
        num = den = 0.0
        for sg in prim_rows:
            b = sg.get("group_bias")
            if b is None:
                continue
            w = float(gweights.get(sg["trader_group"], 1.0))
            num += b * w
            den += w
        primary_bias = None if den <= 0 else (num / den)

        # Soft blend complementary (capped)
        if primary_bias is not None and comp_rows:
            cnum = cden = 0.0
            for sg in comp_rows:
                b = sg.get("group_bias")
                if b is None:
                    continue
                w = float(cweights.get(sg["trader_group"], 0.05))
                cnum += b * w
                cden += w
            if cden > 0:
                comp_bias = cnum / cden
                # Normalize complementary total weight to <= blend_cap of final
                # final = (1-cap)*primary + cap*comp  (cap scaled by available weight)
                cap = min(blend_cap, cden / (cden + 1.0))
                combined = round((1.0 - cap) * primary_bias + cap * comp_bias, 2)
            else:
                combined = round(primary_bias, 2)
        else:
            combined = None if primary_bias is None else round(primary_bias, 2)

        divergence = group_divergence_snapshot(g, rules=rules)
        quality, q_reasons, warns = _evidence_quality(
            prim_rows, dealer, rules, divergence=divergence, complementary_rows=comp_rows
        )
        if rules.get("provisional"):
            warns.insert(
                0,
                "Umbrales PROVISIONALES (config/scoring_rules.json) — no calibrados por mercado.",
            )

        flat: dict[str, Any] = {
            "market": market,
            "report_type": "TFF",
            "as_of_date": str(pd.Timestamp(g["report_date"].max()).date()),
            "combined_bias": combined,
            "combined_bias_label": classify_bias(combined, rules),
            "evidence_quality": quality,
            "quality_reasons": " | ".join(q_reasons),
            "warnings": " | ".join(warns),
            "provisional_thresholds": bool(rules.get("provisional", True)),
            "scoring_version": rules.get("version"),
            "c22_nn_level_gap_pct": divergence.get("nn_level_gap_pct"),
            "c22_nn_levels_diverge": divergence.get("nn_levels_diverge"),
            "c22_weekly_change_agreement": divergence.get("weekly_change_agreement"),
        }

        if dealer is not None:
            flat["dealer_net"] = (
                None if pd.isna(dealer.get("net_position")) else float(dealer["net_position"])
            )
            flat["dealer_nn_pct"] = (
                None
                if pd.isna(dealer.get("normalized_net_pct"))
                else round(float(dealer["normalized_net_pct"]), 4)
            )
            flat["dealer_delta_weekly"] = (
                None
                if pd.isna(dealer.get("delta_net_weekly"))
                else float(dealer["delta_net_weekly"])
            )
            flat["dealer_spread"] = (
                None
                if pd.isna(dealer.get("spreading_positions"))
                else float(dealer["spreading_positions"])
            )
        else:
            flat["dealer_net"] = None
            flat["dealer_nn_pct"] = None
            flat["dealer_delta_weekly"] = None
            flat["dealer_spread"] = None

        # Price snapshot from first primary row
        px_src = next((r for r in prim_rows if r.get("price_available")), None)
        if px_src:
            flat["price_ticker"] = px_src.get("price_ticker")
            flat["price_close"] = px_src.get("price_close")
            flat["price_available"] = True
            flat["oi_price_reading"] = px_src.get("oi_price_reading")
        else:
            flat["price_ticker"] = None
            flat["price_close"] = None
            flat["price_available"] = False
            flat["oi_price_reading"] = None

        for sg in scored_groups:
            if sg["trader_group"] == "Leveraged Funds":
                key = "LF"
            elif sg["trader_group"] == "Asset Manager / Institutional":
                key = "AM"
            elif sg["trader_group"] == "Other Reportables":
                key = "OR"
            elif sg["trader_group"] == "Nonreportable":
                key = "NR"
            else:
                continue
            flat[f"{key}_bias"] = sg["group_bias"]
            flat[f"{key}_bias_label"] = sg["group_bias_label"]
            flat[f"{key}_net"] = sg["net_position"]
            flat[f"{key}_nn_pct"] = sg["normalized_net_pct"]
            flat[f"{key}_pctl_52w"] = sg["net_percentile_52w"]
            flat[f"{key}_pctl_156w"] = sg["net_percentile_156w"]
            flat[f"{key}_consec_up"] = sg["consecutive_net_up"]
            flat[f"{key}_consec_down"] = sg["consecutive_net_down"]
            flat[f"{key}_accel"] = sg["net_change_accel_label"]
            flat[f"{key}_regime_weeks"] = (sg.get("regime") or {}).get("weeks_since")
            flat[f"{key}_spread"] = (sg.get("spread_context") or {}).get("spreading_positions")
            for h in HORIZON_ORDER:
                hd = sg["horizons"].get(h, {})
                flat[f"{key}_{h}_dir"] = hd.get("direction")
                flat[f"{key}_{h}_net_chg"] = hd.get("net_change")
                flat[f"{key}_{h}_score"] = hd.get("horizon_score_m2_p2")
                flat[f"{key}_{h}_px_confirm"] = hd.get("price_position_confirm")

        flat["_groups_detail"] = scored_groups
        flat["_divergence"] = divergence
        records.append(flat)

    return pd.DataFrame(records)


def scored_to_json_payload(
    scored: pd.DataFrame,
    validation_dict: dict[str, Any],
    rules: dict[str, Any],
    price_meta: dict[str, Any] | None = None,
    weekly: pd.DataFrame | None = None,
) -> dict[str, Any]:
    markets = []
    for _, row in scored.iterrows():
        detail = row.get("_groups_detail") or []
        markets.append(
            {
                "market": row["market"],
                "report_type": row["report_type"],
                "as_of_date": row["as_of_date"],
                "combined_bias": row["combined_bias"],
                "combined_bias_label": row["combined_bias_label"],
                "evidence_quality": row["evidence_quality"],
                "quality_reasons": row["quality_reasons"],
                "warnings": [
                    w.strip() for w in str(row.get("warnings") or "").split("|") if w.strip()
                ],
                "group_divergence_c22": row.get("_divergence"),
                "dealer_context": {
                    "net_position": row.get("dealer_net"),
                    "normalized_net_pct": row.get("dealer_nn_pct"),
                    "delta_net_weekly": row.get("dealer_delta_weekly"),
                    "spreading_positions": row.get("dealer_spread"),
                    "note": "Contexto únicamente; no entra en sesgo direccional automático.",
                },
                "price": {
                    "available": bool(row.get("price_available")),
                    "ticker": row.get("price_ticker"),
                    "close": row.get("price_close"),
                    "oi_price_reading": row.get("oi_price_reading"),
                },
                "groups": detail,
            }
        )
    weekly_payload: dict[str, Any] = {}
    if weekly is not None and not weekly.empty:
        from .weekly_recommendations import weekly_to_records, weekly_top_n

        weekly_payload = {
            "disclaimer": (
                "Recomendación semanal de estudio para swing — "
                "no es señal de compra automática."
            ),
            "top": weekly_top_n(weekly, 5),
            "recommendations": weekly_to_records(weekly),
        }
    return {
        "report_type": "TFF",
        "scoring_version": rules.get("version"),
        "provisional_thresholds": bool(rules.get("provisional", True)),
        "as_of_date": validation_dict.get("as_of_date"),
        "min_date": validation_dict.get("min_date"),
        "validation": validation_dict,
        "price_meta": price_meta or {},
        "universe_note": (
            "F10 Currencies + F15 (NZD/BRL si figuran en CFTC) + "
            "USD INDEX (ICE, F90 / 098662). Excluidos: MEXICAN PESO, "
            "SO AFRICAN RAND, USD/CHINESE RENMINBI-OFFSHORE (exclude_markets). "
            "TFF Futures Only."
        ),
        "disclaimer": (
            "Sesgo = orientación de la evidencia de posicionamiento reportado; "
            "calidad ≠ probabilidad de subida/bajada; no son señales de compra/venta. "
            "Spread no es direccional. Other/Nonreportable tienen peso complementario bajo. "
            "La sección semanal de pares swing tampoco es señal automática."
        ),
        "markets": markets,
        "weekly_recommendations": weekly_payload,
    }
