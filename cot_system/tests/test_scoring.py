"""Smoke tests for provisional dual scoring + new criteria wiring."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cot_indicators import compute_indicators, group_divergence_snapshot  # noqa: E402
from src.data_loader import filter_fx, load_market_config  # noqa: E402
from src.scoring import classify_bias, score_markets  # noqa: E402
from src.timeframes import load_scoring_rules  # noqa: E402


def _synthetic_series(n: int = 60) -> pd.DataFrame:
    """Build a short LF+AM+Dealer+Other+Nonrep weekly series with rising LF net."""
    rows = []
    base = pd.Timestamp("2024-01-02")
    for i in range(n):
        d = base + pd.Timedelta(weeks=i)
        oi = 100_000
        lf_long = 10_000 + i * 200
        lf_short = 8_000
        am_long = 20_000
        am_short = 22_000 + i * 50
        dealer_long = 30_000
        dealer_short = 25_000
        for tg, lo, sh, sp in [
            ("Leveraged Funds", lf_long, lf_short, 500),
            ("Asset Manager / Institutional", am_long, am_short, 200),
            ("Dealer / Intermediary", dealer_long, dealer_short, 1000),
            ("Other Reportables", 5_000, 4_000, 100),
            ("Nonreportable", 3_000, 3_500, None),
        ]:
            rows.append(
                {
                    "market": "TEST FX",
                    "report_type": "TFF",
                    "report_date": d,
                    "trader_group": tg,
                    "long_positions": lo,
                    "short_positions": sh,
                    "spreading_positions": sp if sp is not None else pd.NA,
                    "long_change": pd.NA,
                    "short_change": pd.NA,
                    "spread_change": pd.NA,
                    "long_change_recalc": pd.NA,
                    "short_change_recalc": pd.NA,
                    "spread_change_recalc": pd.NA,
                    "open_interest_total": oi,
                    "pct_oi_long_reported": pd.NA,
                    "pct_oi_short_reported": pd.NA,
                }
            )
    df = pd.DataFrame(rows)
    df = df.sort_values(["trader_group", "report_date"])
    g = df.groupby("trader_group")
    df["long_change_recalc"] = g["long_positions"].diff().astype("Int64")
    df["short_change_recalc"] = g["short_positions"].diff().astype("Int64")
    df["spread_change_recalc"] = g["spreading_positions"].diff().astype("Float64")
    df["long_change"] = df["long_change_recalc"]
    df["short_change"] = df["short_change_recalc"]
    return df


def test_classify_bias_bands():
    rules = load_scoring_rules()
    assert classify_bias(70, rules) == "fuertemente_alcista"
    assert classify_bias(30, rules) == "moderadamente_alcista"
    assert classify_bias(0, rules) == "neutral_o_mixto"
    assert classify_bias(-30, rules) == "moderadamente_bajista"
    assert classify_bias(-70, rules) == "fuertemente_bajista"


def test_score_markets_runs():
    rules = load_scoring_rules()
    ind = compute_indicators(_synthetic_series(), rules=rules)
    ind["price_available"] = False
    scored = score_markets(ind, rules=rules)
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["market"] == "TEST FX"
    assert bool(row["provisional_thresholds"]) is True
    assert -100 <= float(row["combined_bias"]) <= 100
    assert 0 <= float(row["evidence_quality"]) <= 100
    assert row["LF_bias"] is not None and not pd.isna(row["LF_bias"])
    assert float(row["LF_bias"]) >= 0
    assert "OR_bias" in scored.columns
    assert "NR_bias" in scored.columns
    assert "c22_weekly_change_agreement" in scored.columns


def test_horizon_columns_present():
    rules = load_scoring_rules()
    ind = compute_indicators(_synthetic_series(), rules=rules)
    for col in [
        "net_change_weekly",
        "net_change_monthly",
        "net_change_quarterly",
        "net_change_semiannual",
        "net_change_annual",
        "net_percentile_52w",
        "net_percentile_156w",
        "consecutive_net_up",
        "net_change_accel_ratio",
        "spread_context_note",
        "regime_cross_flag",
        "weeks_since_regime_cross",
    ]:
        assert col in ind.columns
    latest = ind.sort_values("report_date").groupby("trader_group").tail(1)
    assert latest["net_percentile_52w"].notna().any()


def test_group_divergence_helper():
    rules = load_scoring_rules()
    ind = compute_indicators(_synthetic_series(), rules=rules)
    latest = ind.sort_values("report_date").groupby("trader_group").tail(1)
    d = group_divergence_snapshot(latest, rules=rules)
    assert d["available"] is True
    assert d["nn_level_gap_pct"] is not None


def test_filter_includes_usd_index():
    cfg = load_market_config()
    df = pd.DataFrame(
        {
            "Market_and_Exchange_Names": [
                "EURO FX - CHICAGO MERCANTILE EXCHANGE",
                "USD INDEX - ICE FUTURES U.S.",
                "VIX FUTURES - CBOE FUTURES EXCHANGE",
            ],
            "CFTC_SubGroup_Code": ["F10", "F90", "F90"],
            "CFTC_Contract_Market_Code": ["099741", "098662", "1170E1"],
        }
    )
    out = filter_fx(df, cfg=cfg)
    names = set(out["Market_and_Exchange_Names"])
    assert "EURO FX - CHICAGO MERCANTILE EXCHANGE" in names
    assert "USD INDEX - ICE FUTURES U.S." in names
    assert "VIX FUTURES - CBOE FUTURES EXCHANGE" not in names


if __name__ == "__main__":
    test_classify_bias_bands()
    test_score_markets_runs()
    test_horizon_columns_present()
    test_group_divergence_helper()
    test_filter_includes_usd_index()
    print("OK")
