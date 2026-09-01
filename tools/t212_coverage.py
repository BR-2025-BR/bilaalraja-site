#!/usr/bin/env python3
"""Check which of the screen's picks Trading 212 actually lists.

Trading 212 issues an API key ID and a separate secret, and authenticates with
HTTP Basic over the pair. Credentials are read from the environment and never
written anywhere:

    T212_ID='...' T212_SECRET='...' python3 tools/t212_coverage.py

A leading space on that line keeps both out of your shell history in zsh.
Use a demo key. This script only reads, but the habit is the point.
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

ID  = os.environ.get("T212_ID", "")
SEC = os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET in the environment. Do not hardcode "
             "them: this repo is public.")

HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
AUTH = "Basic " + base64.b64encode(f"{ID}:{SEC}".encode()).decode()
HERE = Path(__file__).resolve().parent


def get(path, tries=4):
    req = urllib.request.Request(HOST + path, headers={"Authorization": AUTH})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                sys.exit("401: credentials rejected. Check the pair matches the "
                         f"environment in T212_HOST ({HOST}).")
            if e.code == 429 and attempt < tries - 1:
                wait = 30 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
    raise SystemExit("gave up after repeated rate limiting")


def picks():
    rows = json.loads((HERE.parent / "pipeline" / "r3k_scored.json").read_text())
    best = {}
    for r in rows:
        if r.get("score") is None or not r.get("sector"):
            continue
        cur = best.get(r["sector"])
        if cur is None or r["score"] > cur["score"]:
            best[r["sector"]] = r
    return sorted(best.values(), key=lambda r: -r["score"])


def main():
    sel = picks()
    print(f"host {HOST}")
    cash = get("/api/v0/equity/account/cash")
    print(f"account: {cash.get('total', 0):,.2f} total, "
          f"{cash.get('free', 0):,.2f} free\n")

    print("fetching tradeable universe ...", flush=True)
    ins = get("/api/v0/equity/metadata/instruments")
    print(f"  {len(ins):,} instruments listed")

    # Trading 212 suffixes many tickers (AAPL_US_EQ); index on the stem, and
    # prefer US listings so a European dual-listing does not mask a real match.
    by_tk = {}
    for i in ins:
        raw = (i.get("ticker") or "").upper()
        stem = (i.get("shortName") or raw.split("_")[0]).upper()
        prev = by_tk.get(stem)
        if prev is None or (i.get("currencyCode") == "USD"
                            and prev.get("currencyCode") != "USD"):
            by_tk[stem] = i

    print(f"\n{'sector':24}{'ticker':8}{'mcap $m':>10}  listed as")
    print("-" * 64)
    ok, missing = 0, []
    for p in sel:
        m = by_tk.get(p["ticker"].upper())
        ok += bool(m)
        if not m:
            missing.append(p)
        mc = p.get("mcap") or 0
        label = (m.get("ticker") if m else "NOT LISTED")
        print(f"{p['sector'][:23]:24}{p['ticker']:8}{mc*1000:>10,.0f}  {label}")

    print(f"\ntradeable: {ok} of {len(sel)}")
    if missing:
        print("\nnot available on Trading 212:")
        for p in missing:
            print(f"  {p['ticker']:8} {p['name'][:40]:42} {p['sector']}")
        print("\nA paper trade of a portfolio you cannot hold measures the "
              "broker's inventory, not the strategy.")


if __name__ == "__main__":
    main()
