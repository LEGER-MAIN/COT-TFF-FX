"""Core COT indicators — Criteria 1–10, 15, 20–22 (+ price attach elsewhere).

Criteria 1–6: net, NN, weekly Δ, accum/liq, OI, % OI.
Criteria 7–10: multi-horizon net change, percentiles 52/156, persistence.
Criterion 15: Spread as non-directional context (never added to directional net).
Criterion 20: acceleration of weekly net change magnitude.
Criterion 21: regime change (net sign cross).
Criterion 22 helpers: NN levels / change agreement used in scoring vs other groups.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .timeframes import HORIZON_ORDER, horizons_from_rules, load_scoring_rules


def _sign_label_net(net: float | None) -> str | None:
    if net is None or (isinstance(net, float) and np.isnan(net)):
        return None
    if net > 0:
        return "neto_positivo"
    if net < 0:
        return "neto_negativo"
    return "neto_cercano_a_cero"


def _delta_net_label(delta: float | None) -> str | None:
    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        return None
    if delta > 0:
        return "mejora_alcista"
    if delta < 0:
        return "deterioro_bajista"
    return "sin_cambio_neto"


def _oi_label(pct: float | None, eps: float = 0.1) -> str | None:
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return None
    if pct > eps:
        return "aumenta"
    if pct < -eps:
        return "disminuye"
    return "estable"


def _direction_from_change(
    change: float | None,
    oi: float | None,
    neutral_oi_pct: float,
) -> str | None:
    if change is None or (isinstance(change, float) and np.isnan(change)):
        return None
    if oi is None or (isinstance(oi, float) and (np.isnan(oi) or oi == 0)):
        if change > 0:
            return "alcista"
        if change < 0:
            return "bajista"
        return "neutral"
    nn = abs(change) / float(oi) * 100.0
    if nn < neutral_oi_pct:
        return "neutral"
    if change > 0:
        return "alcista"
    return "bajista"


def _rolling_percentile(s: pd.Series, window: int, min_obs: int) -> pd.Series:
    """Empirical percentile: 100 * #(hist < current) / M within trailing window incl. current."""

    def one(i: int) -> float:
        start = max(0, i - window + 1)
        hist = s.iloc[start : i + 1].dropna()
        if len(hist) < min_obs:
            return np.nan
        cur = s.iloc[i]
        if pd.isna(cur):
            return np.nan
        return 100.0 * float((hist < cur).sum()) / float(len(hist))

    return pd.Series([one(i) for i in range(len(s))], index=s.index, dtype="float64")


