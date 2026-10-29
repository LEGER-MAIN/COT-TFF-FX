"""Price confirmation (Criteria 16–19) from free high-trust weekly closes.

Source: Yahoo Finance chart API. Tickers mapped in config/markets.json.
Aligns weekly closes to COT report_date via merge_asof (backward).
Never invents prices — missing tickers/dates stay null.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from .data_loader import load_market_config
from .timeframes import HORIZON_ORDER, horizons_from_rules, load_scoring_rules

YAHOO_CHART_HOSTS = (
    "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
)
SOURCE_LABEL = "Yahoo Finance weekly (chart API)"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ticker_map_from_config(cfg: dict | None = None) -> dict[str, str]:
    cfg = cfg or load_market_config()
    return dict((cfg.get("price_source") or {}).get("tickers") or {})


def resolve_ticker(market: str, tickers: dict[str, str]) -> str | None:
    """Match CFTC market name prefix to configured ticker key."""
    name = str(market).strip().upper().replace(" XRATE", "")
    # Prefer longest key match so EURO FX/… wins over EURO FX
    for key in sorted(tickers.keys(), key=len, reverse=True):
        k = key.upper().replace(" XRATE", "")
        if name.startswith(k) or name.split(" - ")[0].strip() == k:
            return tickers[key]
    return None


def _parse_yahoo_chart_payload(payload: dict, ticker: str) -> pd.DataFrame:
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        err = (payload.get("chart") or {}).get("error")
        print(f"WARN: Yahoo no result for {ticker}: {err}")
        return pd.DataFrame(columns=["price_date", "close", "ticker"])
    block = results[0]
    ts = block.get("timestamp") or []
    quote = (block.get("indicators") or {}).get("quote") or [{}]
    closes = (quote[0] or {}).get("close") or []
    rows = []
    for t, c in zip(ts, closes, strict=False):
        if c is None:
            continue
        rows.append(
            {
                "price_date": pd.to_datetime(t, unit="s", utc=True).tz_convert(None).normalize(),
                "close": float(c),
                "ticker": ticker,
            }
        )
    return pd.DataFrame(rows)


def fetch_yahoo_weekly(
    ticker: str,
    range_: str = "5y",
    session: requests.Session | None = None,
    max_retries: int = 4,
) -> pd.DataFrame:
    """Return DataFrame with columns: price_date, close. Empty if blocked/missing.

    Prefers curl subprocess (more reliable vs Yahoo 429 on some hosts), then requests.
    """
    import shutil
    import subprocess
    import time
    import urllib.parse

    # 1) curl path (often avoids Python UA rate limits)
    if shutil.which("curl"):
        for host_tmpl in YAHOO_CHART_HOSTS:
            base = host_tmpl.format(ticker=urllib.parse.quote(ticker, safe=""))
            url = f"{base}?interval=1wk&range={urllib.parse.quote(range_)}"
            try:
                proc = subprocess.run(
                    [
                        "curl",
                        "-sS",
                        "-A",
                        "Mozilla/5.0",
                        "-w",
                        "\n%{http_code}",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                body = proc.stdout or ""
                if "\n" in body:
                    *json_lines, code = body.rsplit("\n", 1)
                    raw = "\n".join(json_lines)
                else:
                    code, raw = "000", body
                if code.strip() == "200" and raw.strip().startswith("{"):
                    return _parse_yahoo_chart_payload(json.loads(raw), ticker)
            except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
                print(f"WARN: curl Yahoo failed for {ticker}: {exc}")
            time.sleep(0.8)

    # 2) requests fallback
    sess = session or requests.Session()
    sess.headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    resp = None
    for attempt in range(max_retries):
        url = YAHOO_CHART_HOSTS[attempt % len(YAHOO_CHART_HOSTS)].format(ticker=ticker)
        try:
            resp = sess.get(url, params={"interval": "1wk", "range": range_}, timeout=45)
        except requests.RequestException as exc:
            print(f"WARN: Yahoo fetch failed for {ticker}: {exc}")
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 429:
            wait = 3 * (attempt + 1)
            print(f"WARN: Yahoo 429 for {ticker}; retry in {wait}s…")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            print(f"WARN: Yahoo HTTP {resp.status_code} for {ticker} via {url.split('/')[2]}")
            time.sleep(1)
            continue
        break
    else:
        print(f"WARN: Yahoo exhausted retries for {ticker}")
        return pd.DataFrame(columns=["price_date", "close", "ticker"])

    assert resp is not None
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        print(f"WARN: Yahoo non-JSON for {ticker}")
        return pd.DataFrame(columns=["price_date", "close", "ticker"])
    return _parse_yahoo_chart_payload(payload, ticker)


def download_price_panel(
    markets: list[str],
    price_dir: Path | None = None,
    cfg: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Download weekly closes for configured markets.
    Returns long panel (market, ticker, price_date, close) + meta.
    """
    cfg = cfg or load_market_config()
    tickers = ticker_map_from_config(cfg)
    price_dir = price_dir or (_project_root() / "data" / "price")
    price_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    frames: list[pd.DataFrame] = []
    meta: dict[str, Any] = {
        "source": SOURCE_LABEL,
        "provider": (cfg.get("price_source") or {}).get("provider"),
        "markets_mapped": {},
        "markets_unmapped": [],
        "fetch_errors": [],
    }

    import time

    seen_tickers: dict[str, pd.DataFrame] = {}
    for market in sorted(set(markets)):
        ticker = resolve_ticker(market, tickers)
        if not ticker:
            meta["markets_unmapped"].append(market)
            continue
        meta["markets_mapped"][market] = ticker
        if ticker not in seen_tickers:
            # Prefer on-disk cache from a prior successful run
            cache = price_dir / f"{ticker.replace('=', '_').replace('^', '')}.csv"
            if cache.exists() and cache.stat().st_size > 50:
                cached = pd.read_csv(cache, parse_dates=["price_date"])
                if not cached.empty:
                    seen_tickers[ticker] = cached
                    print(f"   cache hit {ticker} ({len(cached)} rows)")
            if ticker not in seen_tickers:
                time.sleep(1.2)  # polite spacing to avoid Yahoo 429
                df = fetch_yahoo_weekly(ticker, session=session)
                if df.empty:
                    meta["fetch_errors"].append(ticker)
                    seen_tickers[ticker] = df
                else:
                    df.to_csv(cache, index=False)
                    seen_tickers[ticker] = df
        piece = seen_tickers[ticker].copy()
        if piece.empty:
            continue
        piece["market"] = market
        frames.append(piece)

    if not frames:
        return pd.DataFrame(columns=["market", "ticker", "price_date", "close"]), meta
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["market", "price_date"]).drop_duplicates(
        ["market", "price_date"], keep="last"
    )
    panel_path = price_dir / "fx_dx_weekly_panel.csv"
    out.to_csv(panel_path, index=False)
    meta["panel_path"] = str(panel_path)
    meta["n_rows"] = len(out)
    return out, meta


