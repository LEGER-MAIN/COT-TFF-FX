#!/usr/bin/env python3
"""COT desktop launcher: run pipeline and open the latest HTML report.

Works with a tkinter GUI when available; otherwise falls back to console mode.
Designed for Windows, macOS and Linux with a local Python + cot_system deps.

Dependency checks always use the same interpreter that will run main.py
(resolve_python() / sys.executable), never a different PATH python.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

def _discover_roots() -> tuple[Path, Path, Path]:
    """Return (launcher_dir, cot_system_root, project_root) for the source tree.

    No frozen/PyInstaller layout: Windows runs via BAT → .venv only.
    """
    start = Path(__file__).resolve().parent

    search = [start, *list(start.parents)[:6]]
    for cand in search:
        main = cand / "main.py"
        req = cand / "requirements.txt"
        if main.is_file() and req.is_file():
            cot = cand
            return (start, cot, cot.parent)
        nested = cand / "cot_system" / "main.py"
        if nested.is_file():
            cot = cand / "cot_system"
            return (cot / "launcher", cot, cand)

    return start, start.parent, start.parent.parent


LAUNCHER_DIR, COT_SYSTEM_ROOT, PROJECT_ROOT = _discover_roots()
MAIN_PY = COT_SYSTEM_ROOT / "main.py"
REPORT_HTML = PROJECT_ROOT / "docs" / "reports" / "cot_tff_fx_latest.html"
REQUIREMENTS = COT_SYSTEM_ROOT / "requirements.txt"

APP_TITLE = "COT TFF FX — Lanzador"
APP_NAME = "COT TFF FX"

# pyarrow is optional (Parquet); App Control often blocks it too.
REQUIRED_MODULES = ("pandas", "requests")
OPTIONAL_MODULES = ("pyarrow",)


def resolve_python() -> str:
    """Return the interpreter that will run main.py (same as this process).

    Always use sys.executable so dep-check and pipeline share one interpreter
    (avoids Windows multi-Python false negatives). Windows users should prefer
    EJECUTAR_COT.bat / run_cot.bat → run_cot_windows.ps1 → cot_system/.venv.
    """
    return sys.executable or "python3"


def _run_python(
    python_exe: str,
    code: str,
    *,
    timeout: int = 60,
) -> tuple[int, str, str]:
    """Run `python_exe -c code`. Returns (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(
            [python_exe, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError as exc:
        return 127, "", f"No se encuentra el intérprete: {python_exe}\n{exc}"
    except subprocess.TimeoutExpired:
        return 124, "", "Timeout al consultar el intérprete Python."
    except OSError as exc:
        return 126, "", str(exc)


def _appcontrol_spanish_fix() -> str:
    return (
        "════════════════════════════════════════════════════════════\n"
        " BLOQUEO Application Control / WDAC (pandas DLL)\n"
        "════════════════════════════════════════════════════════════\n"
        "Python 3.15 + App Control NO está soportado.\n"
        "Instala Python 3.12 y ejecuta launcher\\run_cot_windows.ps1\n"
        "(crea cot_system\\.venv, instala deps, abre el HTML).\n"
        "Doble clic: run_cot.bat\n"
        "Sin pandas (CSV ya procesados): python main.py --from-csv-only"
    )


def _looks_like_appcontrol(text: str) -> bool:
    t = (text or "").lower()
    return any(
        h in t
        for h in (
            "application control",
            "dll load failed",
            "wdac",
            "applocker",
            "blocked this file",
            "bloqueado",
        )
    )


def probe_modules(python_exe: str) -> tuple[list[str], str]:
    """Check REQUIRED_MODULES in *python_exe* (subprocess, not this process).

    Actually imports each module (find_spec alone misses App Control DLL blocks).
    Returns (missing_or_broken_module_names, diagnostic_text).
    """
    probe = (
        "import sys\n"
        f"mods = {list(REQUIRED_MODULES)!r}\n"
        "missing = []\n"
        "errors = []\n"
        "for m in mods:\n"
        "    try:\n"
        "        __import__(m)\n"
        "    except Exception as e:\n"
        "        missing.append(m)\n"
        "        errors.append(m + ':' + type(e).__name__ + ':' + str(e))\n"
        "print('MISSING:' + ','.join(missing))\n"
        "print('EXE:' + sys.executable)\n"
        "print('VER:' + sys.version.split()[0])\n"
        "for e in errors:\n"
        "    print('ERR:' + e)\n"
    )
    rc, out, err = _run_python(python_exe, probe, timeout=60)
    if rc != 0 and not out:
        detail = err or "(sin detalle)"
        msg = (
            f"No se pudo consultar dependencias con:\n  {python_exe}\n"
            f"código={rc}\n{detail}"
        )
        if _looks_like_appcontrol(detail):
            msg += "\n\n" + _appcontrol_spanish_fix()
        return list(REQUIRED_MODULES), msg

    missing: list[str] = []
    exe_line = python_exe
    ver_line = "?"
    err_lines: list[str] = []
    for line in out.splitlines():
        if line.startswith("MISSING:"):
            raw = line[len("MISSING:") :].strip()
            missing = [m for m in raw.split(",") if m] if raw else []
        elif line.startswith("EXE:"):
            exe_line = line[len("EXE:") :].strip() or python_exe
        elif line.startswith("VER:"):
            ver_line = line[len("VER:") :].strip() or "?"
        elif line.startswith("ERR:"):
            err_lines.append(line[len("ERR:") :])

    diag = f"Python usado: {exe_line} ({ver_line})"
    if err_lines:
        diag += "\n" + "\n".join(err_lines)
    if err:
        diag += f"\nstderr: {err}"
    joined = "\n".join(err_lines) + "\n" + (err or "")
    if missing and _looks_like_appcontrol(joined):
        diag += "\n\n" + _appcontrol_spanish_fix()
    return missing, diag


def pandas_location(python_exe: str) -> str:
    """Best-effort `import pandas; print(pandas.__file__)` for failure diagnostics."""
    rc, out, err = _run_python(
        python_exe,
        "import pandas; print(pandas.__file__)",
        timeout=30,
    )
    if rc == 0 and out:
        return f"pandas OK → {out}"
    detail = err or out or f"exit {rc}"
    msg = f"pandas NO importable en {python_exe}:\n  {detail}"
    if _looks_like_appcontrol(detail):
        msg += "\n\n" + _appcontrol_spanish_fix()
    return msg


def install_requirements(python_exe: str) -> tuple[bool, str]:
    """Run `python -m pip install -r requirements.txt` with the pipeline interpreter."""
    if not REQUIREMENTS.is_file():
        return False, f"No existe requirements.txt:\n  {REQUIREMENTS}"

    cmd = [python_exe, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(COT_SYSTEM_ROOT),
            capture_output=True,
            text=True,
            timeout=60 * 15,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired:
        return False, "pip install superó el tiempo máximo (15 min)."
    except OSError as exc:
        return False, f"ERROR al lanzar pip:\n{exc}"

    chunks = []
    if proc.stdout:
        chunks.append(proc.stdout.rstrip())
    if proc.stderr:
        chunks.append("--- stderr ---\n" + proc.stderr.rstrip())
    log = "\n".join(chunks) if chunks else "(sin salida de pip)"
    if proc.returncode != 0:
        return False, (
            f"pip terminó con código {proc.returncode}.\n\n{log}\n\n"
            f"Prueba a mano:\n  {python_exe} -m pip install -r \"{REQUIREMENTS}\"\n\n"
            f"Diagnóstico:\n  {pandas_location(python_exe)}"
        )
    return True, log


def check_prerequisites(*, offer_hint: bool = True) -> list[str]:
    """Return human-readable problems, empty list if OK to start.

    Dependency imports are probed via resolve_python(), not in this process
    (avoids Windows multi-Python PATH mismatches).
    """
    errors: list[str] = []
    if not MAIN_PY.is_file():
        errors.append(f"No se encuentra main.py:\n  {MAIN_PY}")
    if not REQUIREMENTS.is_file():
        errors.append(f"No se encuentra requirements.txt:\n  {REQUIREMENTS}")

    py = resolve_python()
    missing, diag = probe_modules(py)
    if missing:
        hint = ""
        if offer_hint:
            hint = (
                f"\n\nInstálalas con el MISMO Python:\n"
                f"  {py} -m pip install -r \"{REQUIREMENTS}\"\n\n"
                f"En Windows (recomendado, sin .exe): doble clic en EJECUTAR_COT.bat\n"
                f"  o launcher\\run_cot.bat → run_cot_windows.ps1\n"
                f"(venv + Python 3.12/3.11/3.10; evita 3.15+App Control).\n\n"
                f"Diagnóstico:\n  {diag}\n  {pandas_location(py)}"
            )
        errors.append(
            "Faltan dependencias Python: "
            + ", ".join(missing)
            + hint
        )
    return errors


def run_pipeline(extra_args: list[str] | None = None) -> tuple[int, str]:
    """Run cot_system/main.py with cwd=cot_system. Returns (exit_code, combined_log)."""
    if not MAIN_PY.is_file():
        return 1, f"ERROR: no existe {MAIN_PY}"

    py = resolve_python()
    cmd = [py, str(MAIN_PY), *(extra_args or [])]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # Ensure UTF-8 console on Windows when possible
    env.setdefault("PYTHONIOENCODING", "utf-8")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(COT_SYSTEM_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=60 * 30,  # 30 min safety net for downloads
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "")
        return 1, out + "\n\nERROR: el pipeline superó el tiempo máximo (30 min)."
    except OSError as exc:
        return 1, (
            f"ERROR al lanzar Python ({py}):\n{exc}\n\n"
            "Comprueba que Python esté instalado y en el PATH.\n"
            f"Diagnóstico:\n  {pandas_location(py)}"
        )

    chunks = []
    if proc.stdout:
        chunks.append(proc.stdout.rstrip())
    if proc.stderr:
        chunks.append("--- stderr ---\n" + proc.stderr.rstrip())
    log = "\n".join(chunks) if chunks else "(sin salida)"
    if proc.returncode != 0:
        log += (
            f"\n\nERROR: el pipeline terminó con código {proc.returncode}.\n"
            "Causas frecuentes: sin red, CFTC/Yahoo no responden, "
            "o dependencias incompletas.\n"
            f"Python: {py}\n"
            f"{pandas_location(py)}"
        )
    return proc.returncode, log


def open_report(html_path: Path | None = None) -> tuple[bool, str]:
    """Open an HTML report in the default browser (latest or backtest override)."""
    target = html_path or REPORT_HTML
    if not target.is_file():
        return False, f"No se generó el informe HTML:\n  {target}"
    try:
        uri = target.resolve().as_uri()
        opened = webbrowser.open(uri)
        if not opened:
            # webbrowser.open can return False on some platforms even if a
            # browser was launched; still treat as soft success with hint.
            return True, (
                f"Se intentó abrir el informe. Si no se abrió el navegador, "
                f"abre manualmente:\n  {target}"
            )
        return True, f"Informe abierto:\n  {target}"
    except Exception as exc:  # noqa: BLE001 — show any browser failure clearly
        return False, f"No se pudo abrir el navegador:\n{exc}\n\nAbre a mano:\n  {target}"


def ensure_deps(*, auto_install: bool = False) -> tuple[bool, str]:
    """Check deps; optionally pip-install into resolve_python(). Returns (ok, message)."""
    problems = check_prerequisites(offer_hint=not auto_install)
    # Separate path/requirements errors from missing modules
    path_errors = [p for p in problems if "Faltan dependencias" not in p]
    if path_errors:
        return False, "\n\n".join(path_errors)

    py = resolve_python()
    missing, diag = probe_modules(py)
    if not missing:
        return True, f"Dependencias OK.\n{diag}"

    if not auto_install:
        return False, "\n\n".join(problems) if problems else f"Faltan: {', '.join(missing)}"

    log_parts = [
        f"Faltan: {', '.join(missing)}. Instalando con:\n  {py} -m pip install -r \"{REQUIREMENTS}\"",
        f"{diag}",
    ]
    ok, pip_log = install_requirements(py)
    log_parts.append(pip_log)
    if not ok:
        log_parts.append(pandas_location(py))
        return False, "\n\n".join(log_parts)

    missing2, diag2 = probe_modules(py)
    if missing2:
        log_parts.append(
            f"Tras pip aún faltan: {', '.join(missing2)}\n{diag2}\n{pandas_location(py)}"
        )
        return False, "\n\n".join(log_parts)

    log_parts.append(f"Instalación OK.\n{diag2}\n{pandas_location(py)}")
    return True, "\n\n".join(log_parts)


def run_and_open(extra_args: list[str] | None = None) -> tuple[bool, str]:
    """Full flow: prereq check → (optional auto-install) → pipeline → open HTML."""
    ok, msg = ensure_deps(auto_install=False)
    if not ok:
        # Soft path: try auto-install once when only deps are missing
        only_deps = "Faltan dependencias" in msg and "No se encuentra main.py" not in msg
        if only_deps:
            ok2, msg2 = ensure_deps(auto_install=True)
            if not ok2:
                return False, "No se puede ejecutar:\n\n" + msg2
            # fall through after successful install
        else:
            return False, "No se puede ejecutar:\n\n" + msg

    code, log = run_pipeline(extra_args)
    if code != 0:
        return False, log

    ok_r, msg_r = open_report()
    return ok_r, log + "\n\n" + msg_r


# ---------------------------------------------------------------------------
# Console fallback (no tkinter)
# ---------------------------------------------------------------------------


def run_console(extra_args: list[str] | None = None) -> int:
    print(f"=== {APP_TITLE} ===")
    print(f"Proyecto : {PROJECT_ROOT}")
    print(f"Pipeline : {MAIN_PY}")
    print(f"Informe  : {REPORT_HTML}")
    print(f"Python   : {resolve_python()}")
    print()
    print("Ejecutando pipeline… (puede tardar por descargas CFTC/Yahoo)")
    print("-" * 60)
    ok, text = run_and_open(extra_args)
    print(text)
    print("-" * 60)
    if ok:
        print("Listo.")
        return 0
    print("Falló. Revisa el mensaje anterior.")
    print(f"Diagnóstico pandas: {pandas_location(resolve_python())}")
    return 1


# ---------------------------------------------------------------------------
# tkinter GUI
# ---------------------------------------------------------------------------


def run_gui(extra_args: list[str] | None = None) -> int:
    import tkinter as tk
    from tkinter import scrolledtext, messagebox

    root = tk.Tk()
    root.title(APP_TITLE)
    root.minsize(520, 420)
    root.geometry("640x520")

    # Neutral, readable palette (no purple/glow defaults)
    bg = "#1c2329"
    panel = "#243038"
    fg = "#e8eef2"
    accent = "#2f8f6b"
    accent_fg = "#ffffff"
    err = "#c45c5c"
    muted = "#9aabb5"

    root.configure(bg=bg)

    header = tk.Frame(root, bg=bg)
    header.pack(fill="x", padx=16, pady=(16, 8))

    tk.Label(
        header,
        text=APP_NAME,
        font=("Segoe UI", 18, "bold"),
        fg=fg,
        bg=bg,
    ).pack(anchor="w")
    tk.Label(
        header,
        text="Ejecuta el pipeline y abre el informe HTML en el navegador.",
        font=("Segoe UI", 10),
        fg=muted,
        bg=bg,
    ).pack(anchor="w", pady=(4, 0))

    py_exe = resolve_python()
    info = tk.Label(
        root,
        text=f"python: {py_exe}\ncwd: {COT_SYSTEM_ROOT}\ninforme: {REPORT_HTML.name}",
        font=("Consolas", 9),
        fg=muted,
        bg=bg,
        justify="left",
    )
    info.pack(anchor="w", padx=16, pady=(0, 8))

    asof_row = tk.Frame(root, bg=bg)
    asof_row.pack(fill="x", padx=16, pady=(0, 4))
    tk.Label(
        asof_row,
        text="Backtest as-of (opcional, YYYY-MM-DD):",
        font=("Segoe UI", 10),
        fg=muted,
        bg=bg,
    ).pack(side="left")
    asof_var = tk.StringVar(value="")
    asof_entry = tk.Entry(
        asof_row,
        textvariable=asof_var,
        width=14,
        font=("Consolas", 11),
        bg=panel,
        fg=fg,
        insertbackground=fg,
        relief="flat",
    )
    asof_entry.pack(side="left", padx=(8, 0), ipady=4)
    tk.Label(
        asof_row,
        text="vacío = informe en vivo",
        font=("Segoe UI", 9),
        fg=muted,
        bg=bg,
    ).pack(side="left", padx=(8, 0))

    btn_row = tk.Frame(root, bg=bg)
    btn_row.pack(fill="x", padx=16, pady=4)

    status_var = tk.StringVar(value="Listo para ejecutar.")
    status = tk.Label(
        root,
        textvariable=status_var,
        font=("Segoe UI", 10),
        fg=fg,
        bg=bg,
        anchor="w",
    )
    status.pack(fill="x", padx=16, pady=(4, 0))

    log = scrolledtext.ScrolledText(
        root,
        wrap="word",
        font=("Consolas", 9),
        bg=panel,
        fg=fg,
        insertbackground=fg,
        relief="flat",
        borderwidth=0,
    )
    log.pack(fill="both", expand=True, padx=16, pady=12)

    run_btn: tk.Button
    open_btn: tk.Button
    install_btn: tk.Button

    def append_log(text: str) -> None:
        log.insert("end", text + "\n")
        log.see("end")

    def set_busy(busy: bool) -> None:
        state = "disabled" if busy else "normal"
        run_btn.configure(state=state)
        open_btn.configure(state=state)
        install_btn.configure(state=state)

    def on_install() -> None:
        set_busy(True)
        status_var.set("Instalando dependencias (pip)…")
        append_log(f"— pip install -r requirements.txt con {py_exe} —")

        def worker() -> None:
            try:
                ok, out = ensure_deps(auto_install=True)
            except Exception:  # noqa: BLE001
                ok, out = False, traceback.format_exc()

            def done() -> None:
                append_log(out)
                if ok:
                    status_var.set("Dependencias instaladas.")
                    status.configure(fg=accent)
                    messagebox.showinfo(APP_TITLE, "Dependencias OK. Ya puedes ejecutar.")
                else:
                    status_var.set("Falló la instalación de dependencias.")
                    status.configure(fg=err)
                    messagebox.showerror(
                        APP_TITLE,
                        "No se pudieron instalar las dependencias.\n"
                        "En Windows: run_cot.bat / run_cot_windows.ps1 "
                        "(Python 3.12 + venv). 3.15+App Control no soportado.",
                    )
                set_busy(False)

            root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def on_run() -> None:
        problems = check_prerequisites(offer_hint=True)
        if problems:
            msg = "\n\n".join(problems)
            append_log(msg)
            status_var.set("Error de dependencias / rutas.")
            status.configure(fg=err)
            # Soft offer: if only deps missing, ask to auto-install
            only_deps = all("Faltan dependencias" in p for p in problems) or (
                any("Faltan dependencias" in p for p in problems)
                and not any("No se encuentra main.py" in p for p in problems)
                and not any("No se encuentra requirements.txt" in p for p in problems)
            )
            if only_deps and messagebox.askyesno(
                APP_TITLE,
                "Faltan dependencias en ESTE Python.\n\n"
                f"{py_exe}\n\n"
                "¿Instalar ahora con pip (mismo intérprete)?",
            ):
                on_install()
                return
            messagebox.showerror(APP_TITLE, msg)
            return

        asof = (asof_var.get() or "").strip()
        run_args = list(extra_args or [])
        html_override: Path | None = None
        if asof:
            if len(asof) < 10:
                messagebox.showerror(
                    APP_TITLE,
                    "As-of inválido. Usa YYYY-MM-DD (p. ej. 2025-06-17) o déjalo vacío.",
                )
                return
            # Avoid duplicate --as-of if already in CLI extra_args
            if "--as-of" not in run_args:
                run_args.extend(["--as-of", asof[:10]])
            html_override = (
                PROJECT_ROOT
                / "docs"
                / "reports"
                / f"cot_tff_fx_backtest_{asof[:10]}.html"
            )

        set_busy(True)
        status_var.set(
            f"Ejecutando backtest as-of={asof[:10]}…"
            if asof
            else "Ejecutando pipeline… (puede tardar)"
        )
        append_log("— Inicio —" + (f" (--as-of {asof[:10]})" if asof else ""))
        log.update_idletasks()

        def worker() -> None:
            try:
                code, out = run_pipeline(run_args)
            except Exception:  # noqa: BLE001
                code, out = 1, traceback.format_exc()

            def done() -> None:
                append_log(out)
                if code != 0:
                    status_var.set("Falló el pipeline.")
                    status.configure(fg=err)
                    messagebox.showerror(
                        APP_TITLE,
                        "El pipeline falló.\nRevisa el registro (red, CFTC/Yahoo o dependencias).",
                    )
                    set_busy(False)
                    return

                ok, msg = open_report(html_override)
                append_log(msg)
                if ok:
                    status_var.set("Completado — informe abierto.")
                    status.configure(fg=accent)
                else:
                    status_var.set("Pipeline OK, pero no se abrió el HTML.")
                    status.configure(fg=err)
                    messagebox.showwarning(APP_TITLE, msg)
                set_busy(False)

            root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def on_open_only() -> None:
        asof = (asof_var.get() or "").strip()
        override = None
        if asof and len(asof) >= 10:
            override = (
                PROJECT_ROOT
                / "docs"
                / "reports"
                / f"cot_tff_fx_backtest_{asof[:10]}.html"
            )
        ok, msg = open_report(override)
        append_log(msg)
        if ok:
            status_var.set("Informe abierto (sin regenerar).")
            status.configure(fg=accent)
        else:
            status_var.set("No hay informe HTML.")
            status.configure(fg=err)
            messagebox.showwarning(APP_TITLE, msg)

    run_btn = tk.Button(
        btn_row,
        text="Ejecutar y abrir informe",
        command=on_run,
        bg=accent,
        fg=accent_fg,
        activebackground="#267a5c",
        activeforeground=accent_fg,
        relief="flat",
        padx=14,
        pady=8,
        font=("Segoe UI", 11, "bold"),
        cursor="hand2",
    )
    run_btn.pack(side="left")

    open_btn = tk.Button(
        btn_row,
        text="Solo abrir último HTML",
        command=on_open_only,
        bg=panel,
        fg=fg,
        activebackground="#2f3c46",
        activeforeground=fg,
        relief="flat",
        padx=12,
        pady=8,
        font=("Segoe UI", 10),
        cursor="hand2",
    )
    open_btn.pack(side="left", padx=(10, 0))

    install_btn = tk.Button(
        btn_row,
        text="Instalar dependencias",
        command=on_install,
        bg=panel,
        fg=fg,
        activebackground="#2f3c46",
        activeforeground=fg,
        relief="flat",
        padx=12,
        pady=8,
        font=("Segoe UI", 10),
        cursor="hand2",
    )
    install_btn.pack(side="left", padx=(10, 0))

    # Pre-flight note in log
    pre = check_prerequisites(offer_hint=True)
    if pre:
        append_log("Aviso antes de ejecutar:\n" + "\n\n".join(pre))
        status_var.set("Hay problemas de entorno — usa run_cot.bat / run_cot_windows.ps1.")
        status.configure(fg=err)
    else:
        append_log(f"Entorno OK ({py_exe}). Pulsa «Ejecutar y abrir informe».")

    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    force_console = "--console" in argv
    if force_console:
        argv = [a for a in argv if a != "--console"]

    # Remaining args are forwarded to main.py (e.g. --skip-price)
    extra = argv

    if force_console:
        return run_console(extra)

    try:
        import tkinter  # noqa: F401
    except ImportError:
        print(
            "tkinter no disponible — modo consola.\n"
            "(En Linux: sudo apt install python3-tk)\n",
            file=sys.stderr,
        )
        return run_console(extra)

    return run_gui(extra)


if __name__ == "__main__":
    raise SystemExit(main())
