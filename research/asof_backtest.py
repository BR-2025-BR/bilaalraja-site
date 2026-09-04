#!/usr/bin/env python3
"""Score the composite at a past date and hold the result for twelve months.

Survivorship-free by construction, which is the whole point and the thing every
earlier version of this got wrong:

  * the universe at date D is every company that had a PRICE on D and had FILED
    fundamentals by D. It is not today's constituent list rolled backwards, so a
    company that delisted in 2021 is eligible at 1 January 2020 exactly as it
    was at the time.
  * share counts are the ones stated on filings made strictly before D, so
    market cap cannot use a number nobody had yet.
  * returns come from a feed that keeps delisted tickers, so a company is
    eligible on the day it was actually investable rather than only if it
    survived to today.

    NOTE what this does NOT do. It reads closes(), not panel(), so no delisting
    return is applied: a holding that stops trading inside the window ends with
    no return and drops out of the basket average. The pool it is compared with
    is built the same way and loses the same names, so this is not the usual
    survivorship error -- but the two sides need not lose them at the same RATE,
    and the composite favours cheap, cash-generative, strong-balance-sheet
    companies, which is also the acquisition-target profile. Most of the names
    lost this way were takeovers, which carry a premium. Switching to panel()
    would price them at the -30% convention, which is right for a bankruptcy and
    badly wrong for a takeover, so neither treatment is obviously correct and
    the honest thing is to say which one is in force. It is this one.

The comparison that matters is not the index. A basket drawn from this universe
is small-cap tilted, so beating SPY may say nothing about the composite. Each
basket is therefore also tested against random selections of the same size from
the same universe on the same date.

    python3 research/asof_backtest.py 2019-01-01 2020-01-01 ...
"""
import importlib.util, json, os, sys, time, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent / "pipeline"
sys.path.insert(0, str(PIPE))

WIDTHS = [1, 3, 5, 10, 20]        # names per sector, all from one panel build
OUT = os.environ.get("ASOF_OUT", "asof_results.json")
HOLD_DAYS = 365
N_DRAWS = 2000
TOP_N_UNIVERSE = 3000


def load_inputs():
    tk = pd.read_parquet(HERE.parent / "prices" / "tickers.parquet")
    tk = tk[tk.cik.notna()].copy()
    tk["cik"] = tk.cik.astype("int64")
    tk["span"] = (pd.to_datetime(tk.lastpricedate, errors="coerce")
                  - pd.to_datetime(tk.firstpricedate, errors="coerce")).dt.days
    tk = tk.sort_values("span", ascending=False).drop_duplicates("cik", keep="first")
    sh = pd.read_parquet(HERE / "shares.parquet")
    return tk, sh


def universe_at(asof, tk, sh, px):
    """Everything priced on the date with fundamentals already filed."""
    asof = pd.Timestamp(asof)
    sess = px.index[px.index <= asof]
    if len(sess) == 0:
        return None, None
    day = sess[-1]
    prices = px.loc[day].dropna()

    s = sh[sh.filed < asof].sort_values("filed").groupby("cik").tail(1)
    u = tk[["cik", "ticker", "name", "siccode"]].merge(s[["cik", "shares"]], on="cik")
    u = u[u.ticker.isin(prices.index)].copy()
    u["price"] = u.ticker.map(prices)
    u["mcap"] = u.price * u.shares / 1e9                 # $bn
    u = u[(u.mcap > 0.05) & u.price.gt(0)]
    u = u.sort_values("mcap", ascending=False).head(TOP_N_UNIVERSE).reset_index(drop=True)
    u["rank"] = np.arange(1, len(u) + 1)
    # Sector must come from the pipeline's own SIC mapping, not the vendor's
    # taxonomy. The composite ranks within sector, so a different partition is a
    # different score, and the point is to test the method as it actually runs.
    import sectors as SEC
    u["sic"] = pd.to_numeric(u.siccode, errors="coerce")
    u["sector"] = [SEC.sector_for_ticker(sc, tkr) if pd.notna(sc) else "Unclassified"
                   for sc, tkr in zip(u.sic, u.ticker)]
    return u, day


def build_panel(u, asof):
    """Run the production per-company build with facts hidden after `asof`."""
    import r3k_facts as F
    F.AS_OF = pd.Timestamp(asof)
    spec = importlib.util.spec_from_file_location("rb", PIPE / "r3k_build.py")
    rb = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(rb)
    except SystemExit:
        pass
    # The staleness gate is hardcoded for today. Anchored to the as-of date it
    # means the same thing it always meant: the newest TTM must be recent
    # relative to when the decision is being made.
    rb.STALE_BEFORE = (pd.Timestamp(asof) - pd.DateOffset(months=12)).strftime("%Y-%m-%d")

    rows, why = [], {}
    for rec in u.to_dict("records"):
        try:
            row, reason = rb.one(rec)
        except Exception as e:
            row, reason = None, type(e).__name__
        if row is not None:
            rows.append(row)
        else:
            why[reason] = why.get(reason, 0) + 1
    return pd.DataFrame(rows), why


def score(panel):
    spec = importlib.util.spec_from_file_location("sc", PIPE / "score.py")
    sc = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(sc)
    except SystemExit:
        pass
    return sc.build(panel)