def _price_direction(ret_pct: float | None, sideways: float) -> str | None:
    if ret_pct is None or (isinstance(ret_pct, float) and np.isnan(ret_pct)):
        return None
    if abs(ret_pct) < sideways:
        return "lateral"
    return "sube" if ret_pct > 0 else "baja"


def _confirm_label(net_dir: str | None, price_dir: str | None) -> str | None:
    """Criterion 17 four-way label (no auto-reversal claim)."""
    if not net_dir or not price_dir or price_dir == "lateral" or net_dir == "neutral":
        if net_dir and price_dir == "lateral":
            return "precio_lateral_sin_confirmacion"
        return None
    if net_dir == "alcista" and price_dir == "sube":
        return "confirmacion_alcista_potencial"
    if net_dir == "bajista" and price_dir == "baja":
        return "confirmacion_bajista_potencial"
    if net_dir == "alcista" and price_dir == "baja":
        return "divergencia_neto_sube_precio_baja"
    if net_dir == "bajista" and price_dir == "sube":
        return "divergencia_neto_baja_precio_sube"
    return "mixta"


def _oi_price_label(price_dir: str | None, oi_label: str | None) -> str | None:
    """Criterion 19 — complementary reading only."""
    if not price_dir or not oi_label:
        return None
    return f"precio_{price_dir}_oi_{oi_label}"


