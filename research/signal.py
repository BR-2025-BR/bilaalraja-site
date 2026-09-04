#!/usr/bin/env python3
"""Build dtone exactly as the pre-registration and its amendments specify.

Order matters and is fixed:

  1. quality filter   drop a filing whose word count is below 50% or above 200%
                      of that company's median for that form (Amendment 1B)
  2. length control   residualise tone on log(words) within company and form, so
                      dtone measures a change in language rather than a change
                      in how much of it the extractor captured (Amendment 1B)
  3. form-matched     baseline is the mean of the previous FOUR filings of the
     baseline         SAME form, strictly before t (Amendment 1A). 10-K tone
                      runs about 0.05 below 10-Q tone, so a mixed baseline would
                      have made every annual report look like deteriorating tone
                      on the calendar alone
  4. dtone            residualised tone minus that baseline

Fewer than four same-form priors: excluded, not zero-filled. Every exclusion is
counted and reported rather than quietly applied.

Writes research/signal.parquet. Development window only; the holdout stays shut.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEV_END = "2023-01-01"
N_PRIOR = 4
Q_LO, Q_HI = 0.50, 2.00          # quality filter bounds, as a fraction of median


def build(path=HERE / "finbert_dev.json"):
    raw = json.loads(Path(path).read_text())
    rows = []
    for cik, filings in raw.items():
        for f in filings:
            rows.append({"cik": int(cik), "form": f["form"], "filed": f["filed"],
                         "period": f["period"], "words": f["words"],
                         "tone": f["fb_tone"], "neg": f["fb_share_neg"],
                         "sd": f["fb_sd"], "lm": f.get("lm_tone")})
    d = pd.DataFrame(rows)
    d["filed"] = pd.to_datetime(d["filed"])
    n0 = len(d)
    print(f"  scored filings                    {n0:,}")

    # The holdout must not be touched. Phase 2 already restricted itself, but
    # assert rather than assume: a silent leak here would invalidate everything.
    leak = (d.filed >= DEV_END).sum()
    if leak:
        raise SystemExit(f"HOLDOUT LEAK: {leak} filings dated {DEV_END} or later")
    print(f"  holdout leakage                   0  (asserted)")

    # ---- 1. quality filter ------------------------------------------------
    med = d.groupby(["cik", "form"])["words"].transform("median")
    keep = (d.words >= Q_LO * med) & (d.words <= Q_HI * med)
    dropped = int((~keep).sum())
    d = d[keep].copy()
    print(f"  dropped by quality filter         {dropped:,}  "
          f"({dropped/n0:.1%})  -> {len(d):,} remain")

    # ---- 2. length control ------------------------------------------------
    # Within company and form, regress tone on log(words) and keep the residual.
    # Groups with fewer than three filings cannot support a slope, so they keep
    # their demeaned tone: no residualisation, but no fabricated slope either.
    d["logw"] = np.log(d.words.clip(lower=1))

    def resid(g):
        if len(g) < 3 or g.logw.std() == 0:
            return g.tone - g.tone.mean()
        b = np.polyfit(g.logw, g.tone, 1)
        return g.tone - (b[0] * g.logw + b[1])

    d["tone_r"] = (d.groupby(["cik", "form"], group_keys=False)
                     .apply(resid, include_groups=False))
    print(f"  length-residualised tone: mean {d.tone_r.mean():+.5f} "
          f"sd {d.tone_r.std():.4f}  (raw sd {d.tone.std():.4f})")

    # ---- 3. form-matched baseline, 4 priors -------------------------------
    d = d.sort_values(["cik", "form", "filed"]).reset_index(drop=True)
    g = d.groupby(["cik", "form"], sort=False)
    for col, src in (("base_r", "tone_r"), ("base_raw", "tone")):
        # shift(1) first so the current filing never enters its own baseline
        d[col] = (g[src].shift(1)
                        .groupby([d.cik, d.form], sort=False)
                        .rolling(N_PRIOR, min_periods=N_PRIOR).mean()
                        .reset_index(level=[0, 1], drop=True))
    d["n_prior"] = g.cumcount()

    usable = d.base_r.notna()
    print(f"  fewer than {N_PRIOR} same-form priors        "
          f"{int((~usable).sum()):,}  -> {int(usable.sum()):,} usable")
    d = d[usable].copy()

    # ---- 4. the signal ----------------------------------------------------
    d["dtone"] = d.tone_r - d.base_r          # primary, length-controlled
    d["dtone_raw"] = d.tone - d.base_raw      # specification 2, no control
    d["level"] = d.tone_r                     # specification 5, the straw man
    d["quarter"] = d.filed.dt.to_period("Q").astype(str)

    print(f"\n  dtone      mean {d.dtone.mean():+.5f}  sd {d.dtone.std():.4f}  "
          f"p5 {d.dtone.quantile(.05):+.3f}  p95 {d.dtone.quantile(.95):+.3f}")
    print(f"  dtone_raw  mean {d.dtone_raw.mean():+.5f}  sd {d.dtone_raw.std():.4f}")
    print(f"  companies {d.cik.nunique():,}   quarters {d.quarter.nunique()}   "
          f"10-K {int((d.form=='10-K').sum()):,}  10-Q {int((d.form=='10-Q').sum()):,}")

    out = HERE / "signal.parquet"
    d.to_parquet(out, index=False)
    print(f"\n  wrote {out.name}  {len(d):,} observations")
    return d


if __name__ == "__main__":
    build()
