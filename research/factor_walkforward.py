#!/usr/bin/env python3
"""Composite-factor characteristic model, beta/sector-neutral, walk-forward.

The 19-ratio version was noisy because the ratios are collinear and single-stock
returns are fat-tailed. This tightens signal-to-noise the honest way -- by
design, not by de-regularising:

  * FEATURES are the six orthogonal-ish factors, not 19 overlapping ratios:
    value, quality, cash, balance sheet, growth (the sector-neutral composites)
    plus size. Fewer, near-independent inputs -> stable coefficients.
  * TARGET is next-quarter return made beta-neutral AND sector-neutral (residual
    of return on trailing beta + sector dummies, as of formation), then
    rank-transformed to normal scores so a few blow-ups can't dominate.
  * VALIDATION is walk-forward: the weighting is learned on 2014-2022 and tested
    on 2023-now, out of sample. If value/quality survive that, they're real; if
    they evaporate, the full-sample fit was hindsight.

Regularisation is left to nested CV -- deliberately not hand-tuned toward a
nicer number, which would just overfit this one history.

    python3 research/factor_walkforward.py
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
from scipy.stats import spearmanr, rankdata, norm  # noqa: E402
from sklearn.linear_model import ElasticNetCV  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

PANELS = sorted(glob.glob(str(HERE / "gated25_panels" / "*.parquet")))
COMPS = ["p_value", "p_quality", "p_cash", "p_balance", "p_growth"]
FEATS = COMPS + ["size"]
PRETTY = {"p_value": "Value", "p_quality": "Quality", "p_cash": "Cash generation",
          "p_balance": "Balance sheet", "p_growth": "Growth", "size": "Size (small=high)"}

SPY = pd.read_parquet(HERE / "spy.parquet").set_index("date")["close"].sort_index()


def norm_scores(x):
    x = np.asarray(x, float)
    r = rankdata(x)                       # 1..n, ties averaged
    return norm.ppf((r - 0.5) / len(r))


def build():
    dates = [Path(f).stem for f in PANELS]
    rows = []
    for i, f in enumerate(PANELS[:-1]):
        d0, d1 = dates[i], dates[i + 1]
        pan = pd.read_parquet(f).copy()
        pan["size"] = np.log(pan["mcap"].clip(lower=1e-3))
        formed, exit_ = pd.Timestamp(d0), pd.Timestamp(d1)
        syms = sorted({t for t in pan.ticker if isinstance(t, str) and t})
        px = closes(syms, (formed - pd.Timedelta(days=380)).strftime("%Y-%m-%d"),
                    (exit_ + pd.Timedelta(days=8)).strftime("%Y-%m-%d"))
        fwd, beta = {}, {}
        if not px.empty:
            idx = px.index
            spy = SPY.reindex(idx).ffill()
            a = idx.searchsorted(formed, "left")          # formation row
            b = idx.searchsorted(exit_, "right") - 1       # exit row
            # trailing window for beta: ~252 sessions up to formation
            t0 = max(0, a - 252)
            tw = px.iloc[t0:a + 1]
            mret = spy.iloc[t0:a + 1].pct_change().to_numpy()[1:]
            mvar = np.nanvar(mret)
            for c in px.columns:
                # forward return, last traded price convention
                if b > a:
                    seg = px[c].iloc[a:b + 1].to_numpy()
                    p0 = seg[0]
                    segv = seg[np.isfinite(seg)]
                    if np.isfinite(p0) and p0 > 0 and segv.size >= 2:
                        fwd[c] = segv[-1] / p0 - 1.0
                # trailing beta as of formation (no look-ahead)
                sret = tw[c].pct_change().to_numpy()[1:]
                m = np.isfinite(sret) & np.isfinite(mret)
                if m.sum() >= 120 and mvar > 0:
                    beta[c] = np.cov(sret[m], mret[m])[0, 1] / np.nanvar(mret[m])
        pan["fwd"] = pan.ticker.map(fwd)
        pan["beta"] = pan.ticker.map(beta)
        sub = pan.dropna(subset=["fwd", "sector"])[["ticker", "sector", "fwd", "beta"] + FEATS].copy()
        sub["period"] = d0
        rows.append(sub)
        print(f"  {d0}: {len(sub):>4} names  (beta on {sub.beta.notna().mean()*100:.0f}%)", flush=True)
    return pd.concat(rows, ignore_index=True)


def prep(df):
    out = df.copy()
    # features: neutral-impute composites to median percentile, then z within period
    for c in COMPS:
        out[c] = out[c].fillna(50.0)
    def zc(g):
        for c in FEATS:
            sd = g[c].std()
            g[c] = (g[c] - g[c].mean()) / sd if sd else 0.0
        return g
    out = out.groupby("period", group_keys=False).apply(zc)
    # target: residualise fwd on [beta + sector dummies] per period, then rank->normal
    ys = []
    for p, g in out.groupby("period"):
        g = g.copy()
        g["beta"] = g["beta"].fillna(g["beta"].median())
        D = pd.get_dummies(g["sector"], drop_first=True).to_numpy(float)
        X = np.column_stack([np.ones(len(g)), g["beta"].to_numpy(), D])
        y = g["fwd"].clip(g["fwd"].quantile(.01), g["fwd"].quantile(.99)).to_numpy()
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        g["yz"] = norm_scores(resid)
        ys.append(g)
    return pd.concat(ys)


def fit_en(d):
    X, y = d[FEATS].to_numpy(), d["yz"].to_numpy()
    grp = d.period.astype("category").cat.codes.to_numpy()
    k = min(5, len(np.unique(grp)))
    m = ElasticNetCV(l1_ratio=[.1, .3, .5, .7, .9, 1.0], n_alphas=60,
                     cv=GroupKFold(k).split(X, y, grp), max_iter=20000, n_jobs=-1)
    m.fit(X, y)
    return m


def ic_by(d):
    """Per-period Spearman IC of each feature vs yz; return series per feature."""
    out = {c: {} for c in FEATS}
    for p, g in d.groupby("period"):
        for c in FEATS:
            out[c][p], _ = spearmanr(g[c], g["yz"])
    return {c: pd.Series(out[c]).sort_index() for c in FEATS}


def fm(s):
    s = s.dropna()
    return s.mean(), s.mean() / (s.std() / np.sqrt(len(s))) if len(s) > 1 else np.nan


def main():
    print("Building beta/sector-neutral panel (trailing beta + forward return)...\n")
    d = prep(build())
    d["yr"] = d.period.str[:4].astype(int)
    periods = sorted(d.period.unique())
    print(f"\n  {len(d):,} obs, {len(periods)} quarters, features: {FEATS}\n")

    ics = ic_by(d)
    full = fit_en(d)

    # eras
    tr = d[d.yr <= 2022]; te = d[d.yr >= 2023]
    m_tr = fit_en(tr)
    # OOS: apply the 2014-2022 weighting to each 2023+ quarter, measure IC
    oos = []
    for p, g in te.groupby("period"):
        pred = g[FEATS].to_numpy() @ m_tr.coef_
        ic, _ = spearmanr(pred, g["yz"]); oos.append(ic)
    oos = pd.Series(oos, index=sorted(te.period.unique()))
    oos_m, oos_t = fm(oos)

    print("="*74)
    print("1) COMPOSITE WEIGHTING  (full sample, elastic net; +ve = rewarded)")
    print(f"   l1={full.l1_ratio_}, alpha={full.alpha_:.4f}\n")
    print(f"   {'factor':<20}{'EN weight':>11}{'IC full':>9}{'t(FM)':>8}"
          f"{'IC 14-22':>10}{'IC 23-26':>10}{'IC last4':>10}")
    order = sorted(FEATS, key=lambda c: abs(full.coef_[FEATS.index(c)]), reverse=True)
    for c in order:
        s = ics[c]
        icf, tf = fm(s)
        ic_tr, _ = fm(s[s.index.str[:4].astype(int) <= 2022])
        ic_te, _ = fm(s[s.index.str[:4].astype(int) >= 2023])
        ic_l4, _ = fm(s.iloc[-4:])
        print(f"   {PRETTY[c]:<20}{full.coef_[FEATS.index(c)]:>+11.3f}"
              f"{icf:>+9.3f}{tf:>+8.2f}{ic_tr:>+10.3f}{ic_te:>+10.3f}{ic_l4:>+10.3f}")

    print("\n" + "="*74)
    print("2) WALK-FORWARD  (weighting learned 2014-2022, tested 2023-now)")
    print(f"   train weighting: " + ", ".join(
        f"{PRETTY[c].split(' (')[0]} {m_tr.coef_[FEATS.index(c)]:+.2f}" for c in FEATS))
    print(f"   OUT-OF-SAMPLE combined-model IC: mean {oos_m:+.3f}, "
          f"Fama-MacBeth t {oos_t:+.2f}, over {len(oos)} quarters")
    print(f"   OOS quarters IC>0: {int((oos>0).sum())}/{len(oos)}")

    print("\n" + "="*74)
    print("3) VERDICT")
    q = ics["p_quality"]
    qtr, _ = fm(q[q.index.str[:4].astype(int) <= 2022])
    qte, _ = fm(q[q.index.str[:4].astype(int) >= 2023])
    v = ics["p_value"]; vf, vt = fm(v)
    print(f"   Value IC full {vf:+.3f} (t {vt:+.1f}); Quality IC 2014-22 {qtr:+.3f} "
          f"-> 2023-26 {qte:+.3f}")

    import json
    json.dump({
        "features": FEATS, "n_obs": int(len(d)),
        "full_l1": float(full.l1_ratio_), "full_alpha": float(full.alpha_),
        "full_coef": {c: float(full.coef_[FEATS.index(c)]) for c in FEATS},
        "train_coef": {c: float(m_tr.coef_[FEATS.index(c)]) for c in FEATS},
        "oos_ic_mean": float(oos_m), "oos_ic_t": float(oos_t),
        "oos_ic_by_q": {k: float(x) for k, x in oos.items()},
        "ic_series": {c: {k: (float(x) if pd.notna(x) else None) for k, x in s.items()}
                      for c, s in ics.items()},
    }, open(HERE / "factor_walkforward_results.json", "w"), indent=1)
    print(f"\n  wrote factor_walkforward_results.json")


if __name__ == "__main__":
    main()