def _consecutive_runs(delta: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Trailing consecutive weeks of positive / negative net change (zeros break the run)."""
    up = []
    down = []
    cu = cd = 0
    for v in delta:
        if pd.isna(v) or v == 0:
            cu = cd = 0
        elif v > 0:
            cu += 1
            cd = 0
        else:
            cd += 1
            cu = 0
        up.append(cu)
        down.append(cd)
    return (
        pd.Series(up, index=delta.index, dtype="Int64"),
        pd.Series(down, index=delta.index, dtype="Int64"),
    )


def compute_indicators(
    df: pd.DataFrame,
    rules: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Input: validated long-format TFF rows (one market × trader_group × date).
    Output: same grain with Criteria 1–10 + 20 columns.
    """
    if rules is None:
        rules = load_scoring_rules()
    horizons = horizons_from_rules(rules)
    neutral = float(rules.get("neutral_net_change_oi_pct", 0.5))
    min_pctl = int(rules.get("min_history_weeks_for_percentile", 10))
    min_156 = int(rules.get("min_history_weeks_for_156w", 40))
    accel_lb = int(rules.get("acceleration_lookback_weeks", 4))
    accel_thr = float(rules.get("acceleration_ratio_threshold", 1.5))

    out = df.sort_values(["market", "trader_group", "report_date"]).copy()

    # Criterio 1 — Net Position
    out["net_position"] = out["long_positions"] - out["short_positions"]
    out["net_class"] = out["net_position"].map(
        lambda v: _sign_label_net(None if pd.isna(v) else float(v))
    )

    # Criterio 2 — Normalized Net (% of OI)
    oi = out["open_interest_total"].astype("Float64")
    net = out["net_position"].astype("Float64")
    out["normalized_net_pct"] = np.where(oi.notna() & (oi != 0), (net / oi) * 100.0, np.nan)

    # Prefer recalculated weekly deltas for integrity; fall back to published.
    long_ch = out["long_change_recalc"].combine_first(out["long_change"]).astype("Float64")
    short_ch = out["short_change_recalc"].combine_first(out["short_change"]).astype("Float64")
    out["long_change_used"] = long_ch
    out["short_change_used"] = short_ch

    # Criterio 3 — Weekly Δ net
    out["delta_net_weekly"] = long_ch - short_ch
    out["delta_net_label"] = out["delta_net_weekly"].map(
        lambda v: _delta_net_label(None if pd.isna(v) else float(v))
    )

    # Criterio 4 — Accumulation / liquidation flags + quantities
    out["long_increase"] = long_ch > 0
    out["short_increase"] = short_ch > 0
    out["long_reduction"] = long_ch < 0
    out["short_reduction"] = short_ch < 0
    out["long_change_qty"] = long_ch
    out["short_change_qty"] = short_ch

    def _accum_label(row) -> str | None:
        dl, ds = row["long_change_used"], row["short_change_used"]
        if pd.isna(dl) or pd.isna(ds):
            return None
        if dl > 0 and ds < 0:
            return "nuevos_long_y_cierre_short"
        if dl > 0 and ds > 0:
            return "aumentan_ambas"
        if dl < 0 and ds < 0:
            return "se_reducen_ambas"
        if dl < 0 and ds > 0:
            return "menos_long_y_mas_short"
        if dl == 0 and ds == 0:
            return "sin_cambio"
        return "mixta_o_unilateral"

    out["accum_liq_pattern"] = out.apply(_accum_label, axis=1)

    # Criterio 5 — OI Δ (market-level; duplicated across groups by design for join ease)
    oi_prev = out.groupby(["market", "trader_group"])["open_interest_total"].shift(1).astype("Float64")
    oi_now = oi.astype("Float64")
    out["oi_change_abs"] = oi_now - oi_prev
    out["oi_change_pct"] = np.where(
        oi_prev.notna() & (oi_prev != 0), ((oi_now - oi_prev) / oi_prev) * 100.0, np.nan
    )
    out["oi_change_label"] = out["oi_change_pct"].map(
        lambda v: _oi_label(None if pd.isna(v) else float(v))
    )

    # Criterio 6 — % of OI by group (calculated; keep reported for contrast)
    long_f = out["long_positions"].astype("Float64")
    short_f = out["short_positions"].astype("Float64")
    spread_f = out["spreading_positions"].astype("Float64")
    out["pct_oi_long_calc"] = np.where(oi_now.notna() & (oi_now != 0), (long_f / oi_now) * 100.0, np.nan)
    out["pct_oi_short_calc"] = np.where(oi_now.notna() & (oi_now != 0), (short_f / oi_now) * 100.0, np.nan)
    out["pct_oi_spread_calc"] = np.where(
        oi_now.notna() & (oi_now != 0) & spread_f.notna(),
        (spread_f / oi_now) * 100.0,
        np.nan,
    )
    gross = long_f.fillna(0) + short_f.fillna(0) + spread_f.fillna(0)
    out["pct_oi_gross_calc"] = np.where(oi_now.notna() & (oi_now != 0), (gross / oi_now) * 100.0, np.nan)

    # Criterio 7 — Net change by horizon (lag within market × group)
    gkeys = ["market", "trader_group"]
    for name, weeks in horizons.items():
        start = out.groupby(gkeys)["net_position"].shift(weeks)
        chg = out["net_position"].astype("Float64") - start.astype("Float64")
        out[f"net_start_{name}"] = start
        out[f"net_change_{name}"] = chg
        out[f"net_change_nn_{name}"] = np.where(
            oi_now.notna() & (oi_now != 0) & chg.notna(),
            (chg / oi_now) * 100.0,
            np.nan,
        )
        out[f"direction_{name}"] = [
            _direction_from_change(
                None if pd.isna(c) else float(c),
                None if pd.isna(o) else float(o),
                neutral,
            )
            for c, o in zip(chg, oi_now, strict=False)
        ]

    # Criterio 8–9 — Percentiles of net and normalized net (52w / 156w)
    def _apply_pctl(col: str, window: int, min_obs: int, out_col: str) -> None:
        out[out_col] = out.groupby(gkeys, group_keys=False)[col].apply(
            lambda s: _rolling_percentile(s, window=window, min_obs=min_obs)
        )

    _apply_pctl("net_position", 52, min_pctl, "net_percentile_52w")
    _apply_pctl("normalized_net_pct", 52, min_pctl, "normalized_net_percentile_52w")
    _apply_pctl("net_position", 156, min_156, "net_percentile_156w")
    _apply_pctl("normalized_net_pct", 156, min_156, "normalized_net_percentile_156w")

    # Criterio 10 — Persistence
    parts_up = []
    parts_down = []
    for _, g in out.groupby(gkeys, sort=False):
        u, d = _consecutive_runs(g["delta_net_weekly"])
        parts_up.append(u)
        parts_down.append(d)
    out["consecutive_net_up"] = pd.concat(parts_up).reindex(out.index)
    out["consecutive_net_down"] = pd.concat(parts_down).reindex(out.index)

    for name, weeks in horizons.items():
        if name == "weekly":
            # Single observation: ratio is 1/0/NA based on sign of weekly Δ
            pos = (out["delta_net_weekly"] > 0).astype("Float64")
            neg = (out["delta_net_weekly"] < 0).astype("Float64")
            out[f"positive_net_change_ratio_{name}"] = np.where(
                out["delta_net_weekly"].notna(), pos, np.nan
            )
            out[f"negative_net_change_ratio_{name}"] = np.where(
                out["delta_net_weekly"].notna(), neg, np.nan
            )
            continue

        def _ratio_pos(s: pd.Series, w: int = weeks) -> pd.Series:
            return s.rolling(w, min_periods=max(2, w // 2)).apply(
                lambda x: float(np.sum(np.asarray(x) > 0) / len(x)), raw=False
            )

        def _ratio_neg(s: pd.Series, w: int = weeks) -> pd.Series:
            return s.rolling(w, min_periods=max(2, w // 2)).apply(
                lambda x: float(np.sum(np.asarray(x) < 0) / len(x)), raw=False
            )

        out[f"positive_net_change_ratio_{name}"] = out.groupby(gkeys, group_keys=False)[
            "delta_net_weekly"
        ].apply(_ratio_pos)
        out[f"negative_net_change_ratio_{name}"] = out.groupby(gkeys, group_keys=False)[
            "delta_net_weekly"
        ].apply(_ratio_neg)

    # Criterio 20 — Acceleration of |weekly Δ net| vs recent mean
    abs_d = out["delta_net_weekly"].abs()
    mean_abs = out.groupby(gkeys, group_keys=False)["delta_net_weekly"].apply(
        lambda s: s.abs().shift(1).rolling(accel_lb, min_periods=2).mean()
    )
    ratio = np.where(mean_abs.notna() & (mean_abs > 0) & abs_d.notna(), abs_d / mean_abs, np.nan)
    out["net_change_accel_ratio"] = ratio
    out["net_change_accel_label"] = [
        (
            None
            if (isinstance(r, float) and np.isnan(r)) or r is None or (isinstance(r, float) and pd.isna(r))
            else (
                "acelerando"
                if float(r) >= accel_thr
                else ("desacelerando" if float(r) <= (1.0 / accel_thr) else "estable")
            )
        )
        for r in ratio
    ]

    # Criterio 15 — Spread context (NOT part of directional net)
    if "spread_change_recalc" not in out.columns:
        out["spread_change_recalc"] = pd.Series([pd.NA] * len(out), dtype="Float64")
    if "spread_change" not in out.columns:
        out["spread_change"] = pd.Series([pd.NA] * len(out), dtype="Float64")
    if "spreading_positions" not in out.columns:
        out["spreading_positions"] = pd.Series([pd.NA] * len(out), dtype="Int64")
    spread_ch = out["spread_change_recalc"].combine_first(out["spread_change"]).astype("Float64")
    out["spread_change_used"] = spread_ch
    out["spread_context_note"] = "spread_no_direccional"
    out["spread_oi_pct"] = out["pct_oi_spread_calc"]
    out["spread_change_label"] = spread_ch.map(
        lambda v: (
            None
            if pd.isna(v)
            else ("spread_aumenta" if float(v) > 0 else ("spread_disminuye" if float(v) < 0 else "spread_sin_cambio"))
        )
    )

    # Criterio 21 — Regime change: sign cross of net_position
    prev_net = out.groupby(gkeys)["net_position"].shift(1)
    cur_net = out["net_position"].astype("Float64")
    crossed = (
        prev_net.notna()
        & cur_net.notna()
        & (prev_net != 0)
        & (cur_net != 0)
        & (np.sign(prev_net) != np.sign(cur_net))
    )
    out["regime_cross_flag"] = crossed
    out["regime_net_before"] = np.where(crossed, prev_net, np.nan)
    out["regime_net_after"] = np.where(crossed, cur_net, np.nan)
    out["regime_direction"] = [
        (
            None
            if not bool(flag)
            else ("cruzo_a_neto_positivo" if float(cur) > 0 else "cruzo_a_neto_negativo")
        )
        for flag, cur in zip(crossed, cur_net, strict=False)
    ]
    # Weeks since last cross (inclusive of cross week = 0)
    weeks_since = []
    for _, g in out.groupby(gkeys, sort=False):
        last = None
        for i, flag in enumerate(g["regime_cross_flag"].tolist()):
            if flag:
                last = i
            weeks_since.append(None if last is None else i - last)
    out["weeks_since_regime_cross"] = pd.Series(weeks_since, index=out.index, dtype="Float64")

    # History length per series (for quality / 156w availability warnings)
    out["history_weeks"] = out.groupby(gkeys).cumcount() + 1

    return out


def group_divergence_snapshot(
    latest: pd.DataFrame,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Criterion 22 — LF vs AM: separate level-NN gap from weekly-change agreement.
    Returns dict suitable for market-level scoring / JSON.
    """
    if rules is None:
        rules = load_scoring_rules()
    dcfg = rules.get("divergence") or {}
    gap_thr = float(dcfg.get("nn_level_gap_pct", 5.0))
    chg_thr = float(dcfg.get("change_disagree_oi_pct", 0.5))

    lf = latest.loc[latest["trader_group"] == "Leveraged Funds"]
    am = latest.loc[latest["trader_group"] == "Asset Manager / Institutional"]
    if lf.empty or am.empty:
        return {
            "available": False,
            "nn_level_gap_pct": None,
            "nn_levels_diverge": None,
            "weekly_change_agreement": None,
            "note": "LF o AM ausente",
        }
    lf_nn = float(lf.iloc[0]["normalized_net_pct"]) if pd.notna(lf.iloc[0]["normalized_net_pct"]) else None
    am_nn = float(am.iloc[0]["normalized_net_pct"]) if pd.notna(am.iloc[0]["normalized_net_pct"]) else None
    lf_dn = float(lf.iloc[0]["delta_net_weekly"]) if pd.notna(lf.iloc[0]["delta_net_weekly"]) else None
    am_dn = float(am.iloc[0]["delta_net_weekly"]) if pd.notna(am.iloc[0]["delta_net_weekly"]) else None
    oi = float(lf.iloc[0]["open_interest_total"]) if pd.notna(lf.iloc[0]["open_interest_total"]) else None

    gap = None if lf_nn is None or am_nn is None else abs(lf_nn - am_nn)
    levels_diverge = None if gap is None else gap >= gap_thr

    agreement = None
    if lf_dn is not None and am_dn is not None and oi and oi != 0:
        lf_nn_chg = lf_dn / oi * 100.0
        am_nn_chg = am_dn / oi * 100.0
        if abs(lf_nn_chg) < chg_thr and abs(am_nn_chg) < chg_thr:
            agreement = "ambos_cambios_neutrales"
        elif lf_nn_chg > chg_thr and am_nn_chg > chg_thr:
            agreement = "acuerdo_mejora"
        elif lf_nn_chg < -chg_thr and am_nn_chg < -chg_thr:
            agreement = "acuerdo_deterioro"
        elif (lf_nn_chg > chg_thr and am_nn_chg < -chg_thr) or (
            lf_nn_chg < -chg_thr and am_nn_chg > chg_thr
        ):
            agreement = "desacuerdo_cambios"
        else:
            agreement = "mixto_un_lado_neutral"

    return {
        "available": True,
        "lf_nn_pct": lf_nn,
        "am_nn_pct": am_nn,
        "nn_level_gap_pct": None if gap is None else round(gap, 4),
        "nn_levels_diverge": levels_diverge,
        "lf_delta_net_weekly": lf_dn,
        "am_delta_net_weekly": am_dn,
        "weekly_change_agreement": agreement,
        "note": (
            "Niveles NN y acuerdo de cambios semanales se evalúan por separado "
            "(Criterio 22); no confundir diferencia de nivel con desacuerdo de Δ."
        ),
    }


def latest_snapshot(indicators: pd.DataFrame) -> pd.DataFrame:
    """One row per market × trader_group at the max report_date available per market."""
    if indicators.empty:
        return indicators
    idx = indicators.groupby(["market", "trader_group"])["report_date"].idxmax()
    return indicators.loc[idx].sort_values(["market", "trader_group"]).reset_index(drop=True)


def market_summary(latest: pd.DataFrame) -> pd.DataFrame:
    """Compact summary focused on Leveraged Funds + Asset Managers."""
    focus = latest[
        latest["trader_group"].isin(["Leveraged Funds", "Asset Manager / Institutional"])
    ].copy()
    cols = [
        "market",
        "report_date",
        "trader_group",
        "net_position",
        "normalized_net_pct",
        "delta_net_weekly",
        "delta_net_label",
        "accum_liq_pattern",
        "open_interest_total",
        "oi_change_pct",
        "oi_change_label",
        "pct_oi_long_calc",
        "pct_oi_short_calc",
        "net_percentile_52w",
        "normalized_net_percentile_52w",
        "net_percentile_156w",
        "normalized_net_percentile_156w",
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
    for h in HORIZON_ORDER:
        cols.append(f"net_change_{h}")
        cols.append(f"direction_{h}")
    return focus[[c for c in cols if c in focus.columns]]
