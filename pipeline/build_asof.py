#!/usr/bin/env python3
"""Rebuild the panel as it would have looked on a past date.

Three things must be rolled back together or the result is not point-in-time:

  fundamentals  only facts filed on or before the date (r3k_facts.AS_OF)
  share counts  the last count filed before the date, not today's
  prices        that date's close, not today's

Getting any one of them wrong reintroduces exactly the look-ahead the exercise
is meant to remove.

What cannot be rolled back: universe membership. The constituent list is
today's, so companies that delisted or were acquired since the date are absent.
Over a short window that is small, but it biases results upward and is stated
rather than hidden.
"""
import importlib.util, json, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

import pandas as pd, yfinance as yf

HERE = Path(__file__).resolve().parent
AS_OF = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else "2026-01-01")
PRICE_ON = (AS_OF + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

sys.path.insert(0, str(HERE))
import r3k_facts as F
F.AS_OF = AS_OF                      # hide anything filed later
from pitquant.fundamentals import _extract_tag_rows, _as_filed, SHARES_DEI_TAG

spec = importlib.util.spec_from_file_location("rb", HERE / "r3k_build.py")
rb = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(rb)
except SystemExit: pass

uni = pd.read_json(HERE / "r3k_universe.json")
print(f"as of {AS_OF.date()}  |  {len(uni):,} companies in the universe", flush=True)

# ---- prices on the formation date
tk = sorted(uni.ticker.astype(str).unique())
cache = HERE / f"px_asof_{AS_OF.date()}.pkl"
if cache.exists():
    px = pd.read_pickle(cache)
    print("prices from cache", flush=True)
else:
    # 3,000 tickers in one request gets rate-limited: the first attempt
    # returned 2,588, the second only 20. Chunk it and pause between.
    import time as _t
    end = (AS_OF + pd.Timedelta(days=8)).strftime("%Y-%m-%d")
    parts = []
    CH = 60
    for i in range(0, len(tk), CH):
        part = tk[i:i + CH]
        for attempt in range(4):
            try:
                d = yf.download(part, start=PRICE_ON, end=end, auto_adjust=True,
                                progress=False, threads=False)["Close"]
                if isinstance(d, pd.Series): d = d.to_frame(part[0])
                got = d.dropna(how="all")
                if len(got): parts.append(d); break
            except Exception:
                pass
            _t.sleep(8 * (attempt + 1))
        if (i // CH) % 10 == 0:
            have = sum(x.shape[1] for x in parts)
            print(f"  priced {have:,}/{len(tk):,}", flush=True)
        _t.sleep(1.5)
    px = pd.concat(parts, axis=1) if parts else pd.DataFrame()
    px.to_pickle(cache)
first = px.dropna(how="all").iloc[0]
print(f"prices from {px.dropna(how='all').index[0].date()}  "
      f"({first.notna().sum():,} of {len(tk):,} priced)", flush=True)

# ---- share counts as they were then
def shares_asof(facts):
    raw = _extract_tag_rows(facts, "dei", SHARES_DEI_TAG)
    if not raw: return None
    df = _as_filed(pd.DataFrame(raw))
    df = df[pd.to_datetime(df["filed"], errors="coerce") <= AS_OF]
    if df.empty: return None
    return float(df.sort_values("filed").iloc[-1]["val"])

rows, why = [], {}
for r in uni.itertuples():
    p = first.get(r.ticker)
    if p is None or pd.isna(p): why["no price"] = why.get("no price", 0) + 1; continue
    f = Path(F.EDGAR) / f"companyfacts_{int(r.cik):010d}.json"
    if not f.exists(): why["no companyfacts"] = why.get("no companyfacts", 0) + 1; continue
    try: facts = json.loads(f.read_text())
    except Exception: why["unreadable"] = why.get("unreadable", 0) + 1; continue
    sh = shares_asof(facts)
    if not sh: why["no share count as of date"] = why.get("no share count as of date", 0) + 1; continue
    rows.append({"cik": int(r.cik), "ticker": r.ticker, "name": r.name,
                 "sector": r.sector, "sic": int(getattr(r, "sic", 0) or 0),
                 "price": float(p), "shares": sh, "mcap": float(p) * sh / 1e9})
print(f"reconstructed {len(rows):,} companies", flush=True)
for k, v in sorted(why.items(), key=lambda x: -x[1]):
    print(f"  dropped {v:>5}  {k}", flush=True)

rows.sort(key=lambda x: -x["mcap"])
for i, x in enumerate(rows, 1): x["rank"] = i
pd.DataFrame(rows).to_json(HERE / "universe_asof.json", orient="records", indent=1)

# ---- panel, using the same builder
out, skipped = [], {}
for i, rec in enumerate(rows, 1):
    try: row, why = rb.one(rec)
    except Exception as e: row, why = None, f"error {type(e).__name__}"
    if row: out.append(row)
    else: skipped[why] = skipped.get(why, 0) + 1
    if i % 400 == 0: print(f"  {i}/{len(rows)}  built {len(out):,}", flush=True)

json.dump(out, open(HERE / "panel_asof.json", "w"))
print(f"\nPANEL AS OF {AS_OF.date()}: {len(out):,} companies")
for k, v in sorted(skipped.items(), key=lambda x: -x[1])[:5]:
    print(f"  skipped {v:>5}  {k}")
