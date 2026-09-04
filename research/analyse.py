#!/usr/bin/env python3
"""Run the five pre-registered specifications on the development window.

Decision rule, fixed before any return data was touched:

  sort filings into quintiles by the signal within each calendar quarter;
  the spread is bottom quintile minus top quintile;
  success needs the spread NEGATIVE and |t| > 2.5, Newey-West at 63 lags.

Why the t-statistic is computed the way it is. Each filing carries a 63-trading-
day forward return, so two filings a month apart share two thirds of their
window and their errors are anything but independent. Treating 38,000 filings as
38,000 independent observations would shrink the standard error by roughly the
square root of the overlap and manufacture significance out of nothing.

So the spread is expressed as a daily portfolio instead: on each session, hold
every filing whose window covers that day, long the bottom quintile and short the
top. The mean daily return of that portfolio is the effect, and Newey-West with
63 lags is then the correct correction for exactly the overlap that constructed
it.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
HOLD = 63
LAGS = 63
T_REQUIRED = 2.5


def newey_west_t(x, lags=LAGS):
    """t-statistic for the mean of a serially correlated series."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < lags + 5:
        return np.nan, np.nan, n
    mu = x.mean()
    e = x - mu
    g0 = (e @ e) / n
    s = g0
    for L in range(1, lags + 1):
        g = (e[L:] @ e[:-L]) / n
        s += 2 * (1 - L / (lags + 1)) * g          # Bartlett kernel
    s = max(s, 1e-18)
    se = np.sqrt(s / n)
    return mu, mu / se, n


def daily_spread(d, sessions, signal, q=5):
    """Daily long-short return: bottom quintile minus top, held 63 sessions."""
    d = d.dropna(subset=[signal, "ab63", "p0"]).copy()
    # quintiles are assigned within calendar quarter, as specified
    d["qt"] = (d.groupby("quarter")[signal]
                 .transform(lambda s: pd.qcut(s.rank(method="first"), q,
                                              labels=False, duplicates="drop")))
    d = d.dropna(subset=["qt"])
    lo = d[d.qt == 0]
    hi = d[d.qt == q - 1]

    n = len(sessions)
    # each filing contributes its per-session average abnormal return across the
    # window it is held: a simple, transparent allocation of a 63-day figure
    def accumulate(g):
        tot = np.zeros(n)
        cnt = np.zeros(n)
        p0 = g.p0.to_numpy().astype(int)
        ab = (g.ab63.to_numpy() / HOLD)
        for a, r in zip(p0, ab):
            b = min(a + HOLD, n)
            if a >= n:
                continue
            tot[a:b] += r
            cnt[a:b] += 1
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)

    return accumulate(lo) - accumulate(hi), len(lo), len(hi)


def run(d, label, signal="dtone", subset=None):
    x = d if subset is None else d[subset]
    x = x.dropna(subset=[signal, "ab63"])
    if len(x) < 500:
        print(f"  {label:38} SKIPPED, only {len(x):,} observations")
        return None
    sessions = np.arange(int(x.p0.max()) + HOLD + 2)
    series, nlo, nhi = daily_spread(x, sessions, signal)
    mu, t, n = newey_west_t(series)

    # the same thing without the overlap correction, to show what it is worth
    g = x.groupby(x.groupby("quarter")[signal]
                   .transform(lambda s: pd.qcut(s.rank(method="first"), 5,
                                                labels=False, duplicates="drop")))
    naive = g.ab63.mean()
    naive_spread = (naive.get(0, np.nan) - naive.get(4, np.nan)) * 100

    ann = mu * 252 * 100 if np.isfinite(mu) else np.nan
    ok = (naive_spread < 0) and np.isfinite(t) and abs(t) > T_REQUIRED
    print(f"  {label:38}{len(x):>8,}{naive_spread:>+9.2f}%{ann:>+9.2f}%"
          f"{t:>8.2f}   {'PASS' if ok else 'fail'}")
    return {"label": label, "n": int(len(x)), "spread_pct": float(naive_spread),
            "ann_pct": float(ann), "t": float(t), "n_lo": int(nlo), "n_hi": int(nhi),
            "pass": bool(ok)}


def main():
    d = pd.read_parquet(HERE / "panel_returns.parquet")
    print(f"  development observations with a primary outcome: "
          f"{int(d.ab63.notna().sum()):,}\n")
    print(f"  {'specification':38}{'n':>8}{'spread':>10}{'annual':>9}{'NW t':>8}")
    print("  " + "-" * 74)

    res = []
    res.append(run(d, "1. primary (length-residualised)", "dtone"))
    res.append(run(d, "2. no length control", "dtone_raw"))
    res.append(run(d, "3. 10-K only", "dtone", d.form == "10-K"))
    mc = HERE / "mcap.parquet"
    if mc.exists():
        cap = pd.read_parquet(mc)
        d = d.merge(cap, on=["ticker", "p1_date"], how="left")
        res.append(run(d, "4. market cap >= $1bn", "dtone", d.marketcap >= 1000))
    else:
        print(f"  {'4. market cap >= $1bn':38} pending, mcap.parquet not built yet")
    res.append(run(d, "5. tone level (straw man)", "level"))

    print("\n  Decision rule: spread must be NEGATIVE and |t| > 2.5.")
    passed = [r for r in res if r and r["pass"]]
    print(f"  Specifications passing: {len(passed)} of {len([r for r in res if r])}")
    if not passed:
        print("  -> development result is a NULL. The holdout is not opened.")
    else:
        print("  -> specification 1 status decides whether the holdout is opened.")
    pd.DataFrame([r for r in res if r]).to_json(HERE / "results_dev.json",
                                                orient="records", indent=1)
    print(f"\n  wrote results_dev.json")


if __name__ == "__main__":
    main()
