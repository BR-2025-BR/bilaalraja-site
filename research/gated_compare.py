#!/usr/bin/env python3
"""Same criteria, two rebalancing frequencies, against the S&P.

    python3 research/gated_compare.py

Both runs span the identical window -- first formation January 2014, final exit
January 2026 -- so the only difference is how often the book is rebuilt.

  annual     formed each January, held twelve months, a holding returning
             under 8% over its year is sold
  quarterly  formed each quarter, held three months, a holding returning under
             2% over its quarter is sold (2% a quarter compounds to about 8% a
             year, so the hurdle means the same thing at both frequencies)

Everything else is common: the six gates, the top 25 by composite score, equal
weight at entry, winners never trimmed, a name kept only if it is also in the
next period's top 25, and cash from sales split equally among the names not
already held.

Gross of costs, deliberately and consistently with the rest of this project.
The quarterly version trades roughly four times as often on a book where a third
of holdings sit below $1bn, so read its margin as an upper bound.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pipeline"))
os.environ.setdefault("GATED25_FROM", "2014")

import numpy as np                                          # noqa: E402
import pandas as pd                                         # noqa: E402

TOP_N = 25
START = 100_000.0


def dates_for(freq):
    """Formation dates, plus the final exit both runs share."""
    if freq == "A":
        d = [f"{y}-01-01" for y in range(2014, 2026)]
    else:
        d = [f"{y}-{m:02d}-01" for y in range(2014, 2026) for m in (1, 4, 7, 10)]
        d = [x for x in d if x <= "2025-10-01"]
    return d, "2026-01-01"


def load(dates, final, CACHE):
    need = dates + [final]
    panels = {}
    for d in need:
        f = CACHE / f"{d}.parquet"
        if not f.exists():
            return None, d
        panels[d] = pd.read_parquet(f)
    return panels, None


def simulate(freq, cut, px, CACHE, G):
    dates, final = dates_for(freq)
    panels, missing = load(dates, final, CACHE)
    if panels is None:
        return {"missing": missing}
    idx = px.index

    picks, sess = {}, {}
    for d in dates + [final]:
        p = panels[d]
        g = p[(p.model == "operating") & G.passes_gates(p)]
        picks[d] = set(g.sort_values("score", ascending=False).head(TOP_N).ticker)
        sess[d] = idx.searchsorted(pd.Timestamp(p.formed.iloc[0]), side="left")

    holdings, cash, log, trades = {}, START, [], 0
    for i, d in enumerate(dates):
        nxt = dates[i + 1] if i + 1 < len(dates) else final
        a, b = sess[d], min(sess[nxt], len(idx) - 1)

        new = [t for t in picks[d] if t not in holdings]
        if new and cash > 0:
            each = cash / len(new)
            for t in new:
                p0 = G.price_at(px, t, a)
                if p0 is None:
                    continue
                holdings[t] = {"value": each, "entry": p0}
                trades += 1
            cash = 0.0
        start_v = sum(h["value"] for h in holdings.values()) + cash

        rets, dead = {}, []
        for t, h in list(holdings.items()):
            p1, gone = G.exit_price(px, t, a, b)
            if p1 is None:
                rets[t] = 0.0
                continue
            r = (p1 / h["entry"] - 1) * 100
            rets[t] = r
            h["value"] *= 1 + r / 100
            if gone:
                dead.append(t)
        end_v = sum(h["value"] for h in holdings.values()) + cash

        keep = picks[nxt]
        for t in list(holdings):
            r = rets.get(t, 0.0)
            if t in dead or r < cut or t not in keep:
                cash += holdings[t]["value"]
                del holdings[t]
                trades += 1
        log.append({"d": d, "formed": str(idx[a].date()), "exit": str(idx[b].date()),
                    "n": len(picks[d]), "start": start_v, "end": end_v,
                    "ret": (end_v / start_v - 1) * 100 if start_v else 0.0,
                    "held": len(holdings)})

    final_v = sum(h["value"] for h in holdings.values()) + cash
    return {"log": log, "final": final_v, "trades": trades,
            "first": log[0]["formed"], "last": log[-1]["exit"]}


def main():
    import gated25 as G
    from prices import closes
    CACHE = G.CACHE

    qd, qf = dates_for("Q")
    have = {p.stem for p in CACHE.glob("*.parquet")}
    miss = [d for d in qd + [qf] if d not in have]
    if miss:
        raise SystemExit(f"  {len(miss)} quarterly panels still missing, first {miss[0]}\n"
                         f"  run: python3 research/build_quarters.py 2014 2026")

    tk, _ = G.AB.load_inputs()
    syms = sorted(t for t in tk.ticker.unique() if isinstance(t, str) and t)
    px = closes(syms, "2013-11-01", "2026-03-31").sort_index()

    out = {}
    for freq, cut, lab in (("A", 8.0, "annual, 8% cut"), ("Q", 2.0, "quarterly, 2% cut")):
        r = simulate(freq, cut, px, CACHE, G)
        out[freq] = r
        n = len(r["log"])
        mult = r["final"] / START
        yrs = 12
        print(f"\n  {lab}: {n} formations, {r['trades']} trades")
        print(f"    {START:,.0f} -> {r['final']:,.0f}   "
              f"{(mult-1)*100:+.1f}%  ({(mult**(1/yrs)-1)*100:+.2f}%/yr)")

    spy = pd.read_parquet(os.path.join(HERE, "spy.parquet")).sort_values("date").reset_index(drop=True)
    d0 = pd.Timestamp(out["A"]["log"][0]["formed"])
    d1 = pd.Timestamp(out["A"]["log"][-1]["exit"])
    i = np.searchsorted(spy.date.values, np.datetime64(d0), "left")
    j = np.searchsorted(spy.date.values, np.datetime64(d1), "right") - 1
    s = float(spy.close.iloc[j] / spy.close.iloc[i])
    print(f"\n  S&P 500 {d0.date()} to {d1.date()}")
    print(f"    {START:,.0f} -> {START*s:,.0f}   {(s-1)*100:+.1f}%  ({(s**(1/12)-1)*100:+.2f}%/yr)")

    out["spy"] = {"mult": s, "final": START * s}
    json.dump(out, open(os.path.join(HERE, "gated_compare.json"), "w"),
              indent=1, default=float)
    print("\n  wrote gated_compare.json")


if __name__ == "__main__":
    main()
