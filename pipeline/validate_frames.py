#!/usr/bin/env python3
"""Cross-check the panel against SEC's own aggregation of the same filings.

The panel is built by walking each company's companyfacts file and picking the
right figure for the right period. SEC separately publishes "frames": every
filer that reported a given tag for a given period, already collected. That is
an independent route to the same number, so disagreement means one of the two
readings is wrong, and it is worth knowing which.

Balance sheet items are used because they are instantaneous: a single value at
a single date, comparable without any reconstruction. Revenue would need the
trailing-twelve-month rebuild, which is the thing being checked.

Only companies whose panel period end matches the frame's own end are compared,
so a company on a different fiscal calendar is skipped rather than counted as a
disagreement.
"""
import json, sys
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
UA   = {"User-Agent": "Bilaal Raja bilaal.raja4567@gmail.com"}
TOL  = 0.005          # 0.5%: rounding, not a different reading
CHECKS = [("Assets", "assets"), ("StockholdersEquity", "equity")]


def frame(tag, period):
    url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
    r = requests.get(url, headers=UA, timeout=90)
    if r.status_code != 200:
        return None
    return {int(d["cik"]): d for d in r.json().get("data", [])}


def main():
    panel = json.loads((HERE / "r3k_scored.json").read_text())
    by_cik = {int(r["cik"]): r for r in panel if r.get("cik")}

    # the period the bulk of the panel sits in
    ends = {}
    for r in panel:
        if r.get("end"):
            ends[r["end"]] = ends.get(r["end"], 0) + 1
    median_end = max(ends, key=ends.get)
    y, m, _ = median_end.split("-")
    period = f"CY{y}Q{(int(m)-1)//3 + 1}I"
    print(f"panel's most common period end {median_end} -> frame {period}")

    total_bad = 0
    summary = {"period": period, "checks": {}, "asof": None}
    for tag, field in CHECKS:
        f = frame(tag, period)
        if f is None:
            print(f"  {tag}: frame unavailable, skipped")
            continue
        checked = bad = 0
        worst = []
        for cik, d in f.items():
            row = by_cik.get(cik)
            if not row or row.get(field) is None:
                continue
            if row.get("end") != d.get("end"):
                continue                       # different fiscal calendar
            mine = float(row[field]) * 1e9     # panel carries $bn
            theirs = float(d["val"])
            if theirs == 0:
                continue
            checked += 1
            diff = abs(mine - theirs) / abs(theirs)
            if diff > TOL:
                bad += 1
                worst.append((diff, row.get("ticker"), mine / 1e9, theirs / 1e9))
        worst.sort(reverse=True)
        total_bad += bad
        pct = 100 * bad / checked if checked else 0
        summary["checks"][tag] = {"compared": checked, "disagreed": bad}
        print(f"  {tag:20} compared {checked:5}  disagreed {bad:4} ({pct:.2f}%)")
        for diff, tk, mine, theirs in worst[:5]:
            print(f"      {tk:6} panel ${mine:,.2f}bn  vs SEC ${theirs:,.2f}bn"
                  f"  ({diff*100:.1f}%)")
    from datetime import date as _d
    summary["asof"] = str(_d.today())
    summary["compared"] = sum(c["compared"] for c in summary["checks"].values())
    summary["disagreed"] = total_bad
    (HERE / "frames_check.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"total disagreements: {total_bad}  ->  frames_check.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
