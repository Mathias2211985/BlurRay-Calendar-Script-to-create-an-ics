# Bluray‑Disc 4K Release Scraper

Dieses kleine Python‑Skript durchsucht die 4K‑UHD‑Seiten von bluray-disc.de und erstellt eine ICS‑Kalenderdatei mit Erscheinungsdaten für Filme, die explizit die Produktion eines bestimmten Jahres angeben (z. B. "Produktion: 2025").

## Zweck
- Vollständiger Crawl paginierter Listing/Monatsseiten (4k‑UHD) und Extraktion von Detail‑Seiten.
- Nur Einträge werden aufgenommen, die im Detailtext ausdrücklich `Produktion: <Jahr>` angeben.
- Ausgabe: eine `.ics` Datei mit `VEVENT`‑Einträgen (Titel, Veröffentlichungsdatum, Quell‑URL).

## Voraussetzungen
- Python 3.8+ (getestet mit Python 3.10/3.11)
- Abhängigkeiten (in `requirements.txt`):
  - requests
  - beautifulsoup4
  - icalendar

Installieren mit:

```powershell
# im Projektordner C:\Test\autostart
python -m pip install -r requirements.txt
```

## Dateien
- `python` — Hauptskript (CLI). Führe es im Ordner `C:\Test\autostart` aus.
- `tools/` — optionale Debug‑Hilfsscripts (Inspect & Collect).
- `run_scraper.ps1` — einfacher PowerShell‑Runner.
- `requirements.txt` — Abhängigkeiten.

## Verwendung
Beispiel: Erzeuge eine ICS für den Januar 2025 (Kalender‑Template):

```powershell
Set-Location -LiteralPath 'C:\Test\autostart'
python -u .\python --year 2025 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01 --out bluray_2025_01.ics
```

Standard‑Run (nutzt die 4k‑UHD‑Listings als Default, crawl für das Jahr 2025):

```powershell
python .\python --year 2025 --out bluray_2025_4k.ics
```

CLI‑Optionen (Kurzüberblick)
- `--year YEAR` — Produktionsjahr, nach dem explizit gesucht wird (default: 2025)
- `--calendar-template URL` — Template für Monats‑Kalenderseiten; Platzhalter `{year}` und `{month:02d}` möglich
- `--months M1,M2,...` — Komma‑separierte Monatsnummern (z. B. `01,02,03`). Wenn weggelassen, werden die Standard‑Listing‑Seiten gecrawlt.
- `--out PATH` — Ziel‑ICS Datei
- `--max-pages N` — Max. Seiten pro Listing (Schutz gegen Endlosschleifen)

Beispiele:

- Crawl einzelner Monate (Januar und Februar 2025):

```powershell
python .\python --year 2025 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01,02 --out bluray_2025_jan_feb.ics
```

- Voller 4k‑UHD Listing‑Crawl (Default‑Listings):

```powershell
python .\python --year 2025 --out bluray_2025_4k.ics
```

### Mehrere Monate / Alle Monate

Wenn du mehrere Monate oder gleich das ganze Jahr scrapen möchtest, gibt es drei einfache Wege.

A) Mehrere Monate in einem einzelnen Aufruf (empfohlen)

```powershell
Set-Location -LiteralPath 'C:\Test\autostart'
python -u .\python --year 2025 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01,02 --out bluray_2025_jan_feb.ics
```

B) Alle Monate (01–12) in einem einzigen Aufruf

```powershell
python -u .\python --year 2025 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01,02,03,04,05,06,07,08,09,10,11,12 --out bluray_2025_all.ics
```

C) Monat für Monat laufen lassen und die Ergebnisse zusammenführen (nützlich bei schrittweiser Prüfung oder Ausfällen)

1) Erzeuge für jeden Monat eine eigene ICS (PowerShell‑Loop):

```powershell
Set-Location -LiteralPath 'C:\Test\autostart'
for ($m = 1; $m -le 12; $m++) {
  $mm = '{0:d2}' -f $m
  python -u .\python --year 2025 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months $mm --out ("bluray_2025_{0}.ics" -f $mm)
}
```

2) Danach alle `VEVENT`‑Blöcke zu einer Jahres‑ICS zusammenfügen:

