#!/usr/bin/env python3
"""Count 10-K and 10-Q filings per company, to skip those that cannot contribute.

The pre-registered signal needs four prior filings *of the same form*, so a
company needs at least five 10-Qs or five 10-Ks in the window to produce even
one observation. Anything below that is fetched, scored, and then discarded at
analysis time. Skipping them up front changes nothing about the sample and
saves a large share of the remaining work.
"""
import json, re, time
from collections import defaultdict
import requests

UA = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
s = requests.Session(); s.headers.update(UA)

count = defaultdict(lambda: {"10-K": 0, "10-Q": 0})
for year in range(2018, 2027):
    for q in (1, 2, 3, 4):
        if year == 2026 and q > 3: continue
        u = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx"
        try: r = s.get(u, timeout=90)
        except Exception: continue
        if r.status_code != 200: continue
        for line in r.text.splitlines():
            if not (line.startswith("10-K") or line.startswith("10-Q")): continue
            form = line[:12].strip()
            if form not in ("10-K", "10-Q"): continue
            m = re.search(r"\s(\d{1,10})\s+\d{4}-\d{2}-\d{2}", line)
            if m: count[int(m.group(1))][form] += 1
        time.sleep(0.25)
    print(f"  {year} done, {len(count):,} CIKs so far", flush=True)

viable = {c for c, d in count.items() if max(d["10-K"], d["10-Q"]) >= 5}
print(f"\nCIKs in the index      : {len(count):,}")
print(f"can yield >=1 observation: {len(viable):,}")
print(f"cannot, will be skipped  : {len(count)-len(viable):,}")

done = {int(k) for k in json.load(open("tone_history.json"))}
todo = sorted(viable - done)
print(f"already fetched          : {len(done):,}")
print(f"REMAINING TO FETCH       : {len(todo):,}  (was 6,646)")
json.dump(todo, open("viable_ciks.json", "w"))
print("wrote viable_ciks.json")
