#!/usr/bin/env python3
"""Fetch SIC codes for the viable universe so non-operating filers can be named.

The corpus records how many filings a company listed and how many yielded an
MD&A block, but not what kind of entity it is. Asset-backed trusts file under
Regulation AB and blank-cheque shells file near-empty 10-Ks; neither contains an
MD&A section, and neither has tradeable equity. Separating those from genuine
extraction failures needs the SIC code, which only the submissions endpoint has.
"""
import json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "sic_map.json"
UA = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}

sess = requests.Session()
sess.headers.update(UA)

ciks = json.loads((HERE / "viable_ciks.json").read_text())
done = json.loads(OUT.read_text()) if OUT.exists() else {}
todo = [c for c in ciks if str(c) not in done]
print(f"universe {len(ciks):,} | have {len(done):,} | to fetch {len(todo):,}", flush=True)


def one(cik):
    for attempt in range(3):
        try:
            r = sess.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                         timeout=30)
            if r.status_code == 200:
                j = r.json()
                return str(cik), {"sic": j.get("sic"),
                                  "desc": j.get("sicDescription"),
                                  "name": j.get("name")}
            if r.status_code == 429:
                time.sleep(15)
                continue
            if r.status_code == 404:
                return str(cik), {"sic": None, "desc": None, "name": None}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return str(cik), {"sic": None, "desc": "FETCH_FAILED", "name": None}


t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as ex:      # SEC tolerates ~10/s; stay under
    for i, (cik, rec) in enumerate(ex.map(one, todo), 1):
        done[cik] = rec
        if i % 250 == 0:
            rate = i / (time.time() - t0)
            print(f"  {i}/{len(todo)}  {rate:.1f}/s  "
                  f"eta {(len(todo)-i)/max(rate,0.1)/60:.1f}m", flush=True)
            OUT.write_text(json.dumps(done))

OUT.write_text(json.dumps(done))
print(f"DONE {len(done):,} companies -> {OUT.name}")
