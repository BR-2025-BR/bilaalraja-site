#!/usr/bin/env python3
"""Pull the study universe out of SEC's bulk companyfacts archive.

One request for the whole archive beats 4,329 requests for its parts. SEC
publishes it precisely so nobody has to walk the API for bulk work, and it kept
working while the API was throttling us - the block is on the JSON endpoint, not
on the static archive.

Only the CIKs the study needs are written out, so the 18GB of uncompressed JSON
never lands on disk.
"""
import json, re, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path('/Users/bilaa/Downloads/pitquant/data/cache/edgar')
ZIP = Path('/Users/bilaa/.claude/jobs/88de6188/tmp/companyfacts.zip')

uni = {int(c) for c in json.loads((HERE / 'universe_final.json').read_text())}
have = {int(re.search(r'companyfacts_(\d+)', p.name).group(1))
        for p in CACHE.glob('companyfacts_*.json')}
want = uni - have
print(f"  universe {len(uni):,} | already cached {len(uni & have):,} | to extract {len(want):,}",
      flush=True)

wanted_names = {f"CIK{c:010d}.json": c for c in want}
written = missing = 0
with zipfile.ZipFile(ZIP) as z:
    names = set(z.namelist())
    present = wanted_names.keys() & names
    print(f"  present in the archive: {len(present):,} of {len(want):,}", flush=True)
    for i, nm in enumerate(sorted(present), 1):
        cik = wanted_names[nm]
        (CACHE / f"companyfacts_{cik:010d}.json").write_bytes(z.read(nm))
        written += 1
        if i % 500 == 0:
            print(f"    {i}/{len(present)}", flush=True)
    # A filer absent from the archive has no XBRL facts at all, which is a fact
    # about the company rather than a gap in the data. Recorded as such so the
    # panel build does not retry it forever.
    for nm, cik in wanted_names.items():
        if nm not in names:
            (CACHE / f"companyfacts_{cik:010d}.json").write_text('{"facts":{}}')
            missing += 1

print(f"  extracted {written:,}, marked absent {missing:,}")
cov = len(uni & ({int(re.search(r'companyfacts_(\d+)', p.name).group(1))
                  for p in CACHE.glob('companyfacts_*.json')}))
print(f"  study universe now covered: {cov:,} of {len(uni):,} ({cov/len(uni):.0%})")