```powershell
$allEvents = @()
for ($m = 1; $m -le 12; $m++) {
  $f = ('bluray_2025_{0:00}.ics' -f $m)
  if (Test-Path $f) {
    $content = Get-Content $f -Raw
    $matches = [regex]::Matches($content, 'BEGIN:VEVENT.*?END:VEVENT', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    foreach ($match in $matches) { $allEvents += $match.Value }
  }
}
$header = "BEGIN:VCALENDAR`r`nVERSION:2.0`r`nPRODID:-//custom//bluray-scraper//DE`r`n"
$footer = "END:VCALENDAR"
($header + ($allEvents -join "`r`n") + "`r`n" + $footer) | Out-File -Encoding utf8 bluray_2025_all.ics
```

Hinweise:
- Variante B (alle Monate als Kommaseparierung) ist der kürzeste Weg.
- Variante C ist praktisch, wenn du Monate einzeln prüfen oder bei Fehlern nur einzelne Monatsdateien neu erzeugen willst.
- Nutze `--max-pages` zum Begrenzen der Paginierung falls du schneller fertig sein willst.

## Verhalten & Implementierungsdetails
- Das Skript verwendet eine `requests.Session` mit Backoff/Retry und Timeout‑Behandlung.
- Paginierte Listings werden seitenweise angefragt, bis keine neuen Detail‑Links mehr gefunden werden oder `--max-pages` erreicht ist.
- Nur Detail‑Seiten mit einem numerischen ID‑Muster werden als Kandidaten betrachtet (Filter reduziert Kategorie/News‑Links).
- Datumsextraktion ist robust: mehrere Formate und Fallbacks werden probiert; nur valide Termine werden als `DTSTART` in die ICS geschrieben.
- Duplikate werden anhand der URL dedupliziert.

## Tipps / Troubleshooting
- Wenn die Ausgabe leer ist, prüfe, ob die Seite das gesuchte `Produktion: <Jahr>` Feld tatsächlich enthält. Manche Filme auf der Website haben kein Produktionsjahr im Detailtext.
- Für Live‑Debugging: starte mit `-u` (unbuffered) für stetige Logs:

```powershell
python -u .\python --year 2025 --calendar-template "https://..." --months 01
```

- Wenn der Crawl lange dauert: erhöhe `--max-pages` oder begrenze mit `--months` nur auf benötigte Monate.

- Wenn PowerShell lokale Skripte blockiert (ExecutionPolicy), kannst du die Policy für einen einmaligen Start umgehen, ohne die System‑Einstellung zu ändern:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_scraper.ps1
```

Du kannst damit auch direkt Parameter übergeben (non‑interactive):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_scraper.ps1 -Years '2025' -Months '01,02' -OutPattern 'bluray_{year}_{months}.ics'
```

## Vordefinierte Template‑Pfade auf bluray-disc.de

Auf bluray-disc.de gibt es verschiedene Bereichs‑/Kategorie‑Slugs, die du in deinen Template‑URLs verwenden kannst. Die folgenden Slugs werden häufig auf der Seite verwendet und sind direkt für das `--calendar-template` oder als Listing‑Basis nutzbar:

- `blu-ray-filme`
- `3d-blu-ray-filme`
- `4k-uhd`
- `serien`
- `blu-ray-importe`

Gängige Template‑Formen (ersetze `{slug}` durch einen der Slugs oben):

```text
# Monatsbasiertes Kalender‑Template (empfohlen)
https://bluray-disc.de/{slug}/kalender?id={year}-{month:02d}

# Paginierte Listings (wenn kein Kalender‑Template verwendet wird)
https://bluray-disc.de/{slug}?page=0
```

Beispiel (Januar 2025, slug `4k-uhd`):

```powershell
python -u .\python --year 2025 --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01 --out bluray_2025_01.ics
```

Tipp: Teste ein Template zuerst mit einem einzigen Monat (`--months 01`) bevor du das ganze Jahr crawlst.

## Automatisierung / Zeitplanung
Verwende die mitgelieferte `run_scraper.ps1` oder trage den PowerShell‑Befehl in den Windows Aufgabenplaner ein, wenn das Skript regelmäßig laufen soll.

Usage

PowerShell (from repository root):

```powershell
Set-Location -LiteralPath 'C:\Test\autostart'
python .\python --year 2025 --out bluray_2025_nov_dec.ics
```

Requirements

Install with pip:

```powershell
python -m pip install --user -r requirements.txt
```

Notes

- The scraper requires the site to show an explicit `Produktion: <year>` entry to include an item. Use `--year` to change the filter.
- The script follows pagination and uses retries for robustness.
- Debug files are available in `tools/` if present.
