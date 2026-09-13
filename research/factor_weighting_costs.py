#!/usr/bin/env python3
"""Turnover- and cost-adjusted comparison of equal vs signal-proportional sizing.

Tracks holdings across quarters, drifts prior weights by realised returns, and
charges a one-way cost on the traded notional at each rebalance. Reports gross
and net (CAGR, Sharpe) for equal weight, signal-sized, and signal-select+size,
across a range of cost assumptions, plus average one-way turnover per book.
"""
import sys, warnings
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

def sw(sig):
    s=sig-sig.min()+0.05*(sig.std() or 1); w=s/s.sum()
    for _ in range(50):
        over=w>CAP
        if not over.any(): break
        ex=(w[over]-CAP).sum(); w[over]=CAP; u=~over; w[u]+=ex*w[u]/w[u].sum()
    return w/w.sum()

# per book: list of dicts {ticker: target_w}, and {ticker: fwd} for drift
books={b:{"prev_w":{},"prev_r":{},"gross":[],"turn":[]} for b in ["eq","size","full"]}
qs=[]
for i,p in enumerate(periods):
    if i<8: continue
    g=elig(df[df.period==p]).copy()
    if len(g)<5: continue
    w=weights(df[df.period.isin(periods[:i])]); g["sig"]=g[ZC].to_numpy()@w
    base=g.sort_values("score",ascending=False).head(TOP)
    fsel=g.sort_values("sig",ascending=False).head(TOP)
    targets={
        "eq":  {t:1/len(base) for t in base.ticker},
        "size":dict(zip(base.ticker, sw(base["sig"].to_numpy()))),
        "full":dict(zip(fsel.ticker, sw(fsel["sig"].to_numpy()))),
    }
    frets={"eq":dict(zip(base.ticker,base.fwd)),"size":dict(zip(base.ticker,base.fwd)),
           "full":dict(zip(fsel.ticker,fsel.fwd))}
    for b in books:
        tw=targets[b]; pw=books[b]["prev_w"]; pr=books[b]["prev_r"]
        # drift prior weights by their realised return over the prior quarter
        if pw:
            dv={t:pw[t]*(1+pr.get(t,0)) for t in pw}; s=sum(dv.values()); dw={t:v/s for t,v in dv.items()}
        else:
            dw={}
        names=set(tw)|set(dw)
        turn2=sum(abs(tw.get(t,0)-dw.get(t,0)) for t in names)   # two-way traded
        books[b]["turn"].append(0.5*turn2)                       # one-way turnover
        books[b]["gross"].append(sum(tw[t]*frets[b][t] for t in tw))
        books[b]["_turn2"]=books[b].get("_turn2",[]); books[b]["_turn2"].append(turn2)
        books[b]["prev_w"]=tw; books[b]["prev_r"]=frets[b]
    qs.append(p)

def stats(r):
    r=np.array(r); c=np.prod(1+r)-1; yr=len(r)/4
    return (1+c)**(1/yr)-1, r.std(ddof=1)*np.sqrt(4), (r.mean()*4)/(r.std(ddof=1)*np.sqrt(4)), c

print(f"\n  OOS {qs[0]}..{qs[-1]} ({len(qs)} quarters)\n")
print(f"  {'book':<22}{'turnover/q':>12}{'gross CAGR':>12}{'gross Shrp':>12}")
for b,nm in [("eq","Equal weight"),("size","Signal-sized"),("full","Signal sel + size")]:
    to=np.mean(books[b]["turn"])*100; cg,v,sh,_=stats(books[b]["gross"])
    print(f"  {nm:<22}{to:>11.0f}%{cg*100:>11.1f}%{sh:>12.2f}")

print(f"\n  NET of one-way transaction cost (applied to traded notional):\n")
print(f"  {'cost (1-way)':<14}{'EQ CAGR':>9}{'SIZE CAGR':>11}{'FULL CAGR':>11}   "
      f"{'EQ Shrp':>8}{'SIZE Shrp':>10}{'FULL Shrp':>10}")
for c in [0.0005,0.0010,0.0020,0.0030]:
    net={b:[g-c*t2 for g,t2 in zip(books[b]["gross"],books[b]["_turn2"])] for b in books}
    s={b:stats(net[b]) for b in books}
    print(f"  {c*1e4:>4.0f} bps      "
          f"{s['eq'][0]*100:>8.1f}%{s['size'][0]*100:>10.1f}%{s['full'][0]*100:>10.1f}%   "
          f"{s['eq'][2]:>8.2f}{s['size'][2]:>10.2f}{s['full'][2]:>10.2f}")

# significance of net return diff at 20bps
c=0.0020
net={b:np.array([g-c*t2 for g,t2 in zip(books[b]["gross"],books[b]["_turn2"])]) for b in books}
for b in ["size","full"]:
    d=net[b]-net["eq"]; t=d.mean()/(d.std(ddof=1)/np.sqrt(len(d)))
    print(f"\n  {b}-eq net@20bps: {d.mean():+.2f}pp/q, t {t:+.2f}, wins {int((d>0).sum())}/{len(d)}")
