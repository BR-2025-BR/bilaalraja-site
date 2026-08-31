#!/usr/bin/env python3
"""Phase 1: fetch MD&A text and keep it. Network-bound, resumable.

The previous fetcher stored only scores, which is precisely why changing the
model cost a complete re-download. This one keeps the extracted text, gzipped,
one file per company, so any future scorer is an inference job rather than
another 35 hours of fetching.

Loughran-McDonald is computed here because it is nearly free once the text is
in hand. FinBERT runs separately in phase 2, batched on the GPU: interleaving
GPU inference with network waits would idle both.
"""
import gzip, json, os, sys, time
from datetime import date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try: os.setsid()
except Exception: pass

import pandas as pd, requests
import pysentiment2 as ps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
import mdna_extract

UA    = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
OUT   = HERE / "corpus"
SINCE = "2018-01-01"
FORMS = ("10-K", "10-Q")
MIN_WORDS = 500

OUT.mkdir(exist_ok=True)
LM = ps.LM()
sess = requests.Session(); sess.headers.update(UA)
THROTTLED = [0]


def get(url, timeout=45):
    for a in range(3):
        try:
            r = sess.get(url, timeout=timeout)
            if r.status_code == 200: return r
            if r.status_code == 404: return None
            if r.status_code == 429:
                THROTTLED[0] += 1; time.sleep(20)
            else: time.sleep(2 * (a + 1))
        except Exception:
            time.sleep(2 * (a + 1))
    return None


def filings_for(cik):
    r = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", 30)
    if r is None: return []
    try: j = r.json()
    except Exception: return []
    out, blocks = [], [j["filings"]["recent"]]
    for extra in j["filings"].get("files", []):
        if (extra.get("filingTo") or "") < SINCE: continue
        rr = get(f"https://data.sec.gov/submissions/{extra['name']}", 30)
        if rr is not None:
            try: blocks.append(rr.json())
            except Exception: pass
    for b in blocks:
        for form, filed, period, acc, doc in zip(
                b.get("form", []), b.get("filingDate", []), b.get("reportDate", []),
                b.get("accessionNumber", []), b.get("primaryDocument", [])):
            if form in FORMS and filed >= SINCE:
                out.append({"form": form, "filed": filed, "period": period,
                            "acc": acc.replace("-", ""), "doc": doc})
    return out


def one_filing(cik, f):
    doc = f["doc"]
    # SEC links the iXBRL viewer, which is a JavaScript shell, not the filing
    if "/ix?doc=" in doc: doc = doc.split("/ix?doc=", 1)[1]
    r = get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['acc']}/{doc}")
    if r is None: return None
    try:
        block = mdna_extract.mdna_block(mdna_extract.to_text(r.text))
    except Exception:
        return None
    if not block: return None
    words = block.split()
    if len(words) < MIN_WORDS: return None
    s = LM.get_score(LM.tokenize(block))
    pos, neg = int(s.get("Positive", 0)), int(s.get("Negative", 0))
    return {"form": f["form"], "filed": f["filed"], "period": f["period"],
            "words": len(words), "text": block,
            "lm_pos": pos, "lm_neg": neg,
            "lm_tone": round((pos - neg) / (pos + neg), 6) if pos + neg else None}


def one(cik):
    cik = int(cik)
    path = OUT / f"{cik}.json.gz"
    fl = filings_for(cik)
    if path.exists():
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                prev = json.load(fh)
            if prev.get("n_filings") == len(fl): return cik, prev.get("n_scored", 0)
        except Exception:
            pass                                   # corrupt or partial: redo it
    scored = [x for x in (one_filing(cik, f) for f in fl) if x]
    rec = {"cik": cik, "n_filings": len(fl), "n_scored": len(scored),
           "fetched": str(date.today()), "filings": scored}
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(rec, fh)
    tmp.replace(path)                              # atomic: no half-written files
    return cik, len(scored)


def main():
    viable = set(json.loads((HERE / "viable_ciks.json").read_text()))
    prior  = {int(k) for k in json.loads((HERE / "tone_history.json").read_text())}
    todo = sorted(viable | prior)
    have = {int(p.stem.split(".")[0]) for p in OUT.glob("*.json.gz")}
    todo = [c for c in todo if c not in have]
    print(f"universe {len(viable | prior):,} | already stored {len(have):,} | "
          f"to fetch {len(todo):,}", flush=True)
    n = tot = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        for cik, k in ex.map(one, todo):
            n += 1; tot += k
            if n % 25 == 0:
                rate = n / (time.time() - t0) * 3600
                print(f"  {n}/{len(todo)}  filings stored={tot:,}  "
                      f"{rate:.0f}/hr  eta {(len(todo)-n)/max(rate,1):.1f}h"
                      + (f"  [throttled {THROTTLED[0]}x]" if THROTTLED[0] else ""),
                      flush=True)
    print(f"PHASE 1 DONE  {n} companies, {tot:,} filings stored")


if __name__ == "__main__":
    main()
