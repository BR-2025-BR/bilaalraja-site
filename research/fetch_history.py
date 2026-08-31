#!/usr/bin/env python3
"""Fetch historical MD&A text and score its tone. Long-running and resumable.

Around 88,000 documents across the panel back to 2018. The text itself is not
kept: it would run to gigabytes, and the pre-registration fixes the signal, so
only the scores and word counts are needed. Storing pos/neg counts rather than
polarity alone leaves room for the specification variants that were named in
advance.

Resumes by company. A company is done when its record carries the same filing
count the submissions index reports, so an interrupted run picks up cleanly.
"""
import json, os, sys, time
from datetime import date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try: os.setsid()                       # survive the launching shell
except Exception: pass

import pandas as pd, requests
import pysentiment2 as ps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
import mdna_extract

UA    = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
OUT   = HERE / "tone_history.json"
SINCE = "2018-01-01"
FORMS = ("10-K", "10-Q")
MIN_WORDS = 500                        # below this, treat as an extraction failure

LM = ps.LM()
sess = requests.Session(); sess.headers.update(UA)
done = json.loads(OUT.read_text()) if OUT.exists() else {}
THROTTLED = [0]


def get(url, timeout=45):
    for a in range(3):
        try:
            r = sess.get(url, timeout=timeout)
            if r.status_code == 200: return r
            if r.status_code == 404: return None
            if r.status_code == 429:
                THROTTLED[0] += 1; time.sleep(20)
            else:
                time.sleep(2 * (a + 1))
        except Exception:
            time.sleep(2 * (a + 1))
    return None


def filings_for(cik):
    """Every 10-K/10-Q since SINCE, including those paged out of `recent`."""
    r = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", 30)
    if r is None: return []
    try: j = r.json()
    except Exception: return []
    out, blocks = [], [j["filings"]["recent"]]
    for extra in j["filings"].get("files", []):
        if (extra.get("filingTo") or "") < SINCE:
            continue                   # entirely before the window
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


def score(cik, f):
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['acc']}/{f['doc']}"
    time.sleep(0.30)
    r = get(url)
    if r is None: return None
    try:
        txt = mdna_extract.to_text(r.text)
        block = mdna_extract.mdna_block(txt)
    except Exception:
        return None
    if not block: return None
    words = block.split()
    if len(words) < MIN_WORDS: return None
    s = LM.get_score(LM.tokenize(block))
    # pysentiment2 hands back numpy ints, which json refuses. Cast at the
    # boundary rather than discovering it at the first checkpoint.
    pos, neg = int(s.get("Positive", 0)), int(s.get("Negative", 0))
    if pos + neg == 0: return None
    return {"form": f["form"], "filed": f["filed"], "period": f["period"],
            "pos": pos, "neg": neg, "words": len(words),
            "tone": round((pos - neg) / (pos + neg), 6)}


def one(rec):
    cik, tic = int(rec.cik), rec.ticker
    key = str(cik)
    prev = done.get(key)
    fl = filings_for(cik)
    if prev and prev.get("n_filings") == len(fl):
        return key, prev                      # already complete
    scored = []
    for f in fl:
        s = score(cik, f)
        if s: scored.append(s)
    return key, {"ticker": tic, "n_filings": len(fl),
                 "n_scored": len(scored), "filings": scored}


def main():
    uni = pd.read_json(HERE.parent / "pipeline" / "r3k_universe.json")
    todo = list(uni.itertuples())
    if "--limit" in sys.argv:
        todo = todo[:int(sys.argv[sys.argv.index("--limit") + 1])]
    print(f"{len(todo)} companies, 10-K/10-Q since {SINCE}, {len(done)} cached",
          flush=True)
    n = 0
    with ThreadPoolExecutor(max_workers=3) as ex:
        for key, rec in ex.map(one, todo):
            if rec: done[key] = rec
            n += 1
            if n % 25 == 0:
                OUT.write_text(json.dumps(done))
                tot = sum(v.get("n_scored", 0) for v in done.values())
                print(f"  {n}/{len(todo)}  companies={len(done)}  filings scored={tot}"
                      + (f"  [throttled {THROTTLED[0]}x]" if THROTTLED[0] else ""),
                      flush=True)
    OUT.write_text(json.dumps(done))
    tot = sum(v.get("n_scored", 0) for v in done.values())
    print(f"DONE {len(done)} companies, {tot} filings scored")


if __name__ == "__main__":
    main()
