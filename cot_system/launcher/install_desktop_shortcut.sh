#!/usr/bin/env bash
# Crea un acceso directo .desktop en el Escritorio (y en aplicaciones) con rutas absolutas.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$DIR/run_cot.sh"
ICON="utilities-terminal"

chmod +x "$DIR/run_cot.sh" "$DIR/run_cot.command" "$DIR/cot_launcher.py" "$DIR/install_desktop_shortcut.sh" 2>/dev/null || true

DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
if [ ! -d "$DESKTOP_DIR" ]; then
  DESKTOP_DIR="$HOME/Escritorio"
fi
if [ ! -d "$DESKTOP_DIR" ]; then
  DESKTOP_DIR="$HOME/Desktop"
  mkdir -p "$DESKTOP_DIR"
fi

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS_DIR"

ENTRY_BODY=$(cat <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=COT TFF FX
Comment=Ejecuta el pipeline COT y abre el informe HTML
Exec=$LAUNCHER
Path=$DIR
Icon=$ICON
Terminal=false
Categories=Finance;Office;
StartupNotify=true
EOF
)

OUT_DESKTOP="$DESKTOP_DIR/COT TFF FX.desktop"
OUT_APPS="$APPS_DIR/cot-tff-fx.desktop"

printf '%s\n' "$ENTRY_BODY" > "$OUT_DESKTOP"
printf '%s\n' "$ENTRY_BODY" > "$OUT_APPS"
chmod +x "$OUT_DESKTOP" "$OUT_APPS"

# Marcar como confiable en GNOME/Ubuntu (si está disponible)
if command -v gio >/dev/null 2>&1; then
  gio set "$OUT_DESKTOP" metadata::trusted true 2>/dev/null || true
fi

echo "Acceso directo creado:"
echo "  $OUT_DESKTOP"
echo "  $OUT_APPS"
echo ""
echo "Si el escritorio pide 'Permitir lanzar' / 'Allow Launch', acéptalo una vez."
