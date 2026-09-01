"""Mag7 historical comps panel: TTM fundamentals x price/market cap per quarter.

Uses the pipeline's as-filed PIT machinery, then stamps each quarter with the
price on the first trading day AFTER the filing date -- so every point is what
was actually observable when that fundamental became public.
"""
import json, sys, os
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/bilaa/Downloads/pitquant")
from pitquant.fundamentals import (
    _extract_tag_rows, _as_filed, _pick_concept, _quarterlyize, CONCEPT_TAGS,
    SHARES_DEI_TAG)
from pitquant.prices import split_factor_between

AS_OF = None   # set to a Timestamp to hide anything filed after that date

def _cutoff(df):
    """Drop facts that had not been filed yet at AS_OF.

    Point-in-time reconstruction depends on this: companyfacts carries every
    restatement, so without a filing-date filter a backtest silently sees
    figures that did not exist on the formation date. Off by default.
    """
    if AS_OF is None or df is None or len(df) == 0 or "filed" not in df:
        return df
    import pandas as _pd
    return df[_pd.to_datetime(df["filed"], errors="coerce") <= AS_OF]


EDGAR = "/Users/bilaa/Downloads/pitquant/data/cache/edgar"
PRICES = "/Users/bilaa/Downloads/pitquant/data/cache/prices"
# Legacy output path from the NASDAQ-100 panel this module was lifted
# from. Unused here; r3k_build writes its own output.
OUT = str(Path(__file__).resolve().parent / "ndx_panel.json")

# Local tag-list extension. ODFL and CRWD tag revenue with the *Including*
# assessed-tax variant, and ODFL also uses the legacy services tag; neither is
# in the library list, so both filers silently produced no revenue series.
# Appended (not prepended) so filers reporting both keep the cleaner Excluding
# figure. Scoped here rather than edited into pitquant/fundamentals.py, which
# produced an already-recorded result.
for _t in ("RevenueFromContractWithCustomerIncludingAssessedTax",
           "SalesRevenueServicesNet",
           # utilities (XEL) report under regulated-revenue tags, not Revenues
           "RegulatedAndUnregulatedOperatingRevenue"):
    if _t not in CONCEPT_TAGS["revenue"]["tags"]:
        CONCEPT_TAGS["revenue"]["tags"].append(_t)
# BKNG tags NetIncomeLoss only ~2x/year since 2022, too sparse for a 4-quarter
# window, while ProfitLoss carries the quarterly cadence but stops in 2021.
for _t in ("NetIncomeLossAvailableToCommonStockholdersBasic",):
    if _t not in CONCEPT_TAGS["net_income"]["tags"]:
        CONCEPT_TAGS["net_income"]["tags"].append(_t)


def ttm(q, col="val"):
    """Rolling 4-quarter sum; requires 4 contiguous quarters."""
    q = q.sort_values("end_dt").reset_index(drop=True)
    keep, last = [], None
    for _, r in q.iterrows():
        if last is not None and (r["end_dt"] - last).days < 45:
            continue                      # twin of the previous quarter
        keep.append(r); last = r["end_dt"]
    q = pd.DataFrame(keep).reset_index(drop=True)
    rows = []
    for i in range(3, len(q)):
        w = q.iloc[i - 3:i + 1]
        span = (w["end_dt"].iloc[-1] - w["end_dt"].iloc[0]).days
        if not (240 <= span <= 300):
            continue
        rows.append({"end_dt": w["end_dt"].iloc[-1], "val": w[col].sum(),
                     "filed": w["filed"].max()})
    return pd.DataFrame(rows)


def flow(facts, cik, concept):
    raw = []
    for tag in CONCEPT_TAGS[concept]["tags"]:
        raw.extend(_extract_tag_rows(facts, "us-gaap", tag))
    if not raw:
        return None
    df = _cutoff(_as_filed(pd.DataFrame(raw)))
    df = _pick_concept(df, CONCEPT_TAGS[concept]["tags"])
    q = _quarterlyize(df, cik=cik)
    if q is None or q.empty:
        return None
    q = q[["end_dt", "val", "filed"]].copy()
    q["filed"] = pd.to_datetime(q["filed"], errors="coerce")
    return q.dropna().drop_duplicates("end_dt", keep="first")


def stock(facts, concept):
    raw = []
    for tag in CONCEPT_TAGS[concept]["tags"]:
        raw.extend(_extract_tag_rows(facts, "us-gaap", tag))
    if not raw:
        return None
    df = _cutoff(_as_filed(pd.DataFrame(raw)))
    df = _pick_concept(df, CONCEPT_TAGS[concept]["tags"])
    df = df[["end", "val", "filed"]].copy()
    df["end_dt"] = pd.to_datetime(df["end"], errors="coerce")
    df["filed"] = pd.to_datetime(df["filed"], errors="coerce")
    return df.dropna().drop_duplicates("end_dt", keep="first")


