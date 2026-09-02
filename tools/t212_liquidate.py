#!/usr/bin/env python3
"""Sell every holding that is not part of the target basket.

Used to free capital held in other positions before rebuilding. Only sells what
is NOT in the basket, so a partially built basket is never unwound by mistake.

Dry run by default. Pass --execute to actually sell.

    T212_ID='...' T212_SECRET='...' T212_HOST='https://live.trading212.com' \
        python3 tools/t212_liquidate.py --execute
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

ID, SEC = os.environ.get("T212_ID", ""), os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET.")
HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
AUTH = "Basic " + base64.b64encode(f"{ID}:{SEC}".encode()).decode()
HERE = Path(__file__).resolve().parent
EXECUTE = "--execute" in sys.argv


def call(path, payload=None, method="GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    hdr = {"Authorization": AUTH}
    if data:
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(HOST + path, data=data, headers=hdr, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw.strip() else None)
        except urllib.error.HTTPError as e:
            body = e.read(300).decode(errors="replace")
            if e.code == 429 and attempt < 3:
                time.sleep(12 * (attempt + 1))
                continue
            return e.code, body
    return 599, "gave up"


def basket_tickers():
    rows = json.loads((HERE.parent / "pipeline" / "r3k_scored.json").read_text())
    best = {}
    for r in rows:
        if r.get("score") is None or not r.get("sector"):
            continue
        c = best.get(r["sector"])
        if c is None or r["score"] > c["score"]:
            best[r["sector"]] = r
    return {r["ticker"] for r in best.values()}


keep = basket_tickers()
_, port = call("/api/v0/equity/portfolio")
if not port:
    sys.exit("No positions.")

sell = []
for p in port:
    stem = p["ticker"].split("_")[0]
    if stem in keep:
        continue
    sell.append(p)

total = sum(p["quantity"] * p["currentPrice"] for p in sell)
print(f"holdings {len(port)} | in basket {len(port)-len(sell)} | to sell {len(sell)}")
print(f"proceeds at current prices: ~{total:,.2f} (position currency)")
print(f"mode: {'EXECUTE' if EXECUTE else 'dry run'}\n")

placed, failed = [], []
for p in sorted(sell, key=lambda x: -(x["quantity"] * x["currentPrice"])):
    qty = -abs(p["quantity"])          # negative quantity is a sell
    tk = p["ticker"]
    line = f"  SELL {tk:12} {abs(qty):>10.4f}  ~{abs(qty)*p['currentPrice']:>8,.2f}"
    if not EXECUTE:
        print(line + "   (dry run)")
        continue
    code, resp = call("/api/v0/equity/orders/market",
                      {"ticker": tk, "quantity": round(qty, 8)}, "POST")
    if code in (200, 201):
        oid = resp.get("id") if isinstance(resp, dict) else None
        print(f"{line}   OK id={oid}")
        placed.append(tk)
    else:
        detail = resp
        if isinstance(resp, str) and '"detail"' in resp:
            detail = resp.split('"detail":', 1)[1][:110]
        print(f"{line}   FAILED {code} {detail}")
        failed.append((tk, code, str(detail)[:90]))
    time.sleep(2.5)

if EXECUTE:
    print(f"\nsold {len(placed)}, failed {len(failed)}")
    for tk, code, d in failed:
        print(f"  {tk}: {code} {d}")
    print("\nProceeds settle as they fill. Non-US listings queue until their own "
          "exchange opens.")
