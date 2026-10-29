#!/usr/bin/env python3
"""Tiny local HTTP server for the HTML week-calendar backtest picker.

Stdlib only (http.server). Serves ``docs/reports/`` and runs the pipeline:

    POST|GET /run?as_of=YYYY-MM-DD  →  python main.py --as-of …  →  redirect to
                                       cot_tff_fx_backtest_<asof>.html

Usage (from cot_system/):

    python report_server.py
    python report_server.py --port 8765
    EJECUTAR_COT.bat --serve

Open http://127.0.0.1:8765/  (latest report with calendar) or
     http://127.0.0.1:8765/cot_week_picker.html
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.as_of import backtest_stem, parse_as_of  # noqa: E402
from src.week_calendar import (  # noqa: E402
    DEFAULT_SERVER_ORIGIN,
    calendar_css,
    calendar_html_section,
    saturday_of_week,
)

DEFAULT_PORT = 8765
REPORTS_DIR = ROOT.parent / "docs" / "reports"
MAIN_PY = ROOT / "main.py"

# Serialize pipeline runs (one at a time).
_run_lock = threading.Lock()
_last_run: dict = {"status": "idle"}


def _python_exe() -> str:
    """Prefer venv python on Windows/Linux when present."""
    if os.name == "nt":
        cand = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        cand = ROOT / ".venv" / "bin" / "python"
    if cand.is_file():
        return str(cand)
    return sys.executable


def _normalize_as_of(raw: str) -> date:
    d = parse_as_of(raw)
    return saturday_of_week(d)


def run_backtest(as_of: date, *, skip_price: bool = False) -> dict:
    """Run main.py --as-of and return result metadata."""
    global _last_run
    stem = backtest_stem(as_of)
    html_name = f"{stem}.html"
    html_path = REPORTS_DIR / html_name
    cmd = [_python_exe(), str(MAIN_PY), "--as-of", as_of.isoformat()]
    if skip_price:
        cmd.append("--skip-price")
    _last_run = {
        "status": "running",
        "as_of": as_of.isoformat(),
        "cmd": cmd,
    }
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=60 * 45,
        )
    except subprocess.TimeoutExpired as exc:
        _last_run = {
            "status": "error",
            "as_of": as_of.isoformat(),
            "error": f"Timeout tras 45 min: {exc}",
        }
        return _last_run
    except OSError as exc:
        _last_run = {
            "status": "error",
            "as_of": as_of.isoformat(),
            "error": str(exc),
        }
        return _last_run

    ok = proc.returncode == 0 and html_path.is_file()
    _last_run = {
        "status": "ok" if ok else "error",
        "as_of": as_of.isoformat(),
        "returncode": proc.returncode,
        "html": str(html_path) if html_path.is_file() else None,
        "html_url": f"/{html_name}" if html_path.is_file() else None,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "error": None
        if ok
        else (
            f"main.py exit={proc.returncode}; "
            f"html_exists={html_path.is_file()}. "
            f"{(proc.stderr or proc.stdout or '')[-800:]}"
        ),
    }
    return _last_run


def ensure_companion_picker() -> Path:
    """Write/update durable companion page in docs/reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "cot_week_picker.html"
    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>COT · Calendario semanal (backtest)</title>
