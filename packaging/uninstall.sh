#!/bin/sh
# Removes the program. Your data is kept (records, pictures, settings).
set -e
PREFIX="${PREFIX:-$HOME/.local}"
rm -rf "$PREFIX/opt/problem-sheets"
rm -f "$PREFIX/bin/problem-sheets" "$PREFIX/share/applications/problem-sheets.desktop" \
      "$PREFIX/share/icons/hicolor/256x256/apps/problem-sheets.png"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
echo "Problem Sheets removed."
echo "Your data is still in ${XDG_DATA_HOME:-$HOME/.local/share}/problem-sheets (delete it yourself if you want it gone)."
