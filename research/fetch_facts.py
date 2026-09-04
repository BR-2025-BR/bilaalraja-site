#!/usr/bin/env python3
"""Fetch companyfacts for the whole study universe, not just today's survivors.

Sharadar's fundamentals are outside this subscription, so the composite still
has to be built from SEC XBRL. The cache holds 4,110 of 8,707 companies, and the
missing 4,597 are disproportionately the ones that delisted - which is precisely
the population a survivorship-free backtest cannot do without.
"""
import json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
CACHE = Path('/Users/bilaa/Downloads/pitquant/data/cache/edgar')
CACHE.mkdir(parents=True, exist_ok=True)
sess = requests.Session()
sess.headers.update({"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"})

uni = [int(c) for c in json.loads((HERE / 'universe_final.json').read_text())]
have = {int(re.search(r'companyfacts_(\d+)', p.name).group(1))
        for p in CACHE.glob('companyfacts_*.json')}
todo = [c for c in uni if c not in have]
print(f"universe {len(uni):,} | cached {len(uni)&len(have) and len(set(uni)&have):,} | "
      f"to fetch {len(todo):,}", flush=True)

def one(cik):
    dest = CACHE / f"companyfacts_{cik:010d}.json"
    if dest.exists():
        return cik, "cached"
    for attempt in range(4):
        try:
            r = sess.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
                         timeout=60)
            if r.status_code == 200:
                dest.write_bytes(r.content)
                return cik, "ok"
            if r.status_code == 429:
                time.sleep(12); continue
            if r.status_code == 404:
                dest.write_text('{"facts":{}}')     # mark as genuinely absent
                return cik, "404"
        except Exception:
            time.sleep(2 * (attempt + 1))
    return cik, "fail"

t0 = time.time(); n = 0; bad = 0
with ThreadPoolExecutor(max_workers=4) as ex:
    for cik, st in ex.map(one, todo):
        n += 1
        bad += st in ("fail",)
        if n % 250 == 0:
            r = n / (time.time() - t0)
            print(f"  {n}/{len(todo)}  {r:.1f}/s  eta {(len(todo)-n)/max(r,.1)/60:.0f}m  "
                  f"failed {bad}", flush=True)
print(f"DONE {n:,} fetched, {bad} failed, {(time.time()-t0)/60:.0f} min", flush=True)
