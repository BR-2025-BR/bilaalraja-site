#!/usr/bin/env python3
"""Build the equal-weight sector basket on a Trading 212 account.

This supersedes t212_execute.py, which sized orders from the panel's stored
price snapshot. That snapshot was days old in places, so a name whose price had
risen since bought more than intended and the basket was never equal weight:
INR's reference was $14.47 against a $15.76 fill, 9% over, and the spread across
the twelve was 12.1% at cost before the market moved at all.

Trading 212 exposes no quote endpoint, so there is still no live price before
the first trade. The fix is to place the basket and then rebalance once fills
are known, which t212_rebalance.py does from currentPrice. Sizing here therefore
spends only part of the free cash, leaving room for a stale price to have run up
without bouncing the tail of the basket on insufficient funds.

    T212_ID='...' T212_SECRET='...' python3 tools/t212_build_basket.py --execute
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

ID, SEC = os.environ.get("T212_ID", ""), os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET. Trading 212 needs both: the key ID "
             "alone returns 401.")

HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
AUTH = "Basic " + base64.b64encode(f"{ID}:{SEC}".encode()).decode()
HERE = Path(__file__).resolve().parent
EXECUTE = "--execute" in sys.argv

BUDGET_USE = 0.92                                  # headroom for stale prices
FX_GBP_USD = float(os.environ.get("T212_FX", "1.3545"))


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
            if e.code == 401:
                sys.exit("401: credentials rejected. Check the id and secret are "
                         f"both from the same key, and match {HOST}.")
            if e.code == 429 and attempt < 3:
                time.sleep(12 * (attempt + 1))
                continue
            return e.code, body
    return 599, "gave up"


def basket():
    """Top scorer in each sector, from the current panel."""
    rows = json.loads((HERE.parent / "pipeline" / "r3k_scored.json").read_text())
    best = {}
    for r in rows:
        if r.get("score") is None or not r.get("sector"):
            continue
        cur = best.get(r["sector"])
        if cur is None or r["score"] > cur["score"]:
            best[r["sector"]] = r
    return sorted(best.values(), key=lambda r: -r["score"])


picks = sorted(basket(), key=lambda r: -r["score"])
_, info = call("/api/v0/equity/account/info")
_, cash = call("/api/v0/equity/account/cash")
_, held = call("/api/v0/equity/portfolio")

ccy = (info or {}).get("currencyCode", "?")
free = float((cash or {}).get("free") or 0)
have = {h["ticker"]: float(h.get("quantity") or 0) for h in (held or [])}

print(f"account {ccy}  free {free:,.2f}  existing positions {len(have)}")
if have:
    print("  " + ", ".join(f"{k.replace('_US_EQ','')} {v:g}" for k, v in have.items()))

budget = free * BUDGET_USE
per_usd = budget / len(picks) * FX_GBP_USD
print(f"budget {budget:,.2f} {ccy} ({BUDGET_USE:.0%}), "
      f"{per_usd:,.2f} USD per name across {len(picks)}")
print(f"mode: {'EXECUTE' if EXECUTE else 'dry run'}\n")

placed, failed = [], []
for p in picks:
    t = p["ticker"] + "_US_EQ"
    qty = round(per_usd / p["price"] - have.get(t, 0.0), 2)
    if qty <= 0:
        print(f"  {t:12} already at target, skipping")
        continue
    line = f"  {t:12} qty {qty:>9.2f}  ~${qty * p['price']:,.2f}"
    if not EXECUTE:
        print(line + "   (dry run)")
        continue
    code, resp = call("/api/v0/equity/orders/market",
                      {"ticker": t, "quantity": qty}, "POST")
    if code in (200, 201):
        oid = resp.get("id") if isinstance(resp, dict) else None
        print(f"{line}   OK id={oid}")
        placed.append({"ticker": t, "quantity": qty, "id": oid})
    else:
        detail = resp
        if isinstance(resp, str) and '"detail"' in resp:
            detail = resp.split('"detail":', 1)[1][:110]
        print(f"{line}   FAILED {code} {detail}")
        failed.append({"ticker": t, "code": code})
        if len(failed) >= 3 and not placed:
            print("\nThree failures and nothing placed. Stopping rather than "
                  "firing the rest at the same wall.")
            break
    time.sleep(2.5)

if EXECUTE:
    print(f"\nplaced {len(placed)}, failed {len(failed)}")
    print("Run tools/t212_rebalance.py once these fill: the basket is not equal "
          "weight until it has been trued up against real fill prices.")
