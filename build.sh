#!/bin/bash
# Baut Presentify.app als echtes py2app-Bundle und startet es zum Test.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3

echo "==> Prüfe py2app ..."
if ! $PY -c "import py2app" 2>/dev/null; then
    echo "==> Installiere py2app ..."
    $PY -m pip install --user py2app setuptools
fi

echo "==> Räume alte Builds auf ..."
rm -rf build dist Presentify.app

echo "==> Baue Bundle mit py2app ..."
$PY setup.py py2app 2>&1 | tail -n 3

if [ ! -d "dist/Presentify.app" ]; then
    echo "FEHLER: dist/Presentify.app wurde nicht erzeugt." >&2
    exit 1
fi

cp -R dist/Presentify.app .
echo "==> Presentify.app erstellt."

echo "==> Starte App ..."
open Presentify.app
sleep 2

if pgrep -f "Presentinize|Presentify" >/dev/null; then
    echo "==> OK: Prozess läuft. Stift-Icon oben rechts in der Menüleiste."
    echo "    Linksklick = Zeichnen an/aus, Rechtsklick = Menü."
    echo "    Hinweis: Für die globalen Shortcuts (fn+Ctrl+P / Opt+Cmd+D) ggf."
    echo "    Systemeinstellungen > Datenschutz > Bedienungshilfen freigeben."
else
    echo "WARNUNG: Prozess nicht gefunden — Konsole.app auf Fehler prüfen." >&2
    exit 1
fi
