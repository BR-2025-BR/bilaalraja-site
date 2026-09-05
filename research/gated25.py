#!/usr/bin/env python3
"""Six quality gates, top 25 by score, held a year, losers cut at 8%.

    phase 1   python3 research/gated25.py panels        ~9 min per January
    phase 2   python3 research/gated25.py run

Phase 1 builds and caches the point-in-time scored panel for each January so the
portfolio rules can be changed and re-run in seconds. Rebuilding a panel takes
minutes; re-simulating takes none, and the rules are the part likely to change.

THE RULES, as specified:

  * gates    revenue growth >= 20%, net income > 0, free cash flow > 0,
             ROIC >= 10%, net debt <= 3x EBITDA, FCF conversion >= 50%
  * picks    the 25 highest composite scores among those passing, no sector cap
  * weight   equal at inception
  * hold     twelve months
  * cut      a holding returning under 8% over its year is sold outright
  * carry    a holding returning 8% or more is kept ONLY if it is in the new
             top 25, and is never trimmed -- it keeps whatever it grew to
  * cash     everything sold is redeployed, split equally among the names in the
             new 25 that are not already held
  * re-entry a name sold under the 8% rule may be bought again later

Returns come from adjusted closes, so dividends are in. A holding that stops
trading inside its year is liquidated at its last traded price rather than
dropped, which is the honest treatment: the money came back, at whatever the
last print was.
"""
import json
import os
import sys

# multiprocessing imports the stdlib signal while spawning; load it before this
# directory can shadow it (see quarterly_backtest.py for the full story)
import signal            # noqa: F401
import multiprocessing

import warnings          # noqa: E402
from pathlib import Path # noqa: E402

warnings.filterwarnings("ignore")
import numpy as np       # noqa: E402
import pandas as pd      # noqa: E402

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent / "pipeline"
sys.path.insert(0, str(PIPE))
import asof_backtest as AB                                   # noqa: E402
from quarterly_backtest import build_panel_parallel          # noqa: E402

CACHE = HERE / "gated25_panels"
# 2014 is where SEC XBRL breadth becomes comparable with today; before that the
# universe is mostly large filers and the gates would be screening a different
# market. The last window exits Jan 2026.
YEAR0 = int(os.environ.get("GATED25_FROM", "2019"))
DATES = [f"{y}-01-01" for y in range(YEAR0, 2026)]
TOP_N = 25
CUT = 8.0                                             # per cent, over the year
START_CAPITAL = 100_000.0


# ------------------------------------------------------------------ gates
def passes_gates(d):
    """Six gates, with 'no figure' treated as failure, matching the dashboard.

    The site's screen classes a missing figure as unknown and drops it, which is
    the same outcome as failing for anything that has to be picked. Stated here
    so it is a decision rather than an accident.
    """
    ok = (d.growth >= 20) & (d.ni > 0) & (d.fcf > 0) & (d.roic >= 10) & (d.fcf_conv >= 50)
    # net debt is the negation of net cash; more cash than debt clears any ceiling
    lev = np.where(d.netcash >= 0, True,
                   np.where(d.ebitda > 0, (-d.netcash) / d.ebitda.replace(0, np.nan) <= 3, False))
    return (ok & pd.Series(lev, index=d.index)).fillna(False)


def price_window():
    """Two months before the first formation, a year after the last exit."""
    lo = (pd.Timestamp(min(DATES)) - pd.DateOffset(months=2)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(max(DATES)) + pd.DateOffset(months=21)).strftime("%Y-%m-%d")
    return lo, hi


