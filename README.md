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
- `--year YEARS` — **Produktionsjahr(e)**, nach denen explizit gesucht wird (default: "2025"). **NEUE FUNKTION**: Unterstützt jetzt mehrere Jahre komma-getrennt, z.B. `--year "2025,2026"` für Filme die 2025 ODER 2026 produziert wurden.
- `--calendar-template URL` — Template für Monats‑Kalenderseiten; Platzhalter `{year}` und `{month:02d}` möglich
- `--months M1,M2,...` — Komma‑separierte Monatsnummern (z. B. `01,02,03`). Wenn weggelassen, werden die Standard‑Listing‑Seiten gecrawlt.
- `--out PATH` — Ziel‑ICS Datei. Unterstützt zusätzlich die Platzhalter `{slug}` und `{release_years}`.
  - Wenn `{slug}` im Muster vorkommt, wird es durch einen sicheren Template‑Slug ersetzt (z. B. `4k-uhd`).
  - Wenn `{release_years}` im Muster vorkommt, wird es durch die (sanierten) Release‑Jahreswerte ersetzt (z. B. `2025-2026`).
  - Wenn eines der Tokens nicht vorhanden ist, fügt `run_scraper.ps1` fehlende Teile automatisch vor der Dateiendung ein, um Überschreibungen zu vermeiden (z. B. `bluray_2025_12_2025-2026_4k-uhd.ics`).
- `--release-years YEARS` — Optional: Komma‑separierte RELEASE‑Jahre (bezogen auf das Veröffentlichungsdatum/`DTSTART`), z. B. `--release-years "2024,2025"`.
  - Wenn gesetzt, werden nur Events berücksichtigt, deren `DTSTART` in einem dieser Jahre liegt.
  - **WICHTIG**: Diese filtern nach dem **Erscheinungsdatum** der Filme, nicht nach dem Produktionsjahr!
  - Wenn du `run_scraper.ps1` interaktiv startest und `-ReleaseYears` nicht übergeben hast, fragt der Runner VOR dem Erstellen des Dateinamens nach den Release‑Jahren, damit die Auswahl in den Dateinamen eingebettet werden kann.
- `--ignore-production` — Optional: Wenn gesetzt, wird die Produktionsjahr‑Prüfung deaktiviert. Nützlich, wenn du ausschließlich nach dem Veröffentlichungsjahr (DTSTART) filtern möchtest und Seiten ohne ein explizites "Produktion:"-Feld trotzdem berücksichtigen willst.
  - Runner‑Param: `-IgnoreProduction` (weitergereicht als `--ignore-production` an Python).
- `--only-production` — Wenn gesetzt, gilt die traditionelle Filterung: es werden nur Einträge aufgenommen, deren Detailseite ausdrücklich `Produktion: <YEAR>` enthält (nutzt `--year`, Standard 2025). Wenn du dieses Flag nicht setzt, ist das Standardverhalten: alle gefundenen Detailseiten werden berücksichtigt (du kannst zusätzlich `--release-years` verwenden, um die Results nach Veröffentlichungsjahr einzuschränken).
- `--max-pages N` — Max. Seiten pro Listing (Schutz gegen Endlosschleifen)

## PowerShell Runner - Interaktive Eingaben

Der `run_scraper.ps1` PowerShell-Runner fragt jetzt nach **drei separaten Eingaben** für maximale Flexibilität:

### 1. Kalender-Jahre
**Eingabe**: "Gib Jahr(e) ein (Komma-getrennt, z.B. 2025 oder 2024,2025)"
- **Zweck**: Bestimmt, welche **Kalender-Seiten** gecrawlt werden
- **Beispiel**: `2026` → crawlt nur 2026-Kalender-Seiten
- **Beispiel**: `2025,2026` → crawlt sowohl 2025- als auch 2026-Kalender-Seiten

