#!/usr/bin/env python3
"""Refresh the Russell 3000 panel end to end, with gates.

  python3 refresh.py                incremental: only companies that filed
  python3 refresh.py --full         refetch every companyfacts file
  python3 refresh.py --prices-only  reprice without touching SEC data
  python3 refresh.py --force        promote even if a gate fails

Two failures on the 25 August run motivated this. The first skipped
build_universe_v2, so the panel carried stale prices while the page stamped a
new price date. The second let a rate-limited price fetch drop 471 names,
including several of the largest in the market, without anything complaining.

Both ran to completion and reported success. So the order is enforced here, and
nothing is promoted until it passes the checks at the end.
"""
import argparse, json, subprocess, sys, time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd, requests

HERE  = Path(__file__).resolve().parent
CACHE = Path("/Users/bilaa/Downloads/pitquant/data/cache/edgar")
PY    = sys.executable
UA    = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
STATE = HERE / "refresh_state.json"

def log(msg): print(msg, flush=True)

def step(title):
    log(f"\n{'='*62}\n{title}\n{'='*62}")

def run(script):
    r = subprocess.run([PY, str(HERE/script)], cwd=HERE,
                       capture_output=True, text=True)
    if r.returncode:
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        sys.exit(f"{script} failed with exit {r.returncode}")
    return r.stdout


# ------------------------------------------------------------ 1. which CIKs
def filed_since(start: date):
    """CIKs with a 10-K or 10-Q in the daily index since `start`.

    Refetching 3,000 companyfacts files takes an hour and downloads 3GB. Only
    companies that actually filed can have new fundamentals, and SEC publishes
    exactly that list each weekday.
    """
    ciks, day, today = set(), start, date.today()
    sess = requests.Session(); sess.headers.update(UA)
    days = 0
    while day <= today:
        if day.weekday() < 5:
            q = (day.month - 1) // 3 + 1
            url = (f"https://www.sec.gov/Archives/edgar/daily-index/"
                   f"{day.year}/QTR{q}/master.{day:%Y%m%d}.idx")
            try:
                r = sess.get(url, timeout=45)
                if r.status_code == 200:
                    days += 1
                    for line in r.text.splitlines():
                        p = line.split("|")
                        if len(p) == 5 and p[2] in ("10-K","10-Q","10-K/A","10-Q/A"):
                            ciks.add(int(p[0]))
                elif r.status_code not in (403, 404):
                    log(f"  {day}: HTTP {r.status_code}")
            except Exception as e:
                log(f"  {day}: {type(e).__name__}")
            time.sleep(0.2)
        day += timedelta(days=1)
    log(f"  {days} index days read, {len(ciks)} CIKs filed a 10-K or 10-Q")
    return ciks


def fetch_facts(ciks):
    if not ciks:
        log("  nothing to fetch"); return 0, 0
    sess = requests.Session(); sess.headers.update(UA)
    ok = fail = 0
    for i, cik in enumerate(sorted(ciks), 1):
        for attempt in range(3):
            try:
                time.sleep(0.12)
                r = sess.get(f"https://data.sec.gov/api/xbrl/companyfacts/"
                             f"CIK{cik:010d}.json", timeout=90)
                if r.status_code == 200:
                    (CACHE/f"companyfacts_{cik:010d}.json").write_bytes(r.content)
                    ok += 1; break
                if r.status_code == 404: fail += 1; break
                time.sleep(30 if r.status_code == 429 else 3*(attempt+1))
            except Exception:
                time.sleep(3*(attempt+1))
        else:
            fail += 1
        if i % 50 == 0: log(f"  {i}/{len(ciks)}  ok={ok} fail={fail}")
    log(f"  done: ok={ok} fail={fail}")
    return ok, fail


