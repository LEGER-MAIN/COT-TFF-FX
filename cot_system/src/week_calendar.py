"""Forex Factory–style week calendar (Sun–Sat) for HTML backtest picker.

COT data is released Friday; the week ends Saturday. Selecting any day in a
week maps to that week's Saturday as ``--as-of``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


def saturday_of_week(d: date | str) -> date:
    """Return the Saturday that ends the Sun–Sat week containing ``d``.

    Python ``date.weekday()``: Mon=0 … Sat=5, Sun=6.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d.strip()[:10])
    # Days forward to Saturday (0 if already Saturday).
    delta = (5 - d.weekday()) % 7
    return d + timedelta(days=delta)


def sunday_of_week(d: date | str) -> date:
    """Sunday that starts the Sun–Sat week containing ``d``."""
    sat = saturday_of_week(d)
    return sat - timedelta(days=6)


def week_range(d: date | str) -> tuple[date, date]:
    """(Sunday, Saturday) for the week containing ``d``."""
    sat = saturday_of_week(d)
    return sat - timedelta(days=6), sat


def this_week_saturday(today: date | None = None) -> date:
    return saturday_of_week(today or date.today())


def last_week_saturday(today: date | None = None) -> date:
    return this_week_saturday(today) - timedelta(days=7)


def quick_saturdays(today: date | None = None, n_past: int = 4) -> list[tuple[str, date]]:
    """Labeled quick links: Esta semana, Semana pasada, Hace 2/3/4 semanas."""
    base = today or date.today()
    sat = saturday_of_week(base)
    labels = [
        ("Esta semana", sat),
        ("Semana pasada", sat - timedelta(days=7)),
    ]
    for i in range(2, n_past + 1):
        labels.append((f"Hace {i} semanas", sat - timedelta(days=7 * i)))
    return labels


def iter_month_days(year: int, month: int) -> Iterable[date]:
    d = date(year, month, 1)
    while d.month == month:
        yield d
        d += timedelta(days=1)


# Default local server (stdlib report_server.py)
DEFAULT_SERVER_ORIGIN = "http://127.0.0.1:8765"


def calendar_css() -> str:
    return """
  /* Week picker (Forex Factory–style Sun–Sat) */
  #week-picker {
    margin: 1.5rem 0;
    background: var(--card, #fbfcfb);
    border: 1px solid var(--line, #c5d0cb);
    padding: 1rem 1.1rem 1.15rem;
  }
  #week-picker h2 { margin: 0 0 .25rem; color: var(--accent, #0d5c4d); font-size: 1.15rem; }
  #week-picker .sub { margin: 0 0 .85rem; font-size: .85rem; opacity: .78; max-width: 70ch; }
  #week-picker .wp-quick {
    display: flex; flex-wrap: wrap; gap: .4rem; margin: 0 0 .9rem;
  }
  #week-picker .wp-quick button {
    font: inherit; font-size: .82rem; padding: .35rem .7rem;
    border: 1px solid var(--line, #c5d0cb); background: #fff; color: var(--ink, #1a2220);
    cursor: pointer;
  }
  #week-picker .wp-quick button:hover { border-color: var(--accent, #0d5c4d); color: var(--accent, #0d5c4d); }
  #week-picker .wp-nav {
    display: flex; align-items: center; justify-content: space-between;
    gap: .75rem; margin-bottom: .65rem; flex-wrap: wrap;
  }
  #week-picker .wp-nav button {
    font: inherit; font-size: .85rem; padding: .3rem .65rem;
    border: 1px solid var(--line, #c5d0cb); background: #fff; cursor: pointer;
  }
  #week-picker .wp-months {
    display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
  }
  @media (max-width: 720px) {
    #week-picker .wp-months { grid-template-columns: 1fr; }
  }
  #week-picker .wp-month h3 {
    margin: 0 0 .45rem; font-size: .95rem; color: var(--ink, #1a2220);
    text-align: center; font-weight: 600;
  }
  #week-picker table.wp-cal {
    width: 100%; border-collapse: collapse; table-layout: fixed;
    font-size: .82rem; user-select: none;
  }
  #week-picker table.wp-cal th {
    font-size: .7rem; text-transform: uppercase; letter-spacing: .04em;
    opacity: .65; padding: .25rem 0; font-weight: 600;
  }
  #week-picker table.wp-cal td {
    text-align: center; padding: .15rem; vertical-align: middle;
  }
  #week-picker table.wp-cal td button {
    width: 100%; aspect-ratio: 1; max-height: 2.4rem;
    border: 1px solid transparent; background: transparent;
    font: inherit; font-size: .85rem; cursor: pointer; color: inherit;
    border-radius: 2px; padding: 0;
  }
  #week-picker table.wp-cal td.out button { opacity: .28; }
  #week-picker table.wp-cal td.sat button { font-weight: 700; }
  #week-picker table.wp-cal tr.wp-week:hover td button,
  #week-picker table.wp-cal tr.wp-week.wp-hover td button {
    background: rgba(13, 92, 77, 0.08);
  }
  #week-picker table.wp-cal tr.wp-week.wp-selected td {
    background: rgba(13, 92, 77, 0.14);
  }
  #week-picker table.wp-cal tr.wp-week.wp-selected td.sat button {
    background: var(--accent, #0d5c4d); color: #fff; border-color: var(--accent, #0d5c4d);
  }
  #week-picker .wp-footer {
    display: flex; flex-wrap: wrap; align-items: center; gap: .75rem;
    margin-top: .95rem; padding-top: .75rem; border-top: 1px solid var(--line, #c5d0cb);
  }
  #week-picker .wp-asof {
    font-size: .95rem;
  }
  #week-picker .wp-asof strong { color: var(--accent, #0d5c4d); font-size: 1.05rem; }
  #week-picker .wp-apply {
    font: inherit; font-weight: 600; font-size: .9rem;
    padding: .5rem 1.1rem; cursor: pointer;
    background: var(--accent, #0d5c4d); color: #fff; border: none;
  }
  #week-picker .wp-apply:disabled { opacity: .45; cursor: not-allowed; }
  #week-picker .wp-apply:hover:not(:disabled) { filter: brightness(1.06); }
  #week-picker .wp-status {
    font-size: .85rem; flex: 1 1 12rem; min-height: 1.2em;
  }
  #week-picker .wp-status.err {
    color: var(--warn, #7a3e12);
    white-space: pre-line; line-height: 1.45; max-width: 60ch;
  }
  #week-picker .wp-status.ok { color: var(--accent, #0d5c4d); }
  #week-picker .wp-hint {
    font-size: .8rem; opacity: .7; margin: .35rem 0 0; max-width: 70ch;
  }
  #week-picker code { font-size: .85em; }
  /* Banner when opened as file:// (Aplicar cannot reach the local server) */
  #cot-file-protocol-warn {
    margin: 0; padding: .85rem 1.25rem;
    background: #7a3e12; color: #fff; font: 600 .95rem/1.4 "Segoe UI", sans-serif;
    border-bottom: 3px solid #5a2c0a;
  }
  #cot-file-protocol-warn a { color: #ffe8c8; font-weight: 700; }
  #cot-file-protocol-warn code {
    background: rgba(0,0,0,.25); padding: .1rem .35rem; font-size: .9em;
  }
"""


