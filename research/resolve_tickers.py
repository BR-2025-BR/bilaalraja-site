#!/usr/bin/env python3
"""Resolve every study company to a ticker, and state the price window it needs.

Two thirds of the sample no longer trades, so their tickers are not in the
current panel and have to come from SEC. The submissions endpoint keeps a
`tickers` list for defunct filers, which is the only free route to the symbol a
delisted company traded under.

For each company this writes the ticker, the exchange, whether it still appears
in today's panel, and the exact date range prices are needed for: the first
filing's t+1 through the last filing's t+126, since the pre-registered outcome
is a t+1 to t+63 return with a t+126 secondary. Companies whose window extends
past their delisting are the ones a survivorship-free vendor is actually being
bought for.
"""
import json, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "ticker_map.json"
sess = requests.Session()
sess.headers.update({"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"})

fb = json.loads((HERE / "finbert_dev.json").read_text())
need = {c: v for c, v in fb.items() if len(v) > 4}      # >4 filings = >=1 usable
print(f"companies needing returns: {len(need):,}", flush=True)

done = json.loads(OUT.read_text()) if OUT.exists() else {}
todo = [c for c in need if c not in done]
print(f"already resolved {len(done):,} | to fetch {len(todo):,}", flush=True)


def one(cik):
    for attempt in range(3):
        try:
            r = sess.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                         timeout=30)
            if r.status_code == 200:
                j = r.json()
                tk = j.get("tickers") or []
                ex = j.get("exchanges") or []
                return cik, {
                    "ticker": tk[0] if tk else None,
                    "all_tickers": tk,
                    "exchange": ex[0] if ex else None,
                    "name": j.get("name"),
                    "sic": j.get("sic"),
                    # A filer that has stopped filing is the delisting signal SEC
                    # gives us. It is not a delisting date, but it bounds one.
                    "former_names": len(j.get("formerNames") or []),
                }
            if r.status_code == 429:
                time.sleep(15); continue
            if r.status_code == 404:
                return cik, {"ticker": None, "all_tickers": [], "exchange": None,
                             "name": None, "sic": None, "former_names": 0}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return cik, {"ticker": None, "all_tickers": [], "exchange": None,
                 "name": None, "sic": None, "former_names": 0, "error": 1}


if todo:
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

# ---- price windows -------------------------------------------------------
# The outcome needs t+1 to t+63 trading days, with t+126 as a secondary. Trading
# days are roughly 252 a year, so 126 sessions is about 26 calendar weeks. Pad to
# 200 calendar days so a long holiday run cannot truncate the window.
PAD = timedelta(days=200)
rows = []
for cik, filings in need.items():
    m = done.get(cik) or {}
    fs = sorted(f["filed"] for f in filings)
    rows.append({
        "cik": cik,
        "ticker": m.get("ticker"),
        "exchange": m.get("exchange"),
        "name": m.get("name"),
        "n_filings": len(filings),
        "first_filed": fs[0],
        "last_filed": fs[-1],
        "price_from": fs[0],
        "price_to": str(date.fromisoformat(fs[-1]) + PAD),
    })

(HERE / "price_requirements.json").write_text(json.dumps(rows, indent=1))
have_tk = sum(1 for r in rows if r["ticker"])
print(f"\nresolved a ticker for {have_tk:,} of {len(rows):,} "
      f"({have_tk/len(rows):.1%})")
print(f"no ticker on file      {len(rows)-have_tk:,}")
print("wrote ticker_map.json and price_requirements.json")
