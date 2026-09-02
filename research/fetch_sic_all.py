#!/usr/bin/env python3
"""Extend sic_map.json to every company in the corpus.

The first SIC pass covered viable_ciks.json, which turned out to be a work queue
rather than the universe, so roughly 5,500 companies in the corpus have no SIC
code and cannot be tested against the Amendment 6 exclusions. This fills them in,
resuming from whatever sic_map.json already holds.
"""
import glob, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "sic_map.json"
sess = requests.Session()
sess.headers.update({"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"})

done = json.loads(OUT.read_text()) if OUT.exists() else {}
corpus = [Path(p).name.split(".")[0] for p in glob.glob(str(HERE / "corpus/*.json.gz"))]
todo = [c for c in corpus if c not in done]
print(f"corpus {len(corpus):,} | have {len(done):,} | to fetch {len(todo):,}", flush=True)


def one(cik):
    for attempt in range(3):
        try:
            r = sess.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                         timeout=30)
            if r.status_code == 200:
                j = r.json()
                return cik, {"sic": j.get("sic"), "desc": j.get("sicDescription"),
                             "name": j.get("name")}
            if r.status_code == 429:
                time.sleep(15); continue
            if r.status_code == 404:
                return cik, {"sic": None, "desc": "NO_SUBMISSIONS", "name": None}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return cik, {"sic": None, "desc": "FETCH_FAILED", "name": None}


t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as ex:
    for i, (cik, rec) in enumerate(ex.map(one, todo), 1):
        done[cik] = rec
        if i % 400 == 0:
            rate = i / (time.time() - t0)
            print(f"  {i}/{len(todo)}  {rate:.1f}/s  "
                  f"eta {(len(todo)-i)/max(rate,.1)/60:.1f}m", flush=True)
            OUT.write_text(json.dumps(done))

OUT.write_text(json.dumps(done))
print(f"DONE {len(done):,} companies", flush=True)
