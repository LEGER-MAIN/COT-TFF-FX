"""Unit checks for Criteria 1–2 against the manual example."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cot_indicators import compute_indicators  # noqa: E402


def test_net_and_normalized_from_manual_example():
    # Manual: Long 18063, Short 14880, OI 100000 → NN = 3.183%
    df = pd.DataFrame(
        [
            {
                "market": "TEST FX",
                "report_type": "TFF",
                "report_date": pd.Timestamp("2024-01-02"),
                "trader_group": "Leveraged Funds",
                "long_positions": 18063,
                "short_positions": 14880,
                "spreading_positions": 0,
                "long_change": pd.NA,
                "short_change": pd.NA,
                "long_change_recalc": pd.NA,
                "short_change_recalc": pd.NA,
                "open_interest_total": 100000,
                "pct_oi_long_reported": pd.NA,
                "pct_oi_short_reported": pd.NA,
            },
            {
                "market": "TEST FX",
                "report_type": "TFF",
                "report_date": pd.Timestamp("2024-01-09"),
                "trader_group": "Leveraged Funds",
                "long_positions": 17118,  # ΔLong −945
                "short_positions": 12828,  # ΔShort −2052
                "spreading_positions": 0,
                "long_change": -945,
                "short_change": -2052,
                "long_change_recalc": -945,
                "short_change_recalc": -2052,
                "open_interest_total": 100000,
                "pct_oi_long_reported": pd.NA,
                "pct_oi_short_reported": pd.NA,
            },
        ]
    )
    out = compute_indicators(df)
    row0 = out.iloc[0]
    row1 = out.iloc[1]
    assert int(row0["net_position"]) == 3183
    assert abs(float(row0["normalized_net_pct"]) - 3.183) < 1e-6
    assert int(row1["delta_net_weekly"]) == 1107
    assert row1["delta_net_label"] == "mejora_alcista"
    assert row1["accum_liq_pattern"] == "se_reducen_ambas"


if __name__ == "__main__":
    test_net_and_normalized_from_manual_example()
    print("OK")