<style>
  :root {{
    --bg: #eef2f0; --ink: #1a2220; --accent: #0d5c4d;
    --warn: #7a3e12; --line: #c5d0cb; --card: #fbfcfb;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    color: var(--ink);
    background:
      radial-gradient(1100px 480px at 8% -8%, #cfe6df 0%, transparent 55%),
      var(--bg);
    line-height: 1.45;
  }}
  header {{ padding: 2rem 1.5rem 1rem; border-bottom: 1px solid var(--line); }}
  header h1 {{ margin: 0 0 .35rem; color: var(--accent); font-size: 1.7rem; }}
  main {{ padding: 1.25rem 1.5rem 3rem; max-width: 960px; margin: 0 auto; }}
  a {{ color: var(--accent); }}
  {calendar_css()}
</style>
</head>
<body>
<header>
  <h1>COT · Calendario semanal</h1>
  <p>Elige una semana (domingo–sábado). El <strong>sábado</strong> es el
  <code>--as-of</code> del backtest. Luego
  <a href="/cot_tff_fx_latest.html">informe latest</a>.</p>
</header>
<main>
{calendar_html_section()}
</main>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")
    return path


class CotReportHandler(SimpleHTTPRequestHandler):
    """Serve reports dir + /run backtest endpoint."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORTS_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[report_server] " + (fmt % args) + "\n")

    def _cors(self) -> None:
        # Allow file:// pages to call the server (browser may still block; GET nav works).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in ("/run", "/run/"):
            self._handle_run(parsed, want_json=False)
            return
        if parsed.path in ("/api/run", "/api/status"):
            if parsed.path.endswith("status"):
                self._json_response(200, _last_run)
                return
            self._handle_run(parsed, want_json=True)
            return
        if parsed.path in ("/", "/index.html"):
            latest = REPORTS_DIR / "cot_tff_fx_latest.html"
            target = "/cot_tff_fx_latest.html" if latest.is_file() else "/cot_week_picker.html"
            self.send_response(302)
            self.send_header("Location", target)
            self._cors()
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in ("/run", "/run/", "/api/run"):
            self._handle_run(parsed, want_json=True)
            return
        self.send_error(404, "Not found")

    def _query_as_of(self, parsed) -> str | None:
        qs = parse_qs(parsed.query)
        vals = qs.get("as_of") or qs.get("asof") or []
        if vals:
            return vals[0]
        # Optional JSON body
        length = int(self.headers.get("Content-Length") or 0)
        if length > 0:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
                if isinstance(body, dict) and body.get("as_of"):
                    return str(body["as_of"])
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        return None

    def _handle_run(self, parsed, *, want_json: bool) -> None:
        raw = self._query_as_of(parsed)
        if not raw:
            self._json_response(
                400,
                {"error": "Falta as_of (YYYY-MM-DD). Ej: /run?as_of=2025-06-17"},
            )
            return
        try:
            as_of = _normalize_as_of(raw)
        except ValueError as exc:
            self._json_response(400, {"error": str(exc)})
            return

        qs = parse_qs(parsed.query)
        skip_price = (qs.get("skip_price") or ["0"])[0] in ("1", "true", "yes")

        if not _run_lock.acquire(blocking=False):
            self._json_response(
                409,
                {
                    "error": "Ya hay un backtest en curso.",
                    "last": _last_run,
                },
            )
            return
        try:
            result = run_backtest(as_of, skip_price=skip_price)
        except Exception as exc:  # noqa: BLE001
            result = {
                "status": "error",
                "as_of": as_of.isoformat(),
                "error": f"{exc}\n{traceback.format_exc()[-1500:]}",
            }
        finally:
            _run_lock.release()

        if want_json or (self.headers.get("Accept") or "").find("json") >= 0:
            code = 200 if result.get("status") == "ok" else 500
            if result.get("status") == "ok" and result.get("html_url"):
                # Absolute-ish URL for the browser on this origin
                result = dict(result)
                result["redirect"] = result["html_url"]
            self._json_response(code, result)
            return

        if result.get("status") == "ok" and result.get("html_url"):
            self.send_response(302)
            self.send_header("Location", result["html_url"])
            self._cors()
            self.end_headers()
            return
        self._json_response(500, result)

    def _json_response(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="COT local report server (week calendar).")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically.",
    )
    p.add_argument(
        "--open",
        default="latest",
        choices=("latest", "picker", "none"),
        help="Which page to open (default: latest HTML with calendar).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not MAIN_PY.is_file():
        print(f"ERROR: no existe {MAIN_PY}", file=sys.stderr)
        return 2
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    picker = ensure_companion_picker()
    print(f"Reports dir : {REPORTS_DIR}")
    print(f"Companion   : {picker}")
    print(f"Pipeline    : {_python_exe()} {MAIN_PY}")
    origin = f"http://{args.host}:{args.port}"
    print()
    print("=" * 64)
    print("  NO abras el HTML a doble clic (file://).")
    print(f"  Usa siempre: {origin}/")
    print("  Se abrirá el navegador solo. Ctrl+C para detener.")
    print("=" * 64)
    print()
    print(f"Listening   : {origin}")
    print(f"  GET/POST  : {origin}/run?as_of=YYYY-MM-DD")
    print(f"  Picker    : {origin}/cot_week_picker.html")
    print(f"  Latest    : {origin}/cot_tff_fx_latest.html")
    print("(Ctrl+C para detener)")

    httpd = ThreadingHTTPServer((args.host, args.port), CotReportHandler)

    if not args.no_browser and args.open != "none":
        path = (
            "/cot_week_picker.html"
            if args.open == "picker"
            else "/cot_tff_fx_latest.html"
        )
        if args.open == "latest" and not (REPORTS_DIR / "cot_tff_fx_latest.html").is_file():
            path = "/cot_week_picker.html"
        try:
            webbrowser.open(origin + path)
        except Exception:  # noqa: BLE001
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
        return 0
    return 0


if __name__ == "__main__":
    # Silence unused import warning for DEFAULT_SERVER_ORIGIN re-export docs
    _ = DEFAULT_SERVER_ORIGIN
    raise SystemExit(main())
