#!/usr/bin/env python3
"""Does re-weighting the score by the factor model improve the quarterly book?

Construction is held identical to the gate-exit book -- six gates, beta <= 1.3,
top 25, equal weight, rebuilt every quarter -- and ONLY the ranking changes:

  * BASELINE   rank eligible names by the existing composite score.
  * FACTOR     rank by a factor-weighted score, where the weights come from an
               elastic net fit ONLY on data before that quarter (expanding
               window). No look-ahead: the weighting at 2020-Q1 has never seen
               2020 onward. The walk-forward validated that quality + cash carry
               the signal, so this is that finding put to work.

Both are compared over the common out-of-sample window against the S&P.

    python3 research/factor_tilt_backtest.py

Writes research/factor_tilt_results.json for the write-up.
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
from scipy.stats import rankdata, norm  # noqa: E402
from sklearn.linear_model import ElasticNetCV  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

PANELS = sorted(glob.glob(str(HERE / "gated25_panels" / "*.parquet")))
COMPS = ["p_value", "p_quality", "p_cash", "p_balance", "p_growth"]
FEATS = COMPS + ["size"]
GATE_COLS = ["growth", "ni", "fcf", "roic", "debt", "cash", "ebitda", "fcf_conv", "score"]
CACHE = HERE / "factor_panel.parquet"
SPY = pd.read_parquet(HERE / "spy.parquet").set_index("date")["close"].sort_index()
TOP_N = 25


def norm_scores(x):
    r = rankdata(np.asarray(x, float))
    return norm.ppf((r - 0.5) / len(r))


def build():
    if CACHE.exists():
        print(f"  using cached {CACHE.name}")
        return pd.read_parquet(CACHE)
    dates = [Path(f).stem for f in PANELS]
    spy_q = {}
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
            a = idx.searchsorted(formed, "left")
            b = idx.searchsorted(exit_, "right") - 1
            if b > a and a < len(idx):
                spy_q[d0] = float(spy.iloc[b] / spy.iloc[a] - 1)
            t0 = max(0, a - 252)
            mret = spy.iloc[t0:a + 1].pct_change().to_numpy()[1:]
            mvar = np.nanvar(mret)
            for c in px.columns:
                if b > a:
                    seg = px[c].iloc[a:b + 1].to_numpy()
                    p0 = seg[0]; sv = seg[np.isfinite(seg)]
                    if np.isfinite(p0) and p0 > 0 and sv.size >= 2:
                        fwd[c] = sv[-1] / p0 - 1.0
                sret = px[c].iloc[t0:a + 1].pct_change().to_numpy()[1:]
                m = np.isfinite(sret) & np.isfinite(mret)
                if m.sum() >= 120 and mvar > 0:
                    beta[c] = np.cov(sret[m], mret[m])[0, 1] / np.nanvar(mret[m])
        pan["fwd"] = pan.ticker.map(fwd)
        pan["beta"] = pan.ticker.map(beta)
        keep = ["ticker", "sector", "fwd", "beta"] + FEATS + GATE_COLS
        sub = pan.dropna(subset=["fwd", "sector"])[keep].copy()
        sub["period"] = d0
        rows.append(sub)
        print(f"  {d0}: {len(sub):>4} names", flush=True)
    df = pd.concat(rows, ignore_index=True)
    # per-period z of features and the beta/sector-neutral rank target
    for c in COMPS:
        df[c] = df[c].fillna(50.0)
    def zc(g):
        for c in FEATS:
            sd = g[c].std(); g[c + "_z"] = (g[c] - g[c].mean()) / sd if sd else 0.0
        return g
    df = df.groupby("period", group_keys=False).apply(zc)
    ys = []
    for p, g in df.groupby("period"):
        g = g.copy(); g["beta_f"] = g["beta"].fillna(g["beta"].median())
        D = pd.get_dummies(g["sector"], drop_first=True).to_numpy(float)
        X = np.column_stack([np.ones(len(g)), g["beta_f"].to_numpy(), D])
        y = g["fwd"].clip(g["fwd"].quantile(.01), g["fwd"].quantile(.99)).to_numpy()
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        g["yz"] = norm_scores(y - X @ coef)
        ys.append(g)
    df = pd.concat(ys)
    df.attrs = {}
    df.to_parquet(CACHE)
    pd.Series(spy_q).to_json(HERE / "factor_spy_q.json")
    print(f"  cached {CACHE.name}")
    return df


def eligible(g):
    nd = g["debt"] - g["cash"]
    return g[(g.growth >= 20) & (g.growth <= 80) & (g.ni > 0) & (g.fcf > 0)
             & (g.roic >= 10) & (nd <= 3 * g.ebitda) & (g.fcf_conv >= 50)
             & (g.beta.notna()) & (g.beta <= 1.3)]


def fit_weights(train):
    X = train[[c + "_z" for c in FEATS]].to_numpy(); y = train["yz"].to_numpy()
    grp = train.period.astype("category").cat.codes.to_numpy()
    k = min(5, len(np.unique(grp)))
    if k < 2:
        return np.zeros(len(FEATS))
    m = ElasticNetCV(l1_ratio=[.1, .5, 1.0], n_alphas=40,
                     cv=GroupKFold(k).split(X, y, grp), max_iter=20000, n_jobs=-1)
    m.fit(X, y)
    return m.coef_


def main():
    df = build()
    spy_q = pd.read_json(HERE / "factor_spy_q.json", typ="series")
    periods = sorted(df.period.unique())
    MIN_TRAIN = 8                                    # quarters before we trust weights
    zcols = [c + "_z" for c in FEATS]

    recs = []
    for i, p in enumerate(periods):
        g = eligible(df[df.period == p]).copy()
        if len(g) < 5:
            continue
        base = g.sort_values("score", ascending=False).head(TOP_N)
        row = {"period": p, "n_elig": len(g), "base_ret": float(base.fwd.mean()),
               "spy": float(spy_q.get(p, np.nan))}
        if i >= MIN_TRAIN:
            w = fit_weights(df[df.period.isin(periods[:i])])   # strictly prior data
            g["fscore"] = g[zcols].to_numpy() @ w
            fac = g.sort_values("fscore", ascending=False).head(TOP_N)
            row["fac_ret"] = float(fac.fwd.mean())
            row["w"] = {c: float(w[j]) for j, c in enumerate(FEATS)}
        recs.append(row)
    R = pd.DataFrame(recs)

    def stats(col, mask):
        r = R.loc[mask, col].dropna().to_numpy() / 100 if False else R.loc[mask, col].dropna().to_numpy()
        comp = np.prod(1 + r) - 1
        yrs = len(r) / 4
        cagr = (1 + comp) ** (1 / yrs) - 1
        vol = r.std(ddof=1) * np.sqrt(4)
        sharpe = (r.mean() * 4) / vol if vol else np.nan
        return comp, cagr, vol, sharpe, len(r)

    # sanity: baseline over full history vs the published ~18.5% CAGR
    full = R.base_ret.notna()
    bc, bcagr, bvol, bsh, bn = stats("base_ret", full)
    print(f"\n  BASELINE sanity (full {R.period.iloc[0]}..{R.period.iloc[-1]}, "
          f"{bn} q): total {bc*100:+.0f}%  CAGR {bcagr*100:.1f}%  "
          f"vol {bvol*100:.1f}%  Sharpe {bsh:.2f}")

    # out-of-sample common window: where the factor book exists
    oos = R.fac_ret.notna()
    win = R[oos]
    print(f"\n  OUT-OF-SAMPLE window: {win.period.iloc[0]}..{win.period.iloc[-1]} "
          f"({len(win)} quarters)\n")
    for name, col in [("Baseline (score)", "base_ret"),
                      ("Factor-tilted", "fac_ret"), ("S&P 500", "spy")]:
        c, cg, v, s, n = stats(col, oos)
        print(f"  {name:<20} total {c*100:>+6.0f}%   CAGR {cg*100:>5.1f}%   "
              f"vol {v*100:>4.1f}%   Sharpe {s:>4.2f}")
    diff = (win.fac_ret - win.base_ret).dropna()
    t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
    print(f"\n  factor - baseline: mean {diff.mean():+.2f}pp/q, "
          f"t {t:+.2f}, factor wins {int((diff>0).sum())}/{len(diff)} quarters")
    beat_base = (win.base_ret > win.spy).mean() * 100
    beat_fac = (win.fac_ret > win.spy).mean() * 100
    print(f"  quarters beating S&P: baseline {beat_base:.0f}%, factor {beat_fac:.0f}%")

    # equity curves for the chart
    def curve(col):
        r = win[col].to_numpy(); return list(np.cumprod(1 + r) * 100)
    import json
    json.dump({
        "oos_periods": list(win.period),
        "curve_base": curve("base_ret"), "curve_fac": curve("fac_ret"),
        "curve_spy": curve("spy"),
        "baseline_full": {"total": bc, "cagr": bcagr, "vol": bvol, "sharpe": bsh, "n": bn},
        "oos": {name: dict(zip(["total", "cagr", "vol", "sharpe", "n"], stats(col, oos)))
                for name, col in [("base", "base_ret"), ("fac", "fac_ret"), ("spy", "spy")]},
        "fac_minus_base_pp_q": float(diff.mean()), "t": float(t),
        "fac_win_q": int((diff > 0).sum()), "n_q": int(len(diff)),
        "last_weights": R.dropna(subset=["fac_ret"]).iloc[-1].get("w", {}),
    }, open(HERE / "factor_tilt_results.json", "w"), indent=1)
    print("\n  wrote factor_tilt_results.json")


if __name__ == "__main__":
    main()
