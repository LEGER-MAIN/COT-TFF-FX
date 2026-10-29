#!/bin/bash
# COT TFF FX — lanzador macOS (doble clic desde Finder)
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  osascript -e 'display dialog "No se encuentra Python 3. Instálalo desde python.org o con Homebrew (brew install python)." buttons {"OK"} default button 1 with title "COT TFF FX"' 2>/dev/null \
    || echo "ERROR: no se encuentra Python 3"
  exit 1
fi

"$PY" "$(dirname "$0")/cot_launcher.py" "$@"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  echo ""
  echo "El lanzador terminó con error $STATUS."
  echo "Pulsa Enter para cerrar…"
  read -r _
fi
exit "$STATUS"
