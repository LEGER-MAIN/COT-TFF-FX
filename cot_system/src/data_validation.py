"""Quality rules for TFF FX series (plan §2.3)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationReport:
    n_rows: int = 0
    n_markets: int = 0
    n_dates: int = 0
    as_of_date: str | None = None
    min_date: str | None = None
    warnings: list[str] = field(default_factory=list)
    oi_duplicate_market_dates: int = 0
    change_mismatch_rows: int = 0
    missing_position_cells: int = 0

    def to_dict(self) -> dict:
        return {
            "n_rows": self.n_rows,
            "n_markets": self.n_markets,
            "n_dates": self.n_dates,
            "as_of_date": self.as_of_date,
            "min_date": self.min_date,
            "oi_duplicate_market_dates": self.oi_duplicate_market_dates,
            "change_mismatch_rows": self.change_mismatch_rows,
            "missing_position_cells": self.missing_position_cells,
            "warnings": list(self.warnings),
        }


def _recalc_changes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["market", "trader_group", "report_date"]).copy()
    g = out.groupby(["market", "trader_group"], sort=False)
    out["long_change_recalc"] = g["long_positions"].diff().astype("Int64")
    out["short_change_recalc"] = g["short_positions"].diff().astype("Int64")
    out["spread_change_recalc"] = g["spreading_positions"].diff().astype("Float64")
    # OI change once per market/date series (same across groups); use Dealer as anchor later.
    oi_by_md = (
        out.drop_duplicates(["market", "report_date"])[["market", "report_date", "open_interest_total"]]
        .sort_values(["market", "report_date"])
        .copy()
    )
    oi_by_md["oi_change_recalc"] = oi_by_md.groupby("market")["open_interest_total"].diff().astype("Int64")
    out = out.merge(
        oi_by_md[["market", "report_date", "oi_change_recalc"]],
        on=["market", "report_date"],
        how="left",
    )
    return out


def validate_and_enrich(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """
    - Recalculate weekly changes for integrity check
    - Flag OI inconsistencies (should be unique per market/date)
    - Never fill missing with 0
    """
    report = ValidationReport()
    if df.empty:
        report.warnings.append("Empty dataset after FX filter.")
        return df, report

    out = _recalc_changes(df)

    # Missing ≠ 0: count true NAs in core position fields.
    pos_cols = ["long_positions", "short_positions", "open_interest_total"]
    report.missing_position_cells = int(out[pos_cols].isna().sum().sum())

    # OI uniqueness: all trader_group rows for same market/date must share same OI.
    oi_var = (
        out.groupby(["market", "report_date"])["open_interest_total"]
        .nunique(dropna=False)
        .reset_index(name="n_oi")
    )
    dup = oi_var[oi_var["n_oi"] > 1]
    report.oi_duplicate_market_dates = int(len(dup))
    if report.oi_duplicate_market_dates:
        report.warnings.append(
            f"OI not unique for {report.oi_duplicate_market_dates} market/date pairs "
            "(should not happen in official TFF)."
        )

    # Compare published vs recalculated changes where both available.
    for pub, recalc in [
        ("long_change", "long_change_recalc"),
        ("short_change", "short_change_recalc"),
    ]:
        both = out[pub].notna() & out[recalc].notna()
        mismatch = both & (out[pub] != out[recalc])
        n = int(mismatch.sum())
        report.change_mismatch_rows += n
        if n:
            report.warnings.append(
                f"{n} rows where published {pub} ≠ recalculated {recalc} "
                "(first-week / revisions / missing prior week are common causes)."
            )

    report.n_rows = int(len(out))
    report.n_markets = int(out["market"].nunique())
    report.n_dates = int(out["report_date"].nunique())
    report.as_of_date = str(pd.to_datetime(out["report_date"]).max().date())
    report.min_date = str(pd.to_datetime(out["report_date"]).min().date())

    # Short history warning per market.
    weeks_per_market = out.groupby("market")["report_date"].nunique()
    short = weeks_per_market[weeks_per_market < 52]
    if len(short):
        names = ", ".join(f"{m} ({n}w)" for m, n in short.items())
        report.warnings.append(f"Markets with <52 weekly observations (percentiles limited): {names}")

    return out, report