def forward_return(tickers, start_day, px, days=HOLD_DAYS):
    end = start_day + pd.Timedelta(days=days)
    idx = px.index
    a = idx.searchsorted(start_day, side="left")
    b = min(idx.searchsorted(end, side="right") - 1, len(idx) - 1)
    if b <= a:
        return pd.Series(dtype=float), None
    p0, p1 = px.iloc[a], px.iloc[b]
    r = (p1 / p0 - 1) * 100
    r = r[np.isfinite(r)]
    return r[r.index.isin(tickers)], idx[b]


def run_one(asof, tk, sh, px):
    u, day = universe_at(asof, tk, sh, px)
    if u is None:
        print(f"  {asof}: no sessions on or before this date"); return None
    t0 = time.time()
    panel, why = build_panel(u, asof)
    if panel.empty:
        top = sorted(why.items(), key=lambda kv: -kv[1])[:3]
        print(f"  {asof}: panel empty. {top}"); return None
    scored = score(panel)
    scored = scored[scored.score.notna() & scored.sector.notna()]

    pool, endday = forward_return(scored.ticker.tolist(), day, px)
    if len(pool) < 50:
        print(f"  {asof}: only {len(pool)} priced in the pool"); return None
    rng = np.random.default_rng(7)

    out = []
    for N in WIDTHS:
        picks = (scored.sort_values("score", ascending=False)
                       .groupby("sector").head(N))
        r, _ = forward_return(picks.ticker.tolist(), day, px)
        if len(r) < 5:
            continue
        n = len(r)
        # the null must match the basket's size: a random 120 is less variable
        # than a random 12 by averaging alone, so comparing across sizes would
        # reward width for arithmetic reasons rather than selection ones
        draws = np.array([rng.choice(pool.values, n, replace=False).mean()
                          for _ in range(N_DRAWS)])
        hold = picks[["ticker", "name", "sector", "score", "mcap"]].copy()
        hold["ret"] = hold.ticker.map(r)
        hold.sort_values("score", ascending=False).to_csv(
            HERE / f"picks_{str(asof)[:10]}_n{N}.csv", index=False)
        held = (endday - day).days
        out.append({"asof": str(asof), "formed": str(day.date()),
                    "exit": str(endday.date()), "days_held": int(held),
                    "partial": bool(held < HOLD_DAYS - 20), "n_per_sector": N,
                    "universe": int(len(u)), "scored": int(len(scored)),
                    "picks": int(n), "ret": float(r.mean()),
                    "median": float(r.median()), "pool_mean": float(pool.mean()),
                    "null_mean": float(draws.mean()), "null_sd": float(draws.std()),
                    # the actual 5th/95th of the draws, not mean +/- 1.645 sd:
                    # the bootstrap distribution is not obliged to be normal and
                    # the chart draws this band directly
                    "null_p5": float(np.percentile(draws, 5)),
                    "null_p95": float(np.percentile(draws, 95)),
                    "pctile": float((draws < r.mean()).mean() * 100),
                    "p": float((draws >= r.mean()).mean()),
                    "secs": round(time.time() - t0)})
        print(f"  {str(asof)[:10]}  N={N:<3} picks {n:>3}  ret {r.mean():>+7.1f}%  "
              f"pool {pool.mean():>+6.1f}%  excess {r.mean()-pool.mean():>+6.1f}pp  "
              f"pctile {out[-1]['pctile']:>5.1f}  p {out[-1]['p']:.3f}", flush=True)
    return out

def main():
    dates = sys.argv[1:] or [f"{y}-01-01" for y in range(2019, 2026)]
    tk, sh = load_inputs()
    from prices import closes
    lo = (pd.Timestamp(min(dates)) - pd.Timedelta(days=40)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(max(dates)) + pd.Timedelta(days=430)).strftime("%Y-%m-%d")
    print(f"  loading prices {lo} to {hi} ...", flush=True)
    # a handful of tickers table rows carry a null symbol; drop them before
    # sorting rather than letting a None reach the comparison
    syms = sorted(t for t in tk.ticker.unique() if isinstance(t, str) and t)
    px = closes(syms, lo, hi).sort_index()
    print(f"  price matrix {px.shape[0]:,} sessions x {px.shape[1]:,} tickers\n", flush=True)

    out = [x for d in dates for x in (run_one(d, tk, sh, px) or [])]
    if out:
        pd.DataFrame(out).to_json(HERE / OUT, orient="records", indent=1)
        d = pd.DataFrame(out)
        if d.partial.any():
            part = sorted(d[d.partial].asof.str[:10].unique())
            print(f"\n  PARTIAL windows, returns not comparable with a full year: "
                  f"{', '.join(part)}")
        print(f"\n  {'N':>4}{'windows':>9}{'mean excess':>13}{'median pctile':>15}{'p<0.05':>9}")
        full = d[~d.partial]
        for N, g in full.groupby("n_per_sector"):
            ex = (g.ret - g.pool_mean)
            print(f"  {N:>4}{len(g):>9}{ex.mean():>+12.2f}pp{g.pctile.median():>14.0f}"
                  f"{int((g.p<0.05).sum()):>6} /{len(g)}")
        print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
