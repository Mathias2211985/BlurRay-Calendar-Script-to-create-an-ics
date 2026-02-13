# BluRay Calendar Scraper

Durchsucht [bluray-disc.de](https://bluray-disc.de) nach Neuerscheinungen und erstellt ICS-Kalenderdateien, die sich in Google Calendar, Outlook, Apple Calendar usw. importieren lassen.

## Features

- **Web-UI** mit Dark Theme, Live-Log und Fortschrittsanzeige
- **Standalone .exe** -- kein Python noetig fuer Endbenutzer
- **Mehrere Kategorien**: 4K UHD, Blu-ray Filme, 3D Blu-ray, Serien, Importe
- **Flexible Filter**: Kalender-Jahre, Release-Jahre, Produktions-Jahre, Monate
- **Kategorie-Erkennung**: filtert automatisch falsche Kategorien heraus (z.B. keine Serien bei 4K-Suche)
- **Deduplizierung**: erkennt Mehrfach-Editionen (Steelbook, Mediabook, ...) und behaelt nur einen Eintrag
- **CLI-Modus**: volle Kontrolle ueber Kommandozeile fuer Automatisierung

## Schnellstart

### Option 1: Standalone .exe (empfohlen)

1. `BluRay-Calendar-Scraper.exe` aus dem `dist/`-Ordner starten
2. Browser oeffnet sich automatisch auf `http://localhost:5000`
3. Einstellungen waehlen und "Scraping starten" klicken
4. ICS-Datei herunterladen

### Option 2: Python + Web-UI

```bash
pip install -r requirements.txt
python web_ui.py
```

Oder per Doppelklick: `start_web.bat`

### Option 3: CLI (ohne Web-UI)

```bash
python scraper.py --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --calendar-year 2026 --category 4k-uhd --ignore-production --out bluray_2026_4k.ics
```

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `web_ui.py` | Flask Web-UI (Hauptanwendung) |
| `scraper.py` | Scraper-Kern (CLI) |
| `build_exe.py` | Build-Script fuer die .exe |
| `start_web.bat` | Doppelklick-Starter fuer die Web-UI |
| `requirements.txt` | Python-Abhaengigkeiten |

## Web-UI

Die Web-UI bietet:

- **Kalender-Jahre**: Dropdown mit Mehrfachauswahl (1950--2028)
- **Kategorien**: Chip-Auswahl (4K UHD, Blu-ray, 3D, Serien, Importe)
- **Monate**: Chip-Auswahl (leer = alle)
- **Release-Jahre**: Dropdown mit Mehrfachauswahl (leer = alle)
- **Produktionsjahr-Filter**: Toggle zum Aktivieren, mit eigener Jahresauswahl
- **Ausgabedatei**: Konfigurierbares Namensmuster mit Platzhaltern
- **Live-Log**: Echtzeit-Ausgabe via Server-Sent Events (rechte Spalte)
- **Vorschau-Tabelle**: alle gefundenen Eintraege mit Checkboxen zur Auswahl vor der ICS-Erstellung
- **Download**: ICS-Datei direkt im Browser herunterladen

Einstellungen werden automatisch in `config.json` gespeichert.

## CLI-Optionen (scraper.py)

| Option | Beschreibung |
|--------|-------------|
| `--year YEARS` | Produktionsjahr(e), komma-getrennt (default: aktuelles Jahr) |
| `--calendar-year YEAR` | Kalender-Jahr fuer URL-Template |
| `--calendar-template URL` | URL-Template mit `{year}` und `{month:02d}` Platzhaltern |
| `--months M1,M2` | Komma-getrennte Monate (z.B. `01,02,03`) |
| `--release-years YEARS` | Filter nach Erscheinungsdatum |
| `--category SLUG` | Kategorie-Filter (`4k-uhd`, `blu-ray-filme`, `serien`, ...) |
| `--ignore-production` | Produktionsjahr-Pruefung deaktivieren |
| `--only-production` | Nur Eintraege mit passendem Produktionsjahr |
| `--out PATH` | Ausgabedatei (Platzhalter: `YYYY`, `MM`, `{slug}`, `{release_years}`) |

## Beispiele (CLI)

**4K-Neuerscheinungen fuer 2026 (alle Monate):**

```bash
python scraper.py --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --calendar-year 2026 --category 4k-uhd --ignore-production --out bluray_2026_4k.ics
```

**Blu-ray Serien, Januar bis Maerz 2026:**

```bash
python scraper.py --calendar-template "https://bluray-disc.de/serien/kalender?id={year}-{month:02d}" --calendar-year 2026 --months 01,02,03 --category serien --ignore-production --out serien_2026_q1.ics
```

**Filme mit Produktionsjahr 2025, Release 2026:**

```bash
python scraper.py --year 2025 --release-years 2026 --calendar-year 2026 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --category 4k-uhd --out neue_filme_2025.ics
```

**Alle Releases ohne Produktionsjahr-Filter:**

```bash
python scraper.py --release-years 2026 --ignore-production --calendar-template "https://bluray-disc.de/blu-ray-filme/kalender?id={year}-{month:02d}" --calendar-year 2026 --category blu-ray-filme --out alle_2026.ics
```

## Verfuegbare Kategorien

| Slug | Beschreibung |
|------|-------------|
| `4k-uhd` | 4K Ultra HD |
| `blu-ray-filme` | Blu-ray Filme |
| `3d-blu-ray-filme` | 3D Blu-ray |
| `serien` | Serien |
| `blu-ray-importe` | Importe |

URL-Template-Format: `https://bluray-disc.de/{slug}/kalender?id={year}-{month:02d}`

## Standalone .exe erstellen

Voraussetzung: Python + PyInstaller (`pip install pyinstaller`)

```bash
python build_exe.py
```

Die fertige .exe liegt danach in `dist/BluRay-Calendar-Scraper.exe`. Der Build-Ordner wird in `%TEMP%` angelegt, um Konflikte mit OneDrive zu vermeiden.

## Voraussetzungen (Entwicklung)

- Python 3.8+
- Abhaengigkeiten installieren:

```bash
pip install -r requirements.txt
```

Enthalten: `requests`, `beautifulsoup4`, `icalendar`, `flask`

## Hinweise

- Der Scraper verwendet Retry-Logik und Timeouts fuer stabile Verbindungen
- Duplikate werden anhand normalisierter Titel dedupliziert (Steelbook, Mediabook, etc.)
- Bei 4K-Suche werden Serien automatisch herausgefiltert (und umgekehrt)
- Die ICS-Datei kann in jeden gaengigen Kalender importiert werden
