#!/usr/bin/env python3
"""Place the equal-weight basket as market orders on Trading 212.

Sizing has two corrections the naive version gets wrong:

  * the account is GBP and the instruments are USD, so the per-name budget must
    be converted or every order comes in ~26% light;
  * Trading 212 exposes no quote endpoint, so quantities are sized off the
    panel's price snapshot, which is days old in places. A market order fills at
    the market, so the basket is sized against a reduced budget and whatever is
    left stays as cash.

Quantities take at most two decimal places: the API rejects anything finer with
"invalid quantity precision". Existing holdings are netted off the target, so
re-running tops up rather than doubling the position.

Dry run by default. Pass --execute to actually submit.

    T212_ID='...' T212_SECRET='...' python3 tools/t212_execute.py --execute
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
LIMIT = int(os.environ.get("T212_LIMIT", "0"))   # 0 = all; 1 = probe one order
BUDGET_USE = 0.92
FX_GBP_USD = float(os.environ.get("T212_FX", "1.3545"))


def call(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    hdr = {"Authorization": AUTH}
    if data:
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(HOST + path, data=data, headers=hdr,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            return r.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode(errors="replace")


def basket():
    rows = json.loads((HERE.parent / "pipeline" / "r3k_scored.json").read_text())
    best = {}
    for r in rows:
        if r.get("score") is None or not r.get("sector"):
            continue
        c = best.get(r["sector"])
        if c is None or r["score"] > c["score"]:
            best[r["sector"]] = r
    return sorted(best.values(), key=lambda r: -r["score"])


picks = basket()
_, cash = call("/api/v0/equity/account/cash")
free = float(cash.get("free") or 0)

budget_gbp = free * BUDGET_USE
per_gbp = budget_gbp / len(picks)
per_usd = per_gbp * FX_GBP_USD

print(f"free {free:,.2f} GBP   using {BUDGET_USE:.0%} = {budget_gbp:,.2f} GBP")
print(f"per name {per_gbp:,.2f} GBP = {per_usd:,.2f} USD at {FX_GBP_USD}")
print(f"mode: {'EXECUTE' if EXECUTE else 'dry run'}"
      f"{f' (first {LIMIT} only)' if LIMIT else ''}\n")

_, port = call("/api/v0/equity/portfolio")
held = {h["ticker"]: float(h.get("quantity") or 0) for h in (port or [])}
if held:
    print("already held: " + ", ".join(f"{k} {v:g}" for k, v in held.items()) + "\n")

orders = []
for p in picks:
    t = p["ticker"] + "_US_EQ"
    target = per_usd / p["price"]
    qty = round(target - held.get(t, 0.0), 2)   # 2dp is the API maximum
    if qty <= 0:
        print(f"  {t:12} already at or above target, skipping")
        continue
    orders.append({"ticker": t, "quantity": qty,
                   "ref": p["price"], "sector": p["sector"]})

todo = orders[:LIMIT] if LIMIT else orders
placed, failed = [], []
for o in todo:
    line = f"  {o['ticker']:12} qty {o['quantity']:>10.4f}  ~${o['quantity']*o['ref']:,.2f}"
    if not EXECUTE:
        print(line + "   (dry run)")
        continue
    code, resp = call("/api/v0/equity/orders/market",
                      {"ticker": o["ticker"], "quantity": o["quantity"]})
    if code in (200, 201):
        oid = resp.get("id") if isinstance(resp, dict) else None
        print(f"{line}   OK  id={oid}")
        placed.append({**o, "id": oid})
    else:
        print(f"{line}   FAILED {code} {str(resp)[:150]}")
        failed.append({**o, "code": code, "error": str(resp)[:300]})
        if len(failed) >= 2 and not placed:
            print("\nTwo failures and nothing placed - stopping rather than "
                  "firing the rest at the same wall.")
            break
    time.sleep(2.0)   # the orders endpoint is rate limited

if EXECUTE:
    out = HERE.parent / "pipeline" / "t212_orders.json"
    out.write_text(json.dumps({"placed": placed, "failed": failed}, indent=1))
    print(f"\nplaced {len(placed)}, failed {len(failed)} -> {out.name}")
