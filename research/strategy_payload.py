#!/usr/bin/env python3
"""Build the JSON the dashboard's strategy chart reads.

Joins three things per year: the basket-level backtest result, the holdings that
made up that basket, and what the S&P 500 did over the identical two sessions.

    python3 research/strategy_payload.py --results asof_results_2019_2025.json \
        --width 10 --out strategy_results.json

WHY SPY AND NOT ^GSPC. Basket returns come from adjusted closes, so dividends are
reinvested. The bare index is price-only and would understate the benchmark by
roughly 1.8% a year, which is most of the gap being argued about. SPY with
auto_adjust is the like-for-like series.

WHY THE S&P IS THE WEAKER TEST. It answers "would an index fund have done
better", which is worth knowing, but a basket drawn from this universe is
smaller-cap than the S&P, so beating it can be a size tilt rather than skill.
The random-basket band is the comparison that isolates the choosing. Both are
carried here; the chart shows both.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def spy_return(spy, d0, d1):
    """Total return between the two sessions the basket actually used."""
    if spy is None:
        return None
    idx = spy.date.values
    a = np.searchsorted(idx, np.datetime64(pd.Timestamp(d0)), side="left")
    b = np.searchsorted(idx, np.datetime64(pd.Timestamp(d1)), side="right") - 1
    if a >= len(spy) or b <= a:
        return None
    p0, p1 = spy.close.iloc[a], spy.close.iloc[b]
    return round(float((p1 / p0 - 1) * 100), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="asof_results.json")
    ap.add_argument("--width", type=int, default=10)
    ap.add_argument("--out", default="strategy_results.json")
    ap.add_argument("--top", type=int, default=0,
                    help="holdings to embed per year, 0 = all")
    a = ap.parse_args()

    res = json.loads((HERE / a.results).read_text())
    res = [r for r in res if int(r.get("n_per_sector", a.width)) == a.width]
    if not res:
        raise SystemExit(f"  no rows with n_per_sector={a.width} in {a.results}")

    spyf = HERE / "spy.parquet"
    spy = pd.read_parquet(spyf).sort_values("date").reset_index(drop=True) if spyf.exists() else None
    if spy is None:
        print("  note: spy.parquet absent, the S&P column will be blank")

    out = []
    for r in sorted(res, key=lambda x: str(x["asof"])):
        asof = str(r["asof"])[:10]
        year = asof[:4]
        # the band: exact bootstrap percentiles when the run stored them, else
        # the normal approximation, flagged so the two are never confused
        if r.get("null_p5") is not None:
            lo, hi, exact = r["null_p5"], r["null_p95"], True
        else:
            lo = r["null_mean"] - 1.645 * r["null_sd"]
            hi = r["null_mean"] + 1.645 * r["null_sd"]
            exact = False

        s = spy_return(spy, r["formed"], r["exit"])
        row = {
            "y": year, "formed": r["formed"], "exit": r["exit"],
            "ret": round(r["ret"], 1), "pool": round(r["pool_mean"], 1),
            "ex": round(r["ret"] - r["pool_mean"], 1),
            "spy": s, "vs_spy": None if s is None else round(r["ret"] - s, 1),
            "pct": round(r["pctile"], 1), "p": r["p"], "n": int(r["picks"]),
            "lo": round(lo, 1), "hi": round(hi, 1), "nm": round(r["null_mean"], 1),
            "band_exact": exact,
            "days": r.get("days_held"), "partial": bool(r.get("partial", False)),
        }

        f = HERE / f"picks_{asof}_n{a.width}.csv"
        holds = []
        if f.exists():
            d = pd.read_csv(f).sort_values("score", ascending=False)
            if a.top:
                d = d.head(a.top)
            for x in d.itertuples():
                holds.append({
                    "t": x.ticker,
                    "n": (x.name if isinstance(x.name, str) else "")[:42],
                    "s": x.sector,
                    "sc": round(float(x.score), 1),
                    "r": None if pd.isna(x.ret) else round(float(x.ret), 1),
                })
        else:
            print(f"  note: {f.name} missing, {year} will have no holdings")
        row["h"] = holds
        out.append(row)

    (HERE / a.out).write_text(json.dumps(out, separators=(",", ":")))
    kb = (HERE / a.out).stat().st_size / 1024
    print(f"  {len(out)} years, width {a.width}, "
          f"{sum(len(r['h']) for r in out):,} holdings embedded  ({kb:.0f} KB)")
    print(f"\n  {'year':>6}{'basket':>9}{'S&P 500':>10}{'vs S&P':>9}"
          f"{'pool':>8}{'vs pool':>9}{'pctile':>8}{'held':>7}")
    for r in out:
        sp = "n/a" if r["spy"] is None else f"{r['spy']:+.1f}%"
        vs = "n/a" if r["vs_spy"] is None else f"{r['vs_spy']:+.1f}pp"
        flag = "  PARTIAL" if r["partial"] else ""
        print(f"  {r['y']:>6}{r['ret']:>+8.1f}%{sp:>10}{vs:>9}"
              f"{r['pool']:>+7.1f}%{r['ex']:>+8.1f}pp{r['pct']:>8.1f}{r['n']:>7}{flag}")
    print(f"\n  wrote {a.out}")


if __name__ == "__main__":
    main()
