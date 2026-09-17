#!/usr/bin/env python3
"""Historical US Treasury yields and the Fed funds rate, for the rates chart.

Two public, no-key sources (FRED itself is unreachable behind some networks):
  * Treasury daily par yield curve  -> 2y / 10y / 30y (and 1y / 5y)
  * New York Fed reference rates API -> EFFR, the effective federal funds rate,
    i.e. the US policy ("bank") rate.

Writes rates_history.json: aligned daily series from START to today.

    python3 fetch_rates_history.py
"""
import csv, io, json, sys
from datetime import date
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "rates_history.json"
START = 2015
UA = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
TCOLS = {"1 Yr": "y1", "2 Yr": "y2", "5 Yr": "y5", "10 Yr": "y10", "30 Yr": "y30"}
TURL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        "daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&_format=csv")
EFFR = ("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
        "?startDate={a}&endDate={b}")


def iso(mdy):
    m, d, y = mdy.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def treasury():
    """{date: {y1,y2,y5,y10,y30}} across all years from START."""
    out = {}
    for y in range(START, date.today().year + 1):
        r = requests.get(TURL.format(y=y), headers=UA, timeout=60)
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.text)))
        for row in rows:
            d = iso(row["Date"])
            rec = {}
            for col, key in TCOLS.items():
                v = (row.get(col) or "").strip()
                if v not in ("", "N/A"):
                    rec[key] = float(v)
            if rec:
                out[d] = rec
        print(f"  treasury {y}: {len(rows)} rows", flush=True)
    return out


def effr():
    """{date: rate} effective federal funds rate."""
    a, b = f"{START}-01-01", date.today().isoformat()
    r = requests.get(EFFR.format(a=a, b=b), headers=UA, timeout=60)
    r.raise_for_status()
    out = {}
    for x in r.json().get("refRates", []):
        if x.get("type") == "EFFR" and x.get("percentRate") is not None:
            out[x["effectiveDate"]] = float(x["percentRate"])
    print(f"  EFFR: {len(out)} observations", flush=True)
    return out


def main():
    ty = treasury()
    ff = effr()
    dates = sorted(set(ty) | set(ff))
    series = {k: [] for k in ("y1", "y2", "y5", "y10", "y30", "ffr")}
    for d in dates:
        rec = ty.get(d, {})
        for k in ("y1", "y2", "y5", "y10", "y30"):
            series[k].append(rec.get(k))
        series["ffr"].append(ff.get(d))
    payload = {
        "updated": date.today().isoformat(),
        "start": dates[0], "end": dates[-1], "n": len(dates),
        "sources": {"yields": "US Treasury daily par yield curve",
                    "ffr": "Federal Reserve Bank of New York (EFFR)"},
        "dates": dates, **series,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    last = {k: next((v for v in reversed(series[k]) if v is not None), None)
            for k in series}
    print(f"\n  {len(dates)} days {dates[0]}..{dates[-1]}  ({kb:.0f} KB)")
    print(f"  latest: 2y {last['y2']}  10y {last['y10']}  30y {last['y30']}  "
          f"Fed funds {last['ffr']}")


if __name__ == "__main__":
    main()