# ------------------------------------------------------------------ 2. prices
def fetch_prices(tickers, snap):
    """Merge into the existing snapshot; never replace it wholesale.

    The bulk fetch is rate limited often enough that an overwrite can silently
    halve coverage. Merging means a bad run leaves yesterday's price in place
    rather than removing the company from the universe.
    """
    import yfinance as yf
    todo = list(tickers); added = 0
    CH = 60
    for i in range(0, len(todo), CH):
        chunk = todo[i:i+CH]
        for attempt in range(4):
            try:
                d = yf.download(chunk, period="7d", progress=False,
                                auto_adjust=False, threads=False)
                if d is None or d.empty: raise ValueError("empty frame")
                cl = d["Close"] if isinstance(d.columns, pd.MultiIndex) else d[["Close"]]
                if not isinstance(d.columns, pd.MultiIndex): cl.columns = chunk[:1]
                cl = cl.ffill()
                for t in cl.columns:
                    s = cl[t].dropna()
                    if len(s):
                        snap[t] = {"price": float(s.iloc[-1]),
                                   "date": str(s.index[-1])[:10]}
                        added += 1
                break
            except Exception:
                if attempt < 3: time.sleep(10*(attempt+1))
        json.dump(snap, open(HERE/"prices_snapshot.json","w"))
        if (i//CH) % 5 == 0: log(f"  {min(i+CH,len(todo))}/{len(todo)}  priced={added}")
        time.sleep(2)
    return added


# -------------------------------------------------------------------- 3. gates
def gates(prev, now, force):
    """Refuse to promote a build that looks wrong. Each check exists because
    something already went wrong in that exact way."""
    fails, warns = [], []

    if prev:
        d_mcap = (now["total_mcap"] - prev["total_mcap"]) / prev["total_mcap"]
        if abs(d_mcap) > 0.12:
            fails.append(f"total market cap moved {d_mcap:+.1%} "
                         f"(${prev['total_mcap']/1000:.1f}tn -> "
                         f"${now['total_mcap']/1000:.1f}tn)")
        elif abs(d_mcap) > 0.05:
            warns.append(f"total market cap moved {d_mcap:+.1%}")

        d_n = now["n"] - prev["n"]
        if abs(d_n) > 150:
            fails.append(f"company count moved by {d_n:+d} ({prev['n']} -> {now['n']})")
        elif abs(d_n) > 40:
            warns.append(f"company count moved by {d_n:+d}")

        if now["floor"] < prev["floor"] * 0.5:
            fails.append(f"size floor collapsed: ${prev['floor']:.3f}bn -> "
                         f"${now['floor']:.3f}bn (usually means missing prices)")

        if now["priced"] < prev["priced"] - 100:
            fails.append(f"price coverage dropped {prev['priced'] - now['priced']} names")

        if now["price_date"] < prev["price_date"]:
            fails.append(f"price date went backwards: {prev['price_date']} -> {now['price_date']}")

    # A build that used stale prices is worse than one that failed outright,
    # because it looks fine and states a date it did not use.
    if now.get("price_mismatch", 0) > 25:
        fails.append(f"{now['price_mismatch']} companies carry a price that "
                     f"differs from the snapshot: the panel did not use the "
                     f"prices it claims to")

    # A large price move with no split behind it is a real move. A large price
    # move WITH a split means the share count needs to have moved too, and if
    # it has not the market cap is wrong by the ratio.
    sm = now.get("split_mismatch") or []
    if sm:
        # Over a week a few genuine moves of this size are normal, so list them
        # for a look rather than blocking. Many at once means splits are not
        # being applied, which is a pipeline fault rather than a market.
        msg = (f"{len(sm)} companies moved more than a third on an unchanged "
               f"share count: {', '.join(sm[:10])}")
        (fails if len(sm) > 8 else warns).append(msg)

    if now["n"] < 2000:
        fails.append(f"only {now['n']} companies built")
    if now["priced"] < 4000:
        warns.append(f"only {now['priced']} prices in the snapshot")

    for w in warns: log(f"  WARN  {w}")
    for f in fails: log(f"  FAIL  {f}")
    if not fails and not warns: log("  all checks passed")
    if fails and not force:
        sys.exit("\nnot promoted. Investigate, or rerun with --force if you are sure.")
    if fails: log("\n  --force given, promoting anyway")
    return not fails


def measure():
    uni = pd.read_json(HERE/"r3k_universe.json")
    scored = json.load(open(HERE/"r3k_scored.json"))
    snap = json.load(open(HERE/"prices_snapshot.json"))

    # The direct test for the pipeline-order bug: the price the panel actually
    # used must equal the price in the snapshot. Inferring this from market cap
    # does not work, because a build that ignores new prices produces a total
    # identical to last time, which reads as "nothing moved" rather than as a
    # fault. Compare the numbers themselves.
    mismatch = 0
    for _, r in uni.iterrows():
        s = snap.get(r.ticker)
        if s and abs(s["price"] - r.price) > max(0.01, r.price * 1e-6):
            mismatch += 1

    # Compare per company against the previous universe. Where price moved by
    # more than a third and shares did not move at all, a split has almost
    # certainly landed that the share count has not caught up with.
    split_mismatch = []
    prevf = HERE/"r3k_universe.prev.json"
    if prevf.exists():
        pv = pd.read_json(prevf).set_index("ticker")
        for t, r in uni.set_index("ticker").iterrows():
            if t not in pv.index: continue
            a, b = pv.loc[t,"price"], r.price
            sa, sb = pv.loc[t,"shares"], r.shares
            if not a or a <= 0: continue
            ratio = b / a
            if (ratio < 0.66 or ratio > 1.5) and abs(sb - sa) < 1:
                split_mismatch.append(t)

    return {
        "split_mismatch": split_mismatch,
        "price_mismatch": mismatch,
        "n": len(scored),
        "total_mcap": float(uni.mcap.sum()),
        "floor": float(uni.mcap.min()),
        "priced": len(snap),
        "price_date": max(v["date"] for v in snap.values()),
        "built": str(date.today()),
    }


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="refetch every companyfacts file")
    ap.add_argument("--prices-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="promote despite failed gates")
    a = ap.parse_args()

    prev = json.load(open(STATE)) if STATE.exists() else None
    t0 = time.time()
    log(f"refresh starting {datetime.now():%Y-%m-%d %H:%M}")
    if prev: log(f"  last run {prev.get('built')}  "
                 f"{prev['n']} companies  ${prev['total_mcap']/1000:.2f}tn")

    if not a.prices_only:
        step("1. SEC filings")
        uni_ciks = set(int(c) for c in pd.read_json(HERE/"r3k_universe.json").cik)
        if a.full:
            todo = uni_ciks
            log(f"  full refresh: {len(todo)} companies")
        else:
            since = date.fromisoformat(prev["built"]) if prev else date.today()-timedelta(days=7)
            log(f"  reading daily indexes since {since}")
            todo = filed_since(since) & uni_ciks
            log(f"  {len(todo)} of them are in the universe")
        fetch_facts(todo)

    step("2. Prices")
    snap = json.load(open(HERE/"prices_snapshot.json"))
    before = len(snap)
    stage0 = pd.read_json(HERE/"universe_stage0.json")
    extra = json.load(open(HERE/"needs_price.json"))
    want = list(dict.fromkeys(list(stage0.ticker) + [e[1] for e in extra]))
    log(f"  {len(want)} tickers wanted, snapshot holds {before}")
    fetch_prices(want, snap)
    snap = json.load(open(HERE/"prices_snapshot.json"))
    log(f"  snapshot now holds {len(snap)} ({len(snap)-before:+d})")

    step("3. Splits and share counts")
    # A cover-page share count is dated. If the company split after that date,
    # the count no longer matches the shares the quoted price refers to and
    # market cap is wrong by the split ratio. On 25 August three companies
    # split and a fourth did a 1-for-10 reverse, and the build carried
    # post-split prices against pre-split counts.
    run("fetch_splits.py"); log("  splits refreshed")
    run("fetch_shares.py"); log("  share counts refreshed")

    step("4. Universe")
    # keep the previous universe so the checks can compare prices per company
    if (HERE/"r3k_universe.json").exists():
        (HERE/"r3k_universe.prev.json").write_bytes((HERE/"r3k_universe.json").read_bytes())
    out = run("build_universe_v2.py")
    log("  " + out.strip().splitlines()[-1] if out.strip() else "  built")
    r = pd.read_json(HERE/"universe_ranked.json")
    top = r.sort_values("mcap", ascending=False).head(3000).reset_index(drop=True)
    top["rank"] = range(1, len(top)+1)
    top.to_json(HERE/"r3k_universe.json", orient="records", indent=1)
    log(f"  {len(r)} ranked, top 3000 kept, floor ${top.mcap.min():.3f}bn, "
        f"total ${top.mcap.sum()/1000:.2f}tn")

    step("5. Panel")
    log("  parsing companyfacts, this takes about twenty minutes")
    out = run("r3k_build.py")
    log("  " + [l for l in out.splitlines() if l.startswith("built ")][-1])

    step("6. Scores")
    log("  " + run("score.py").strip().splitlines()[0])

    step("7. Checks")
    now = measure()
    ok = gates(prev, now, a.force)

    step("8. Dashboard")
    run("make_r3k_dash.py")
    log("  rebuilt")

    json.dump(now, open(STATE,"w"), indent=1)
    log(f"\ndone in {(time.time()-t0)/60:.1f} minutes")
    log(f"  {now['n']} companies  ${now['total_mcap']/1000:.2f}tn  "
        f"prices {now['price_date']}")
    log("\nnext:  cd .. && python3 publish.py && git add -A && "
        "git commit -m 'refresh' && git push")


if __name__ == "__main__":
    main()
