"""Russell 3000 proxy: one cross-sectional row per company.

Unlike the NDX panel this needs no price history and no point-in-time stamping
across time -- it is a single snapshot. What it does still need is the fact
reconstruction discipline: TTM only from four contiguous quarters, twin-quarter
dedup for 52/53-week filers, and duration-aware concept picking. Those come from
r3k_facts, extracted verbatim from the validated NDX build.

Growth compares the latest TTM against the TTM four quarters earlier, and is left
blank -- never zero -- when that window is not reconstructible.
"""
import json, sys, os, warnings
try: os.setsid()
except Exception: pass
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import r3k_facts as F
from r3k_facts import (ttm, flow, stock, best_q, da_quarterly, stock_tags,
                       CONCEPT_TAGS, DEBT_LT, DEBT_CUR, CASH, STI)

HERE  = Path(__file__).resolve().parent
EDGAR = "/Users/bilaa/Downloads/pitquant/data/cache/edgar"

def safe(n, d):
    """Ratio guarded against zero, NaN and None on either side."""
    try:
        if n is None or d is None: return None
        n, d = float(n), float(d)
        if d == 0 or not np.isfinite(n) or not np.isfinite(d): return None
        v = n / d
        return round(v, 4) if np.isfinite(v) else None
    except Exception: return None

def num(x):
    try:
        if x is None: return None
        v = float(x)
        return v if np.isfinite(v) else None
    except Exception: return None

STALE_BEFORE = "2025-09-30"   # a cross-section cannot carry older than this


def bank_revenue(facts, cik):
    """Total revenue for a depository: net interest income + non-interest income.

    Banks do not tag Revenues. Using gross InterestAndDividendIncomeOperating
    instead would overstate them against every non-bank on any revenue multiple,
    so the two components are summed on matching quarter ends -- which is what
    "total revenue" means on a bank income statement.
    """
    nii = best_q(facts, cik, ["InterestIncomeExpenseNet",
                              "InterestIncomeExpenseAfterProvisionForLoanLoss"])
    nonint = best_q(facts, cik, ["NoninterestIncome"])
    if nii is None: return None
    if nonint is None: return nii
    m = nii.merge(nonint[["end_dt","val"]], on="end_dt", how="inner",
                  suffixes=("","_ni"))
    if m.empty: return nii
    m["val"] = m["val"] + m["val_ni"]
    return m[["end_dt","val","filed"]]


