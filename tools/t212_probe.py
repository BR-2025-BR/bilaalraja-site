#!/usr/bin/env python3
"""Work out which credential form Trading 212 accepts, then report coverage.

Trading 212 authenticates with a SINGLE key in the Authorization header. If you
were handed something that looks like an id and a secret, one of them is
probably the whole key and the other belongs to a different service. This tries
the plausible forms and tells you which one answered.

    T212_A='first-value' T212_B='second-value' python3 tools/t212_probe.py

A leading space keeps both out of your shell history in zsh, and in bash with
HIST_IGNORE_SPACE set. Nothing is written to disk.
"""
import json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

A = os.environ.get("T212_A", "")
B = os.environ.get("T212_B", "")
if not A:
    sys.exit("Set T212_A (and optionally T212_B) in the environment.")

FORMS = [(n, v) for n, v in
         [("A alone", A), ("B alone", B), ("A+B joined", A + B if B else "")] if v]
HOSTS = ["https://demo.trading212.com", "https://live.trading212.com"]


def call(host, key, path):
    req = urllib.request.Request(host + path, headers={"Authorization": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)


print("probing ...\n")
good = None
for host in HOSTS:
    for name, key in FORMS:
        code, _ = call(host, key, "/api/v0/equity/account/cash")
        env = "demo" if "demo" in host else "LIVE"
        print(f"  {env:5}  {name:12}  HTTP {code}")
        if code == 200 and good is None:
            good = (host, key, name, env)
        if code == 429:
            print("        rate limited; pausing 35s")
            time.sleep(35)

if not good:
    sys.exit("\nNothing authenticated. Regenerate the key in the Trading 212 app "
             "(Settings -> API) and check it was created for the account you "
             "expect. 401 everywhere means the key is wrong, not missing.")

host, key, name, env = good
print(f"\nauthenticated: {name} against {env}")
if env == "LIVE":
    print("NOTE: that is the live account, not demo. Read-only here, but know it.")

print("\nfetching tradeable universe ...")
code, instruments = call(host, key, "/api/v0/equity/metadata/instruments")
if code != 200:
    sys.exit(f"instruments returned HTTP {code}")
print(f"  {len(instruments):,} instruments listed")

rows = json.loads((Path(__file__).resolve().parent.parent /
                   "pipeline" / "r3k_scored.json").read_text())
best = {}
for r in rows:
    if r.get("score") is None or not r.get("sector"):
        continue
    cur = best.get(r["sector"])
    if cur is None or r["score"] > cur["score"]:
        best[r["sector"]] = r
picks = sorted(best.values(), key=lambda r: -r["score"])

by_tk = {}
for ins in instruments:
    t = (ins.get("shortName") or ins.get("ticker") or "").upper()
    by_tk.setdefault(t.split("_")[0], ins)

print(f"\n{'sector':22}{'ticker':8}{'score':>7}   listed?")
ok = 0
for p in picks:
    ins = by_tk.get(p["ticker"].upper())
    ok += bool(ins)
    tail = f"   {ins.get('name','')[:32]}" if ins else ""
    print(f"{p['sector']:22}{p['ticker']:8}{p['score']:7.1f}   "
          f"{'yes' if ins else 'NO '}{tail}")
print(f"\ntradeable: {ok} of {len(picks)}")