def attach_price_features(
    indicators: pd.DataFrame,
    price_panel: pd.DataFrame,
    rules: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Merge weekly closes onto indicator rows and compute Criteria 16–19 columns.
    Price is market-level (duplicated across trader_groups for join ease).
    """
    if rules is None:
        rules = load_scoring_rules()
    out = indicators.copy()
    pcfg = rules.get("price") or {}
    sideways = float(pcfg.get("sideways_abs_return_pct", 0.5))
    horizons = horizons_from_rules(rules)

    def _with_empty_price(df: pd.DataFrame) -> pd.DataFrame:
        gg = df.copy()
        gg["price_close"] = np.nan
        gg["price_ticker"] = pd.NA
        gg["price_source"] = pd.NA
        gg["price_asof"] = pd.NaT
        gg["price_available"] = False
        return gg

    if price_panel is None or price_panel.empty:
        out = _with_empty_price(out)
        for h in HORIZON_ORDER:
            out[f"price_return_{h}"] = np.nan
            out[f"price_direction_{h}"] = pd.NA
            out[f"price_position_confirm_{h}"] = pd.NA
        out["price_extreme_alert"] = pd.NA
        out["oi_price_reading"] = pd.NA
        return out

    # Align: for each market, asof-merge report_date → latest weekly close on/before
    # Do NOT pre-create price_close on the left (merge would suffix _x/_y).
    pieces: list[pd.DataFrame] = []
    for market, g in out.groupby("market", sort=False):
        pp = price_panel.loc[price_panel["market"] == market].sort_values("price_date")
        if pp.empty:
            pieces.append(_with_empty_price(g))
            continue
        left = g.sort_values("report_date").copy()
        left["_rd"] = pd.to_datetime(left["report_date"])
        right = pp.rename(columns={"price_date": "_pd", "close": "_price_close"}).copy()
        right["_pd"] = pd.to_datetime(right["_pd"])
        merged = pd.merge_asof(
            left,
            right[["_pd", "_price_close", "ticker"]],
            left_on="_rd",
            right_on="_pd",
            direction="backward",
        )
        merged = merged.rename(
            columns={
                "ticker": "price_ticker",
                "_pd": "price_asof",
                "_price_close": "price_close",
            }
        )
        merged["price_source"] = SOURCE_LABEL
        merged["price_available"] = merged["price_close"].notna()
        merged = merged.drop(columns=["_rd"], errors="ignore")
        pieces.append(merged)
    out = pd.concat(pieces, ignore_index=True)
    out = out.sort_values(["market", "trader_group", "report_date"]).reset_index(drop=True)

    # Criterion 16 — returns by horizon (market-level price series; apply per group identically)
    gkeys = ["market", "trader_group"]
    for name, weeks in horizons.items():
        px0 = out.groupby(gkeys)["price_close"].shift(weeks)
        ret = np.where(
            out["price_close"].notna() & px0.notna() & (px0 != 0),
            (out["price_close"] / px0 - 1.0) * 100.0,
            np.nan,
        )
        out[f"price_return_{name}"] = ret
        out[f"price_direction_{name}"] = [
            _price_direction(None if (isinstance(r, float) and np.isnan(r)) else r, sideways)
            for r in ret
        ]
        # Criterion 17
        out[f"price_position_confirm_{name}"] = [
            _confirm_label(
                None if pd.isna(nd) else str(nd),
                None if pd.isna(pd_) else str(pd_),
            )
            for nd, pd_ in zip(out[f"direction_{name}"], out[f"price_direction_{name}"], strict=False)
        ]

    # Criterion 18 — extreme positioning + price (alert only)
    ext_p = float(pcfg.get("extension_percentile", 90))

    def _extreme_alert(row) -> str | None:
        p = row.get("net_percentile_52w")
        px = row.get("price_direction_monthly")
        net = row.get("net_position")
        if p is None or pd.isna(p) or px is None or pd.isna(px):
            return None
        if float(p) >= ext_p and not pd.isna(net) and float(net) > 0 and px == "sube":
            return "extremo_largo_con_precio_subiendo_alerta_extension"
        if float(p) <= (100 - ext_p) and not pd.isna(net) and float(net) < 0 and px == "baja":
            return "extremo_corto_con_precio_bajando_alerta_extension"
        return None

    out["price_extreme_alert"] = out.apply(_extreme_alert, axis=1)

    # Criterion 19 — OI × price (monthly window)
    out["oi_price_reading"] = [
        _oi_price_label(
            None if pd.isna(a) else str(a),
            None if pd.isna(b) else str(b),
        )
        for a, b in zip(out["price_direction_monthly"], out["oi_change_label"], strict=False)
    ]

    return out
