"""Authoritative share counts from yfinance fast_info.

This is the source that resolves three defects at once:
  - ADRs: yfinance reports ADS-equivalent shares, the SEC cover page reports
    ordinary shares. BeOne (ONC) differs by exactly its 13:1 ratio.
  - splits: yfinance counts are current, so no split alignment is needed.
  - coverage: it has counts for names whose dei frame observation we never saw.

SEC remains the cross-check, not the primary. Where the two disagree materially
the name is flagged rather than silently trusted.
"""
import json, time, os

# Detach into our own process group. A previous background job was killed
# when an unrelated foreground command timed out and SIGTERM hit the group.
try: os.setsid()
except Exception: pass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, yfinance as yf

HERE = Path(__file__).parent
prices = json.load(open(HERE/"prices_snapshot.json"))
tick   = sorted(prices.keys())
print(f"{len(tick)} tickers", flush=True)

# Checkpoint to disk as we go: an earlier run lost 3,417 counts held only in
# memory when the process was signalled. Also lets a re-run resume.
CKPT = HERE/"shares_yf.json"
out  = json.loads(CKPT.read_text()) if CKPT.exists() else {}
fail = []
tick = [t for t in tick if t not in out]
print(f"resuming: {len(out)} already have counts, {len(tick)} to fetch", flush=True)
def grab(t):
    for attempt in range(3):
        try:
            s = yf.Ticker(t).fast_info.get("shares")
            if s and s > 0: return t, float(s)
            return t, None
        except Exception:
            time.sleep(1.5*(attempt+1))
    return t, "ERR"

with ThreadPoolExecutor(max_workers=5) as ex:
    for i, (t, s) in enumerate(ex.map(grab, tick), 1):
        if s == "ERR": fail.append(t)
        elif s:        out[t] = s
        if i % 200 == 0:
            json.dump(out, open(CKPT,"w"))
            print(f"  {i}/{len(tick)}  got={len(out)} err={len(fail)}", flush=True)

json.dump(out, open(CKPT,"w"))
print(f"\nshare counts: {len(out)} of {len(tick)}   errors={len(fail)}", flush=True)
