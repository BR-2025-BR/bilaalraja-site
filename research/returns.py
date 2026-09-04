#!/usr/bin/env python3
"""Attach the pre-registered outcome to each filing.

Primary: return from close on t+1 to close on t+63 trading days, minus the
equal-weighted return of all sample companies over the identical window.
Secondary: the same at t+21 and t+126.

t+1 rather than t avoids same-day look-ahead: a filing published during a
session cannot be traded at that session's close.

The benchmark is computed once as a daily equal-weighted index of every company
in the sample, so "the identical window" means exactly that — the same two
trading days, not an approximation in calendar time.

Companies are joined to prices on CIK, not ticker. A third of this sample has no
ticker in SEC's data at all, which is the entire reason for buying a feed whose
own table carries CIKs.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
from prices import panel, PXDIR                       # noqa: E402

HORIZONS = {"r63": 63, "r21": 21, "r126": 126}        # primary is r63


def main():
    d = pd.read_parquet(HERE / "signal.parquet")
    tk = pd.read_parquet(HERE.parent / "prices" / "tickers.parquet")
    tk = tk[tk.cik.notna()].copy()
    tk["cik"] = tk.cik.astype("int64")

    # A CIK can carry several share classes. Prefer the one that traded longest,
    # which is the primary listing in practice; picking arbitrarily would mix
    # A and B shares across filings of the same company.
    tk["span"] = (pd.to_datetime(tk.lastpricedate, errors="coerce")
                  - pd.to_datetime(tk.firstpricedate, errors="coerce")).dt.days
    tk = tk.sort_values("span", ascending=False).drop_duplicates("cik", keep="first")
    m = dict(zip(tk.cik, tk.ticker))

    d["ticker"] = d.cik.map(m)
    n0 = len(d)
    unmapped = d.ticker.isna().sum()
    d = d[d.ticker.notna()].copy()
    print(f"  observations                 {n0:,}")
    print(f"  no ticker for that CIK       {unmapped:,}  -> {len(d):,} mapped")

    # prices over the window plus the longest horizon, with delisting returns
    lo = d.filed.min() - pd.Timedelta(days=10)
    hi = d.filed.max() + pd.Timedelta(days=400)
    px = panel(sorted(d.ticker.unique()), lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d"))
    px = px.sort_index()
    print(f"  price matrix                 {px.shape[0]:,} sessions x {px.shape[1]:,} tickers")

    have = set(px.columns)
    nopx = (~d.ticker.isin(have)).sum()
    d = d[d.ticker.isin(have)].copy()
    print(f"  ticker present, no price     {nopx:,}  -> {len(d):,} priced")

    sess = px.index
    # position of the first session strictly after the filing date, i.e. t+1
    pos = sess.searchsorted(pd.DatetimeIndex(d.filed), side="right")
    d["p0"] = pos

    # equal-weighted index of the sample, rebuilt daily from whatever is trading
    rets = px.pct_change()
    ew = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()

    vals = px.to_numpy()
    col = {t: i for i, t in enumerate(px.columns)}
    ci = d.ticker.map(col).to_numpy()
    ewv = ew.to_numpy()
    nsess = len(sess)

    for name, h in HORIZONS.items():
        a = d.p0.to_numpy()
        b = a + h
        ok = (a < nsess) & (b < nsess)
        r = np.full(len(d), np.nan)
        bm = np.full(len(d), np.nan)
        ia, ib = a[ok], b[ok]
        pa = vals[ia, ci[ok]]
        pb = vals[ib, ci[ok]]
        good = np.isfinite(pa) & np.isfinite(pb) & (pa > 0)
        idx = np.where(ok)[0][good]
        r[idx] = pb[good] / pa[good] - 1
        bm[idx] = ewv[ib[good]] / ewv[ia[good]] - 1
        d[name] = r
        d[f"ab{name[1:]}"] = r - bm                    # abnormal return
        n = int(np.isfinite(r).sum())
        print(f"  t+{h:<4} priced           {n:>7,}  "
              f"mean raw {np.nanmean(r):+.2%}  mean abnormal {np.nanmean(r-bm):+.2%}")

    d["p1_date"] = sess[np.clip(d.p0.to_numpy(), 0, nsess - 1)]
    out = HERE / "panel_returns.parquet"
    d.to_parquet(out, index=False)
    print(f"\n  wrote {out.name}: {len(d):,} rows, "
          f"{int(d.ab63.notna().sum()):,} with a primary outcome")


if __name__ == "__main__":
    main()
