#!/usr/bin/env python3
"""Check which of the screen's picks Trading 212 actually lists.

The key is read from the environment and never written anywhere. Set it for a
single command so it does not persist in shell history:

    T212_API_KEY='...' python3 tools/t212_coverage.py

Use a DEMO key. This script only reads, but a live key in a shell on a machine
with a public repo is a bad habit to start.
"""
import json, os, sys, time
from pathlib import Path
import urllib.request, urllib.error

HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
KEY  = os.environ.get("T212_API_KEY")
HERE = Path(__file__).resolve().parent

if not KEY:
    sys.exit("Set T212_API_KEY in the environment. Do not hardcode it, and do "
             "not paste it into a chat: this repo is public.")


def get(path):
    req = urllib.request.Request(HOST + path, headers={"Authorization": KEY})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit("401 from Trading 212: the key was rejected. Check it is "
                     "for the environment named in T212_HOST (demo vs live).")
        if e.code == 429:
            print("  rate limited, waiting 60s", flush=True); time.sleep(60)
            return get(path)
        raise


def main():
    picks_file = HERE.parent / "pipeline" / "r3k_scored.json"
    rows = json.loads(picks_file.read_text())
    best = {}
    for r in rows:
        if r.get("score") is None or not r.get("sector"): continue
        cur = best.get(r["sector"])
        if cur is None or r["score"] > cur["score"]: best[r["sector"]] = r
    picks = sorted(best.values(), key=lambda r: -r["score"])

    print(f"host {HOST}\nfetching the tradeable universe ...", flush=True)
    instruments = get("/api/v0/equity/metadata/instruments")
    print(f"  {len(instruments):,} instruments listed", flush=True)

    # match on ticker; T212 suffixes many US listings, so compare the stem too
    by_tk = {}
    for ins in instruments:
        t = (ins.get("shortName") or ins.get("ticker") or "").upper()
        by_tk.setdefault(t.split("_")[0], ins)

    print(f"\n{'sector':22}{'ticker':8}{'score':>7}   listed?")
    ok = 0
    for p in picks:
        ins = by_tk.get(p["ticker"].upper())
        mark = "yes" if ins else "NO"
        if ins: ok += 1
        extra = f"   {ins.get('name','')[:34]}" if ins else ""
        print(f"{p['sector']:22}{p['ticker']:8}{p['score']:7.1f}   {mark}{extra}")
    print(f"\ntradeable: {ok} of {len(picks)}")
    if ok < len(picks):
        print("The missing names are the point: a paper trade of a portfolio you\n"
              "cannot actually hold tests something other than the strategy.")


if __name__ == "__main__":
    main()
