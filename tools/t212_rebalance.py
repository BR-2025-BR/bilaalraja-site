#!/usr/bin/env python3
"""Rebalance the held basket to equal weight by current market value.

The original basket was never equal weight. It was sized on the panel's price
snapshot, which was days old in places, so a name whose price had risen since
the snapshot bought more than intended: INR's reference was $14.47 against a
$15.76 fill, putting that leg 9% over. The cost spread across the twelve was
12.1% before the market moved at all.

Sizing here uses `currentPrice` from the portfolio endpoint rather than any
stored figure, which is the same reason the original went wrong.

Sells are placed before buys: a sell frees cash a buy may need, and the reverse
order can fail the tail of the basket on insufficient funds.

    T212_ID='...' T212_SECRET='...' python3 tools/t212_rebalance.py --execute
"""
import base64, json, os, sys, time, urllib.request, urllib.error

ID, SEC = os.environ.get("T212_ID", ""), os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET.")
HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
AUTH = "Basic " + base64.b64encode(f"{ID}:{SEC}".encode()).decode()
EXECUTE = "--execute" in sys.argv

# --deploy-cash puts free cash to work as part of the rebalance: the target
# becomes (basket value + cash) / n rather than basket value / n. Topping up an
# existing basket from cash alone gets this wrong, sizing each name at cash/n as
# though nothing were held, which under-deploys by whatever is already invested.
DEPLOY_CASH = "--deploy-cash" in sys.argv
CASH_USE = 0.97                     # leave a little for price drift between calls
FX_GBP_USD = float(os.environ.get("T212_FX", "1.3545"))

# Below this the trade is not worth its own currency-conversion charge.
MIN_TRADE_USD = float(os.environ.get("T212_MIN_TRADE", "5"))


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


def target_basket():
    """The names the basket is defined as: top scorer per sector."""
    from pathlib import Path
    rows = json.loads((Path(__file__).resolve().parent.parent /
                       "pipeline" / "r3k_scored.json").read_text())
    best = {}
    for r in rows:
        if r.get("score") is None or not r.get("sector"):
            continue
        c = best.get(r["sector"])
        if c is None or r["score"] > c["score"]:
            best[r["sector"]] = r
    return {r["ticker"] for r in best.values()}


_, held = call("/api/v0/equity/portfolio")
if not held:
    sys.exit("No open positions to rebalance.")

# Rebalance the basket, not the account. Anything else held is somebody else's
# decision - a legacy position, or something mid-liquidation - and buying more of
# it to hit an equal weight would be inventing a trade nobody asked for.
want = target_basket()
port = [p for p in held if p["ticker"].split("_")[0] in want]
skipped = [p["ticker"] for p in held if p["ticker"].split("_")[0] not in want]
if skipped:
    print(f"outside the basket, left alone: {', '.join(skipped)}")
if not port:
    sys.exit("None of the basket names are held.")

total = sum(p["quantity"] * p["currentPrice"] for p in port)
deployable = 0.0
if DEPLOY_CASH:
    _, cash = call("/api/v0/equity/account/cash")
    free = float((cash or {}).get("free") or 0)
    deployable = free * CASH_USE * FX_GBP_USD          # account ccy -> USD
    print(f"free cash {free:,.2f} -> ${deployable:,.2f} deployable at {FX_GBP_USD}")

target = (total + deployable) / len(port)
print(f"basket ${total:,.2f}" + (f" + ${deployable:,.2f} cash" if deployable else "") +
      f"  target ${target:,.2f} across {len(port)}")
print(f"mode: {'EXECUTE' if EXECUTE else 'dry run'}\n")

plan = []
for p in port:
    val = p["quantity"] * p["currentPrice"]
    dq = round((target - val) / p["currentPrice"], 2)
    usd = dq * p["currentPrice"]
    if dq == 0 or abs(usd) < MIN_TRADE_USD:
        print(f"  {p['ticker']:12} skip, ${abs(usd):.2f} below the ${MIN_TRADE_USD:.0f} floor")
        continue
    plan.append({"ticker": p["ticker"], "quantity": dq, "usd": usd})

plan.sort(key=lambda t: t["usd"])            # sells first: they fund the buys
placed, failed = [], []
for t in plan:
    side = "SELL" if t["quantity"] < 0 else "BUY "
    line = f"  {side} {t['ticker']:12} {t['quantity']:>8.2f}  ${t['usd']:>8,.2f}"
    if not EXECUTE:
        print(line + "   (dry run)")
        continue
    code, resp = call("/api/v0/equity/orders/market",
                      {"ticker": t["ticker"], "quantity": t["quantity"]}, "POST")
    if code in (200, 201):
        oid = resp.get("id") if isinstance(resp, dict) else None
        print(f"{line}   OK id={oid}")
        placed.append({**t, "id": oid})
    else:
        detail = resp
        if isinstance(resp, str) and '"detail"' in resp:
            detail = resp.split('"detail":', 1)[1][:110]
        print(f"{line}   FAILED {code} {detail}")
        failed.append({**t, "code": code})
    time.sleep(2.5)                          # the orders endpoint is rate limited

if EXECUTE:
    print(f"\nplaced {len(placed)}, failed {len(failed)}")
    if failed:
        print("Failures leave the book partly rebalanced. Re-run to finish: "
              "sizing is always computed from live positions, never from a plan file.")
