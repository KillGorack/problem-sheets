#!/bin/sh
# Build the self-contained Linux package: dist/problem-sheets-<version>-linux-<arch>.tar.gz
# Needs: python3 with tkinter (python3-tkinter), internet for pip. No admin rights.
set -e
cd "$(dirname "$0")/.."                       # the app folder
VERSION="$(python3 -c 'from version import VERSION; print(VERSION)')"
ARCH="$(uname -m)"
OUT="dist/problem-sheets-$VERSION-linux-$ARCH"

# a clean, throw-away build environment (so nothing from your own setup leaks in)
python3 -m venv build/venv
build/venv/bin/pip install --quiet --upgrade pip
build/venv/bin/pip install --quiet -r packaging/requirements.txt pyinstaller
build/venv/bin/pip freeze > packaging/requirements.lock      # exactly what went into this build

rm -rf build/pyi dist/problem-sheets "$OUT" "$OUT.tar.gz"
build/venv/bin/pyinstaller --noconfirm --clean --windowed --name problem-sheets \
    --workpath build/pyi --specpath build/pyi --distpath dist \
    --paths . \
    --collect-all customtkinter --collect-all reportlab --hidden-import PIL._tkinter_finder \
    --add-data "$PWD/icons:icons" --add-data "$PWD/icon.png:." \
    main.py

echo "== self-test of the built app"
dist/problem-sheets/problem-sheets --selftest

# assemble the download: the app + a no-admin installer
mkdir -p "$OUT"
cp -R dist/problem-sheets "$OUT/app"
cp packaging/install.sh packaging/uninstall.sh packaging/problem-sheets.desktop.in packaging/icon.png "$OUT/"
cp README.md CHANGELOG.md "$OUT/" 2>/dev/null || true
chmod +x "$OUT/install.sh" "$OUT/uninstall.sh"
tar -C dist -czf "$OUT.tar.gz" "$(basename "$OUT")"
echo "Built $OUT.tar.gz ($(du -h "$OUT.tar.gz" | cut -f1))"
