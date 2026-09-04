#!/usr/bin/env python3
"""One place that decides where daily prices come from.

    PRICE_SOURCE=sharadar   one API call for the whole market
    PRICE_SOURCE=yfinance   the original chunked fetch
    PRICE_SOURCE=local      the archived parquet store, no network at all
    PRICE_SOURCE=auto       sharadar if a key is present, else yfinance (default)

The point of the switch is that cancelling a subscription is a one-line change
and not a rewrite. Every backend returns the same shape:

    {"AAPL": {"price": 328.21, "date": "2026-09-03"}, ...}

WHICH TO USE, AND A LICENCE WARNING. Sharadar is licensed data. Using it to
compute and publish derived figures is ordinary use; republishing the price
series itself is not covered, and this site is public. yfinance carries its own
grey-area exposure but is what the site has always shipped. If in doubt for the
published site, keep yfinance and reserve Sharadar for research, which is what
it was bought for.
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
STORE = HERE.parent / "prices" / "daily"

SOURCE = os.environ.get("PRICE_SOURCE", "auto").lower()
KEY = os.environ.get("SHARADAR_KEY", "")


def resolve():
    if SOURCE != "auto":
        return SOURCE
    return "sharadar" if KEY else "yfinance"


# ---------------------------------------------------------------- sharadar
def _sharadar(tickers, lookback=8):
    """Whole-market close for the most recent session, in one request.

    Sharadar serves a full day of prices for every ticker at once, so this asks
    for the market rather than for 4,500 symbols in chunks. Walk back a few
    days because the newest session may not be posted yet, and a weekend or a
    holiday is not an error.
    """
    import json, urllib.request, urllib.error
    want = set(tickers)
    today = pd.Timestamp.utcnow().normalize()
    for back in range(lookback):
        day = (today - pd.Timedelta(days=back)).strftime("%Y-%m-%d")
        url = (f"https://api.sharadar.com/v1.0/data/SEP?date={day}&limit=20000")
        req = urllib.request.Request(url, headers={"x-api-key": KEY})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                txt = r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20)
                continue
            if e.code in (401, 403):
                raise SystemExit(f"sharadar rejected the key ({e.code}). "
                                 f"Set PRICE_SOURCE=yfinance to fall back.")
            continue
        lines = txt.splitlines()
        if len(lines) < 2:
            continue
        head = lines[0].split(",")
        try:
            ti, di, ci = head.index("ticker"), head.index("date"), head.index("closeadj")
        except ValueError:
            ti, di, ci = 0, 1, 7
        out = {}
        for ln in lines[1:]:
            p = ln.split(",")
            if len(p) <= ci:
                continue
            t = p[ti]
            if t not in want:
                continue
            try:
                out[t] = {"price": float(p[ci]), "date": p[di]}
            except ValueError:
                pass
        if out:
            print(f"  sharadar: {len(out):,} of {len(want):,} priced on {day} "
                  f"(1 request)", flush=True)
            return out
    print("  sharadar returned nothing for the last 8 days", flush=True)
    return {}


# ---------------------------------------------------------------- yfinance
def _yfinance(tickers, chunk=60):
    """The original path, unchanged in behaviour: chunked, retried, merged."""
    import yfinance as yf
    out, todo = {}, list(tickers)
    for i in range(0, len(todo), chunk):
        part = todo[i:i + chunk]
        for attempt in range(4):
            try:
                d = yf.download(part, period="7d", progress=False,
                                auto_adjust=False, threads=False)
                if d is None or d.empty:
                    raise ValueError("empty frame")
                cl = d["Close"] if isinstance(d.columns, pd.MultiIndex) else d[["Close"]]
                if not isinstance(d.columns, pd.MultiIndex):
                    cl.columns = part[:1]
                for t in cl.columns:
                    s = cl[t].dropna()
                    if len(s):
                        out[t] = {"price": float(s.iloc[-1]),
                                  "date": str(s.index[-1].date())}
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        if i and i % 600 == 0:
            print(f"    {i}/{len(todo)}  priced={len(out)}", flush=True)
    print(f"  yfinance: {len(out):,} of {len(todo):,} priced "
          f"({len(todo)//chunk + 1} requests)", flush=True)
    return out


# ------------------------------------------------------------------- local
def _local(tickers):
    """Last close in the archived store. Offline, and never fresher than it."""
    parts = sorted(STORE.glob("*.parquet"))
    if not parts:
        raise SystemExit(f"no local store at {STORE}")
    df = pd.read_parquet(parts[-1])
    df = df[df.ticker.isin(set(tickers))]
    last = df.sort_values("date").groupby("ticker").tail(1)
    out = {r.ticker: {"price": float(r.close), "date": str(pd.Timestamp(r.date).date())}
           for r in last.itertuples()}
    print(f"  local store: {len(out):,} of {len(tickers):,} priced "
          f"(newest {max((v['date'] for v in out.values()), default='n/a')})", flush=True)
    return out


def latest(tickers):
    """{ticker: {price, date}} from whichever backend is selected."""
    src = resolve()
    fn = {"sharadar": _sharadar, "yfinance": _yfinance, "local": _local}.get(src)
    if fn is None:
        raise SystemExit(f"unknown PRICE_SOURCE={src!r}")
    return fn(list(dict.fromkeys(tickers)))


if __name__ == "__main__":
    tk = sys.argv[1:] or ["AAPL", "MSFT", "NVDA", "JPM", "XOM"]
    print(f"  PRICE_SOURCE={SOURCE} -> {resolve()}")
    for t, v in sorted(latest(tk).items()):
        print(f"    {t:8} {v['price']:>10.2f}  {v['date']}")
