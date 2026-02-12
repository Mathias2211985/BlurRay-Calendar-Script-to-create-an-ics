# Debug-Kopie des Scrapers: zusätzliche Ausgaben für Link- und Datumserkennung
# Benötigte Pakete:
# pip install requests beautifulsoup4 icalendar

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
import time
import re
from urllib.parse import urljoin

BASE = "https://bluray-disc.de"

MONTH_PAGES = [
    "https://bluray-disc.de/blu-ray-filme/neuerscheinungen?ansicht=detail&id=1975-11&page=0",
    "https://bluray-disc.de/blu-ray-filme/neuerscheinungen?id=1992-12&page=1"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BluRayScraper/1.0)"}


def fetch(url):
    print(f"FETCH -> {url}")
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def extract_item_links_from_month_page(html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    for a in soup.select("a"):
        href = a.get("href", "")
        if not href:
            continue
        # normalize to absolute URL (strip query/fragments)
        full = urljoin(BASE, href.split("?")[0].split('#')[0])
        # accept film detail pages when they contain an numeric id segment
        # examples: /blu-ray-filme/197299-... or /blu-ray-news/filme/157192-...
        if re.search(r"/blu-ray-filme/\d+", full) or re.search(r"/blu-ray-news/filme/\d+", full):
            links.add(full)
    print(f"DEBUG: extract_item_links -> found {len(links)} links")
    return list(links)


def parse_detail_page(html):
    soup = BeautifulSoup(html, "html.parser")
    result = {"title": None, "release_date": None, "production_year": None, "url": None}

    h1 = soup.find(["h1", "h2"])
    if h1:
        result["title"] = h1.get_text(strip=True)

    text = soup.get_text(" ", strip=True)
    m = re.search(r"Produktion[:\s]*([0-9]{4})", text)
    if not m:
        m2 = re.search(r"\(([0-9]{4})\)", text)
        if m2:
            result["production_year"] = int(m2.group(1))
    else:
        result["production_year"] = int(m.group(1))

    date_patterns = [
        r"Ab\s+([0-3]?\d\.[01]?\d\.[0-9]{4})",
        r"ab\s+([0-3]?\d\.[01]?\d\.[0-9]{4})",
        r"([0-3]?\d\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*[0-9]{4})",
        r"([0-3]?\d\.[01]?\d\.[0-9]{4})"
    ]
    month_dict = {
        "Januar":"01","Februar":"02","März":"03","April":"04","Mai":"05","Juni":"06",
        "Juli":"07","August":"08","September":"09","Oktober":"10","November":"11","Dezember":"12"
    }
    for pat in date_patterns:
        mm = re.search(pat, text, flags=re.IGNORECASE)
        if mm:
            s = mm.group(1)
            s = s.strip()
            # replace month names with numeric month
            for name, num in month_dict.items():
                if re.search(name, s, flags=re.IGNORECASE):
                    s = re.sub(name, "."+num+".", s, flags=re.IGNORECASE)
            # keep only digits and dots and whitespace, then collapse dots
            s = re.sub(r"[^0-9\.\s]", "", s)
            s = re.sub(r"\.{2,}", ".", s)
            s = s.replace(" ", "")
            # try several parse attempts
            for fmt in ("%d.%m.%Y", "%d.%m.%y"):
                try:
                    dt = datetime.strptime(s, fmt)
                    result["release_date"] = dt.date()
                    break
                except Exception:
                    pass
            if result["release_date"] is None:
                # try to find day.month and a 4-digit year somewhere nearby in text
                m2 = re.search(r"([0-3]?\d\.[01]?\d)\D{0,30}([0-9]{4})", text)
                if m2:
                    candidate = f"{m2.group(1)}.{m2.group(2)}"
                    candidate = re.sub(r"\.{2,}", ".", candidate)
                    try:
                        dt = datetime.strptime(candidate, "%d.%m.%Y")
                        result["release_date"] = dt.date()
                    except Exception as e:
                        print("DEBUG: fallback date parse failed for", candidate, e)
            if result["release_date"]:
                break

    return result


def main():
    cal = Calendar()
    cal.add('prodid', '-//BlurayDisc Scraper//de//')
    cal.add('version', '2.0')

    found = []
    visited = set()

    for month_url in MONTH_PAGES:
        try:
            html = fetch(month_url)
        except Exception as e:
            print(f"Fehler beim Laden {month_url}: {e}")
            continue
        links = extract_item_links_from_month_page(html)
        print(f"{len(links)} mögliche Detail-Links gefunden auf {month_url}")
        for link in links:
            print("PROCESS ->", link)
            if link in visited:
                print(" SKIP visited")
                continue
            visited.add(link)
            time.sleep(0.5)
            try:
                d_html = fetch(link)
            except Exception as e:
                print(f"Fehler beim Laden Detailseite {link}: {e}")
                continue
            meta = parse_detail_page(d_html)
            meta["url"] = link
            title = meta.get("title") or link
            py = meta.get("production_year")
            rdate = meta.get("release_date")
            print(" -> meta:", title, py, rdate)
            target_year = datetime.now().year
            if py == target_year:
                if rdate:
                    if rdate.month in (11, 12):
                        found.append((title, rdate, link))
                        ev = Event()
                        ev.add('summary', title)
                        ev.add('dtstamp', datetime.utcnow())
                        ev.add('dtstart', rdate)
                        ev.add('description', f"Quelle: {link}")
                        ev['uid'] = f"{abs(hash(link))}@bluray-disc.de"
                        cal.add_component(ev)
                else:
                    found.append((title, None, link))

    outfile = f"bluray_{datetime.now().year}_debug.ics"
    with open(outfile, "wb") as f:
        f.write(cal.to_ical())
    print(f"Fertig. {len(found)} Einträge gefunden. ICS erzeugt: {outfile}")
    for t, d, l in found:
        print("-", t, "|", d, "|", l)

if __name__ == "__main__":
    main()
