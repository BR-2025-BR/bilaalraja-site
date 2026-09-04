#!/usr/bin/env python3
"""Load a survivorship-free daily price history and serve panels from it.

Nothing here is vendor-specific beyond one column map. The vendor supplies CSV,
this normalises it once into Parquet, and every caller afterwards gets a plain
pandas DataFrame. Parquet rather than CSV only because 9.3 million rows reads in
about a second instead of half a minute; it is an open format and `to_csv()` is
one line away if you ever want the file somewhere else.

    python3 pipeline/prices.py ingest ~/Downloads/SHARADAR_SEP.csv
    python3 pipeline/prices.py ingest ~/Downloads/SHARADAR_TICKERS.csv --tickers
    python3 pipeline/prices.py check

    from prices import panel, closes
    px = closes(["AAPL", "MSFT"], "2019-01-01", "2023-12-31")

WHY THIS EXISTS AT ALL: yfinance drops a ticker the moment it delists, so a
backtest built on it can only ever hold companies that survived to today. Two
thirds of the study universe is already gone. A feed that keeps delisted names
is the whole point of paying for one, and this module refuses to silently
paper over a name it cannot price.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
STORE = HERE.parent / "prices"
STORE.mkdir(exist_ok=True)
PX = STORE / "daily.parquet"
TK = STORE / "tickers.parquet"

# Vendor column -> our name. Add a vendor by adding a row, not by editing logic.
COLMAP = {
    # Sharadar SEP
    "ticker": "ticker", "date": "date", "closeadj": "close",
    "volume": "volume", "close": "close_raw",
    # Polygon flat files
    "T": "ticker", "t": "date", "c": "close", "v": "volume",
    # EODHD
    "Date": "date", "Adjusted_close": "close", "Volume": "volume", "Code": "ticker",
}

# A performance-related delisting is not a zero return, and using the last quoted
# price overstates performance because the collapse never appears in the series.
# Shumway (1997) is the standard reference; -30% is the convention for
# performance-related delistings on NYSE/AMEX/Nasdaq.
DELIST_RETURN = -0.30


def ingest(csv_path, is_tickers=False):
    """Normalise a vendor CSV into the store. Safe to re-run."""
    src = Path(csv_path).expanduser()
    if not src.exists():
        sys.exit(f"no such file: {src}")

    if is_tickers:
        t = pd.read_csv(src, low_memory=False)
        t.columns = [c.strip().lower() for c in t.columns]
        keep = [c for c in ("permaticker", "ticker", "cik", "exchange", "isdelisted",
                            "firstpricedate", "lastpricedate", "name", "sector")
                if c in t.columns]
        if "cik" not in keep:
            print("  WARNING: no cik column. Without it the 2,805 companies whose "
                  "ticker SEC no longer publishes cannot be joined to the panel.")
        t = t[keep]
        if "cik" in t:
            t["cik"] = pd.to_numeric(t["cik"], errors="coerce").astype("Int64")
        t.to_parquet(TK, index=False)
        print(f"  tickers: {len(t):,} rows -> {TK.name}")
        if "isdelisted" in t:
            d = (t.isdelisted.astype(str).str.upper() == "Y").sum()
            print(f"  of which delisted: {d:,}  ({d/len(t):.0%})")
        return

    rows = []
    for chunk in pd.read_csv(src, chunksize=1_000_000, low_memory=False):
        chunk.columns = [c.strip() for c in chunk.columns]
        chunk = chunk.rename(columns=COLMAP)
        need = {"ticker", "date", "close"}
        if not need <= set(chunk.columns):
            sys.exit(f"columns {sorted(need - set(chunk.columns))} missing. "
                     f"Saw: {list(chunk.columns)[:12]}. Add them to COLMAP.")
        chunk = chunk[[c for c in ("ticker", "date", "close", "volume")
                       if c in chunk.columns]]
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce", format="mixed")
        chunk = chunk.dropna(subset=["date", "close"])
        rows.append(chunk)
        print(f"    {sum(len(r) for r in rows):,} rows", end="\r", flush=True)

    df = pd.concat(rows, ignore_index=True)
    df["ticker"] = df["ticker"].astype("category")
    df = df.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    df.to_parquet(PX, index=False)
    print(f"\n  prices: {len(df):,} rows, {df.ticker.nunique():,} tickers, "
          f"{df.date.min().date()} to {df.date.max().date()} -> {PX.name}")


def closes(tickers, start, end):
    """Wide DataFrame of adjusted closes: rows are dates, columns are tickers.

    Missing tickers are NOT silently dropped. A caller computing returns over a
    universe needs to know which names it could not price, because quietly
    omitting them is how survivorship bias gets back in after being paid to
    remove it.
    """
    if not PX.exists():
        sys.exit(f"{PX} not found. Run: python3 pipeline/prices.py ingest <csv>")
    want = list(dict.fromkeys(tickers))
    df = pd.read_parquet(PX, filters=[("date", ">=", pd.Timestamp(start)),
                                      ("date", "<=", pd.Timestamp(end))])
    df = df[df.ticker.isin(want)]
    wide = df.pivot_table(index="date", columns="ticker", values="close", observed=True)
    missing = [t for t in want if t not in wide.columns]
    if missing:
        print(f"  note: {len(missing)} of {len(want)} tickers have no price in "
              f"{start}..{end}: {missing[:8]}{' ...' if len(missing) > 8 else ''}")
    wide.attrs["missing"] = missing
    return wide


def panel(tickers, start, end, delist_return=DELIST_RETURN):
    """Adjusted closes with an explicit delisting return applied at the end.

    Where a ticker stops trading inside the window and the tickers table marks it
    delisted, one final observation is appended at `delist_return`. Forward
    filling the last price instead would treat a company that went to zero as
    though it had simply gone quiet.
    """
    wide = closes(tickers, start, end)
    if not TK.exists():
        print("  note: no tickers table, so no delisting returns applied.")
        return wide
    t = pd.read_parquet(TK)
    if "isdelisted" not in t or "lastpricedate" not in t:
        return wide
    dead = t[t.isdelisted.astype(str).str.upper() == "Y"]
    dead = dead.set_index("ticker")["lastpricedate"]
    applied = 0
    for tk in wide.columns:
        if tk not in dead.index:
            continue
        lastdate = pd.to_datetime(dead[tk], errors="coerce")
        if pd.isna(lastdate) or not (pd.Timestamp(start) <= lastdate <= pd.Timestamp(end)):
            continue
        s = wide[tk].dropna()
        if s.empty:
            continue
        after = wide.index[wide.index > s.index[-1]]
        if len(after):
            wide.loc[after[0], tk] = s.iloc[-1] * (1 + delist_return)
            applied += 1
    if applied:
        print(f"  applied a {delist_return:+.0%} delisting return to {applied} ticker(s)")
    return wide


def check():
    """What is actually in the store, and what the study still cannot price."""
    if not PX.exists():
        sys.exit("no price store yet")
    df = pd.read_parquet(PX, columns=["ticker", "date"])
    print(f"  rows      {len(df):,}")
    print(f"  tickers   {df.ticker.nunique():,}")
    print(f"  span      {df.date.min().date()} to {df.date.max().date()}")
    if TK.exists():
        t = pd.read_parquet(TK)
        print(f"  tickers table {len(t):,} rows, cik present: {'cik' in t.columns}")
        if "isdelisted" in t:
            d = (t.isdelisted.astype(str).str.upper() == "Y").sum()
            print(f"  delisted names carried: {d:,}")
    req = HERE.parent / "research" / "price_needs.csv"
    if req.exists():
        need = pd.read_csv(req)
        have = set(df.ticker.unique())
        by = need.assign(ok=need.ticker.isin(have)).groupby("group").ok.agg(["sum", "count"])
        print("\n  coverage against research/price_needs.csv:")
        for grp, r in by.iterrows():
            print(f"    {grp:20} {int(r['sum']):>5,} of {int(r['count']):>5,}"
                  f"  ({r['sum']/r['count']:.0%})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "ingest":
        ingest(sys.argv[2], is_tickers="--tickers" in sys.argv)
    elif cmd == "check":
        check()
    else:
        sys.exit(__doc__)
