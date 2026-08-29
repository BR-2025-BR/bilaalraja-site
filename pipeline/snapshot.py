#!/usr/bin/env python3
"""Archive each build, so the panel becomes a history instead of a snapshot.

Every refresh currently overwrites the last one. That throws away the single
most valuable property this pipeline has: the figures are as-filed, with no
lookahead and no restatement. Keep them and you accumulate a point-in-time
database that cannot be reconstructed later, because once a filer restates,
the earlier reading is gone from companyfacts and there is no way back to what
a screen actually showed on a given day.

The whole panel is kept rather than a chosen subset. It gzips to well under a
megabyte, and a field left out today cannot be recovered in a year's time.

Same-day rebuilds overwrite: the last build of a day is what that day saw.
"""
import gzip, json, re, sys
from datetime import date
from pathlib import Path

HERE    = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "archive"


def _load(name):
    f = HERE / name
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        print(f"  WARNING: {name} unreadable, archived as null")
        return None


def main():
    panel = _load("r3k_scored.json")
    if not panel:
        sys.exit("snapshot: no scored panel to archive")

    dash = (HERE / "r3k_dashboard.html")
    meta = {}
    if dash.exists():
        m = re.search(r"META\s*=\s*(\{.*?\})\s*,\s*METRICS\s*=",
                      dash.read_text(errors="replace"), re.S)
        if m:
            meta = json.loads(m.group(1))

    # Date the snapshot by the data, not the clock: a build run after midnight
    # belongs to the day whose prices it carries.
    day = meta.get("price_date") or str(date.today())

    snap = {
        "snapshot_date": day,
        "built": meta.get("built"),
        "price_date": meta.get("price_date"),
        "latest_filing": meta.get("latest_filing"),
        "n": len(panel),
        "meta": meta,
        "rates": _load("rates.json"),
        "frames_check": _load("frames_check.json"),
        "form4": _load("form4.json"),
        "panel": panel,
    }

    ARCHIVE.mkdir(exist_ok=True)
    out = ARCHIVE / f"{day}.json.gz"
    existed = out.exists()
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(snap, fh, separators=(",", ":"))

    # An index so a reader can see the history without opening every file.
    idx_path = ARCHIVE / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    idx = [e for e in idx if e.get("date") != day]
    idx.append({
        "date": day,
        "built": snap["built"],
        "n": snap["n"],
        "latest_filing": snap["latest_filing"],
        "total_mcap_bn": round(sum(r.get("mcap") or 0 for r in panel), 1),
        "bytes": out.stat().st_size,
    })
    idx.sort(key=lambda e: e["date"])
    idx_path.write_text(json.dumps(idx, indent=1) + "\n")

    mb = out.stat().st_size / 1e6
    total = sum(e["bytes"] for e in idx) / 1e6
    print(f"  {'rewrote' if existed else 'archived'} {out.name}  {mb:.2f} MB  "
          f"{snap['n']} companies")
    print(f"  archive now holds {len(idx)} snapshot(s), {total:.1f} MB total")


if __name__ == "__main__":
    main()
