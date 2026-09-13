#!/usr/bin/env python3
"""Equal weight vs signal-proportional position sizing, walk-forward.

Uses the cached panel from factor_tilt_backtest. Three quarterly books, all on
the same gate+beta eligible set, weights/selection fit only on prior data:
  EQ        top 25 by score, equal weight (the current book)
  SIZE      top 25 by score, weight proportional to factor signal (capped)
  FULL      top 25 by factor signal, weight proportional to factor signal
"""
import glob, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import GroupKFold
COMPS=["p_value","p_quality","p_cash","p_balance","p_growth"]; FEATS=COMPS+["size"]
ZC=[c+"_z" for c in FEATS]; TOP=25; CAP=0.08
df=pd.read_parquet(HERE/"factor_panel.parquet")
spy=pd.read_json(HERE/"factor_spy_q.json", typ="series")
periods=sorted(df.period.unique())

def elig(g):
    nd=g["debt"]-g["cash"]
    return g[(g.growth>=20)&(g.growth<=80)&(g.ni>0)&(g.fcf>0)&(g.roic>=10)
             &(nd<=3*g.ebitda)&(g.fcf_conv>=50)&g.beta.notna()&(g.beta<=1.3)]

def weights(train):
    X=train[ZC].to_numpy(); y=train["yz"].to_numpy()
    grp=train.period.astype("category").cat.codes.to_numpy(); k=min(5,len(np.unique(grp)))
    if k<2: return np.zeros(len(FEATS))
    m=ElasticNetCV(l1_ratio=[.1,.5,1.0],n_alphas=40,cv=GroupKFold(k).split(X,y,grp),
                   max_iter=20000,n_jobs=-1); m.fit(X,y); return m.coef_

def sw(sig):                                   # signal -> capped long weights
    s=sig-sig.min()+0.05*(sig.std() or 1); w=s/s.sum()
    for _ in range(50):
        over=w>CAP
        if not over.any(): break
        ex=(w[over]-CAP).sum(); w[over]=CAP
        u=~over; w[u]+=ex*w[u]/w[u].sum()
    return w/w.sum()

rows=[]
for i,p in enumerate(periods):
    g=elig(df[df.period==p]).copy()
    if len(g)<5: continue
    r={"period":p,"spy":float(spy.get(p,np.nan))}
    base=g.sort_values("score",ascending=False).head(TOP)
    r["eq"]=float(base.fwd.mean())
    if i>=8:
        w=weights(df[df.period.isin(periods[:i])])
        g["sig"]=g[ZC].to_numpy()@w
        b=base.copy(); b["sig"]=b[ZC].to_numpy()@w
        r["size"]=float(np.dot(sw(b["sig"].to_numpy()), b.fwd.to_numpy()))
        f=g.sort_values("sig",ascending=False).head(TOP)
        r["full"]=float(np.dot(sw(f["sig"].to_numpy()), f.fwd.to_numpy()))
    rows.append(r)
R=pd.DataFrame(rows); oos=R["size"].notna()
def st(col):
    r=R.loc[oos,col].dropna().to_numpy(); c=np.prod(1+r)-1; yr=len(r)/4
    return c, (1+c)**(1/yr)-1, r.std(ddof=1)*np.sqrt(4), (r.mean()*4)/(r.std(ddof=1)*np.sqrt(4))
print(f"\n  OOS {R[oos].period.iloc[0]}..{R[oos].period.iloc[-1]} ({int(oos.sum())} quarters)\n")
for nm,c in [("Equal weight (current)","eq"),("Signal-sized top25","size"),
             ("Signal select + size","full"),("S&P 500","spy")]:
    tot,cg,v,s=st(c); print(f"  {nm:<24} total {tot*100:>+6.0f}%  CAGR {cg*100:>5.1f}%  vol {v*100:>4.1f}%  Sharpe {s:>4.2f}")
for c in ["size","full"]:
    d=(R.loc[oos,c]-R.loc[oos,"eq"]).dropna()
    t=d.mean()/(d.std(ddof=1)/np.sqrt(len(d)))
    print(f"  {c} - equal: {d.mean():+.2f}pp/q, t {t:+.2f}, wins {int((d>0).sum())}/{len(d)}")
