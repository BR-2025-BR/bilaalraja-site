#!/usr/bin/env python3
"""Point-in-time market cap for specification 4.

Sharadar's DAILY table is not in this subscription: the bulk route 403s and the
paged one returns about thirty Dow names. So market cap is built from the share
count on each filing's own cover page - dei:EntityCommonStockSharesOutstanding,
as filed, taken from the most recent report ending on or before the filing date -
multiplied by that day's close.

That is arguably a better source than a vendor's: it is the number the company
itself stated at the time, and it cannot be restated after the fact.
"""
import json, re, sys
from pathlib import Path
import pandas as pd, numpy as np

HERE = Path(__file__).resolve().parent
C = Path('/Users/bilaa/Downloads/pitquant/data/cache/edgar')
sys.path.insert(0, str(HERE.parent / 'pipeline'))
from prices import closes

d = pd.read_parquet(HERE / 'panel_returns.parquet')
ciks = sorted(d.cik.unique())
rows = []
for i, c in enumerate(ciks):
    f = C / f"companyfacts_{c:010d}.json"
    if not f.exists():
        continue
    try:
        dei = json.loads(f.read_text()).get('facts', {}).get('dei', {})
    except Exception:
        continue
    sh = dei.get('EntityCommonStockSharesOutstanding')
    if not sh:
        continue
    for units in (sh.get('units') or {}).values():
        for u in units:
            if u.get('end') and u.get('val'):
                rows.append((c, u['end'], float(u['val'])))
    if i % 800 == 0:
        print(f"    {i}/{len(ciks)}", flush=True)

s = pd.DataFrame(rows, columns=['cik', 'end', 'shares'])
s['end'] = pd.to_datetime(s['end'], errors='coerce')
s = s.dropna().sort_values(['cik', 'end']).drop_duplicates(['cik', 'end'], keep='last')
print(f"  share observations {len(s):,} for {s.cik.nunique():,} companies")

# most recent count on or before each filing date
d2 = d[['cik', 'ticker', 'filed', 'p1_date']].sort_values('filed')
merged = pd.merge_asof(d2, s.rename(columns={'end': 'filed'}).sort_values('filed'),
                       on='filed', by='cik', direction='backward')
print(f"  matched a share count for {merged.shares.notna().sum():,} of {len(merged):,}")

px = closes(sorted(d.ticker.unique()), '2018-01-01', '2023-06-30')
stack = px.stack().rename('close').reset_index()
stack.columns = ['p1_date', 'ticker', 'close']
out = merged.merge(stack, on=['ticker', 'p1_date'], how='left')
out['marketcap'] = out.shares * out.close / 1e6          # $m
out = out[['ticker', 'p1_date', 'marketcap']].dropna().drop_duplicates(['ticker','p1_date'])
out.to_parquet(HERE / 'mcap.parquet', index=False)
print(f"  wrote mcap.parquet {len(out):,} rows")
print(f"  median ${out.marketcap.median():,.0f}m   "
      f">= $1bn: {(out.marketcap>=1000).sum():,} ({(out.marketcap>=1000).mean():.0%})")