def ytd_to_quarterly(facts, taglist):
    """Quarterly values from YTD-cumulative filings (cash-flow style tagging).

    Within a fiscal year all periods share a start date; sorted by duration,
    Qn = cum_n - cum_(n-1). Derived rows inherit max(filed) of their components.

    Filers also publish ROLLING twelve-month windows (Amazon files one every
    quarter). Those share neither a fiscal-year start nor a quarterly cadence,
    and differencing them yields nonsense. So a directly tagged ~3-month fact
    always beats a differenced one for the same period end.
    """
    raw = []
    for t in taglist:
        raw.extend(_extract_tag_rows(facts, "us-gaap", t))
    if not raw:
        return None
    df = _pick_concept(_cutoff(_as_filed(pd.DataFrame(raw))), taglist)
    df["s"] = pd.to_datetime(df["start"], errors="coerce")
    df["e"] = pd.to_datetime(df["end"], errors="coerce")
    df["filed"] = pd.to_datetime(df["filed"], errors="coerce")
    df = df.dropna(subset=["s", "e", "filed"])
    df["dur"] = (df["e"] - df["s"]).dt.days
    out = []
    for _, g in df.groupby("s"):
        g = g.sort_values("dur")
        pv = pf = None
        for _, r in g.iterrows():
            if 80 <= r["dur"] <= 100:
                out.append({"end_dt": r["e"], "val": r["val"],
                            "filed": r["filed"], "pri": 0})
                pv, pf = r["val"], r["filed"]
            elif pv is not None and r["dur"] <= 380:
                out.append({"end_dt": r["e"], "val": r["val"] - pv,
                            "filed": max(r["filed"], pf), "pri": 1})
                pv, pf = r["val"], r["filed"]
    if not out:
        return None
    q = pd.DataFrame(out).sort_values(["end_dt", "pri"])
    q = q.drop_duplicates("end_dt", keep="first")
    return q.drop(columns=["pri"]).reset_index(drop=True)


def best_q(facts, cik, taglist):
    """Whichever reconstruction yields more quarters: direct 3-month facts, or
    differencing the YTD-cumulative ones."""
    raw = []
    for t in taglist:
        raw.extend(_extract_tag_rows(facts, "us-gaap", t))
    a = None
    if raw:
        dfa = _pick_concept(_as_filed(pd.DataFrame(raw)), taglist)
        qa = _quarterlyize(dfa, cik=cik)
        if qa is not None and not qa.empty:
            a = qa[["end_dt", "val", "filed"]].copy()
            a["filed"] = pd.to_datetime(a["filed"], errors="coerce")
            a = a.dropna().drop_duplicates("end_dt", keep="first")
    b = ytd_to_quarterly(facts, taglist)
    if a is None:
        return b
    if b is None:
        return a
    return b if len(b) > len(a) else a


DA_COMBINED = ["DepreciationDepletionAndAmortization",
               "DepreciationAmortizationAndAccretionNet"]
DA_DEP = ["Depreciation"]
DA_AMORT = ["AmortizationOfIntangibleAssets"]


def da_quarterly(facts, cik):
    """Quarterly D&A. Prefer the combined tag; where it is absent for a period
    (Tesla drops it after 2018, Apple's amortisation stops in 2017), fall back
    to Depreciation + AmortizationOfIntangibleAssets for that period."""
    comb = best_q(facts, cik, DA_COMBINED)
    dep = best_q(facts, cik, DA_DEP)
    amo = best_q(facts, cik, DA_AMORT)
    parts = None
    if dep is not None:
        parts = dep.rename(columns={"val": "dep"})[["end_dt", "dep", "filed"]]
        if amo is not None:
            parts = parts.merge(amo.rename(columns={"val": "amo"})[["end_dt", "amo"]],
                                on="end_dt", how="left")
        else:
            parts["amo"] = 0.0
        parts["val"] = parts["dep"] + parts["amo"].fillna(0.0)
        parts = parts[["end_dt", "val", "filed"]]
    if comb is None:
        return parts
    if parts is None:
        return comb
    have = set(comb["end_dt"])
    return (pd.concat([comb, parts[~parts["end_dt"].isin(have)]])
              .sort_values("end_dt").reset_index(drop=True))


def stock_tags(facts, taglist):
    """Latest-per-period balance value over an explicit tag priority list."""
    raw = []
    for tag in taglist:
        raw.extend(_extract_tag_rows(facts, "us-gaap", tag))
    if not raw:
        return None
    df = _cutoff(_as_filed(pd.DataFrame(raw)))
    df = _pick_concept(df, taglist)
    df = df[["end", "val"]].copy()
    df["end_dt"] = pd.to_datetime(df["end"], errors="coerce")
    return df.dropna().drop_duplicates("end_dt", keep="first")


DEBT_LT = ["LongTermDebtNoncurrent", "LongTermDebt"]
DEBT_CUR = ["DebtCurrent", "ShortTermBorrowings"]
CASH = ["CashAndCashEquivalentsAtCarryingValue"]
STI = ["ShortTermInvestments", "MarketableSecuritiesCurrent",
       "AvailableForSaleSecuritiesDebtSecuritiesCurrent"]

# pitquant lives outside this directory and only resolved before because the
# working directory happened to be its parent. Make that explicit so the
# pipeline runs from anywhere, including a scheduler.
_PQ = Path("/Users/bilaa/Downloads/pitquant")
if _PQ.is_dir() and str(_PQ) not in sys.path:
    sys.path.insert(0, str(_PQ))
import pitquant.fundamentals as _pf
_orig_pick = _pf._pick_concept
def _pick_concept_dur(df, tags):
    import pandas as _pd
    d = df.copy()
    _s = _pd.to_datetime(d["start"], errors="coerce")
    _e = _pd.to_datetime(d["end"], errors="coerce")
    dur = (_e - _s).dt.days
    d["_db"] = _pd.cut(dur, [0, 100, 190, 285, 400], labels=["q", "h", "n", "y"])
    d["_db"] = d["_db"].cat.add_categories(["x"]).fillna("x")
    parts = []
    for b in ("q", "h", "n", "y", "x"):
        sub = d[d["_db"] == b]
        if len(sub):
            parts.append(_orig_pick(sub.drop(columns=["_db"]), tags))
    out = _pd.concat(parts, ignore_index=True) if parts else d.drop(columns=["_db"])
    return out
_pf._pick_concept = _pick_concept_dur
_pick_concept = _pick_concept_dur
