"""Compare core outputs against fixtures/ + golden/expected.json."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.as_of import parse_as_of, saturday_of_week
from src.cot_indicators import compute_indicators
from src.data_loader import filter_fx, load_market_config
from src.scoring import classify_bias, score_markets
from src.timeframes import load_scoring_rules

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
GOLDEN = HERE / "golden" / "expected.json"


def _expected() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_classify_bias_matches_golden():
    rules = load_scoring_rules()
    exp = _expected()["classify_bias"]
    for raw, label in exp.items():
        assert classify_bias(float(raw), rules) == label


def test_manual_net_matches_golden():
    df = pd.read_csv(FIXTURES / "manual_net_example.csv", parse_dates=["report_date"])
    out = compute_indicators(df)
    exp = _expected()["manual_net"]
    assert int(out.iloc[0]["net_position"]) == exp["net_position_w0"]
    assert abs(float(out.iloc[0]["normalized_net_pct"]) - exp["normalized_net_pct_w0"]) < 1e-6
    assert int(out.iloc[1]["delta_net_weekly"]) == exp["delta_net_weekly_w1"]
    assert out.iloc[1]["delta_net_label"] == exp["delta_net_label_w1"]
    assert out.iloc[1]["accum_liq_pattern"] == exp["accum_liq_pattern_w1"]


def test_synthetic_scoring_matches_golden():
    rules = load_scoring_rules()
    df = pd.read_csv(FIXTURES / "synthetic_long.csv", parse_dates=["report_date"])
    ind = compute_indicators(df, rules=rules)
    ind["price_available"] = False
    scored = score_markets(ind, rules=rules)
    assert len(scored) == 1
    row = scored.iloc[0]
    exp = _expected()["synthetic_scored"]
    assert row["market"] == exp["market"]
    assert bool(row["provisional_thresholds"]) is True
    assert round(float(row["combined_bias"]), 2) == exp["combined_bias"]
    assert round(float(row["evidence_quality"]), 2) == exp["evidence_quality"]
    assert round(float(row["LF_bias"]), 2) == exp["LF_bias"]
    assert -100 <= float(row["combined_bias"]) <= 100
    assert 0 <= float(row["evidence_quality"]) <= 100


def test_universe_excludes_mxn_zar_cnh_keeps_nzd():
    wide = pd.read_csv(FIXTURES / "universe_wide_sample.csv")
    cfg = load_market_config()
    out = filter_fx(wide, cfg=cfg)
    names = sorted(out["Market_and_Exchange_Names"].tolist())
    assert names == _expected()["universe_after_exclude"]
    joined = " | ".join(names)
    assert "MEXICAN" not in joined
    assert "AFRICAN" not in joined
    assert "RENMINBI" not in joined
    assert "NZ DOLLAR" in joined
    assert "USDMXN" not in {p["symbol"] for p in cfg["swing_pairs"]}
    assert "USDZAR" not in {p["symbol"] for p in cfg["swing_pairs"]}
    assert "USDCNH" not in {p["symbol"] for p in cfg["swing_pairs"]}
    assert "NZDUSD" in {p["symbol"] for p in cfg["swing_pairs"]}


def test_saturday_of_week_matches_golden():
    exp = _expected()["saturday_of_week"]
    for raw, sat in exp.items():
        assert saturday_of_week(parse_as_of(raw)).isoformat() == sat