### 2. Release-Jahre  
**Eingabe**: "Gib Release-Jahr(e) ein (Komma-getrennt, z.B. 2025 oder 2024,2025). Leer = ALL"
- **Zweck**: Filtert Filme nach dem **Erscheinungsdatum** (wann sie in den Handel kommen)
- **Beispiel**: `2025,2026` → nur Filme die 2025 oder 2026 released werden
- **Leer lassen**: Alle gefundenen Filme, egal wann sie erscheinen

### 3. Produktions-Jahre *(NEU!)*
**Eingabe**: "Gib Produktions-Jahr(e) ein (Komma-getrennt, z.B. 2025 oder 2025,2026). [Enter = gleich wie Release-Jahre]"
- **Zweck**: Filtert Filme nach dem **Produktionsjahr** (wann sie gedreht wurden)  
- **Beispiel**: `2025,2026` → nur Filme die 2025 oder 2026 produziert wurden
- **Leer lassen**: Verwendet die gleichen Jahre wie Release-Jahre

### 4. Produktionsjahr-Prüfung
**Eingabe**: "Ignoriere Produktionsjahr-Prüfung? (J/n)"
- **J** (Standard): Ignoriert Produktionsjahre komplett, nimmt alle gefundenen Filme
- **n**: Verwendet die angegebenen Produktions-Jahre zum Filtern

## Beispiel-Szenario

**Du suchst**: Filme mit Produktionsjahr 2025, die 2026 released werden

**Eingaben**:
```
Kalender-Jahre: 2026          (crawlt 2026-Kalender)
Release-Jahre: 2026           (nur 2026-Releases)  
Produktions-Jahre: 2025       (nur 2025-Produktionen)
Produktionsjahr-Prüfung: n    (Prüfung aktivieren)
```

**Ergebnis**: Script crawlt 2026-Kalender-Seiten und findet Filme wie "Das Kanu des Manitu 4K" (prod=2025, release=2026-01-02) ✅

 
 Beispiel — Aufruf mit Ignorieren der Produktionsprüfung
 
 ```powershell
 Set-Location -LiteralPath 'C:\Test\autostart'
 # interaktiv gefragt wird: Ignoriere Produktionsjahr-Prüfung? (J/n)  -> Enter (Default = J)
 .\run_scraper.ps1 -Years '2025' -Months '11' -CalendarTemplate 'blu-ray-filme' -OutPattern 'bluray_{year}_{months}.ics' -ReleaseYears '2025'
 ```
 
 Oder non‑interactive direkt mit dem Switch:
 
 ```powershell
 powershell -NoProfile -ExecutionPolicy Bypass -File .\run_scraper.ps1 -Years '2025' -Months '11' -CalendarTemplate 'blu-ray-filme' -OutPattern 'bluray_{year}_{months}.ics' -ReleaseYears '2025' -IgnoreProduction
 ```
 
 Erwartete (gekürzte) Ausgabe in der erzeugten ICS (Beispiel‑EVENTs):
 
 ```
 BEGIN:VCALENDAR
 VERSION:2.0
 PRODID:-//BlurayDisc Scraper//de//
 BEGIN:VEVENT
 SUMMARY:Safe House - Verrat ist die ultimative Waffe Blu-ray
 DTSTART;VALUE=DATE:20251107
 DESCRIPTION:Quelle: https://bluray-disc.de/blu-ray-filme/200717-safe_house_verrat_ist_die_ultimative_waffe
 END:VEVENT
 BEGIN:VEVENT
 SUMMARY:James Bond 007 - Feuerball 4K (4K UHD + Blu-ray) Blu-ray
 DTSTART;VALUE=DATE:20251106
 DESCRIPTION:Quelle: https://bluray-disc.de/blu-ray-filme/200419-james_bond_007_feuerball_4k_4k_uhd_bluray
 END:VEVENT
 END:VCALENDAR
 ```
 
 Hinweis: Die tatsächlichen Events hängen von den Seiteninhalten ab; mit `-IgnoreProduction` werden Einträge mit passendem Veröffentlichungsjahr aufgenommen, auch wenn kein explizites "Produktion:"-Feld vorhanden ist.
