#!/usr/bin/env python3
"""COT TFF FX pipeline entrypoint (F10 + USD INDEX/DXY).

Usage (from cot_system/):
    python main.py
    python main.py --years 2023 2024 2025 2026
    python main.py --skip-price
    python main.py --from-csv-only   # regenerar HTML/JSON desde CSV (sin pandas)
    python main.py --as-of 2025-06-17  # backtest: solo datos <= esa semana (sin look-ahead)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.appcontrol_help import format_import_failure  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download CFTC TFF FX+DXY data and build reports.")
    p.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2023, 2024, 2025, 2026],
        help="Calendar years of official fut_fin_txt archives to download.",
    )
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=ROOT.parent / "docs" / "reports",
        help="Directory for HTML/JSON outputs (default: docs/reports).",
    )
    p.add_argument(
        "--skip-price",
        action="store_true",
        help="Skip Yahoo price download (Criteria 16-19 omitted from scoring blend).",
    )
    p.add_argument(
        "--from-csv-only",
        action="store_true",
        help=(
            "Regenerate HTML/JSON from data/processed/*.csv using only "
            "stdlib csv (no pandas). Escape hatch when App Control "
            "blocks pandas DLLs but processed CSVs already exist."
        ),
    )
    p.add_argument(
        "--as-of",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Backtest cutoff (week end or any calendar day). Pipeline keeps only "
            "COT report_date <= date and price_date <= date before indicators/"
            "percentiles/scoring/weekly recs (no look-ahead). Outputs "
            "docs/reports/cot_tff_fx_backtest_<asof>.{html,json}; does not "
            "overwrite cot_tff_fx_latest.*"
        ),
    )
    return p.parse_args()


def run_from_csv_only(reports_dir: Path) -> int:
    """Pandas-free path: rebuild reports from processed CSVs."""
    try:
        from src.report_lite import regenerate_from_processed
    except ImportError as exc:
        print(format_import_failure(exc), file=sys.stderr)
        return 1

    processed_dir = ROOT / "data" / "processed"
    print("Modo --from-csv-only (sin pandas): regenerando informes desde CSV...")
    try:
        paths = regenerate_from_processed(processed_dir, reports_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Necesitas data/processed/fx_tff_scored.csv de una ejecución previa "
            "con pandas. En Windows usa launcher\\run_cot_windows.ps1 con Python 3.12.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        print(format_import_failure(exc) if "dll" in str(exc).lower() else f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Done (lite).")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    return 0


def run_full(args: argparse.Namespace) -> int:
    try:
        from src.as_of import (
            backtest_meta,
            backtest_stem,
            effective_report_as_of,
            parse_as_of,
            truncate_cot_history,
            truncate_price_history,
        )
        from src.cot_indicators import compute_indicators
        from src.data_loader import load_fx_tff
        from src.data_validation import validate_and_enrich
        from src.price_confirmation import attach_price_features, download_price_panel
        from src.report import write_html
        from src.scoring import score_markets
        from src.timeframes import load_scoring_rules
    except ImportError as exc:
        print(format_import_failure(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - DLL load often raises ImportError subclass or OSError
        from src.appcontrol_help import looks_like_appcontrol

        if looks_like_appcontrol(exc):
            print(format_import_failure(exc), file=sys.stderr)
            return 2
        raise

    raw_dir = ROOT / "data" / "raw"
    processed_dir = ROOT / "data" / "processed"
    price_dir = ROOT / "data" / "price"
    processed_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    rules = load_scoring_rules(ROOT / "config" / "scoring_rules.json")

    as_of_date = None
    bt_meta = None
    if args.as_of:
        try:
            as_of_date = parse_as_of(args.as_of)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(
            f"Modo BACKTEST as-of={as_of_date.isoformat()} "
            "(solo report_date/price_date <= cutoff; sin look-ahead)."
        )

    print("1/7 Loading CFTC TFF Futures Only (F10 + F15 si hay + USD INDEX/DXY)...")
    long_df = load_fx_tff(years=args.years, raw_dir=raw_dir)
    n_before = len(long_df)
    if as_of_date is not None:
        long_df = truncate_cot_history(long_df, as_of_date)
        print(
            f"   truncate COT: {n_before} → {len(long_df)} rows "
            f"(report_date <= {as_of_date.isoformat()})"
        )
    markets = sorted(long_df["market"].unique().tolist())
    print(f"   rows={len(long_df)} markets={len(markets)}")
    for m in markets:
        print(f"   - {m}")

    print("2/7 Validating (recalc changes, OI uniqueness)...")
    validated, vreport = validate_and_enrich(long_df)
    print(
        f"   as_of={vreport.as_of_date} weeks={vreport.n_dates} "
        f"warnings={len(vreport.warnings)}"
    )
    if as_of_date is not None:
        eff = effective_report_as_of(validated) or vreport.as_of_date
        bt_meta = backtest_meta(
            as_of_date,
            eff,
            n_rows_before=n_before,
            n_rows_after=len(validated),
        )
        if eff and eff > as_of_date.isoformat():
            print(
                f"ERROR: look-ahead detectado: effective_as_of={eff} > "
                f"requested={as_of_date.isoformat()}",
                file=sys.stderr,
            )
            return 3
        print(
            f"   backtest requested={bt_meta['requested_as_of']} "
            f"effective_COT_week={bt_meta['effective_as_of']}"
        )

    print("3/7 Computing indicators (1-10, 15, 20-21)...")
    indicators = compute_indicators(validated, rules=rules)

    price_meta: dict = {"enabled": False, "skipped": True}
    if args.skip_price or not (rules.get("price") or {}).get("enabled", True):
        print("4/7 Price confirmation SKIPPED (--skip-price or rules.price.enabled=false).")
        indicators["price_available"] = False
    else:
        print("4/7 Downloading Yahoo weekly prices (CME FX + DX-Y.NYB + F15)...")
        panel, price_meta = download_price_panel(markets, price_dir=price_dir)
        if as_of_date is not None:
            n_px_before = len(panel)
            panel = truncate_price_history(panel, as_of_date)
            print(
                f"   truncate price: {n_px_before} → {len(panel)} rows "
                f"(price_date <= {as_of_date.isoformat()})"
            )
            price_meta["as_of_truncated"] = True
            price_meta["as_of"] = as_of_date.isoformat()
        price_meta["enabled"] = True
        price_meta["skipped"] = False
        indicators = attach_price_features(indicators, panel, rules=rules)
        n_px = int(indicators["price_available"].fillna(False).sum()) if "price_available" in indicators else 0
        print(
            f"   price_rows={len(panel)} mapped={len(price_meta.get('markets_mapped', {}))} "
            f"indicator_rows_with_price={n_px} errors={price_meta.get('fetch_errors')}"
        )

    # Avoid clobbering live processed artifacts when backtesting
    if as_of_date is not None:
        stem = backtest_stem(as_of_date)
        csv_path = processed_dir / f"{stem}_indicators.csv"
        parquet_path = processed_dir / f"{stem}_indicators.parquet"
        scored_csv = processed_dir / f"{stem}_scored.csv"
        weekly_csv = processed_dir / f"{stem}_weekly.csv"
    else:
        csv_path = processed_dir / "fx_tff_indicators.csv"
        parquet_path = processed_dir / "fx_tff_indicators.parquet"
        scored_csv = processed_dir / "fx_tff_scored.csv"
        weekly_csv = processed_dir / "fx_tff_weekly.csv"

    indicators.to_csv(csv_path, index=False)
    try:
        indicators.to_parquet(parquet_path, index=False)
        print(f"   wrote {csv_path.name} + {parquet_path.name}")
    except Exception as exc:  # noqa: BLE001
        print(f"   wrote {csv_path.name} (parquet skipped: {exc})")

    print("5/7 Scoring (bias + quality; complementary Other/Nonrep; C22; price if present)...")
    scored = score_markets(indicators, rules=rules)
    scored.drop(columns=[c for c in scored.columns if c.startswith("_")], errors="ignore").to_csv(
        scored_csv, index=False
    )
    print(f"   markets_scored={len(scored)} -> {scored_csv.name}")

    print("6/7 Recomendación semanal de pares swing (secciones)...")
    from src.data_loader import load_market_config
    from src.weekly_recommendations import build_weekly_recommendations, weekly_top_n

    mkt_cfg = load_market_config()
    weekly = build_weekly_recommendations(scored, cfg=mkt_cfg, rules=rules)
    weekly.to_csv(weekly_csv, index=False)
    top3 = weekly_top_n(weekly, 3)
    print(f"   pairs={len(weekly)} -> {weekly_csv.name}")
    for t in top3:
        print(
            f"   #{t.get('rank_global')} {t.get('symbol')} "
            f"{t.get('priority')} bias={t.get('pair_bias')} q={t.get('evidence_quality')}"
        )

    print("7/7 Writing HTML + JSON reports...")
    if as_of_date is not None:
        stem = backtest_stem(as_of_date)
        html = args.reports_dir / f"{stem}.html"
        write_html(
            indicators,
            vreport,
            html,
            scored=scored,
            rules=rules,
            price_meta=price_meta,
            weekly=weekly,
            backtest=bt_meta,
        )
        print("Done (backtest).")
        print(f"  HTML:  {html}")
        print(f"  JSON:  {html.with_suffix('.json')}")
        print(f"  (latest aliases NOT updated in backtest mode)")
    else:
        as_of = vreport.as_of_date or "unknown"
        html = args.reports_dir / f"cot_tff_fx_{as_of}.html"
        html_latest = args.reports_dir / "cot_tff_fx_latest.html"

        write_html(
            indicators,
            vreport,
            html,
            scored=scored,
            rules=rules,
            price_meta=price_meta,
            weekly=weekly,
        )
        write_html(
            indicators,
            vreport,
            html_latest,
            scored=scored,
            rules=rules,
            price_meta=price_meta,
            weekly=weekly,
        )
        print("Done.")
        print(f"  HTML:  {html}")
        print(f"  Latest: {html_latest.name}")

    print(f"  Scoring version: {rules.get('version')} provisional={rules.get('provisional')}")
    if vreport.warnings:
        print("  Warnings:")
        for w in vreport.warnings:
            print(f"   - {w}")
    return 0


def main() -> int:
    args = parse_args()
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    if args.from_csv_only and args.as_of:
        print(
            "ERROR: --from-csv-only no soporta --as-of (necesita truncar con pandas "
            "antes de indicadores). Ejecuta el pipeline completo con --as-of.",
            file=sys.stderr,
        )
        return 2
    if args.from_csv_only:
        return run_from_csv_only(args.reports_dir)
    return run_full(args)


if __name__ == "__main__":
    raise SystemExit(main())
