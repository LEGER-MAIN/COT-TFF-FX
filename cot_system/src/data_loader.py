"""Download and normalize CFTC Traders in Financial Futures (TFF) Futures Only data."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

# Official CFTC bulk historical archives (Futures Only TFF text).
HIST_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
# Current-week snapshot (often no header — yearly archives are preferred for parsing).
WEEKLY_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"

SOURCE_LABEL = "CFTC TFF Futures Only (fut_fin_txt / FinFutWk)"

TRADER_GROUPS = [
    {
        "trader_group": "Dealer / Intermediary",
        "long": "Dealer_Positions_Long_All",
        "short": "Dealer_Positions_Short_All",
        "spread": "Dealer_Positions_Spread_All",
        "long_change": "Change_in_Dealer_Long_All",
        "short_change": "Change_in_Dealer_Short_All",
        "spread_change": "Change_in_Dealer_Spread_All",
        "pct_long": "Pct_of_OI_Dealer_Long_All",
        "pct_short": "Pct_of_OI_Dealer_Short_All",
        "pct_spread": "Pct_of_OI_Dealer_Spread_All",
    },
    {
        "trader_group": "Asset Manager / Institutional",
        "long": "Asset_Mgr_Positions_Long_All",
        "short": "Asset_Mgr_Positions_Short_All",
        "spread": "Asset_Mgr_Positions_Spread_All",
        "long_change": "Change_in_Asset_Mgr_Long_All",
        "short_change": "Change_in_Asset_Mgr_Short_All",
        "spread_change": "Change_in_Asset_Mgr_Spread_All",
        "pct_long": "Pct_of_OI_Asset_Mgr_Long_All",
        "pct_short": "Pct_of_OI_Asset_Mgr_Short_All",
        "pct_spread": "Pct_of_OI_Asset_Mgr_Spread_All",
    },
    {
        "trader_group": "Leveraged Funds",
        "long": "Lev_Money_Positions_Long_All",
        "short": "Lev_Money_Positions_Short_All",
        "spread": "Lev_Money_Positions_Spread_All",
        "long_change": "Change_in_Lev_Money_Long_All",
        "short_change": "Change_in_Lev_Money_Short_All",
        "spread_change": "Change_in_Lev_Money_Spread_All",
        "pct_long": "Pct_of_OI_Lev_Money_Long_All",
        "pct_short": "Pct_of_OI_Lev_Money_Short_All",
        "pct_spread": "Pct_of_OI_Lev_Money_Spread_All",
    },
    {
        "trader_group": "Other Reportables",
        "long": "Other_Rept_Positions_Long_All",
        "short": "Other_Rept_Positions_Short_All",
        "spread": "Other_Rept_Positions_Spread_All",
        "long_change": "Change_in_Other_Rept_Long_All",
        "short_change": "Change_in_Other_Rept_Short_All",
        "spread_change": "Change_in_Other_Rept_Spread_All",
        "pct_long": "Pct_of_OI_Other_Rept_Long_All",
        "pct_short": "Pct_of_OI_Other_Rept_Short_All",
        "pct_spread": "Pct_of_OI_Other_Rept_Spread_All",
    },
    {
        "trader_group": "Nonreportable",
        "long": "NonRept_Positions_Long_All",
        "short": "NonRept_Positions_Short_All",
        "spread": None,
        "long_change": "Change_in_NonRept_Long_All",
        "short_change": "Change_in_NonRept_Short_All",
        "spread_change": None,
        "pct_long": "Pct_of_OI_NonRept_Long_All",
        "pct_short": "Pct_of_OI_NonRept_Short_All",
        "pct_spread": None,
    },
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_market_config(path: Path | None = None) -> dict:
    cfg = path or (_project_root() / "config" / "markets.json")
    with open(cfg, encoding="utf-8") as f:
        return json.load(f)


def _clean_numeric_frame(df: pd.DataFrame, cols: list[str], as_int: bool = True) -> pd.DataFrame:
    """Parse CFTC numeric fields; blank/'.' → NA (never coerce missing to 0)."""
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = pd.NA
            continue
        s = out[c].astype(str).str.strip()
        s = s.replace({"": pd.NA, ".": pd.NA, "nan": pd.NA, "None": pd.NA})
        num = pd.to_numeric(s, errors="coerce")
        out[c] = num.astype("Int64") if as_int else num
    return out


def download_year_zip(year: int, raw_dir: Path, session: requests.Session | None = None) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / f"fut_fin_txt_{year}.zip"
    url = HIST_URL.format(year=year)
    sess = session or requests.Session()
    resp = sess.get(url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to download {url}: HTTP {resp.status_code}")
    dest.write_bytes(resp.content)
    return dest


def read_tff_zip(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise ValueError(f"No .txt inside {zip_path}")
        with zf.open(names[0]) as fh:
            return pd.read_csv(fh, low_memory=False)


def download_weekly(raw_dir: Path, session: requests.Session | None = None) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / "FinFutWk.txt"
    sess = session or requests.Session()
    resp = sess.get(WEEKLY_URL, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to download {WEEKLY_URL}: HTTP {resp.status_code}")
    dest.write_bytes(resp.content)
    return dest


def fetch_tff_history(
    years: Iterable[int],
    raw_dir: Path | None = None,
    include_weekly: bool = True,
) -> pd.DataFrame:
    """Download yearly TFF Futures Only archives and concatenate."""
    root = _project_root()
    raw_dir = raw_dir or (root / "data" / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    frames: list[pd.DataFrame] = []
    tried: list[str] = []

    for year in years:
        url = HIST_URL.format(year=year)
        tried.append(url)
        zip_path = raw_dir / f"fut_fin_txt_{year}.zip"
        try:
            if not zip_path.exists() or zip_path.stat().st_size < 1000:
                download_year_zip(year, raw_dir, session=session)
            df = read_tff_zip(zip_path)
            df["_source_file"] = zip_path.name
            frames.append(df)
        except Exception as exc:  # noqa: BLE001 — collect per-year failures
            print(f"WARN: could not load year {year} from {url}: {exc}")

    if include_weekly and frames:
        try:
            download_weekly(raw_dir, session=session)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: weekly snapshot unavailable ({WEEKLY_URL}): {exc}")

    if not frames:
        raise RuntimeError(
            "No TFF data downloaded. Tried:\n  - "
            + "\n  - ".join(tried)
            + "\nDo not invent market data; retry when network/CFTC is reachable."
        )

    out = pd.concat(frames, ignore_index=True)
    key_cols = ["Market_and_Exchange_Names", "Report_Date_as_YYYY-MM-DD", "CFTC_Contract_Market_Code"]
    out = out.drop_duplicates(subset=key_cols, keep="last")
    return out


def filter_fx(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """Keep F10 Currencies, optional extra subgroups (e.g. F15), plus named extras (DXY/F90)."""
    if cfg is None:
        cfg = load_market_config()
    code = df["CFTC_SubGroup_Code"].astype(str).str.strip()
    name = df["Market_and_Exchange_Names"].astype(str)
    subgroup = str(cfg.get("cftc_subgroup_code", "F10")).strip()
    mask = code == subgroup

    for sg in cfg.get("extra_subgroups") or []:
        sg_s = str(sg).strip()
        if sg_s:
            mask = mask | (code == sg_s)

    for extra in cfg.get("extra_markets") or []:
        name_pat = str(extra.get("name_contains") or "").strip()
        if not name_pat:
            continue
        extra_mask = name.str.contains(name_pat, case=False, regex=False)
        cmc = extra.get("cftc_contract_market_code")
        if cmc:
            cmc_s = str(cmc).strip()
            extra_mask = extra_mask & (
                df["CFTC_Contract_Market_Code"].astype(str).str.strip() == cmc_s
            )
        mask = mask | extra_mask

    out = df.loc[mask].copy()
    for ex in cfg.get("exclude_markets") or []:
        pat = str(ex.get("name_contains") or "").strip()
        if not pat:
            continue
        out = out.loc[
            ~out["Market_and_Exchange_Names"].astype(str).str.contains(
                pat, case=False, regex=False
            )
        ].copy()
    return out


def normalize_long(df: pd.DataFrame, report_type: str = "TFF") -> pd.DataFrame:
    """Wide CFTC row → long format matching plan §2.2 fields."""
    base = df.copy()
    base["market"] = base["Market_and_Exchange_Names"].astype(str).str.strip()
    base["report_date"] = pd.to_datetime(base["Report_Date_as_YYYY-MM-DD"], errors="coerce")
    base["cftc_contract_market_code"] = base["CFTC_Contract_Market_Code"].astype(str).str.strip()
    base["cftc_commodity_code"] = base["CFTC_Commodity_Code"].astype(str).str.strip()
    base["cftc_subgroup_code"] = base["CFTC_SubGroup_Code"].astype(str).str.strip()
    base["source_file"] = base.get("_source_file", pd.Series([""] * len(base))).astype(str)
    base = _clean_numeric_frame(base, ["Open_Interest_All"], as_int=True)

    pieces: list[pd.DataFrame] = []
    for g in TRADER_GROUPS:
        int_cols = [g["long"], g["short"], g["long_change"], g["short_change"]]
        if g["spread"]:
            int_cols.append(g["spread"])
        if g["spread_change"]:
            int_cols.append(g["spread_change"])
        float_cols = [g["pct_long"], g["pct_short"]]
        if g["pct_spread"]:
            float_cols.append(g["pct_spread"])

        chunk = _clean_numeric_frame(base, int_cols, as_int=True)
        chunk = _clean_numeric_frame(chunk, float_cols, as_int=False)

        part = pd.DataFrame(
            {
                "market": chunk["market"],
                "report_type": report_type,
                "report_date": chunk["report_date"],
                "publication_date": pd.NaT,
                "trader_group": g["trader_group"],
                "long_positions": chunk[g["long"]],
                "long_change": chunk[g["long_change"]],
                "short_positions": chunk[g["short"]],
                "short_change": chunk[g["short_change"]],
                "spreading_positions": (
                    chunk[g["spread"]]
                    if g["spread"]
                    else pd.Series([pd.NA] * len(chunk), index=chunk.index, dtype="Int64")
                ),
                "spread_change": (
                    chunk[g["spread_change"]]
                    if g["spread_change"]
                    else pd.Series([pd.NA] * len(chunk), index=chunk.index, dtype="Int64")
                ),
                "open_interest_total": chunk["Open_Interest_All"],
                "source": SOURCE_LABEL,
                "source_file": chunk["source_file"],
                "cftc_contract_market_code": chunk["cftc_contract_market_code"],
                "cftc_commodity_code": chunk["cftc_commodity_code"],
                "cftc_subgroup_code": chunk["cftc_subgroup_code"],
                "pct_oi_long_reported": chunk[g["pct_long"]],
                "pct_oi_short_reported": chunk[g["pct_short"]],
                "pct_oi_spread_reported": (
                    chunk[g["pct_spread"]]
                    if g["pct_spread"]
                    else pd.Series([float("nan")] * len(chunk), index=chunk.index, dtype="float64")
                ),
            }
        )
        pieces.append(part)

    out = pd.concat(pieces, ignore_index=True)
    out = out.sort_values(["market", "trader_group", "report_date"]).reset_index(drop=True)
    return out


def load_fx_tff(
    years: Iterable[int] | None = None,
    raw_dir: Path | None = None,
) -> pd.DataFrame:
    cfg = load_market_config()
    if years is None:
        years = [2023, 2024, 2025, 2026]
    wide = fetch_tff_history(years=years, raw_dir=raw_dir, include_weekly=True)
    fx = filter_fx(wide, cfg=cfg)
    if fx.empty:
        raise RuntimeError(
            "No FX/TFF rows found after filter (F10 + extras such as USD INDEX). "
            "Check CFTC archive contents and config/markets.json."
        )
    return normalize_long(fx, report_type=cfg.get("report_type", "TFF"))
