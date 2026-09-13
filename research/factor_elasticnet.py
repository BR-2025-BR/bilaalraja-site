#!/usr/bin/env python3
"""Which fundamentals are being rewarded, and how strongly, right now.

A cross-sectional characteristic model on the survivorship-free, point-in-time
panels. For every quarterly formation we take each company's fundamentals as of
that date (no look-ahead) and its NEXT-QUARTER return from the delisting-aware
price feed (dead names priced at their last print, not dropped). Features and
the return are standardised WITHIN sector and period, so the target is relative,
sector-neutral performance -- "which characteristics separated the winners from
the losers", not "did the market go up".

Two readings are produced, because they answer two different questions:

  * INFORMATION COEFFICIENT (IC) -- the average rank correlation between one
    fundamental and next-quarter relative return, on its own. This is the
    "how strongly is X correlated with performance" number, immune to the
    collinearity between the valuation ratios. Reported with a Fama-MacBeth
    t-stat (mean over periods / standard error over periods).

  * ELASTIC NET weighting -- all fundamentals fit jointly, so overlapping
    signals (EV/EBIT vs EV/EBITDA vs P/E) share credit rather than double-count.
    The standardised coefficients are the objective weighting: how much emphasis
    to place on each, controlling for the others.

Both are reported full-sample and over the trailing four quarters (the current
regime), and the trailing-4q elastic-net weights are applied to the latest
cross-section to rank what is being rewarded now.

    python3 research/factor_elasticnet.py
"""
import glob
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
from prices import closes  # noqa: E402
from sklearn.linear_model import ElasticNetCV  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

PANELS = sorted(glob.glob(str(HERE / "gated25_panels" / "*.parquet")))

# Curated, interpretable fundamentals spanning value / quality / growth /
# balance sheet / capital allocation / size. Raw ratios, not composites, so the
# model speaks in terms of individual line items.
VALUE = ["ev_sales", "ev_ebit", "ev_ebitda", "pe", "ps", "fcf_yield", "payout_yield"]
QUALITY = ["roe", "roic", "roce", "margin", "ebitda_margin", "fcf_conv"]
OTHER = ["growth", "capex_rev", "sbc_rev"]           # growth + capital intensity
FEATS = VALUE + QUALITY + OTHER + ["size", "nd_ebitda", "netcash_mcap"]

PRETTY = {
    "ev_sales": "EV / Sales", "ev_ebit": "EV / EBIT", "ev_ebitda": "EV / EBITDA",
    "pe": "P/E", "ps": "P/Sales", "fcf_yield": "FCF yield", "payout_yield": "Payout yield",
    "roe": "ROE", "roic": "ROIC", "roce": "ROCE", "margin": "Net margin",
    "ebitda_margin": "EBITDA margin", "fcf_conv": "FCF conversion", "growth": "Revenue growth",
    "capex_rev": "Capex / rev", "sbc_rev": "SBC / rev", "size": "Size (log mcap)",
    "nd_ebitda": "Net debt / EBITDA", "netcash_mcap": "Net cash / mcap",
}


def load_long():
    """Assemble (features, next-quarter return) for every name in every panel."""
    dates = [Path(f).stem for f in PANELS]           # 'YYYY-MM-DD'
    rows = []
    for i, f in enumerate(PANELS[:-1]):              # last panel has no full fwd window
        d0, d1 = dates[i], dates[i + 1]
        pan = pd.read_parquet(f).copy()
        pan["nd_ebitda"] = (pan["debt"] - pan["cash"]) / pan["ebitda"].replace(0, np.nan)
        pan["netcash_mcap"] = pan["netcash"] / pan["mcap"].replace(0, np.nan)
        pan["size"] = np.log(pan["mcap"].clip(lower=1e-3))
        formed = pd.Timestamp(pan["formed"].iloc[0]) if "formed" in pan else pd.Timestamp(d0)
        exit_ = pd.Timestamp(d1)
        syms = sorted({t for t in pan.ticker if isinstance(t, str) and t})
        px = closes(syms, (formed - pd.Timedelta(days=8)).strftime("%Y-%m-%d"),
                    (exit_ + pd.Timedelta(days=8)).strftime("%Y-%m-%d"))
        ret = {}
        if not px.empty:
            idx = px.index
            a = idx.searchsorted(formed, "left")
            b = idx.searchsorted(exit_, "right") - 1
            if b > a and a < len(idx):
                win = px.iloc[a:b + 1]
                first = win.iloc[0]
                for c in win.columns:
                    p0 = first[c]
                    if not np.isfinite(p0) or p0 <= 0:
                        continue
                    col = win[c].to_numpy()
                    col = col[np.isfinite(col)]
                    if col.size >= 2:
                        ret[c] = col[-1] / p0 - 1.0
        pan["fwd"] = pan.ticker.map(ret)
        sub = pan.dropna(subset=["fwd", "sector"])[["ticker", "sector", "fwd"] + FEATS].copy()
        sub["period"] = d0
        rows.append(sub)
        print(f"  {d0} -> {d1}: {len(sub):>4} names with a forward return", flush=True)
    return pd.concat(rows, ignore_index=True)


