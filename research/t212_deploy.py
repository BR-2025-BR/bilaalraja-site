#!/usr/bin/env python3
"""Liquidate the live account and deploy it equally across today's basket.

    T212_KEY=... python3 research/t212_deploy.py plan     # read-only, shows everything
    T212_KEY=... python3 research/t212_deploy.py execute  # places real orders

`plan` touches nothing. It authenticates, reads cash and positions, resolves every
basket ticker to a Trading 212 instrument, prices the orders, and prints exactly
what `execute` would do. Run it first, every time.

WHY THIS IS CAREFUL IN THE PLACES IT IS:

  * sizing uses the LIVE price from the instrument feed, not the price in the
    research panel. A basket sized on stale prices is not equal weight, which is
    how an earlier run put 9% more into one name than intended.
  * quantities are floored to 2 decimals, which is the precision the API accepts.
    Rounding up can overdraw the account on the last order of the batch.
  * a cash buffer is held back. Market orders fill at whatever the book gives,
    and a fill above the quote on the final order fails the whole order rather
    than partially filling.
  * every endpoint is rate limited to one request per 5 seconds, per T212's
    documented limit. This is slow on purpose.
  * positions inside a Pie cannot be sold through /orders/market -- the API
    reports them as owned 0.0. Those must be dissolved in the app first, and
    this script says so rather than silently skipping them.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = os.environ.get("T212_KEY", "")
BASE = os.environ.get("T212_BASE", "https://live.trading212.com/api/v0")
PAUSE = 5.2                      # documented limit is one call per 5s per endpoint
CASH_BUFFER = 0.985              # deploy 98.5%, leaving room for fills above quote
SETTLE_WAIT = 45                 # seconds to let sales settle before buying

BASKET = ["AMN", "EVER", "EXE", "SD", "GCT", "CF", "TPC", "ANIP", "FSLR", "LMB",
          "SEZL", "EQT", "VMD", "HL", "NBIX", "ARW", "CHE", "RELY", "CDE",
          "HALO", "MU", "SCCO", "GRND", "RDDT", "COCO"]


def call(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 headers={"Authorization": KEY,
                                          "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            txt = r.read().decode(errors="replace")
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise SystemExit(f"  {method} {path} -> {e.code} {e.reason}\n  {detail}")


def resolve(instruments):
    """Map plain tickers to Trading 212 instrument codes (AAPL -> AAPL_US_EQ).

    Matching on the API's own `shortName`/`ticker` rather than guessing the
    suffix: the pattern is not uniform and a wrong code buys the wrong company.
    """
    by_short, out, missing = {}, {}, []
    for i in instruments:
        s = (i.get("shortName") or "").upper()
        if i.get("type") == "STOCK" and (i.get("currencyCode") == "USD"):
            by_short.setdefault(s, i)
    for t in BASKET:
        hit = by_short.get(t.upper())
        if hit:
            out[t] = hit
        else:
            missing.append(t)
    return out, missing


def main():
    if not KEY:
        raise SystemExit("  set T212_KEY (Settings -> API (Beta), read + orders scopes)")
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    live = mode == "execute"
    print(f"  mode: {'EXECUTE -- places real orders' if live else 'plan (read-only)'}")
    print(f"  base: {BASE}\n")

    cash = call("/equity/account/cash"); time.sleep(PAUSE)
    positions = call("/equity/portfolio"); time.sleep(PAUSE)
    free = float(cash.get("free", 0))
    invested = float(cash.get("invested", 0))
    total = float(cash.get("total", free + invested))
    print(f"  free cash   {free:>12,.2f}")
    print(f"  invested    {invested:>12,.2f}")
    print(f"  total       {total:>12,.2f}")
    print(f"  positions   {len(positions):>12}")

    if positions:
        print("\n  HOLDINGS TO LIQUIDATE")
        for p in positions:
            q = float(p.get("quantity", 0))
            print(f"    {p.get('ticker',''):<18} qty {q:>12,.2f}  "
                  f"value {float(p.get('quantity',0))*float(p.get('currentPrice',0)):>12,.2f}")
        pie_like = [p for p in positions if float(p.get("quantity", 0)) == 0]
        if pie_like:
            print(f"\n  {len(pie_like)} position(s) report quantity 0 -- these are held in a Pie "
                  f"and cannot be sold through the API. Dissolve the Pie in the app first.")

    instruments = call("/equity/metadata/instruments"); time.sleep(PAUSE)
    found, missing = resolve(instruments)
    print(f"\n  basket resolved: {len(found)}/{len(BASKET)}")
    if missing:
        print(f"  NOT TRADEABLE HERE: {', '.join(missing)} -- they will be skipped and the "
              f"remaining names sized to absorb the cash")

    if live and positions:
        print("\n  selling...")
        for p in positions:
            q = float(p.get("quantity", 0))
            if q <= 0:
                continue
            call("/equity/orders/market", "POST",
                 {"ticker": p["ticker"], "quantity": -round(q, 2)})
            print(f"    sold {p['ticker']}")
            time.sleep(PAUSE)
        print(f"  waiting {SETTLE_WAIT}s for settlement")
        time.sleep(SETTLE_WAIT)
        cash = call("/equity/account/cash"); time.sleep(PAUSE)
        free = float(cash.get("free", 0))
        print(f"  free cash after liquidation: {free:,.2f}")

    deploy = (free if live else total) * CASH_BUFFER
    each = deploy / max(len(found), 1)
    print(f"\n  deploying {deploy:,.2f} across {len(found)} names, {each:,.2f} each\n")
    print(f"  {'ticker':<8}{'T212 code':<18}{'price':>10}{'qty':>10}{'value':>12}")
    orders = []
    for t, inst in found.items():
        code = inst["ticker"]
        px = next((float(p["currentPrice"]) for p in positions
                   if p.get("ticker") == code), None)
        if px is None:
            px = float(inst.get("lastPrice") or 0) or None
        if not px:
            print(f"  {t:<8}{code:<18}{'no price':>10}  skipped")
            continue
        qty = int(each / px * 100) / 100          # floor to 2dp, never round up
        if qty <= 0:
            print(f"  {t:<8}{code:<18}{px:>10.2f}{'too small':>10}")
            continue
        orders.append((t, code, qty, qty * px))
        print(f"  {t:<8}{code:<18}{px:>10.2f}{qty:>10.2f}{qty*px:>12,.2f}")
    print(f"\n  total to deploy: {sum(o[3] for o in orders):,.2f}")

    if not live:
        print("\n  plan only. Re-run with `execute` to place these orders.")
        return
    print("\n  buying...")
    for t, code, qty, val in orders:
        call("/equity/orders/market", "POST", {"ticker": code, "quantity": qty})
        print(f"    bought {t:<6} {qty:>10.2f}  ~{val:,.2f}")
        time.sleep(PAUSE)
    print("\n  done. Revoke the API key now -- the basket needs no further access.")


if __name__ == "__main__":
    main()
