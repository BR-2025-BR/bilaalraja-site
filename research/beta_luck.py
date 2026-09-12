#!/usr/bin/env python3
"""Test the beta-capped book against luck, by calendar year.

The Russell 3000 dashboard used to carry a luck test built around the annual
top-by-score basket. This rebuilds the SAME test around the beta-capped book
instead: for every calendar year the book was live, does the book's realised
return beat what random selection of the same size, from the same companies,
over the same quarters, would have produced?

The book is quarterly (four overlapping ~3-month sleeves a year), so the null
is compounded to match: for each quarter draw a random basket of the book's own
holding-count from that quarter's scored universe, compound the four quarters
into a random "book-year", and repeat 2,000 times. The book's actual year comes
from its own equity curve; the S&P from the reference curve the book carries.

    python3 research/beta_luck.py            # writes beta_strategy_results.json

The eligible pool each quarter is the scored panel already cached under
research/gated25_panels/ -- the companies the book was choosing among -- so the
comparison isolates the choosing, exactly as the original test did.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
from prices import closes  # noqa: E402

PANELS = HERE / "gated25_panels"
BOOK_HTML = HERE.parent / "pipeline" / "beta_book.html"
N_DRAWS = 2000
SEED = 7


def load_book():
    t = BOOK_HTML.read_text()
    Q = json.loads(re.search(r"const\s+Q\s*=\s*(\[.*?\])\s*;", t, re.S).group(1))
    return Q


def pool_returns(tickers, formed, exit_):
    """Forward return, formed -> exit, for every priced name in the pool.

    A name that stops trading inside the window is taken at its last traded
    price, which is how the book itself treats a delisting -- the money came
    back at the last print rather than vanishing.
    """
    formed, exit_ = pd.Timestamp(formed), pd.Timestamp(exit_)
    syms = sorted({t for t in tickers if isinstance(t, str) and t})
    px = closes(syms, (formed - pd.Timedelta(days=12)).strftime("%Y-%m-%d"),
                (exit_ + pd.Timedelta(days=6)).strftime("%Y-%m-%d"))
    if px.empty:
        return np.array([])
    idx = px.index
    a = idx.searchsorted(formed, side="left")          # first session on/after formed
    b = idx.searchsorted(exit_, side="right") - 1       # last session on/before exit
    if a >= len(idx) or b <= a:
        return np.array([])
    out = []
    win = px.iloc[a:b + 1]
    first = win.iloc[0]
    for c in win.columns:
        p0 = first[c]
        if not np.isfinite(p0) or p0 <= 0:
            continue
        col = win[c].to_numpy()
        col = col[np.isfinite(col)]
        if col.size < 2:
            continue
        p1 = col[-1]                                     # last traded price in window
        out.append(p1 / p0 - 1.0)
    return np.array(out) * 100.0                         # per cent


def main():
    Q = load_book()
    rng = np.random.default_rng(SEED)

    # index formations by calendar year of their formation date
    by_year = {}
    for q in Q:
        by_year.setdefault(q["d"][:4], []).append(q)
    for y in by_year:
        by_year[y].sort(key=lambda q: q["d"])

    rows = []
    years = sorted(by_year)
    for y in years:
        qs = by_year[y]
        full = len(qs) == 4
        # book's own year return, straight off the equity curve
        book_year = qs[-1]["end"] / qs[0]["start"] - 1.0
        # S&P over the same span, from the book's reference curve
        spy0 = qs[0]["spy"]
        nxt = by_year.get(str(int(y) + 1))
        spy1 = nxt[0]["spy"] if nxt else qs[-1]["spy"] * (qs[-1]["end"] / qs[-1]["start"])
        spy_year = spy1 / spy0 - 1.0 if spy0 else None

        # per-quarter random draws, then compound four quarters into 2,000 books
        rand = np.ones(N_DRAWS)
        pool_curve = 1.0
        held_days = 0
        ok = True
        for q in qs:
            pan = pd.read_parquet(PANELS / f"{q['d']}.parquet")
            pool = pool_returns(pan.ticker.tolist(), q["formed"], q["exit"])
            n = int(q["n"])
            if pool.size < max(n, 5):
                ok = False
                break
            draws = np.array([rng.choice(pool, n, replace=False).mean()
                              for _ in range(N_DRAWS)]) / 100.0
            rng.shuffle(draws)                            # de-correlate the sleeves
            rand *= (1.0 + draws)
            pool_curve *= (1.0 + pool.mean() / 100.0)
            held_days += (pd.Timestamp(q["exit"]) - pd.Timestamp(q["formed"])).days
        if not ok:
            print(f"  {y}: pool too thin, skipped")
            continue

        rand_year = rand - 1.0                            # 2,000 random book-years
        pool_year = pool_curve - 1.0
        pct = float((rand_year < book_year).mean() * 100)
        p = float((rand_year >= book_year).mean())

        # holdings held during the year: union across quarters, compounded
        held = {}
        for q in qs:
            for h in q.get("rows", []):
                d = held.setdefault(h["t"], {"t": h["t"], "n": h.get("name", ""),
                                             "s": h.get("sec", ""), "sc": h.get("sc"),
                                             "beta": h.get("beta"), "mult": 1.0, "qn": 0})
                d["mult"] *= (1.0 + (h.get("ret") or 0) / 100.0)
                d["qn"] += 1
                if h.get("sc") is not None and (d["sc"] is None or h["sc"] > d["sc"]):
                    d["sc"] = h["sc"]
        holds = []
        for d in held.values():
            holds.append({"t": d["t"], "n": (d["n"] or "")[:42], "s": d["s"],
                          "sc": None if d["sc"] is None else round(d["sc"], 1),
                          "beta": d["beta"],
                          "r": round((d["mult"] - 1.0) * 100, 1), "q": d["qn"]})
        holds.sort(key=lambda h: (h["sc"] is not None, h["sc"] or 0), reverse=True)

        rows.append({
            "y": y, "formed": qs[0]["formed"], "exit": qs[-1]["exit"],
            "ret": round(book_year * 100, 1),
            "pool": round(pool_year * 100, 1),
            "ex": round((book_year - pool_year) * 100, 1),
            "spy": None if spy_year is None else round(spy_year * 100, 1),
            "vs_spy": None if spy_year is None else round((book_year - spy_year) * 100, 1),
            "pct": round(pct, 1),
            "p": round(p, 4),
            "n": len(holds),
            "lo": round(float(np.percentile(rand_year, 5)) * 100, 1),
            "hi": round(float(np.percentile(rand_year, 95)) * 100, 1),
            "nm": round(float(rand_year.mean()) * 100, 1),
            "band_exact": True,
            "days": held_days,
            "partial": not full,
            "h": holds,
        })

    out = HERE / "beta_strategy_results.json"
    out.write_text(json.dumps(rows, separators=(",", ":")))
    print(f"\n  {len(rows)} years -> {out.name} ({out.stat().st_size/1024:.0f} KB)\n")
    hdr = f"  {'year':>6}{'book':>9}{'S&P':>9}{'vs S&P':>9}{'pool':>8}{'excess':>9}{'pctile':>8}{'p':>8}{'names':>7}"
    print(hdr)
    for r in rows:
        sp = "n/a" if r["spy"] is None else f"{r['spy']:+.1f}%"
        vs = "n/a" if r["vs_spy"] is None else f"{r['vs_spy']:+.1f}pp"
        flag = "  PARTIAL" if r["partial"] else ""
        print(f"  {r['y']:>6}{r['ret']:>+8.1f}%{sp:>9}{vs:>9}{r['pool']:>+7.1f}%"
              f"{r['ex']:>+8.1f}pp{r['pct']:>8.1f}{r['p']:>8.3f}{r['n']:>7}{flag}")

    # whole-period summary for the write-up
    full = [r for r in rows if not r["partial"]]
    def comp(key):
        m = 1.0
        for r in full:
            if r[key] is not None:
                m *= (1.0 + r[key] / 100.0)
        return (m - 1.0) * 100
    print(f"\n  full years: {full[0]['y']}-{full[-1]['y']} ({len(full)})")
    print(f"  book compounded : {comp('ret'):+.0f}%")
    print(f"  pool compounded : {comp('pool'):+.0f}%")
    print(f"  S&P  compounded : {comp('spy'):+.0f}%")
    beat_spy = sum(1 for r in full if r['vs_spy'] is not None and r['vs_spy'] > 0)
    cleared = sum(1 for r in full if r['ret'] > r['hi'])
    print(f"  years beating S&P : {beat_spy}/{len(full)}")
    print(f"  years clearing the luck band : {cleared}/{len(full)}")
    print(f"  median percentile vs luck : {np.median([r['pct'] for r in full]):.0f}")
    # $10k outcomes
    b = 10000 * (1 + comp('ret') / 100)
    s = 10000 * (1 + comp('spy') / 100)
    print(f"  $10k -> book ${b:,.0f} | S&P ${s:,.0f}")


if __name__ == "__main__":
    main()