def neutralise(df, cols):
    """Winsorise then z-score each column within (period, sector); NaN -> 0
    (the sector-period mean, i.e. a neutral bet on a missing ratio)."""
    out = df.copy()
    g = out.groupby(["period", "sector"])
    for c in cols:
        def _z(s):
            s = s.clip(s.quantile(.01), s.quantile(.99))
            sd = s.std()
            return (s - s.mean()) / sd if sd and np.isfinite(sd) else s * 0.0
        out[c] = g[c].transform(_z)
    out[cols] = out[cols].fillna(0.0)
    return out


def elastic(X, y, groups):
    k = min(5, len(np.unique(groups)))               # leave-one-quarter-out when few
    m = ElasticNetCV(l1_ratio=[.1, .3, .5, .7, .9, .95, 1.0],
                     n_alphas=60, cv=GroupKFold(k).split(X, y, groups),
                     max_iter=20000, n_jobs=-1, random_state=7)
    m.fit(X, y)
    # honest out-of-fold R^2
    from sklearn.linear_model import ElasticNet
    from sklearn.model_selection import cross_val_score
    r2 = cross_val_score(ElasticNet(alpha=m.alpha_, l1_ratio=m.l1_ratio_, max_iter=20000),
                         X, y, groups=groups, cv=GroupKFold(k), scoring="r2").mean()
    return m, r2


def ic_table(df):
    """Per-period Spearman IC of each (neutralised) feature vs (neutralised) fwd,
    with Fama-MacBeth mean/t full-sample and over the trailing 4 quarters."""
    periods = sorted(df.period.unique())
    recs = {c: [] for c in FEATS}
    for p in periods:
        g = df[df.period == p]
        for c in FEATS:
            ic, _ = spearmanr(g[c], g["yz"])
            recs[c].append(ic)
    rowsout = []
    for c in FEATS:
        s = pd.Series(recs[c], index=periods).dropna()
        full_m, full_t = s.mean(), s.mean() / (s.std() / np.sqrt(len(s)))
        r = s.iloc[-4:]
        rowsout.append((c, full_m, full_t, r.mean()))
    return pd.DataFrame(rowsout, columns=["feat", "ic_full", "t_full", "ic_4q"]), \
        {c: pd.Series(recs[c], index=periods) for c in FEATS}


