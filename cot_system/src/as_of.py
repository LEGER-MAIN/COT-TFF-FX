"""As-of / backtest cutoff helpers — no look-ahead.

All COT (`report_date`) and price (`price_date`) rows after the cutoff are dropped
*before* indicators, percentiles, scoring, and weekly recommendations.

Week convention (Forex Factory–style): Sunday–Saturday; COT released Friday →
week ends Saturday. See ``week_calendar.saturday_of_week``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from .week_calendar import (  # noqa: F401 — re-export for callers
    last_week_saturday,
    saturday_of_week,
    this_week_saturday,
    week_range,
)


def parse_as_of(value: str | date | datetime | pd.Timestamp) -> date:
    """Parse YYYY-MM-DD (or date-like) into a calendar date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    s = str(value).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError as exc:
        raise ValueError(
            f"--as-of debe ser YYYY-MM-DD (p. ej. 2025-06-17); recibido: {value!r}"
        ) from exc


def truncate_cot_history(df: pd.DataFrame, as_of: date | str) -> pd.DataFrame:
    """Keep rows with report_date <= as_of. Empty → RuntimeError."""
    cutoff = parse_as_of(as_of)
    if df is None or df.empty:
        raise RuntimeError(f"Sin filas COT que truncar a as-of={cutoff.isoformat()}.")
    if "report_date" not in df.columns:
        raise KeyError("DataFrame COT sin columna report_date.")
    out = df.copy()
    rd = pd.to_datetime(out["report_date"], errors="coerce")
    mask = rd.notna() & (rd.dt.normalize() <= pd.Timestamp(cutoff))
    out = out.loc[mask].copy()
    if out.empty:
        raise RuntimeError(
            f"Tras truncar a report_date <= {cutoff.isoformat()} no queda historial COT. "
            "Elige una fecha posterior a la primera semana disponible."
        )
    return out.reset_index(drop=True)


def truncate_price_history(panel: pd.DataFrame, as_of: date | str) -> pd.DataFrame:
    """Keep rows with price_date <= as_of (empty panel stays empty)."""
    cutoff = parse_as_of(as_of)
    if panel is None or panel.empty:
        return panel if panel is not None else pd.DataFrame()
    if "price_date" not in panel.columns:
        return panel
    out = panel.copy()
    pd_ = pd.to_datetime(out["price_date"], errors="coerce")
    mask = pd_.notna() & (pd_.dt.normalize() <= pd.Timestamp(cutoff))
    return out.loc[mask].copy().reset_index(drop=True)


def effective_report_as_of(df: pd.DataFrame) -> str | None:
    """Max report_date in truncated COT frame (ISO date string)."""
    if df is None or df.empty or "report_date" not in df.columns:
        return None
    mx = pd.to_datetime(df["report_date"], errors="coerce").max()
    if pd.isna(mx):
        return None
    return str(pd.Timestamp(mx).date())


def backtest_meta(
    requested: date | str,
    effective: str | None,
    *,
    n_rows_before: int | None = None,
    n_rows_after: int | None = None,
) -> dict[str, Any]:
    """Metadata for reports / JSON (mode=backtest, no look-ahead)."""
    req = parse_as_of(requested).isoformat()
    return {
        "mode": "backtest",
        "requested_as_of": req,
        "effective_as_of": effective or req,
        "no_look_ahead": True,
        "note_es": (
            "Backtest semanal: solo datos COT/precio con fecha <= as-of "
            "(report_date / price_date). Sin look-ahead: indicadores, percentiles, "
            "scoring y recomendación semanal usan únicamente historial hasta esa semana."
        ),
        "n_rows_before": n_rows_before,
        "n_rows_after": n_rows_after,
    }


def backtest_stem(as_of: date | str) -> str:
    """Filename stem: cot_tff_fx_backtest_YYYY-MM-DD."""
    return f"cot_tff_fx_backtest_{parse_as_of(as_of).isoformat()}"
