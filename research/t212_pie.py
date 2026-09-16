#!/usr/bin/env python3
"""Build a Trading 212 Pie from the signal-weighted portfolio.

    T212_KEY=... python3 research/t212_pie.py plan     # read-only: resolves tickers,
                                                        # shows target weights + payload
    T212_KEY=... T212_BASE=https://live.trading212.com/api/v0 \
        python3 research/t212_pie.py create             # actually creates the pie

Defaults to the DEMO endpoint and to `plan`. Creating a pie only defines a target
allocation -- it does NOT buy anything by itself; you fund it separately. Even so
this writes to your account, so `plan` first, demo first.

Weights come from research/signal_pie_weights.json (the current signal-weighted
book). Any name Trading 212 cannot trade is dropped and the rest are renormalised
to sum to 1.0, which the API requires.
"""
import json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = os.environ.get("T212_KEY", "")
BASE = os.environ.get("T212_BASE", "https://demo.trading212.com/api/v0")
PAUSE = 5.2
PIE_NAME = os.environ.get("PIE_NAME", "Signal-weighted (gate + quality/cash)")


def call(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 headers={"Authorization": KEY, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            txt = r.read().decode(errors="replace")
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"  {method} {path} -> {e.code} {e.reason}\n  {e.read().decode(errors='replace')[:400]}")


def resolve(instruments, tickers):
    """Plain ticker -> Trading 212 USD-stock instrument code, matched on shortName."""
    by_short = {}
    for i in instruments:
        if i.get("type") == "STOCK" and i.get("currencyCode") == "USD":
            by_short.setdefault((i.get("shortName") or "").upper(), i)
    found, missing = {}, []
    for t in tickers:
        hit = by_short.get(t.upper())
        (found.__setitem__(t, hit["ticker"]) if hit else missing.append(t))
    return found, missing


def renorm(shares):
    s = sum(shares.values())
    out = {k: round(v / s, 4) for k, v in shares.items()}
    out[max(out, key=out.get)] += round(1 - sum(out.values()), 4)   # fix rounding residual
    return out


def main():
    if not KEY:
        raise SystemExit("  set T212_KEY (Settings -> API (Beta), needs pies scope)")
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    tgt = json.load(open(HERE / "signal_pie_weights.json"))
    print(f"  mode: {'CREATE -- writes a pie to your account' if mode=='create' else 'plan (read-only)'}")
    print(f"  base: {BASE}")
    print(f"  source weights: {tgt['asof']}, {tgt['n']} names\n")

    instruments = call("/equity/metadata/instruments"); time.sleep(PAUSE)
    found, missing = resolve(instruments, tgt["weights"].keys())
    print(f"  resolved {len(found)}/{tgt['n']} to tradeable T212 instruments")
    if missing:
        print(f"  NOT ON T212 (dropped, weights renormalised): {', '.join(missing)}")

    shares = renorm({found[t]: tgt["weights"][t] for t in found})
    print(f"\n  {'ticker':<8}{'T212 code':<18}{'weight':>9}")
    inv = {v: k for k, v in found.items()}
    for code, wt in sorted(shares.items(), key=lambda kv: -kv[1]):
        print(f"  {inv[code]:<8}{code:<18}{wt*100:>8.2f}%")
    print(f"  {'sum':<26}{sum(shares.values())*100:>8.2f}%")

    payload = {"name": PIE_NAME, "dividendCashAction": "REINVEST",
               "icon": "Cash", "instrumentShares": shares}
    print(f"\n  payload that `create` would POST to /equity/pies:")
    print("   ", json.dumps(payload)[:300], "...")

    if mode != "create":
        print("\n  plan only. Re-run with `create` (and T212_BASE=live... for the live account) to build it.")
        return
    time.sleep(PAUSE)
    res = call("/equity/pies", "POST", payload)
    print(f"\n  created pie id {res.get('id')} -- fund it in the app to start investing.")


if __name__ == "__main__":
    main()
