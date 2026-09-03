#!/usr/bin/env python3
"""State exactly what price history the study needs, and from whom.

Splits the sample three ways, because they are three different purchases:

  listed     ticker known and still in the current panel. A retail feed covers
             these; they are the cheap two thirds of nothing.
  delisted   ticker known, no longer in the panel. Either delisted, acquired,
             or simply below the market-cap floor now. A survivorship-free
             vendor is bought for exactly this group.
  unresolved no ticker anywhere in SEC's data. `submissions` drops the field
             once a company stops filing, and companyfacts cannot help because
             that API exposes only numeric facts - NVIDIA's file carries two dei
             concepts, both numbers, and TradingSymbol is text. These need the
             vendor's own CIK mapping, which the survivorship-free vendors have.
"""
import csv, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
req = json.loads((HERE / "price_requirements.json").read_text())
cur = {str(r["cik"]): r["ticker"]
       for r in json.loads((HERE.parent / "pipeline" / "r3k_scored.json").read_text())}

for r in req:
    if not r["ticker"]:
        r["group"] = "unresolved"
    elif r["cik"] in cur:
        r["group"] = "listed"
    else:
        r["group"] = "delisted_or_shrunk"

out = HERE / "price_needs.csv"
with out.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["cik", "ticker", "exchange", "name", "group",
                                       "n_filings", "first_filed", "last_filed",
                                       "price_from", "price_to"])
    w.writeheader()
    for r in sorted(req, key=lambda x: (x["group"], x["ticker"] or "")):
        w.writerow({k: r.get(k) for k in w.fieldnames})

from collections import Counter
c = Counter(r["group"] for r in req)
print(f"  wrote {out.name}: {len(req):,} rows")
for k, v in c.most_common():
    f = sum(r["n_filings"] for r in req if r["group"] == k)
    print(f"    {k:20} {v:>5,} companies  {f:>7,} filings")
print(f"\n  window: {min(r['price_from'] for r in req)} -> {max(r['price_to'] for r in req)}")
print(f"  daily OHLC rows needed (approx): "
      f"{len(req) * 1400:,} at ~1,400 sessions over the window")
