"""No look-ahead: truncate COT/price before indicators; week→Saturday."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.as_of import (
    backtest_stem,
    parse_as_of,
    saturday_of_week,
    truncate_cot_history,
    truncate_price_history,
    week_range,
)
from src.week_calendar import last_week_saturday, this_week_saturday


def test_parse_as_of():
    assert parse_as_of("2025-06-17") == date(2025, 6, 17)
    with pytest.raises(ValueError):
        parse_as_of("not-a-date")


def test_truncate_cot_no_lookahead():
    df = pd.DataFrame(
        {
            "market": ["A", "A", "A"],
            "report_date": pd.to_datetime(
                ["2025-06-10", "2025-06-17", "2025-06-24"]
            ),
            "net": [1, 2, 3],
        }
    )
    out = truncate_cot_history(df, "2025-06-17")
    assert list(out["report_date"].dt.strftime("%Y-%m-%d")) == [
        "2025-06-10",
        "2025-06-17",
    ]
    assert out["net"].max() == 2


def test_truncate_price_no_lookahead():
    panel = pd.DataFrame(
        {
            "market": ["A", "A"],
            "price_date": pd.to_datetime(["2025-06-16", "2025-06-23"]),
            "close": [1.0, 2.0],
        }
    )
    out = truncate_price_history(panel, "2025-06-17")
    assert len(out) == 1
    assert float(out["close"].iloc[0]) == 1.0


def test_backtest_stem():
    assert backtest_stem("2025-06-17") == "cot_tff_fx_backtest_2025-06-17"


def test_saturday_of_week_maps_any_day():
    # Week Sun 2025-06-15 … Sat 2025-06-21
    assert saturday_of_week(date(2025, 6, 15)) == date(2025, 6, 21)  # Sunday
    assert saturday_of_week(date(2025, 6, 17)) == date(2025, 6, 21)  # Tuesday
    assert saturday_of_week(date(2025, 6, 20)) == date(2025, 6, 21)  # Friday (COT release)
    assert saturday_of_week(date(2025, 6, 21)) == date(2025, 6, 21)  # Saturday
    assert saturday_of_week("2025-06-18") == date(2025, 6, 21)


def test_week_range_sun_sat():
    sun, sat = week_range("2025-06-17")
    assert sun == date(2025, 6, 15)
    assert sat == date(2025, 6, 21)
    assert (sat - sun).days == 6


def test_this_and_last_week_saturday():
    today = date(2025, 6, 18)  # Wednesday
    assert this_week_saturday(today) == date(2025, 6, 21)
    assert last_week_saturday(today) == date(2025, 6, 14)