- Wenn du das Python‑Skript direkt ausführst, fragt es ebenfalls interaktiv (nur wenn stdin ein TTY ist) nach `--release-years`, falls das Argument nicht bereits gesetzt wurde.

## Beispiele

### Interaktiv (Runner fragt nach allen Parametern):

```powershell
Set-Location -LiteralPath 'C:\Test\autostart'
.\run_scraper.ps1
# Oder per Doppelklick die mitgelieferte run_scraper_doubleclick.bat
```

### Non‑interactive (Parameter übergeben):

```powershell
# PowerShell Runner mit allen Parametern
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_scraper.ps1 -Years '2026' -Months '01,02' -CalendarTemplate '4k-uhd' -OutPattern 'bluray_{year}_{months}_{release_years}.ics' -ReleaseYears '2025,2026'

# Python direkt mit neuer Mehrfach-Jahr-Syntax:
python -u .\python --year "2025,2026" --release-years "2025,2026" --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01,02 --out bluray_multi_year.ics
```

### Praktische Anwendungsfälle:

**1. Aktuelle Filme (produziert 2024/2025, erscheinen 2025/2026):**
```powershell
python -u .\python --year "2024,2025" --release-years "2025,2026" --calendar-template "https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}" --months 01,02,03 --out current_movies.ics
```

**2. Klassiker-Neuauflagen (alte Produktionsjahre, neue Releases):**
```powershell
python -u .\python --year "1990,1995,2000" --release-years "2025" --ignore-production --out classics_remastered.ics
```

**3. Nur Release-Filter (ignoriere Produktionsjahr komplett):**
```powershell
python -u .\python --release-years "2025,2026" --ignore-production --out all_releases_2025_2026.ics
```

Hinweis: Standard ist „ALL“ — du musst nichts eingeben, wenn du alle gefundenen Einträge behalten willst.

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

### Double‑Click Starter (einfach per Doppelklick)

Wenn du das Tool per Doppelklick starten möchtest (ohne manuelles Öffnen eines PowerShell‑Fensters), liegt eine kleine Batch‑Datei im Projekt, die beim Doppelklick ein PowerShell‑Fenster öffnet und das interaktive `run_scraper.ps1` startet.

- Datei: `run_scraper_doubleclick.bat`
- Zweck: startet `run_scraper.ps1` in einem neuen PowerShell‑Fenster, umgeht die ExecutionPolicy nur für diesen Aufruf und hält das Fenster offen, sodass du die Eingabeaufforderungen (Prompts) sehen und beantworten kannst.

Inhalt (kurz):

```text
@echo off
pushd "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0run_scraper.ps1"
popd
```

So verwendest du die Datei:

1. Öffne den Ordner `C:\Test\autostart` im Explorer.
2. Doppelklicke auf `run_scraper_doubleclick.bat` — ein neues PowerShell‑Fenster öffnet sich.
3. Folge den Eingabeaufforderungen (Jahr/Monat/Template/OutPattern).

Alternative: Desktop‑Verknüpfung

1. Rechtsklicke auf `run_scraper_doubleclick.bat` → Senden an → Desktop (Verknüpfung erstellen).
2. Optional: Rechtsklick auf die Verknüpfung → Eigenschaften → Erweitert → "Als Administrator ausführen" (nur falls nötig).

Sicherheits‑Hinweis

- Die Batch‑Datei ruft PowerShell mit `-ExecutionPolicy Bypass` auf — das umgeht die lokale Ausführungsbeschränkung nur für diesen Aufruf. Verwende diese Methode nur, wenn du der Quelle der Skripte vertraust.
- Wenn du lieber keine Policy‑Bypass verwenden möchtest, kannst du stattdessen die Datei freigeben (`Unblock-File .\run_scraper.ps1`) oder die ExecutionPolicy dauerhaft mit Bedacht anpassen (z. B. `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`).

Wenn du möchtest, erstelle ich gerne automatisch eine Desktop‑Verknüpfung mit eigenem Icon und einem kurzen Hinweistext; sag kurz Bescheid und welche Art Icon (standard / eigenes PNG) du willst.

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
