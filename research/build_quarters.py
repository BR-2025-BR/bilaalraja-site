#!/usr/bin/env python3
"""Cache a scored point-in-time panel for every quarter, so portfolio rules can
be re-run in seconds afterwards.

    python3 research/build_quarters.py 2014 2026 [workers]

Panels already in gated25_panels/ are skipped, so this is safe to re-run and
resumes where it left off if interrupted.

The main guard below is load-bearing. multiprocessing spawns workers by
re-importing this module; any work left at module level runs again in every
child, including creating another pool, which recurses until the machine dies.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pipeline"))
os.environ.setdefault("GATED25_FROM", "2014")


def quarters(y0, y1):
    out = []
    for y in range(y0, y1 + 1):
        for m in (1, 4, 7, 10):
            out.append(f"{y}-{m:02d}-01")
    return out


def main():
    import pandas as pd
    import gated25 as G, asof_backtest as AB
    from quarterly_backtest import build_panel_parallel
    from prices import closes

    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2014
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    G.CACHE.mkdir(exist_ok=True)
    dates = [d for d in quarters(y0, y1) if d <= "2026-07-01"]
    todo = [d for d in dates if not (G.CACHE / f"{d}.parquet").exists()]
    print(f"  {len(dates)} quarters, {len(todo)} to build, {workers} workers", flush=True)
    if not todo:
        print("  nothing to do"); return

    tk, sh = AB.load_inputs()
    syms = sorted(t for t in tk.ticker.unique() if isinstance(t, str) and t)
    lo = (pd.Timestamp(min(todo)) - pd.DateOffset(months=2)).strftime("%Y-%m-%d")
    hi = "2026-09-30"
    px = closes(syms, lo, hi).sort_index()
    print(f"  price matrix {px.shape[0]:,} x {px.shape[1]:,}\n", flush=True)

    for i, asof in enumerate(todo, 1):
        u, day = AB.universe_at(pd.Timestamp(asof), tk, sh, px)
        if u is None or not len(u):
            print(f"  [{i}/{len(todo)}] {asof}: no universe, skipped", flush=True)
            continue
        panel, why = build_panel_parallel(u, pd.Timestamp(asof), workers)
        if panel.empty:
            print(f"  [{i}/{len(todo)}] {asof}: panel empty", flush=True)
            continue
        scored = AB.score(panel)
        scored = scored[scored.score.notna() & scored.sector.notna()].copy()
        scored["formed"] = str(day.date())
        # write then rename: a reboot or kill mid-write would otherwise leave a
        # truncated parquet that the resume logic sees as "already cached"
        tmp = G.CACHE / f".{asof}.parquet.part"
        scored.to_parquet(tmp, index=False)
        tmp.replace(G.CACHE / f"{asof}.parquet")
        g = scored[(scored.model == "operating") & G.passes_gates(scored)]
        print(f"  [{i}/{len(todo)}] {asof}: {len(scored):,} scored, "
              f"{len(g)} pass all six gates", flush=True)
    print("  ALL QUARTERS BUILT", flush=True)


if __name__ == "__main__":
    main()
