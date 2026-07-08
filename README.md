# Presentinize

Zeichnen über den Bildschirm für Screen-Recordings & Live-Präsentationen — als native macOS-Menüleisten-App. Pure Python 3 + PyObjC (AppKit), **keine externen Abhängigkeiten**.

![macOS](https://img.shields.io/badge/macOS-12%2B-black) ![Python](https://img.shields.io/badge/Python-3.9%2B-C9A84C) ![License](https://img.shields.io/badge/License-MIT-black)

## Features

- **Menüleisten-App** (kein Dock-Icon): Linksklick auf das Stift-Icon = Zeichnen an/aus (golden = aktiv), Rechtsklick = Menü
- **Transparentes Overlay** über allen Apps und Spaces (auch Vollbild-Apps); klick-durchlässig, solange Zeichnen aus ist
- **6 Werkzeuge:** Freihand, Pfeil, Rechteck (abgerundet), Ellipse, Linie, Highlighter
- **6 Farben** (Rot, Gold, Grün, Blau, Weiß, Schwarz), **3 Strichstärken**
- **Schwebende Glas-Toolbar** unten mittig (verschiebbar, nur Icons, Gold-Akzent)
- **Spotlight-Modus 🔦:** dunkelt den Bildschirm ab, heller Kreis folgt der Maus (Größe per Scrollrad / ↑↓), großer goldener Präsentations-Cursor
- Shortcuts: `fn+Ctrl+P` / `⌥⌘D` = Zeichnen togglen · `1–6` = Werkzeug · `⌘Z` = Rückgängig · `⌫` = alles löschen · `Esc` = beenden

## Installation

```bash
git clone https://github.com/calvinhollywood/presentinize.git
cd presentinize
./build.sh
```

`build.sh` installiert bei Bedarf `py2app`, baut ein echtes doppelklickbares `Presentify.app`-Bundle und startet es. Danach erscheint das Stift-Icon oben rechts in der Menüleiste.

> **Hinweis:** Für die globalen Tastatur-Shortcuts einmalig freigeben unter
> Systemeinstellungen → Datenschutz & Sicherheit → Bedienungshilfen.
> Der Linksklick aufs Menüleisten-Icon funktioniert immer, auch ohne Freigabe.

## Ohne Build direkt starten (zum Testen)

```bash
python3 presentify.py
```

(Für den Dauereinsatz das App-Bundle bauen — nur so erscheint das Icon auf neueren macOS-Versionen zuverlässig.)

## Bedienung

| Aktion | Eingabe |
|---|---|
| Zeichnen an/aus | Linksklick aufs Menüleisten-Icon, `fn+Ctrl+P`, `⌥⌘D` |
| Werkzeug wechseln | Toolbar oder Tasten `1`–`6` |
| Rückgängig | `⌘Z` |
| Alles löschen | `⌫` (Backspace) |
| Spotlight an/aus | 🔦 in der Toolbar, beenden mit `Esc` |
| Spotlight-Größe | Scrollrad oder `↑`/`↓` (40–600 px) |
| Zeichnen beenden | `Esc` oder roter ✕ in der Toolbar |

## Lizenz

MIT — © Calvin Hollywood
