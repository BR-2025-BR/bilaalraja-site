#!/usr/bin/env python3
"""How many companies actually filed a 10-K or 10-Q since 2018?

The panel is today's survivors. SEC's quarterly full-index lists every filing
by every filer at the time, so the union across quarters is the universe as it
really was, dead companies included. This only measures the size, so the cost
of doing it properly is known before it is paid.
"""
import re, sys, time
from collections import defaultdict
import requests

UA = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
s = requests.Session(); s.headers.update(UA)

ciks_by_year = defaultdict(set)
allciks = set()
rows = 0
for year in range(2018, 2027):
    for q in (1, 2, 3, 4):
        if year == 2026 and q > 3: continue
        url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx"
        try:
            r = s.get(url, timeout=90)
        except Exception:
            print(f"  {year}Q{q} fetch error", flush=True); continue
        if r.status_code != 200:
            print(f"  {year}Q{q} HTTP {r.status_code}", flush=True); continue
        n = 0
        for line in r.text.splitlines():
            if not (line.startswith("10-K") or line.startswith("10-Q")): continue
            form = line[:12].strip()
            if form not in ("10-K", "10-Q"): continue
            m = re.search(r"\s(\d{1,10})\s+\d{4}-\d{2}-\d{2}", line)
            if not m: continue
            cik = int(m.group(1))
            ciks_by_year[year].add(cik); allciks.add(cik); n += 1
        rows += n
        print(f"  {year}Q{q}  {n:>6,} filings   running distinct CIKs {len(allciks):,}", flush=True)
        time.sleep(0.25)

print(f"\ntotal 10-K/10-Q filings 2018-2026 : {rows:,}")
print(f"distinct filers over the period   : {len(allciks):,}")
print("\nfilers per year:")
for y in sorted(ciks_by_year):
    print(f"  {y}  {len(ciks_by_year[y]):,}")
import json
json.dump(sorted(allciks), open("historical_ciks.json","w"))
print(f"\nwrote historical_ciks.json")