def build_panels(workers):
    CACHE.mkdir(exist_ok=True)
    tk, sh = AB.load_inputs()
    from prices import closes
    syms = sorted(t for t in tk.ticker.unique() if isinstance(t, str) and t)
    lo, hi = price_window()
    px = closes(syms, lo, hi).sort_index()
    print(f"  price matrix {px.shape[0]:,} x {px.shape[1]:,}\n", flush=True)
    for asof in DATES:
        f = CACHE / f"{asof}.parquet"
        if f.exists():
            print(f"  {asof} cached, skipping", flush=True)
            continue
        u, day = AB.universe_at(pd.Timestamp(asof), tk, sh, px)
        if u is None or not len(u):
            print(f"  {asof}: no universe -- price history does not reach this date")
            continue
        panel, why = build_panel_parallel(u, pd.Timestamp(asof), workers)
        if panel.empty:
            print(f"  {asof} EMPTY {sorted(why.items(), key=lambda k: -k[1])[:2]}")
            continue
        scored = AB.score(panel)
        scored = scored[scored.score.notna() & scored.sector.notna()].copy()
        scored["formed"] = str(day.date())
        scored.to_parquet(f, index=False)
        g = scored[(scored.model == "operating") & passes_gates(scored)]
        print(f"  {asof}: {len(scored):,} scored, {len(g)} pass all six gates "
              f"-> taking {min(TOP_N, len(g))}", flush=True)


# -------------------------------------------------------------- portfolio
def price_at(px, tkr, i):
    """Close on session i, walking forward a few days if it did not trade."""
    if tkr not in px.columns:
        return None
    col = px[tkr].to_numpy()
    for k in range(i, min(i + 6, len(col))):
        if np.isfinite(col[k]):
            return float(col[k])
    return None


def exit_price(px, tkr, a, b):
    """Last traded close at or before session b. Returns (price, delisted)."""
    if tkr not in px.columns:
        return None, False
    col = px[tkr].to_numpy()
    for k in range(b, a, -1):
        if np.isfinite(col[k]):
            # more than a fortnight of silence before the exit means it stopped
            return float(col[k]), (b - k) > 10
    return None, False


