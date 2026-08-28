#!/usr/bin/env python3
"""Open-market insider buying and selling, from Forms 4 filed in the last 90 days.

Why filter by transaction code: most Form 4 activity is compensation, not
conviction. Codes A (grant/award), M (option exercise) and F (shares withheld
to pay tax) are the machinery of being paid in stock and say nothing about what
an insider thinks. Counting them makes every company look like heavy insider
selling, because executives routinely sell a slice of each vest.

Only P (open-market purchase) and S (open-market sale) reflect a decision to put
money in or take it out, so only those are counted.

Resumable, and re-fetches a company whose newest Form 4 is later than the one
already recorded.
"""
import json, os, sys, time
# Detach from the launching shell: this runs for hours and must not die with it.
try: os.setsid()
except Exception: pass
from datetime import date, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import pandas as pd, requests

HERE = Path(__file__).resolve().parent
UA   = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
OUT  = HERE / "form4.json"
DAYS = 90
CUT  = str(date.today() - timedelta(days=DAYS))

uni  = pd.read_json(HERE / "r3k_universe.json")
done = json.loads(OUT.read_text()) if OUT.exists() else {}

sess = requests.Session(); sess.headers.update(UA)

def get(url, timeout=45):
    for a in range(3):
        try:
            r = sess.get(url, timeout=timeout)
            if r.status_code == 200: return r
            if r.status_code == 404: return None
            time.sleep(20 if r.status_code == 429 else 2 * (a + 1))
        except Exception:
            time.sleep(2 * (a + 1))
    return None

def raw_xml_path(doc):
    """Form 4 primaryDocument is often an XSL-rendered wrapper; the machine
    readable XML sits at the same path with the xslF345X0n/ prefix removed."""
    if "/" in doc and doc.split("/")[0].lower().startswith("xsl"):
        return doc.split("/", 1)[1]
    return doc

def txt(node, tag):
    el = node.find(tag)
    if el is None: return None
    v = el.find("value")
    return (v.text if v is not None else el.text)

def parse(xml):
    """Return (bought_value, sold_value, n_buyers, n_sellers) for one Form 4."""
    try: root = ET.fromstring(xml)
    except Exception: return None
    owner = root.find(".//reportingOwner/reportingOwnerId/rptOwnerName")
    who = owner.text.strip() if owner is not None and owner.text else "?"
    buy = sell = 0.0
    for t in root.findall(".//nonDerivativeTransaction"):
        code = txt(t, "transactionCoding/transactionCode")
        if code not in ("P", "S"): continue
        try:
            sh = float(txt(t, "transactionAmounts/transactionShares") or 0)
            px = float(txt(t, "transactionAmounts/transactionPricePerShare") or 0)
        except (TypeError, ValueError):
            continue
        val = sh * px
        if val <= 0: continue
        if code == "P": buy += val
        else:          sell += val
    return who, buy, sell

def one(rec):
    cik = int(rec.cik)
    key = str(cik)
    sub = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", 30)
    if sub is None:
        return key, done.get(key)
    try: r = sub.json()["filings"]["recent"]
    except Exception:
        return key, done.get(key)
    idx = [i for i, (f, d) in enumerate(zip(r["form"], r["filingDate"]))
           if f == "4" and d >= CUT]
    # 6 workers at ~0.18s each sits near SEC's 10 req/s ceiling; get() backs off
    # on a 429 if that estimate is wrong.
    newest = r["filingDate"][idx[0]] if idx else None
    prev = done.get(key)
    if prev and prev.get("newest") == newest:
        return key, prev                      # nothing new since last time

    buyers, sellers = set(), set()
    buy = sell = 0.0
    for i in idx[:60]:                        # a few filers run to hundreds
        acc = r["accessionNumber"][i].replace("-", "")
        doc = raw_xml_path(r["primaryDocument"][i])
        time.sleep(0.18)
        d = get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}")
        if d is None: continue
        p = parse(d.content)
        if not p: continue
        who, b, s = p
        buy += b; sell += s
        if b > 0: buyers.add(who)
        if s > 0: sellers.add(who)
    return key, {"ticker": rec.ticker, "newest": newest, "n_filings": len(idx),
                 "bought": round(buy, 2), "sold": round(sell, 2),
                 "net": round(buy - sell, 2),
                 "buyers": len(buyers), "sellers": len(sellers),
                 "window_days": DAYS, "asof": str(date.today())}

todo = list(uni.itertuples())
print(f"{len(todo)} companies · Form 4s filed since {CUT} · {len(done)} cached",
      flush=True)
n = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    for key, rec in ex.map(one, todo):
        if rec: done[key] = rec
        n += 1
        if n % 100 == 0:
            OUT.write_text(json.dumps(done))
            withbuy = sum(1 for v in done.values() if v and v.get("bought", 0) > 0)
            print(f"  {n}/{len(todo)}  cached={len(done)}  with buying={withbuy}",
                  flush=True)
OUT.write_text(json.dumps(done))
wb = sum(1 for v in done.values() if v and v.get("bought", 0) > 0)
ws = sum(1 for v in done.values() if v and v.get("sold", 0) > 0)
print(f"DONE {len(done)} companies · with open-market buying {wb} · selling {ws}")
