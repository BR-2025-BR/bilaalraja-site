#!/usr/bin/env python3
"""As-filed share counts for the whole study universe, once.

dei:EntityCommonStockSharesOutstanding is the number the company stated on the
cover page of a filing, together with the date that filing was made. Keeping the
filing date is what makes it usable point-in-time: at any as-of date, take the
most recent count filed strictly before it, and nothing later can leak in.
"""
import json, re
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
C = Path('/Users/bilaa/Downloads/pitquant/data/cache/edgar')
uni = [int(c) for c in json.loads((HERE / 'universe_final.json').read_text())]

rows = []
for i, cik in enumerate(uni):
    f = C / f"companyfacts_{cik:010d}.json"
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
            if u.get('val') and u.get('filed'):
                rows.append((cik, u['filed'], u.get('end'), float(u['val'])))
    if i % 1500 == 0:
        print(f"    {i}/{len(uni)}", flush=True)

d = pd.DataFrame(rows, columns=['cik', 'filed', 'end', 'shares'])
d['filed'] = pd.to_datetime(d.filed, errors='coerce')
d = d.dropna(subset=['filed', 'shares'])
d = d.sort_values(['cik', 'filed']).drop_duplicates(['cik', 'filed'], keep='last')
d.to_parquet(HERE / 'shares.parquet', index=False)
print(f"  {len(d):,} share observations for {d.cik.nunique():,} companies")
print(f"  filing dates {d.filed.min().date()} to {d.filed.max().date()}")
