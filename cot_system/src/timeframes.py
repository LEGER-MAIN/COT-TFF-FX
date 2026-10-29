"""Horizon window helpers (plan §3 — Criterios 7–10 base).

Windows are observation counts on the weekly TFF series (approx. calendar spans).
Prefer lag-by-row within market × group after sorting by report_date.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_HORIZONS: dict[str, int] = {
    "weekly": 1,
    "monthly": 4,
    "quarterly": 13,
    "semiannual": 26,
    "annual": 52,
}

HORIZON_ORDER = ("weekly", "monthly", "quarterly", "semiannual", "annual")


def load_scoring_rules(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parents[1] / "config" / "scoring_rules.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def horizons_from_rules(rules: dict[str, Any] | None = None) -> dict[str, int]:
    if rules is None:
        rules = load_scoring_rules()
    raw = rules.get("horizons_weeks") or DEFAULT_HORIZONS
    return {k: int(raw[k]) for k in HORIZON_ORDER if k in raw}
