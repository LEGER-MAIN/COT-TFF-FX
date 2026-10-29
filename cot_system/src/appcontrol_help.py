"""Mensajes claros en español cuando App Control / WDAC bloquea DLLs de pandas."""

from __future__ import annotations

APPCONTROL_HINTS = (
    "application control",
    "dll load failed",
    "wdac",
    "applocker",
    "blocked this file",
    "bloqueado",
)


def looks_like_appcontrol(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return any(h in text for h in APPCONTROL_HINTS)


SPANISH_FIX = """
════════════════════════════════════════════════════════════
 BLOQUEO Application Control / WDAC (pandas / numpy DLL)
════════════════════════════════════════════════════════════

Python 3.15 (pythoncore) + App Control suele bloquear las DLLs
nativas de pandas. ESA COMBINACIÓN NO ESTÁ SOPORTADA.

Qué hacer:
  1) Instala Python 3.12 desde https://www.python.org/downloads/
     (marca "Add python.exe to PATH").
  2) Desde la raiz del proyecto ejecuta (doble clic):
       EJECUTAR_COT.bat
     Eso crea cot_system\\.venv, instala deps y abre
     http://127.0.0.1:8765/
  3) Si ya tienes CSV procesados y solo quieres el informe:
       EJECUTAR_COT.bat --from-csv-only
     (usa csv stdlib, sin pandas).

No uses 3.15 con App Control para este pipeline.
""".strip()


def format_import_failure(exc: BaseException) -> str:
    detail = f"{type(exc).__name__}: {exc}"
    if looks_like_appcontrol(exc):
        return f"{SPANISH_FIX}\n\nDetalle: {detail}"
    return (
        f"No se pudo importar una dependencia del pipeline:\n  {detail}\n\n"
        "En Windows, usa EJECUTAR_COT.bat (venv + Python 3.12).\n"
        "Si el error menciona Application Control / DLL load failed, "
        "instala Python 3.12 — 3.15+App Control no está soportado."
    )
