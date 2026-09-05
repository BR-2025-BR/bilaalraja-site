#!/usr/bin/env python3
"""Score every quarter, then hold for several lengths from the same snapshot.

Two questions get asked about "quarterly", and they are different:

  * quarterly REBALANCING -- score in January, sell in April, score again. Does
    the signal decay faster than a year?
  * quarterly FORMATION with a twelve-month hold -- four overlapping sleeves
    running at once. Does the whole result depend on January being the start?

Both need the same expensive thing: a point-in-time panel built and scored at
each quarter end. Once that exists, forward returns at 3, 6 and 12 months cost
almost nothing, so one sweep answers both rather than two sweeps answering one
each. Every horizon gets its own bootstrap null, because a random basket held
three months is far less variable than one held a year and comparing across
horizons without that would reward the short holds for arithmetic reasons.

The panel build is the bottleneck -- roughly 3,000 companies parsed one at a
time -- so it runs across processes here. Everything else is asof_backtest's.

    python3 research/quarterly_backtest.py 2019 2025
    python3 research/quarterly_backtest.py 2014 2026 --workers 5
"""
import os
import sys

# multiprocessing imports the stdlib `signal` while spawning, and any module in
# this directory named after a stdlib one will shadow it in both parent and
# child. research/signal.py used to do exactly that and is now finbert_signal.py;
# this loads the real one up front so sys.modules is already correct either way.
import signal            # noqa: F401  -- stdlib, cached before any spawn
import multiprocessing

import argparse          # noqa: E402
import importlib.util    # noqa: E402
import json              # noqa: E402
import time              # noqa: E402
import warnings          # noqa: E402
from pathlib import Path # noqa: E402

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent / "pipeline"
sys.path.insert(0, str(PIPE))

import asof_backtest as AB                                   # noqa: E402

WIDTHS = [1, 3, 5, 10, 20]
HORIZONS = {"3m": 91, "6m": 182, "12m": 365}
N_DRAWS = 2000

_RB = None          # per-worker module handle


def _init(asof_iso):
    """Each worker loads its own r3k_build pinned to the as-of date."""
    global _RB
    import r3k_facts as F
    F.AS_OF = pd.Timestamp(asof_iso)
    spec = importlib.util.spec_from_file_location("rb", PIPE / "r3k_build.py")
    rb = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(rb)
    except SystemExit:
        pass
    rb.STALE_BEFORE = (pd.Timestamp(asof_iso)
                       - pd.DateOffset(months=12)).strftime("%Y-%m-%d")
    _RB = rb


def _one(rec):
    try:
        row, reason = _RB.one(rec)
    except Exception as e:
        return None, type(e).__name__
    return row, reason


def build_panel_parallel(u, asof, workers):
    recs = u.to_dict("records")
    if workers <= 1:
        _init(str(asof))
        out = [_one(r) for r in recs]
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(workers, initializer=_init, initargs=(str(asof),)) as pool:
            out = pool.map(_one, recs, chunksize=40)
    rows, why = [], {}
    for row, reason in out:
        if row is not None:
            rows.append(row)
        else:
            why[reason] = why.get(reason, 0) + 1
    return pd.DataFrame(rows), why


def quarters(y0, y1):
    d = []
    for y in range(y0, y1 + 1):
        for m in (1, 4, 7, 10):
            d.append(pd.Timestamp(f"{y}-{m:02d}-01"))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("y0", type=int)
    ap.add_argument("y1", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="quarterly_results.json")
    a = ap.parse_args()

    tk, sh = AB.load_inputs()
    from prices import closes
    dates = quarters(a.y0, a.y1)
    lo = (min(dates) - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    hi = (max(dates) + pd.Timedelta(days=430)).strftime("%Y-%m-%d")
    print(f"  loading prices {lo} to {hi} ...", flush=True)
    syms = sorted(t for t in tk.ticker.unique() if isinstance(t, str) and t)
    px = closes(syms, lo, hi).sort_index()
    print(f"  price matrix {px.shape[0]:,} sessions x {px.shape[1]:,} tickers")
    print(f"  {len(dates)} quarters, {a.workers} workers\n", flush=True)

    out = []
    for qi, asof in enumerate(dates, 1):
        t0 = time.time()
        u, day = AB.universe_at(asof, tk, sh, px)
        if u is None:
            print(f"  {asof.date()}: no sessions on or before"); continue
        panel, why = build_panel_parallel(u, asof, a.workers)
        if panel.empty:
            print(f"  {asof.date()}: panel empty {sorted(why.items(), key=lambda k:-k[1])[:2]}")
            continue
        scored = AB.score(panel)
        scored = scored[scored.score.notna() & scored.sector.notna()]
        secs = round(time.time() - t0)

        for hname, hdays in HORIZONS.items():
            pool, endday = AB.forward_return(scored.ticker.tolist(), day, px, days=hdays)
            if endday is None or len(pool) < 50:
                continue
            held = (endday - day).days
            # a window still running is not comparable on RETURN, though its
            # percentile against same-length random baskets still is
            partial = held < hdays - 20
            rng = np.random.default_rng(7)
            for N in WIDTHS:
                picks = (scored.sort_values("score", ascending=False)
                               .groupby("sector").head(N))
                r, _ = AB.forward_return(picks.ticker.tolist(), day, px, days=hdays)
                if len(r) < 5:
                    continue
                n = len(r)
                draws = np.array([rng.choice(pool.values, n, replace=False).mean()
                                  for _ in range(N_DRAWS)])
                out.append({
                    "asof": str(asof.date()), "formed": str(day.date()),
                    "exit": str(endday.date()), "horizon": hname,
                    "days_held": int(held), "partial": bool(partial),
                    "n_per_sector": N, "picks": int(n),
                    "universe": int(len(u)), "scored": int(len(scored)),
                    "ret": float(r.mean()), "pool_mean": float(pool.mean()),
                    "null_mean": float(draws.mean()), "null_sd": float(draws.std()),
                    "null_p5": float(np.percentile(draws, 5)),
                    "null_p95": float(np.percentile(draws, 95)),
                    "pctile": float((draws < r.mean()).mean() * 100),
                    "p": float((draws >= r.mean()).mean()), "secs": secs})
            row = [o for o in out if o["asof"] == str(asof.date())
                   and o["horizon"] == hname and o["n_per_sector"] == 10]
            if row:
                o = row[0]
                print(f"  {asof.date()}  {hname:>3}  N=10  ret {o['ret']:>+7.1f}%  "
                      f"pool {o['pool_mean']:>+6.1f}%  excess "
                      f"{o['ret']-o['pool_mean']:>+6.1f}pp  p {o['p']:.3f}"
                      f"{'  PARTIAL' if partial else ''}", flush=True)
        print(f"  [{qi}/{len(dates)}] {asof.date()} done in {secs}s", flush=True)
        pd.DataFrame(out).to_json(HERE / a.out, orient="records", indent=1)

    if not out:
        raise SystemExit("  nothing produced")
    d = pd.DataFrame(out)
    full = d[~d.partial]
    print(f"\n  {'horizon':>8}{'N':>4}{'windows':>9}{'mean excess':>13}"
          f"{'median pctile':>15}{'p<0.05':>9}")
    for (h, N), g in full.groupby(["horizon", "n_per_sector"]):
        ex = g.ret - g.pool_mean
        print(f"  {h:>8}{N:>4}{len(g):>9}{ex.mean():>+12.2f}pp"
              f"{g.pctile.median():>14.0f}{int((g.p<0.05).sum()):>6} /{len(g)}")
    print(f"\n  wrote {a.out}")


if __name__ == "__main__":
    main()
