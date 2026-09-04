#!/usr/bin/env python3
"""Gather the per-basket pick files into one tidy table.

asof_backtest.py writes one CSV per (date, width) as it goes. That is the right
shape for the backtest and the wrong shape for looking at, so this joins them
into a single long table -- one row per holding per basket -- and attaches the
basket-level result each holding belongs to.

    python3 research/compositions.py                     # everything present
    python3 research/compositions.py --years 2019-2025 \
        --results asof_results_2019_2025.json \
        --out compositions_2019_2025.csv

A holding's `ret` is its own twelve-month return, already carrying the -30%
delisting convention where it stopped trading inside the window. `excess_vs_pool`
is that return against the equal-weighted return of everything investable on the
same day, which is the comparison the backtest actually makes -- not an index.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PAT = re.compile(r"picks_(\d{4})-(\d{2})-(\d{2})_n(\d+)\.csv$")


def load_results(name):
    """Basket-level stats keyed by (asof, width), if the run wrote them."""
    f = HERE / name
    if not f.exists():
        print(f"  note: {name} absent, basket-level columns will be blank")
        return {}
    d = json.loads(f.read_text())
    out = {}
    for r in d:
        # results written before the width sweep carry no n_per_sector; they
        # describe a different run and cannot be keyed, so skip rather than guess
        if "n_per_sector" not in r:
            continue
        out[(str(r["asof"])[:10], int(r["n_per_sector"]))] = r
    if not out:
        print(f"  note: {name} has no per-width rows, basket columns will be blank")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="asof_results.json")
    ap.add_argument("--out", default="compositions.csv")
    ap.add_argument("--years", default="", help="e.g. 2019-2025, inclusive")
    a = ap.parse_args()

    lo, hi = 0, 9999
    if a.years:
        lo, hi = (int(x) for x in a.years.split("-"))

    res = load_results(a.results)
    frames = []
    for f in sorted(HERE.glob("picks_*.csv")):
        m = PAT.search(f.name)
        if not m:
            continue
        y, mo, dd, n = int(m[1]), m[2], m[3], int(m[4])
        if not (lo <= y <= hi):
            continue
        asof = f"{y}-{mo}-{dd}"
        d = pd.read_csv(f)
        d.insert(0, "asof", asof)
        d.insert(1, "year", y)
        d.insert(2, "n_per_sector", n)
        # the file is already sorted by score, so position is the pick order
        d.insert(3, "pick", range(1, len(d) + 1))
        r = res.get((asof, n), {})
        d["basket_ret"] = r.get("ret")
        d["pool_ret"] = r.get("pool_mean")
        d["basket_pctile"] = r.get("pctile")
        d["basket_p"] = r.get("p")
        d["days_held"] = r.get("days_held")
        d["partial_window"] = r.get("partial")
        if r.get("pool_mean") is not None:
            d["excess_vs_pool"] = d.ret - r["pool_mean"]
        frames.append(d)

    if not frames:
        raise SystemExit("  no picks_*.csv matched")

    d = pd.concat(frames, ignore_index=True)
    d = d.sort_values(["year", "n_per_sector", "pick"]).reset_index(drop=True)
    out = HERE / a.out
    d.to_csv(out, index=False)

    baskets = d.groupby(["year", "n_per_sector"]).size()
    print(f"  {len(d):,} holdings across {len(baskets)} baskets "
          f"({d.year.min()}-{d.year.max()}, widths {sorted(d.n_per_sector.unique())})")
    print(f"  distinct companies ever held: {d.ticker.nunique():,}")
    miss = int(d.ret.isna().sum())
    if miss:
        print(f"  holdings with no return recorded: {miss}")
    print(f"\n  {'year':>6}" + "".join(f"{f'N={n}':>9}" for n in sorted(d.n_per_sector.unique())))
    piv = d.pivot_table(index="year", columns="n_per_sector", values="ticker",
                        aggfunc="count")
    for y, row in piv.iterrows():
        print(f"  {y:>6}" + "".join(f"{int(v) if pd.notna(v) else 0:>9}" for v in row))
    print(f"\n  wrote {out.name}")


if __name__ == "__main__":
    main()
