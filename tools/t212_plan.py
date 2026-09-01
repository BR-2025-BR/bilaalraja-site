#!/usr/bin/env python3
"""Size an equal-weight basket for Trading 212 and show the plan. Places nothing.

Trading 212 has no quote endpoint, so quantities are sized off the panel's price
snapshot. Those prices are days old in places, and a market order fills at the
market, so the basket is sized against a reduced budget: a stale price that has
run up would otherwise overspend the account and bounce the tail of the orders.
"""
import base64, json, os, sys, urllib.request, urllib.error
from pathlib import Path

ID, SEC = os.environ.get("T212_ID", ""), os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET.")
HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
AUTH = "Basic " + base64.b64encode(f"{ID}:{SEC}".encode()).decode()
HERE = Path(__file__).resolve().parent

# Headroom against stale prices and the FX spread on a GBP account buying USD
# stock. Whatever is left simply stays as cash.
BUDGET_USE = 0.92


def get(path):
    req = urllib.request.Request(HOST + path, headers={"Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


rows = json.loads((HERE.parent / "pipeline" / "r3k_scored.json").read_text())
best = {}
for r in rows:
    if r.get("score") is None or not r.get("sector"):
        continue
    c = best.get(r["sector"])
    if c is None or r["score"] > c["score"]:
        best[r["sector"]] = r
picks = sorted(best.values(), key=lambda r: -r["score"])

cash = get("/api/v0/equity/account/cash")
info = get("/api/v0/equity/account/info")
ccy = info.get("currencyCode", "?")
free = float(cash.get("free") or 0)
total = float(cash.get("total") or 0)
print(f"account currency {ccy}   total {total:,.2f}   free {free:,.2f}")

positions = get("/api/v0/equity/portfolio")
print(f"open positions: {len(positions)}")
for p in positions:
    print(f"  {p.get('ticker')}  qty {p.get('quantity')}")

ins = {i["ticker"]: i for i in get("/api/v0/equity/metadata/instruments")}
print(f"\n{'ticker':12}{'price$':>9}{'minQty':>10}{'maxQty':>12}  type")
for p in picks:
    t = p["ticker"] + "_US_EQ"
    i = ins.get(t, {})
    print(f"{t:12}{p['price']:>9.2f}{str(i.get('minTradeQuantity')):>10}"
          f"{str(i.get('maxOpenQuantity')):>12}  {i.get('type')}")

budget = free * BUDGET_USE
per = budget / len(picks)
print(f"\nbudget {budget:,.2f} {ccy} ({BUDGET_USE:.0%} of free), "
      f"{per:,.2f} per name across {len(picks)}")
print("NOTE: prices are USD, account is", ccy,
      "- quantities below ignore FX and are indicative only.")

plan = []
for p in picks:
    t = p["ticker"] + "_US_EQ"
    i = ins.get(t, {})
    mn = float(i.get("minTradeQuantity") or 0)
    qty = per / p["price"]
    # T212 quantities respect the instrument's minimum increment
    qty = round(qty, 8)
    flag = "" if qty >= mn else f"  BELOW MIN {mn}"
    plan.append((t, qty, p["price"]))
    print(f"  {t:12} qty {qty:>12.4f}  ~${qty * p['price']:,.2f}{flag}")

(HERE.parent / "pipeline" / "t212_plan.json").write_text(
    json.dumps([{"ticker": t, "quantity": q, "ref_price": pr}
                for t, q, pr in plan], indent=1))
print("\nplan written to pipeline/t212_plan.json - nothing submitted")