def calendar_html_section(
    *,
    initial_as_of: str | None = None,
    server_origin: str = DEFAULT_SERVER_ORIGIN,
) -> str:
    """Self-contained HTML+JS section for dual-month week picker."""
    today = date.today()
    init = saturday_of_week(initial_as_of) if initial_as_of else saturday_of_week(today)
    init_iso = init.isoformat()
    origin = server_origin.rstrip("/")
    quick = quick_saturdays(today)
    quick_btns = "".join(
        f'<button type="button" data-sat="{s.isoformat()}">{lab}</button>'
        for lab, s in quick
    )
    return f"""
  <section class="market" id="week-picker" data-server="{origin}" data-initial="{init_iso}">
    <h2>Calendario semanal · backtest</h2>
    <p class="sub">Estilo Forex Factory: la semana va de <strong>domingo a sábado</strong>.
    Los datos COT se publican el viernes; el corte de la semana es el <strong>sábado</strong>
    (parámetro <code>--as-of</code>). Haz clic en cualquier día para seleccionar esa semana.</p>
    <div class="wp-quick" id="wp-quick">{quick_btns}</div>
    <div class="wp-nav">
      <button type="button" id="wp-prev" aria-label="Mes anterior">← Anterior</button>
      <span id="wp-nav-label" style="font-size:.9rem;opacity:.8"></span>
      <button type="button" id="wp-next" aria-label="Mes siguiente">Siguiente →</button>
    </div>
    <div class="wp-months" id="wp-months"></div>
    <div class="wp-footer">
      <div class="wp-asof">Semana (sábado / as-of): <strong id="wp-sat">{init_iso}</strong></div>
      <button type="button" class="wp-apply" id="wp-apply">Aplicar · regenerar informe</button>
      <div class="wp-status" id="wp-status" role="status"></div>
    </div>
    <p class="wp-hint">NO abras este HTML a doble clic. Usa
    <code>ABRIR_CALENDARIO.bat</code> o <code>EJECUTAR_COT.bat --serve</code>
    y abre <a href="{origin}/">{origin}/</a>.
    Sin servidor: <code>EJECUTAR_COT.bat --as-of {init_iso}</code></p>
  </section>
  <script>
(function () {{
  var root = document.getElementById("week-picker");
  if (!root) return;
  var SERVER = root.getAttribute("data-server") || "{origin}";
  var IS_FILE = (location.protocol === "file:");
  var DOW = ["Do", "Lu", "Ma", "Mi", "Ju", "Vi", "Sa"];
  var MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];

  if (IS_FILE && !document.getElementById("cot-file-protocol-warn")) {{
    var ban = document.createElement("div");
    ban.id = "cot-file-protocol-warn";
    ban.setAttribute("role", "alert");
    ban.innerHTML =
      "Estás viendo este informe como <code>file://</code> (doble clic en el HTML). " +
      "<strong>Aplicar no funciona así.</strong> " +
      "Cierra esta pestaña · doble clic en <code>ABRIR_CALENDARIO.bat</code> " +
      "(o <code>EJECUTAR_COT.bat --serve</code>) · usa " +
      "<a href=\\"" + SERVER + "/\\">" + SERVER + "/</a>.";
    document.body.insertBefore(ban, document.body.firstChild);
  }}

  function pad(n) {{ return n < 10 ? "0" + n : "" + n; }}
  function iso(d) {{
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }}
  function parseIso(s) {{
    var p = (s || "").slice(0, 10).split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }}
  /** Saturday ending the Sun–Sat week that contains d. */
  function saturdayOfWeek(d) {{
    var x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var day = x.getDay(); /* Sun=0 … Sat=6 */
    var add = (6 - day + 7) % 7;
    x.setDate(x.getDate() + add);
    return x;
  }}
  function sundayOfWeek(d) {{
    var sat = saturdayOfWeek(d);
    var sun = new Date(sat.getFullYear(), sat.getMonth(), sat.getDate());
    sun.setDate(sun.getDate() - 6);
    return sun;
  }}
  function sameDay(a, b) {{
    return a.getFullYear() === b.getFullYear() &&
           a.getMonth() === b.getMonth() &&
           a.getDate() === b.getDate();
  }}
  function addMonths(d, n) {{
    return new Date(d.getFullYear(), d.getMonth() + n, 1);
  }}

  var selectedSat = saturdayOfWeek(parseIso(root.getAttribute("data-initial")));
  var viewMonth = new Date(selectedSat.getFullYear(), selectedSat.getMonth(), 1);

  function setStatus(msg, kind) {{
    var el = document.getElementById("wp-status");
    el.textContent = msg || "";
    el.className = "wp-status" + (kind ? " " + kind : "");
  }}

  function fetchFailHelp(asOf, err) {{
    var detail = (err && err.message) ? err.message : String(err || "");
    var lines = [];
    if (IS_FILE) {{
      lines.push("Has abierto el HTML a doble clic (file://). Eso provoca Failed to fetch.");
    }} else {{
      lines.push("No hay servidor en " + SERVER + " (o el navegador bloqueó la petición).");
    }}
    lines.push("");
    lines.push("Pasos:");
    lines.push("1. Cierra esta pestaña file://");
    lines.push("2. Doble clic en ABRIR_CALENDARIO.bat  (o EJECUTAR_COT.bat --serve)");
    lines.push("3. Espera a que abra " + SERVER + "/  — NO abras el .html a mano");
    lines.push("4. Elige la semana y pulsa Aplicar ahí");
    lines.push("");
    lines.push("Sin servidor (solo una fecha): EJECUTAR_COT.bat --as-of " + asOf);
    if (detail) lines.push("(" + detail + ")");
    return lines.join("\\n");
  }}

  function selectSat(d) {{
    selectedSat = saturdayOfWeek(d);
    document.getElementById("wp-sat").textContent = iso(selectedSat);
    var hint = root.querySelector(".wp-hint code:last-of-type");
    /* keep hint generic */
    render();
  }}

  function buildMonth(year, month) {{
    var wrap = document.createElement("div");
    wrap.className = "wp-month";
    var h = document.createElement("h3");
    h.textContent = MONTHS[month] + " " + year;
    wrap.appendChild(h);
    var table = document.createElement("table");
    table.className = "wp-cal";
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    DOW.forEach(function (lab) {{
      var th = document.createElement("th");
      th.textContent = lab;
      hr.appendChild(th);
    }});
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    var first = new Date(year, month, 1);
    var start = sundayOfWeek(first);
    /* 6 weeks grid */
    var cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate());
    for (var w = 0; w < 6; w++) {{
      var tr = document.createElement("tr");
      tr.className = "wp-week";
      var weekSat = saturdayOfWeek(cursor);
      if (sameDay(weekSat, selectedSat)) tr.classList.add("wp-selected");
      for (var i = 0; i < 7; i++) {{
        var td = document.createElement("td");
        var cell = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate());
        if (cell.getMonth() !== month) td.classList.add("out");
        if (cell.getDay() === 6) td.classList.add("sat");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = String(cell.getDate());
        btn.setAttribute("data-date", iso(cell));
        btn.addEventListener("click", (function (cd) {{
          return function () {{ selectSat(cd); }};
        }})(cell));
        td.appendChild(btn);
        tr.appendChild(td);
        cursor.setDate(cursor.getDate() + 1);
      }}
      tr.addEventListener("mouseenter", function () {{ this.classList.add("wp-hover"); }});
      tr.addEventListener("mouseleave", function () {{ this.classList.remove("wp-hover"); }});
      tbody.appendChild(tr);
    }}
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }}

  function render() {{
    var host = document.getElementById("wp-months");
    host.innerHTML = "";
    var m0 = viewMonth;
    var m1 = addMonths(viewMonth, 1);
    host.appendChild(buildMonth(m0.getFullYear(), m0.getMonth()));
    host.appendChild(buildMonth(m1.getFullYear(), m1.getMonth()));
    document.getElementById("wp-nav-label").textContent =
      MONTHS[m0.getMonth()] + " – " + MONTHS[m1.getMonth()] + " " + m1.getFullYear();
    document.getElementById("wp-sat").textContent = iso(selectedSat);
  }}

  document.getElementById("wp-prev").addEventListener("click", function () {{
    viewMonth = addMonths(viewMonth, -1);
    render();
  }});
  document.getElementById("wp-next").addEventListener("click", function () {{
    viewMonth = addMonths(viewMonth, 1);
    render();
  }});
  document.getElementById("wp-quick").addEventListener("click", function (ev) {{
    var t = ev.target;
    if (!t || !t.getAttribute) return;
    var s = t.getAttribute("data-sat");
    if (!s) return;
    var d = parseIso(s);
    viewMonth = new Date(d.getFullYear(), d.getMonth(), 1);
    selectSat(d);
  }});

  document.getElementById("wp-apply").addEventListener("click", function () {{
    var asOf = iso(selectedSat);
    var applyBtn = document.getElementById("wp-apply");
    applyBtn.disabled = true;
    setStatus("Regenerando backtest as-of=" + asOf + "… (puede tardar unos minutos)", "");
    var url = SERVER + "/run?as_of=" + encodeURIComponent(asOf);
    /* Prefer POST; fall back to navigation GET if fetch blocked (file://). */
    function goGet() {{
      window.location.href = url;
    }}
    if (typeof fetch !== "function") {{ goGet(); return; }}
    fetch(url, {{ method: "POST", headers: {{ "Accept": "application/json" }} }})
      .then(function (r) {{
        if (r.redirected) {{ window.location.href = r.url; return null; }}
        var ct = r.headers.get("content-type") || "";
        if (ct.indexOf("json") >= 0) {{
          return r.json().then(function (j) {{
            if (!r.ok) throw new Error((j && j.error) || ("HTTP " + r.status));
            if (j.html_url) {{ window.location.href = j.html_url; return; }}
            if (j.redirect) {{ window.location.href = j.redirect; return; }}
            throw new Error("Respuesta sin html_url");
          }});
        }}
        if (r.ok) {{ goGet(); return null; }}
        throw new Error("HTTP " + r.status);
      }})
      .catch(function (err) {{
        setStatus(fetchFailHelp(asOf, err), "err");
        applyBtn.disabled = false;
      }});
  }});

  render();
}})();
  </script>
"""


