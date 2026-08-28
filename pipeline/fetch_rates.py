#!/usr/bin/env python3
"""The US Treasury yield curve, from Treasury's own daily publication.

Why this is here: a valuation multiple on its own says nothing about whether
something is dear. A company on 28x earnings returns about 3.6p per pound a
year; a 10-year Treasury note currently pays more than that for no equity risk
at all. Holding the two side by side is the difference between "expensive"
as an opinion and as a measurement.

Public domain, no API key, no rate limit, no terms to fall foul of.
"""
import csv, io, json, sys
from datetime import date
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
OUT  = HERE / "rates.json"
URL  = ("https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/daily-treasury-rates.csv/{y}/all"
        "?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
WANT = {"1 Yr": "y1", "2 Yr": "y2", "5 Yr": "y5", "10 Yr": "y10", "30 Yr": "y30"}


def main():
    year = date.today().year
    r = requests.get(URL.format(y=year), timeout=45,
                     headers={"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"})
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    if not rows:
        sys.exit("fetch_rates: Treasury returned no rows")

    # The file is newest-first, but do not rely on that.
    def parsed(row):
        m, d, y = row["Date"].split("/")
        return f"{y}-{m}-{d}"
    rows.sort(key=parsed, reverse=True)
    latest = rows[0]

    out = {"date": parsed(latest), "source": "US Treasury daily par yield curve"}
    for col, key in WANT.items():
        v = (latest.get(col) or "").strip()
        out[key] = float(v) if v else None
    if out.get("y10") is None:
        sys.exit("fetch_rates: no 10-year yield in the latest row")

    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"  rates {out['date']}  "
          + "  ".join(f"{k}={out[k]}%" for k in ("y2","y10","y30") if out.get(k)))


if __name__ == "__main__":
    main()
