import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from urllib.parse import urljoin

BASE = "https://bluray-disc.de"
MONTH_PAGES = [
    "https://bluray-disc.de/blu-ray-filme/neuerscheinungen?ansicht=detail&id=1975-11&page=0",
    "https://bluray-disc.de/blu-ray-filme/neuerscheinungen?id=1992-12&page=1"
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Collector/1.0)"}
MAX_LINKS = 40
REQUEST_TIMEOUT = 8

month_dict = {
    "Januar":"01","Februar":"02","März":"03","April":"04","Mai":"05","Juni":"06",
    "Juli":"07","August":"08","September":"09","Oktober":"10","November":"11","Dezember":"12"
}

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text


def extract_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    for a in soup.select('a'):
        href = a.get('href')
        if not href:
            continue
        full = urljoin(BASE, href.split('?')[0].split('#')[0])
        if re.search(r"/blu-ray-filme/\d+", full) or re.search(r"/blu-ray-news/filme/\d+", full):
            links.add(full)
    return list(links)


def parse_meta(html):
    soup = BeautifulSoup(html, 'html.parser')
    title = None
    h1 = soup.find(['h1','h2'])
    if h1:
        title = h1.get_text(strip=True)
    text = soup.get_text(' ', strip=True)
    py = None
    m = re.search(r"Produktion[:\s]*([0-9]{4})", text)
    if m:
        py = int(m.group(1))
    else:
        m2 = re.search(r"\(([0-9]{4})\)", text)
        if m2:
            py = int(m2.group(1))
    # find date
    rdate = None
    mdate = re.search(r"([0-3]?\d\.[01]?\d\.[0-9]{4})", text)
    if mdate:
        s = mdate.group(1)
        s = re.sub(r"\.{2,}", '.', s)
        try:
            rdate = datetime.strptime(s, "%d.%m.%Y").date()
        except Exception:
            pass
    return title, py, rdate


found = []
visited = set()
for page in MONTH_PAGES:
    print('PAGE:', page)
    try:
        html = fetch(page)
    except Exception as e:
        print('ERR', e)
        continue
    links = extract_links(html)
    print('links found:', len(links))
    for link in links[:MAX_LINKS]:
        if link in visited:
            continue
        visited.add(link)
        try:
            d = requests.get(link, headers=HEADERS, timeout=REQUEST_TIMEOUT).text
        except Exception as e:
            print('ERR fetch', link, e)
            continue
        title, py, rdate = parse_meta(d)
        target_year = datetime.now().year
        if py == target_year:
            found.append((title, py, rdate, link))

print(f'\n=== Found items with production_year == {datetime.now().year} ===')
for t, py, rd, l in found:
    print('-', t, '|', py, '|', rd, '|', l)
print('TOTAL:', len(found))