def one(rec):
    """Build a single company's cross-sectional row, or a reason it could not be."""
    cik, tic = int(rec["cik"]), rec["ticker"]
    path = f"{EDGAR}/companyfacts_{cik:010d}.json"
    if not os.path.exists(path): return None, "no companyfacts"
    try: facts = json.load(open(path))
    except Exception: return None, "unparseable companyfacts"

    rev_q = flow(facts, cik, "revenue")
    rev_src = "standard"
    # The fallback used to trigger only on a short series, which meant a filer
    # holding plenty of quarters from a tag it abandoned years ago never reached
    # it. JPM carried 25 quarters from a Revenues tag it stopped using in 2014
    # and was dropped as stale at rank 13, while its bank series ran to
    # 2026-06-30. So try the bank route when the standard series is short OR
    # stale, and keep whichever actually reaches further forward.
    thin  = rev_q is None or len(rev_q) < 4
    stale = (not thin) and str(rev_q["end_dt"].max())[:10] < STALE_BEFORE
    if thin or stale:
        bank_q = bank_revenue(facts, cik)         # depositories tag no Revenues
        if bank_q is not None and len(bank_q) >= 4 and (
                thin or bank_q["end_dt"].max() > rev_q["end_dt"].max()):
            rev_q = bank_q
            rev_src = "bank NII + non-interest income"
    if rev_q is None or len(rev_q) < 4: return None, "no revenue series"
    rev_t = ttm(rev_q)
    if rev_t.empty: return None, "revenue TTM not reconstructible"
    rev_t = rev_t.sort_values("end_dt").reset_index(drop=True)
    last = rev_t.iloc[-1]
    end   = last["end_dt"]

    # Tag-migration guard. _pick_concept resolves per period, so a filer that
    # switched revenue tags mid-series can have consecutive quarters drawn from
    # different concepts; differencing across that boundary yields a large
    # negative quarter. CareTrust showed Q1-Q3 2025 near $100-130m, Q4 at
    # -$340m, then 2026 quarters near $4m. Revenue cannot be negative for an
    # operating company, so any negative quarter inside the TTM window condemns
    # the whole window rather than being netted quietly into the sum.
    win = rev_q[(rev_q["end_dt"] <= end) &
                (rev_q["end_dt"] > end - pd.Timedelta(days=370))]
    if (win["val"] < 0).any(): return None, "negative quarter in TTM window (tag migration)"
    if float(last["val"]) < 0:  return None, "negative TTM revenue"

    # Recency floor. A cross-section that claims to show the index now cannot
    # carry a company whose most recent reconstructible TTM ended years ago
    # (Nelnet resolved to 2017-12-31 on a sparse series).
    if str(end)[:10] < STALE_BEFORE: return None, f"stale: latest TTM ends {str(end)[:10]}"

    row = {"ticker": tic, "cik": cik, "name": rec["name"], "sector": rec["sector"],
           "sic": int(rec["sic"]), "end": str(end)[:10],
           "filed": str(last["filed"])[:10],
           "price": num(rec["price"]), "shares": num(rec["shares"]),
           "mcap": num(rec["mcap"]), "rank": int(rec["rank"]), "rev_src": rev_src}
    row["rev"] = num(last["val"]) 

    # year-ago TTM: the row whose end is 330-400 days earlier, never a positional
    # offset -- a missing quarter would silently compare the wrong periods
    prior = rev_t[(end - rev_t["end_dt"]).dt.days.between(330, 400)]
    row["growth"] = None
    if len(prior) and num(prior.iloc[-1]["val"]):
        p = float(prior.iloc[-1]["val"])
        if p > 0: row["growth"] = round((float(last["val"]) / p - 1) * 100, 2)

    def ttm_at(q, minq=4):
        """TTM value aligned to the same period end as revenue."""
        if q is None or len(q) < minq: return None
        t = ttm(q)
        if t.empty: return None
        m = t[t["end_dt"] == end]
        return num(m.iloc[0]["val"]) if len(m) else None

    row["ni"]  = ttm_at(flow(facts, cik, "net_income"))
    row["cfo"] = ttm_at(best_q(facts, cik, CONCEPT_TAGS["cfo"]["tags"]))
    row["op"]  = ttm_at(flow(facts, cik, "op_income"))
    row["da"]  = ttm_at(da_quarterly(facts, cik))
    for nm, tags in [("capex", CONCEPT_TAGS["capex"]["tags"]),
                     ("sbc",   ["ShareBasedCompensation","AllocatedShareBasedCompensationExpense"]),
                     ("buyback", ["PaymentsForRepurchaseOfCommonStock"]),
                     ("dividend",["PaymentsOfDividendsCommonStock","PaymentsOfDividends"])]:
        row[nm] = ttm_at(best_q(facts, cik, tags))

    # balance sheet at the same period end
    for lbl, s in [("assets", stock(facts, "assets")), ("equity", stock(facts, "equity"))]:
        row[lbl] = None
        if s is not None:
            m = s[s["end_dt"] == end]
            if len(m): row[lbl] = num(m.iloc[0]["val"])
    bs = {}
    for lbl, tl in [("debt_lt",DEBT_LT),("debt_cur",DEBT_CUR),("cash",CASH),("sti",STI)]:
        bs[lbl] = None
        sdf = stock_tags(facts, tl)
        if sdf is not None:
            m = sdf[sdf["end_dt"] == end]
            if len(m): bs[lbl] = num(m.iloc[0]["val"])
    debt = (bs["debt_lt"] or 0) + (bs["debt_cur"] or 0)
    liq  = (bs["cash"] or 0) + (bs["sti"] or 0)
    row["debt"], row["cash"] = debt or None, liq or None
    row["netcash"] = (liq - debt) if (bs["cash"] is not None or bs["debt_lt"] is not None) else None

    # derived — every one guarded, so a missing input yields blank not zero
    mc = row["mcap"] * 1e9 if row["mcap"] else None
    ev = (mc + debt - liq) if mc is not None else None
    row["ev"] = round(ev/1e9, 3) if ev is not None else None
    fcf = (row["cfo"] - row["capex"]) if (row["cfo"] is not None and row["capex"] is not None) else None
    row["fcf"] = fcf
    ebitda = (row["op"] + row["da"]) if (row["op"] is not None and row["da"] is not None) else None
    row["ebitda"] = ebitda

    r = row["rev"]
    row["margin"]        = round(safe(row["ni"], r)*100, 2) if safe(row["ni"], r) is not None else None
    row["ebitda_margin"] = round(safe(ebitda, r)*100, 2) if safe(ebitda, r) is not None else None
    row["roe"]           = round(safe(row["ni"], row["equity"])*100, 2) if safe(row["ni"], row["equity"]) is not None else None
    row["ps"]            = safe(mc, r)
    row["pe"]            = safe(mc, row["ni"]) if (row["ni"] or 0) > 0 else None
    row["ev_sales"]      = safe(ev, r)
    row["ev_ebit"]       = safe(ev, row["op"]) if (row["op"] or 0) > 0 else None
    row["ev_ebitda"]     = safe(ev, ebitda) if (ebitda or 0) > 0 else None
    row["fcf_yield"]     = round(safe(fcf, mc)*100, 2) if safe(fcf, mc) is not None else None
    row["fcf_conv"]      = round(safe(fcf, row["ni"])*100, 2) if (row["ni"] or 0) > 0 and fcf is not None else None
    row["capex_rev"]     = round(safe(row["capex"], r)*100, 2) if safe(row["capex"], r) is not None else None
    row["capex_da"]      = safe(row["capex"], row["da"])
    row["sbc_rev"]       = round(safe(row["sbc"], r)*100, 2) if safe(row["sbc"], r) is not None else None
    row["fcf_sbc"]       = (fcf - row["sbc"]) if (fcf is not None and row["sbc"] is not None) else None
    payout = ((row["buyback"] or 0) + (row["dividend"] or 0)) or None
    row["payout_yield"]  = round(safe(payout, mc)*100, 2) if safe(payout, mc) is not None else None
    inv = ((row["equity"] or 0) + debt - liq) or None
    row["roic"] = round(safe(row["op"], inv)*100, 2) if (inv or 0) > 0 and row["op"] is not None else None

    # report money in $bn to keep the JSON small and the dashboard readable
    for k in ("rev","ni","cfo","op","da","capex","sbc","buyback","dividend",
              "assets","equity","debt","cash","netcash","fcf","ebitda","fcf_sbc"):
        if row.get(k) is not None: row[k] = round(row[k]/1e9, 4)
    return row, None

