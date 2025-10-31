import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LinkInspector/1.0)"}
MONTH_PAGES = [
    "https://bluray-disc.de/blu-ray-filme/neuerscheinungen?ansicht=detail&id=1975-11&page=0",
    "https://bluray-disc.de/blu-ray-filme/neuerscheinungen?id=1992-12&page=1"
]

seen = set()
for url in MONTH_PAGES:
    print('\n--- PAGE:', url)
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    anchors = soup.find_all('a')
    for a in anchors:
        href = a.get('href')
        if not href:
            continue
        if 'blu-ray' in href or 'bluray' in href or 'blu_ray' in href:
            seen.add(href)
    # print first 30 found on this page
    i = 0
    for h in list(seen)[:30]:
        print(h)
    print('TOTAL unique (so far):', len(seen))

print('\nFULL LIST:')
for h in sorted(seen):
    print(h)