def run():
    from prices import closes
    tk, _ = AB.load_inputs()
    syms = sorted(t for t in tk.ticker.unique() if isinstance(t, str) and t)
    lo, hi = price_window()
    px = closes(syms, lo, hi).sort_index()
    idx = px.index

    panels = {}
    for asof in DATES:
        f = CACHE / f"{asof}.parquet"
        if not f.exists():
            raise SystemExit(f"  {f.name} missing -- run `gated25.py panels` first")
        panels[asof] = pd.read_parquet(f)

    picks_by_year, sess = {}, {}
    for asof in DATES:
        d = panels[asof]
        g = d[(d.model == "operating") & passes_gates(d)]
        g = g.sort_values("score", ascending=False).head(TOP_N)
        picks_by_year[asof] = g.set_index("ticker")
        sess[asof] = idx.searchsorted(pd.Timestamp(d.formed.iloc[0]), side="left")

    # the exit session for each year is the entry session of the next January,
    # and for the last year it is the first session on or after Jan 2026
    exits = {}
    for i, asof in enumerate(DATES):
        nxt = DATES[i + 1] if i + 1 < len(DATES) else "2026-01-01"
        exits[asof] = idx.searchsorted(pd.Timestamp(nxt), side="left")

    holdings, cash = {}, START_CAPITAL
    log, trades = [], []
    for i, asof in enumerate(DATES):
        picks = picks_by_year[asof]
        a, b = sess[asof], min(exits[asof], len(idx) - 1)

        # ---- buy: cash split equally among names not already held
        new = [t for t in picks.index if t not in holdings]
        if new and cash > 0:
            each = cash / len(new)
            for t in new:
                p = price_at(px, t, a)
                if p is None:
                    continue
                holdings[t] = {"value": each, "entry": p, "bought": str(idx[a].date())}
                trades.append({"year": asof[:4], "action": "buy", "ticker": t,
                               "amount": round(each, 2),
                               "score": round(float(picks.loc[t, "score"]), 1)})
            cash = 0.0
        start_value = sum(h["value"] for h in holdings.values()) + cash

        # ---- hold twelve months
        rets, dead = {}, []
        for t, h in list(holdings.items()):
            p1, delisted = exit_price(px, t, a, b)
            if p1 is None:
                rets[t] = 0.0                  # never priced; carried flat
                continue
            r = (p1 / h["entry"] - 1) * 100
            rets[t] = r
            h["value"] *= (1 + r / 100)
            if delisted:
                dead.append(t)

        end_value = sum(h["value"] for h in holdings.values()) + cash
        nxt = DATES[i + 1] if i + 1 < len(DATES) else None
        keep_set = set(picks_by_year[nxt].index) if nxt else set()

        # ---- sell: under the cut, or not in next year's list, or stopped trading
        sold_cut = sold_gone = 0
        for t in list(holdings):
            r = rets.get(t, 0.0)
            reason = None
            if t in dead:
                reason = "delisted"
            elif r < CUT:
                reason = "under 8%"
                sold_cut += 1
            elif nxt is None:
                reason = "end of test"
            elif t not in keep_set:
                reason = "not in next 25"
                sold_gone += 1
            if reason or nxt is None:
                cash += holdings[t]["value"]
                trades.append({"year": asof[:4], "action": "sell", "ticker": t,
                               "amount": round(holdings[t]["value"], 2),
                               "ret": round(r, 1),
                               "reason": reason or "end of test"})
                del holdings[t]

        carried = len(holdings)
        log.append({
            "year": asof[:4], "formed": str(idx[a].date()), "exit": str(idx[b].date()),
            "picks": int(len(picks)), "gate_pass": int(((panels[asof].model == "operating")
                                                        & passes_gates(panels[asof])).sum()),
            "start": round(start_value, 2), "end": round(end_value, 2),
            "ret": round((end_value / start_value - 1) * 100, 2) if start_value else None,
            "carried": carried, "sold_cut": sold_cut, "sold_gone": sold_gone,
            "delisted": len(dead),
            "median_ret": round(float(np.median(list(rets.values()))), 1) if rets else None,
        })
        print(f"  {asof[:4]}  picks {len(picks):>2}  "
              f"{start_value:>12,.0f} -> {end_value:>12,.0f}  "
              f"{log[-1]['ret']:>+7.2f}%   carried {carried:>2}  "
              f"cut {sold_cut:>2}  rotated {sold_gone:>2}", flush=True)

    final = sum(h["value"] for h in holdings.values()) + cash
    # ---- benchmark over the identical two sessions
    spy = pd.read_parquet(HERE / "spy.parquet").sort_values("date").reset_index(drop=True)
    d0, d1 = idx[sess[DATES[0]]], idx[min(exits[DATES[-1]], len(idx) - 1)]
    s0 = spy.close.iloc[np.searchsorted(spy.date.values, np.datetime64(d0), "left")]
    s1 = spy.close.iloc[np.searchsorted(spy.date.values, np.datetime64(d1), "right") - 1]
    spy_ret = float(s1 / s0 - 1) * 100

    out = {"log": log, "trades": trades,
           "start_capital": START_CAPITAL, "final": round(final, 2),
           "total_ret": round((final / START_CAPITAL - 1) * 100, 2),
           "years": len(DATES),
           "annualised": round(((final / START_CAPITAL) ** (1 / len(DATES)) - 1) * 100, 2),
           "spy_ret": round(spy_ret, 2),
           "spy_annualised": round(((1 + spy_ret / 100) ** (1 / len(DATES)) - 1) * 100, 2),
           "first": str(d0.date()), "last": str(d1.date()),
           "holdings_end": [{"t": t, "value": round(h["value"], 2)} for t, h in holdings.items()],
           "cash_end": round(cash, 2)}
    (HERE / "gated25_results.json").write_text(json.dumps(out, indent=1))
    print(f"\n  {START_CAPITAL:,.0f} -> {final:,.0f}   {out['total_ret']:+.1f}% "
          f"({out['annualised']:+.2f}%/yr)")
    print(f"  S&P 500 over the same span: {spy_ret:+.1f}% "
          f"({out['spy_annualised']:+.2f}%/yr)")
    print(f"  wrote gated25_results.json")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "panels":
        build_panels(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    else:
        run()