def main():
    uni = pd.read_json(HERE/"r3k_universe.json").to_dict("records")
    tag = sys.argv[1] if len(sys.argv) > 1 else "full"
    if tag == "sample":
        # stratified across the whole rank range: the messy tagging lives in the
        # small caps, so a top-N slice would not exercise what actually breaks
        idx = np.linspace(0, len(uni)-1, 300).astype(int)
        uni = [uni[i] for i in sorted(set(idx))]
    # Incremental rebuild. Parsing 3,000 companyfacts files takes twenty
    # minutes and 11GB of reads, but on a normal refresh only a handful of
    # companies have filed anything new. Reuse the previous row wherever the
    # facts file has not been touched since that row was built, and wherever
    # the price is unchanged. Anything that fails either test is rebuilt.
    prev, prev_built = {}, 0.0
    pfile = HERE/f"r3k_panel_{tag}.json"
    if tag == "full" and pfile.exists() and "--full" not in sys.argv:
        try:
            prev = {r["cik"]: r for r in json.load(open(pfile))}
            prev_built = pfile.stat().st_mtime
        except Exception:
            prev = {}

    def unchanged(rec):
        if not prev: return None
        old_row = prev.get(rec["cik"])
        if not old_row: return None
        f = Path(EDGAR)/f"companyfacts_{int(rec['cik']):010d}.json"
        if (not f.exists()) or f.stat().st_mtime > prev_built: return None
        if abs(old_row.get("price", 0) - rec["price"]) > 1e-9: return None
        if abs(old_row.get("shares", 0) - rec["shares"]) > 1e-6: return None
        return old_row

    print(f"building {len(uni)} companies ({tag})"
          + (f", {len(prev)} rows available to reuse" if prev else ""), flush=True)
    rows, skipped, reused = [], [], 0
    for i, rec in enumerate(uni, 1):
        keep = unchanged(rec)
        if keep is not None:
            rows.append(keep); reused += 1
            if i % 500 == 0:
                print(f"  {i}/{len(uni)}  built={len(rows)} reused={reused}", flush=True)
            continue
        try:
            r, why = one(rec)
        except Exception as e:
            r, why = None, f"{type(e).__name__}: {e}"
        if r: rows.append(r)
        else: skipped.append({"ticker": rec["ticker"], "rank": int(rec["rank"]), "why": why})
        if i % 50 == 0:
            print(f"  {i}/{len(uni)}  built={len(rows)} reused={reused} "
                  f"skipped={len(skipped)}", flush=True)
    out = HERE/(f"r3k_panel_{tag}.json")
    json.dump(rows, open(out,"w"))
    json.dump(skipped, open(HERE/f"r3k_skipped_{tag}.json","w"), indent=1)
    print(f"\nbuilt {len(rows)} / {len(uni)}   "
          f"({reused} reused, {len(rows)-reused} recomputed)   skipped {len(skipped)}")
    print(f"-> {out}")

if __name__ == "__main__":
    main()
