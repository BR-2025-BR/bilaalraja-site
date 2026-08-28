"""Download the latest 10-Q and 10-K for the universe and extract results commentary.

Raw filings are discarded immediately after extraction: 5,088 documents at a mean
3.4 MB would be ~17 GB, while the extracted slices total ~13 MB. Only the slices
are kept.

Resumable -- checkpoints every 25 companies and skips anything already done.
"""
import json, time, os, sys
from datetime import date
try: os.setsid()
except Exception: pass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests
sys.path.insert(0, str(Path(__file__).parent))
from mdna_extract import extract

HERE = Path(__file__).parent
UA   = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
OUT  = HERE / "mdna_slices.json"
LIMIT = 2600

uni  = pd.read_json(HERE / "r3k_universe.json")
done = json.loads(OUT.read_text()) if OUT.exists() else {}
# Resuming on presence alone means a company already in the file is skipped
# for ever, so a new 10-Q never reaches the page: NVDA sat on its April quarter
# while the panel had moved to July. Re-fetch anyone the panel has a newer
# filing for, as well as anyone missing.
panel = {}
_sc = HERE / "r3k_scored.json"
if _sc.exists():
    panel = {r["ticker"]: r for r in json.loads(_sc.read_text())}

def outdated(rec):
    p = panel.get(rec.ticker)
    if not p or not p.get("filed"):
        return False
    rec_done = done.get(str(int(rec.cik))) or {}
    # Compare against the newest slice of either form. Checking the 10-Q alone
    # makes a company whose latest filing is a 10-K permanently unsatisfiable,
    # so it would be re-fetched on every run for ever.
    seen = [(rec_done.get(k) or {}).get("filed") for k in ("q", "a")]
    have = max([d for d in seen if d], default=None)
    if have and have >= p["filed"]:
        return False
    # Extraction fails outright for some filers. Without this they would be
    # retried on every run, since nothing we fetch can ever satisfy the test.
    return rec_done.get("checked") != str(date.today())

todo = [r for r in uni.itertuples()
        if str(int(r.cik)) not in done or outdated(r)]
print(f"{len(uni)} companies · {len(done)} already done · {len(todo)} to fetch", flush=True)

sess = requests.Session(); sess.headers.update(UA)

def get(url, timeout=90):
    for a in range(3):
        try:
            r = sess.get(url, timeout=timeout)
            if r.status_code == 200: return r
            if r.status_code == 404: return None
            time.sleep(30 if r.status_code == 429 else 3 * (a + 1))
        except Exception:
            time.sleep(3 * (a + 1))
    return None

def one(rec):
    cik = int(rec.cik)
    out = {"ticker": rec.ticker, "name": rec.name, "sector": rec.sector,
           "q": None, "a": None, "checked": str(date.today())}
    time.sleep(0.2)
    sub = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", 45)
    if sub is None: return str(cik), out
    try: r = sub.json()["filings"]["recent"]
    except Exception: return str(cik), out
    picks = {}
    for i, f in enumerate(r["form"]):
        if f in ("10-Q", "10-K") and f not in picks:
            picks[f] = i                       # recent[] is newest-first
        if len(picks) == 2: break
    for form, key in (("10-Q", "q"), ("10-K", "a")):
        i = picks.get(form)
        if i is None: continue
        acc = r["accessionNumber"][i].replace("-", "")
        time.sleep(0.2)
        doc = get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{r['primaryDocument'][i]}")
        if doc is None: continue
        try:
            e = extract(doc.text, LIMIT)       # raw text is dropped when this returns
        except Exception:
            continue
        if e["slice"]:
            out[key] = {"text": e["slice"], "period": r["reportDate"][i],
                        "filed": r["filingDate"][i], "form": form}
    return str(cik), out

n = 0
with ThreadPoolExecutor(max_workers=3) as ex:
    for cik, rec in ex.map(one, todo):
        done[cik] = rec; n += 1
        if n % 25 == 0:
            OUT.write_text(json.dumps(done))
            q = sum(1 for v in done.values() if v.get("q"))
            a = sum(1 for v in done.values() if v.get("a"))
            print(f"  {n}/{len(todo)}  total={len(done)}  with 10-Q={q}  with 10-K={a}", flush=True)
OUT.write_text(json.dumps(done))
q = sum(1 for v in done.values() if v.get("q")); a = sum(1 for v in done.values() if v.get("a"))
print(f"\nDONE {len(done)} companies · quarterly {q} · annual {a} · "
      f"payload {OUT.stat().st_size/1e6:.1f} MB", flush=True)
