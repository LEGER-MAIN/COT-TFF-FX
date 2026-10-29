"""Pandas-free HTML/JSON regeneration from processed CSVs (stdlib csv only).

Used when Application Control blocks pandas/numpy DLLs but
data/processed/fx_tff_scored.csv (and optionally weekly) already exist.
"""

from __future__ import annotations

import csv
import html
import json
from datetime import date
from pathlib import Path
from typing import Any


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"No existe CSV: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _cell(row: dict[str, str], key: str, default: str = "") -> str:
    v = row.get(key)
    if v is None:
        return default
    return str(v).strip()


def write_html_lite(
    scored_rows: list[dict[str, str]],
    path: Path,
    *,
    as_of: str,
    weekly_rows: list[dict[str, str]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "market",
        "as_of_date",
        "combined_bias",
        "combined_bias_label",
        "evidence_quality",
        "LF_bias",
        "LF_bias_label",
        "AM_bias",
        "AM_bias_label",
    ]
    if scored_rows:
        present = [c for c in cols if c in scored_rows[0]]
        if not present:
            present = list(scored_rows[0].keys())[:10]
    else:
        present = cols

    rows_html: list[str] = []
    for row in scored_rows:
        tds = "".join(f"<td>{html.escape(_cell(row, c))}</td>" for c in present)
        rows_html.append(f"<tr>{tds}</tr>")

    thead = "".join(f"<th>{html.escape(c)}</th>" for c in present)
    body = "\n".join(rows_html) if rows_html else "<tr><td colspan='99'>(sin filas)</td></tr>"

    weekly_block = ""
    if weekly_rows:
        wcols = [
            c
            for c in [
                "rank_global",
                "section_label",
                "symbol",
                "priority",
                "pair_bias",
                "evidence_quality",
                "direction_hint",
                "por_que",
                "riesgo",
                "correlation_warnings",
            ]
            if c in weekly_rows[0]
        ]
        if not wcols:
            wcols = list(weekly_rows[0].keys())[:10]
        wthead = "".join(f"<th>{html.escape(c)}</th>" for c in wcols)
        wbody = "\n".join(
            "<tr>"
            + "".join(f"<td>{html.escape(_cell(r, c))}</td>" for c in wcols)
            + "</tr>"
            for r in weekly_rows
        )
        weekly_block = f"""
  <h2 id="recomendacion-semanal">Recomendación semanal</h2>
  <p class="note">No es señal de compra automática. Secciones: Majors USD, Crosses, Índice DXY, Opcionales.</p>
  <table>
    <thead><tr>{wthead}</tr></thead>
    <tbody>
{wbody}
    </tbody>
  </table>
"""

    from .week_calendar import calendar_css, calendar_html_section

    picker = calendar_html_section(initial_as_of=as_of or None)
    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>COT TFF FX — {html.escape(as_of)} (lite)</title>
<style>
  body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 24px; background: #f4f6f8; color: #1c2329; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 1.5rem; }}
  .note {{ color: #5a6a75; margin-bottom: 1rem; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; margin-bottom: 1rem; }}
  th, td {{ border: 1px solid #d5dde3; padding: 6px 8px; font-size: 0.9rem; text-align: left; }}
  th {{ background: #e8eef2; }}
  {calendar_css()}
</style>
</head>
<body>
  <h1>COT TFF FX — informe lite</h1>
  <p class="note">as_of={html.escape(as_of)} · regenerado sin pandas (csv).
  No es una señal de compra/venta. <a href="#week-picker">Calendario semanal</a>.</p>
{picker}
{weekly_block}
  <h2>Sesgo / calidad</h2>
  <table>
    <thead><tr>{thead}</tr></thead>
    <tbody>
{body}
    </tbody>
  </table>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def write_json_lite(
    scored_rows: list[dict[str, str]],
    path: Path,
    *,
    as_of: str,
    weekly_rows: list[dict[str, str]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "as_of": as_of,
        "engine": "report_lite",
        "n_markets": len(scored_rows),
        "rows": scored_rows,
        "weekly_recommendations": weekly_rows or [],
        "disclaimer": "No es señal de compra automática.",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def regenerate_from_processed(
    processed_dir: Path,
    reports_dir: Path,
) -> dict[str, Path]:
    """Build HTML/JSON from fx_tff_scored.csv without pandas."""
    scored_path = processed_dir / "fx_tff_scored.csv"
    rows = _read_csv_dicts(scored_path)
    weekly_path = processed_dir / "fx_tff_weekly.csv"
    weekly_rows = _read_csv_dicts(weekly_path) if weekly_path.is_file() else []
    as_of = ""
    if rows:
        as_of = _cell(rows[0], "as_of_date") or _cell(rows[0], "report_date")
    if not as_of and weekly_rows:
        as_of = _cell(weekly_rows[0], "as_of_date")
    if not as_of:
        as_of = date.today().isoformat()

    reports_dir.mkdir(parents=True, exist_ok=True)
    dated = {
        "html": reports_dir / f"cot_tff_fx_{as_of}.html",
        "json": reports_dir / f"cot_tff_fx_{as_of}.json",
    }
    latest = {
        "html": reports_dir / "cot_tff_fx_latest.html",
        "json": reports_dir / "cot_tff_fx_latest.json",
    }

    write_html_lite(rows, dated["html"], as_of=as_of, weekly_rows=weekly_rows)
    write_html_lite(rows, latest["html"], as_of=as_of, weekly_rows=weekly_rows)
    write_json_lite(rows, dated["json"], as_of=as_of, weekly_rows=weekly_rows)
    write_json_lite(rows, latest["json"], as_of=as_of, weekly_rows=weekly_rows)

    return {**{f"dated_{k}": v for k, v in dated.items()}, **{f"latest_{k}": v for k, v in latest.items()}}
