#!/usr/bin/env python3
"""Top up the as-of price cache for tickers Yahoo declined to serve.

The cache holds a column per requested ticker, and a rate-limited request
leaves that column entirely empty. Without this, a rerun sees the column
present and never asks again, permanently locking in whatever coverage the
throttled run happened to get.
"""
import sys, time, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd, yfinance as yf

HERE  = Path(__file__).resolve().parent
AS_OF = pd.Timestamp("2026-01-01")
CACHE = HERE / f"px_asof_{AS_OF.date()}.pkl"
START = (AS_OF + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
END   = (AS_OF + pd.Timedelta(days=8)).strftime("%Y-%m-%d")

px = pd.read_pickle(CACHE)
first = px.dropna(how="all").iloc[0]
missing = sorted([c for c in px.columns if pd.isna(first.get(c))])
uni = set(pd.read_json(HERE / "r3k_universe.json").ticker.astype(str))
missing = [m for m in missing if m in uni]
print(f"cache holds {px.shape[1]:,} tickers, {first.notna().sum():,} priced; "
      f"{len(missing):,} to retry", flush=True)

CH, added = 25, 0
for i in range(0, len(missing), CH):
    part = missing[i:i + CH]
    for attempt in range(5):
        try:
            d = yf.download(part, start=START, end=END, auto_adjust=True,
                            progress=False, threads=False)["Close"]
            if isinstance(d, pd.Series): d = d.to_frame(part[0])
            got = d.dropna(how="all")
            if len(got):
                for c in d.columns:
                    if c in px.columns: px[c] = px[c].combine_first(d[c])
                    else: px[c] = d[c]
                added += int(d.iloc[0].notna().sum()) if len(d) else 0
                break
        except Exception:
            pass
        time.sleep(12 * (attempt + 1))       # back off hard; Yahoo is throttling
    if (i // CH) % 8 == 0:
        px.to_pickle(CACHE)
        cur = px.dropna(how="all").iloc[0].notna().sum()
        print(f"  {i + len(part):,}/{len(missing):,} retried, now priced {cur:,}", flush=True)
    time.sleep(3)

px.to_pickle(CACHE)
cur = px.dropna(how="all").iloc[0].notna().sum()
print(f"DONE  priced {cur:,} of {px.shape[1]:,}", flush=True)
