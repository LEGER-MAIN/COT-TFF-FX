#!/usr/bin/env bash
# COT TFF FX — lanzador Linux / terminal (también usado por el .desktop)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: no se encuentra Python 3 en el PATH." >&2
  exit 1
fi

exec "$PY" "$DIR/cot_launcher.py" "$@"
