"""Split history for every candidate, so share counts can be aligned to the price date.

A cover-page share count carries the date it was filed. If the company split its
stock after that date, the count no longer corresponds to the shares the quoted
price refers to, and market cap is wrong by the split ratio. Reverse splits
inflate, which puts shell-scale companies high in a market-cap ranking.
"""
import json, time
from pathlib import Path
import pandas as pd, yfinance as yf

HERE = Path(__file__).resolve().parent
df    = pd.read_json(HERE/"universe_stage0.json")
extra = json.load(open(HERE/"needs_price.json"))
tick  = list(dict.fromkeys(list(df.ticker) + [e[1] for e in extra]))
print(f"{len(tick)} tickers", flush=True)

out, CH = {}, 100
for i in range(0, len(tick), CH):
    chunk = tick[i:i+CH]
    for attempt in range(4):
        try:
            d = yf.download(chunk, period="2y", progress=False, auto_adjust=False,
                            actions=True, threads=True)
            if d is None or d.empty: raise ValueError("empty frame")
            sp = d["Stock Splits"] if isinstance(d.columns, pd.MultiIndex) else d[["Stock Splits"]]
            if not isinstance(d.columns, pd.MultiIndex): sp.columns = chunk[:1]
            for t in sp.columns:
                s = sp[t]; nz = s[(s != 0) & s.notna()]
                if len(nz):
                    out[t] = [[str(dt)[:10], float(v)] for dt, v in nz.items()]
            break
        except Exception as e:
            if attempt == 3: print(f"  chunk {i} gave up: {type(e).__name__}", flush=True)
            time.sleep(5*(attempt+1))          # rate limits need real backoff
    print(f"  {min(i+CH,len(tick))}/{len(tick)}  with-splits={len(out)}", flush=True)
    time.sleep(2)                              # deliberate pacing between chunks

json.dump(out, open(HERE/"splits_snapshot.json","w"), indent=0)
print(f"\ntickers with >=1 split in 2y: {len(out)}", flush=True)
rev = {t:v for t,v in out.items() if any(r < 1 for _,r in v)}
print(f"of which have a REVERSE split: {len(rev)}", flush=True)