def main():
    print("Building the panel (this loads prices per quarter)...\n")
    long = load_long()
    long = neutralise(long, FEATS)
    # target: relative, sector-neutral next-quarter return
    long["yz"] = long.groupby(["period", "sector"])["fwd"].transform(
        lambda s: (s - s.mean()) / s.std() if s.std() else s * 0.0)
    long = long.dropna(subset=["yz"])
    periods = sorted(long.period.unique())
    print(f"\n  {len(long):,} observations, {len(periods)} quarters "
          f"({periods[0]} .. {periods[-1]}), {len(FEATS)} features\n")

    X = long[FEATS].to_numpy()
    y = long["yz"].to_numpy()
    grp = long.period.astype("category").cat.codes.to_numpy()

    print("Fitting elastic net (full sample)...")
    m_full, r2_full = elastic(X, y, grp)
    last4 = periods[-4:]
    sub = long[long.period.isin(last4)]
    # A CV-tuned net on four quarters collapses to zero -- too little data. So we
    # hold the penalty at the full-sample level and re-fit on the recent window:
    # the coefficients then reflect the RECENT cross-sectional relationships at a
    # sensible, non-degenerate regularisation rather than being tuned to nothing.
    from sklearn.linear_model import ElasticNet
    print(f"Fitting elastic net (trailing 4q: {last4[0]}..{last4[-1]}, "
          f"penalty fixed to full-sample level)...")
    m_4q = ElasticNet(alpha=m_full.alpha_, l1_ratio=m_full.l1_ratio_, max_iter=20000)
    m_4q.fit(sub[FEATS].to_numpy(), sub["yz"].to_numpy())
    r2_4q = float("nan")

    ic, ic_series = ic_table(long)

    # ---- report -----------------------------------------------------------
    coef = pd.DataFrame({"feat": FEATS, "b_full": m_full.coef_, "b_4q": m_4q.coef_})
    tab = coef.merge(ic, on="feat")
    tab["name"] = tab.feat.map(PRETTY)
    tab = tab.sort_values("b_4q", key=lambda s: s.abs(), ascending=False)

    print(f"\n  full-sample: l1={m_full.l1_ratio_}, alpha={m_full.alpha_:.4f}, "
          f"out-of-fold R^2={r2_full:.4f}")
    print(f"  trailing-4q: l1={m_4q.l1_ratio}, alpha={m_4q.alpha:.4f} "
          f"(fixed to full-sample penalty)\n")
    hdr = f"  {'fundamental':<20}{'EN wt now':>11}{'EN wt full':>12}{'IC now':>9}{'IC full':>9}{'t(full)':>9}"
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    for _, r in tab.iterrows():
        print(f"  {r['name']:<20}{r.b_4q:>+11.3f}{r.b_full:>+12.3f}"
              f"{r.ic_4q:>+9.3f}{r.ic_full:>+9.3f}{r.t_full:>+9.2f}")

    # ---- apply the current-regime weights to the latest cross-section ------
    cur = pd.read_parquet(PANELS[-1]).copy()
    cur["nd_ebitda"] = (cur["debt"] - cur["cash"]) / cur["ebitda"].replace(0, np.nan)
    cur["netcash_mcap"] = cur["netcash"] / cur["mcap"].replace(0, np.nan)
    cur["size"] = np.log(cur["mcap"].clip(lower=1e-3))
    cur["period"] = PANELS[-1].split("/")[-1][:10]
    cur = neutralise(cur.dropna(subset=["sector"]), FEATS)
    cur["regime_score"] = cur[FEATS].to_numpy() @ m_4q.coef_
    top = cur.sort_values("regime_score", ascending=False).head(12)
    print(f"\n  Top names on the current-regime weighting ({cur.period.iloc[0]} cross-section):")
    for _, r in top.iterrows():
        print(f"    {r.ticker:<6} {str(r.get('name',''))[:34]:<34} {r.sector:<20} {r.regime_score:+.2f}")

    out = HERE / "factor_elasticnet_results.json"
    import json
    json.dump({
        "periods": periods, "n_obs": int(len(long)),
        "r2_full": float(r2_full), "r2_4q": float(r2_4q),
        "l1_full": float(m_full.l1_ratio_), "alpha_full": float(m_full.alpha_),
        "l1_4q": float(m_4q.l1_ratio), "alpha_4q": float(m_4q.alpha),
        "table": [{"feat": r.feat, "name": r["name"], "b_full": float(r.b_full),
                   "b_4q": float(r.b_4q), "ic_full": float(r.ic_full),
                   "t_full": float(r.t_full), "ic_4q": float(r.ic_4q)}
                  for _, r in tab.iterrows()],
        "ic_series": {c: {str(k): (float(v) if pd.notna(v) else None)
                          for k, v in s.items()} for c, s in ic_series.items()},
    }, open(out, "w"), indent=1)
    print(f"\n  wrote {out.name}")


if __name__ == "__main__":
    main()
