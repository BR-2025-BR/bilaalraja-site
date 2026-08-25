"""Composite score, sector-neutral, regime-tilted toward balance sheet and cash.

Every guard here exists because the raw data produced a specific false positive:
  - Financials and Real Estate are scored on a SEPARATE model. FCF and EV are
    meaningless for them (Consumer Portfolio Services shows a 171% FCF yield
    because lending cash flows run through CFO).
  - ROIC is capped at 100%. RH prints 11,703% on $0.06bn of equity.
  - A negative or absent EV/EBIT is not "cheap" -- it is unscoreable, so the
    value factor goes missing rather than ranking best.
  - Factors are winsorised at the 2nd/98th percentile within sector before
    ranking, so one extreme filer cannot dominate a percentile.
  - A name needs most of its factors present or it gets no score at all. A
    partial score would silently reward companies with thin disclosure.
"""
import json
import numpy as np, pandas as pd

FIN = {"Financials", "Real Estate"}

# Weights tilt to cash generation and balance sheet: in a rising-yield regime
# those decide who is forced to refinance and who is not.
W_OP  = {"value":0.25, "cash":0.25, "balance":0.20, "quality":0.20, "growth":0.10}
W_FIN = {"value":0.30, "quality":0.30, "growth":0.20, "payout":0.20}
MIN_OP, MIN_FIN = 4, 3          # factors required before a score is issued

def winsor(s, lo=0.02, hi=0.98):
    v = s.dropna()
    if len(v) < 8: return s
    return s.clip(v.quantile(lo), v.quantile(hi))

def pctile(df, col, higher_is_better):
    """Percentile within sector, winsorised first. 0-100, higher always better."""
    out = pd.Series(np.nan, index=df.index)
    for _, idx in df.groupby("sector").groups.items():
        s = winsor(df.loc[idx, col])
        if s.notna().sum() < 5: continue
        out.loc[idx] = s.rank(pct=True, ascending=higher_is_better) * 100
    return out

def build(df):
    d = df.copy()
    d["is_fin"] = d.sector.isin(FIN)

    # --- factor inputs, cleaned -------------------------------------------
    d["f_value_op"] = np.where(d.ev_ebit > 0, d.ev_ebit, np.nan)      # negative EBIT is not cheap
    # Quality uses return on CAPITAL EMPLOYED (operating profit over equity plus
    # debt), not ROIC. ROIC subtracts cash, so for a net-cash company the
    # denominator collapses: United printed 8,123% because $16.70bn of equity was
    # almost exactly cancelled by $16.64bn of net cash. Capping bounds that
    # without making it meaningful, and a denominator floor instead knocked out
    # Apple and NVIDIA -- cash-rich quality names the factor should reward.
    # ROCE avoids both failures: United 29%, Apple 87%, NVIDIA 80%.
    ce = d.equity + d.debt.fillna(0)
    d["roce"] = np.where(ce > 0.05, d.op / ce * 100, np.nan)
    d["f_qual_op"] = d.roce.clip(upper=150)          # p99 is 116; 6 names above 200
    d["f_cash_op"]  = d.fcf_yield
    d["f_bal_op"]   = np.where(d.mcap > 0, d.netcash / d.mcap * 100, np.nan)
    # Growth is capped at 50%. Above that the number stops carrying information
    # about the business and starts carrying noise: mortgage REITs printed 255%,
    # 414% and 182% "revenue growth" on interest-income swings across a leveraged
    # bond book, which lifted the four most rate-SENSITIVE names in the index into
    # the top 25 of a screen built for rising rates. Their median growth is 9%.
    # Capping means 40% and 400% tie at the top of the factor, which is honest --
    # past a point, more reported growth does not tell you more.
    d["f_grow"]     = d.growth.clip(upper=50)

    d["f_value_fin"]= np.where(d.pe > 0, d.pe, np.nan)
    d["f_qual_fin"] = d.roe.clip(lower=-100, upper=100)
    d["f_pay_fin"]  = d.payout_yield

    op, fin = d[~d.is_fin].copy(), d[d.is_fin].copy()

    op["p_value"]  = pctile(op, "f_value_op", higher_is_better=False)   # cheap wins
    op["p_quality"]= pctile(op, "f_qual_op",  higher_is_better=True)
    op["p_cash"]   = pctile(op, "f_cash_op",  higher_is_better=True)
    op["p_balance"]= pctile(op, "f_bal_op",   higher_is_better=True)
    op["p_growth"] = pctile(op, "f_grow",     higher_is_better=True)
    opcols = {"value":"p_value","cash":"p_cash","balance":"p_balance",
              "quality":"p_quality","growth":"p_growth"}

    fin["p_value"]  = pctile(fin, "f_value_fin", higher_is_better=False)
    fin["p_quality"]= pctile(fin, "f_qual_fin",  higher_is_better=True)
    fin["p_growth"] = pctile(fin, "f_grow",      higher_is_better=True)
    fin["p_payout"] = pctile(fin, "f_pay_fin",   higher_is_better=True)
    fincols = {"value":"p_value","quality":"p_quality",
               "growth":"p_growth","payout":"p_payout"}

    def composite(frame, cols, weights, need):
        present = frame[list(cols.values())].notna()
        n = present.sum(axis=1)
        w = pd.DataFrame({k: np.where(present[c], weights[k], 0.0)
                          for k, c in cols.items()}, index=frame.index)
        tot = w.sum(axis=1)
        num = sum(frame[c].fillna(0) * w[k] for k, c in cols.items())
        sc = np.where(tot > 0, num / tot.replace(0, np.nan), np.nan)   # reweight to present factors
        return pd.Series(np.where(n >= need, sc, np.nan), index=frame.index), n

    op["score"],  op["nfac"]  = composite(op,  opcols,  W_OP,  MIN_OP)
    fin["score"], fin["nfac"] = composite(fin, fincols, W_FIN, MIN_FIN)
    op["model"], fin["model"] = "operating", "financial"

    out = pd.concat([op, fin]).sort_index()
    out["score"] = out["score"].round(1)
    return out

if __name__ == "__main__":
    df = pd.DataFrame(json.load(open("r3k_panel_full.json")))
    s = build(df)
    s.to_json("r3k_scored.json", orient="records")
    print(f"scored {s.score.notna().sum()} of {len(s)}")
    print(f"  operating {s[(s.model=='operating')].score.notna().sum()} / {(s.model=='operating').sum()}")
    print(f"  financial {s[(s.model=='financial')].score.notna().sum()} / {(s.model=='financial').sum()}")