def inject_calendar_into_html(html_text: str, *, initial_as_of: str | None = None) -> str:
    """Insert or replace #week-picker section in an existing HTML document."""
    section = calendar_html_section(initial_as_of=initial_as_of)
    css = calendar_css()
    # CSS: before </style>
    if "/* Week picker" not in html_text and "</style>" in html_text:
        html_text = html_text.replace("</style>", css + "\n</style>", 1)
    # Remove previous picker if present
    import re

    html_text = re.sub(
        r'<section class="market" id="week-picker"[\s\S]*?</section>\s*<script>\s*\(function \(\) \{[\s\S]*?\}\)\(\);\s*</script>',
        "",
        html_text,
        count=1,
    )
    # Prefer insert after meta block / before backtest or warnings
    anchor_ids = (
        'id="backtest-as-of"',
        'class="warn"',
        'class="ok"',
        'id="recomendacion-semanal"',
    )
    inserted = False
    for marker in anchor_ids:
        idx = html_text.find(marker)
        if idx == -1:
            continue
        # find start of that section/div
        start = html_text.rfind("<", 0, idx)
        if start == -1:
            continue
        html_text = html_text[:start] + section + "\n  " + html_text[start:]
        inserted = True
        break
    if not inserted:
        # before </main>
        if "</main>" in html_text:
            html_text = html_text.replace("</main>", section + "\n</main>", 1)
        else:
            html_text = html_text + section
    return html_text
