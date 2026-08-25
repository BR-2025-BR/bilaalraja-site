"""Final universe build: authoritative shares, Russell eligibility, ranked.

Share counts come from yfinance (ADS-equivalent and split-current). The SEC
cover-page count, split-corrected, is retained as an independent cross-check
and as a fallback where yfinance has no value.

The ratio between the two is itself a signal: an ADR reports ordinary shares to
the SEC but trades as an ADS, so a large ratio identifies a foreign issuer even
when its stateOfIncorporation field is blank -- which is how BeOne (ONC) slipped
past a metadata-only filter and reached rank 13 at a fictitious $555bn.
"""
import json, re, sys
from pathlib import Path
import datetime as _dt
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from sectors import sector_for_ticker

HERE = Path(__file__).parent
US = {'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY',
      'LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
      'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
      'DC','PR','VI','GU','AS','MP','X1'}
SIC_EXCLUDE  = {6726, 6770}
DERIV = re.compile(r"-(P[A-Z]?|WT|RI|R|UN|U)$|W$|R$|U$", re.I)
NAME_EXCLUDE = re.compile(r"\b(L\.?P\.?|LIMITED PARTNERSHIP|PARTNERS L P|ROYALTY TRUST|"
                          r"ACQUISITION CORP|ETF|INDEX FUND)\b|\bTRUST$", re.I)
ADR_RATIO = 1.5      # SEC ordinary shares / yf ADS shares above this => ADR

# Business addresses for foreign-chartered filers, used for the home-country test.
ADDR = {int(f.stem): json.load(open(f)) for f in (HERE/"addresses").glob("*.json")}

prices  = json.load(open(HERE/"prices_snapshot.json"))
splits  = json.load(open(HERE/"splits_snapshot.json"))
yfsh    = json.load(open(HERE/"shares_yf.json"))
stage0  = pd.read_json(HERE/"universe_stage0.json")
extra   = json.load(open(HERE/"needs_price.json"))

sec_sh = {int(r.cik): (r.shares_end, float(r.shares)) for r in stage0.itertuples()}
for cik, tk, s, title in extra: sec_sh.setdefault(int(cik), (None, float(s)))

def split_corrected(tk, cik):
    """SEC cover-page count carried forward through any later splits."""
    if cik not in sec_sh: return None
    end, raw = sec_sh[cik]
    if not end: return raw
    f = 1.0
    for d, r in (splits.get(tk) or []):
        if d > str(end)[:10]: f *= r
    return raw * f

# A split inside this window means any third-party share count may still be
# pre-split. Wide enough to cover the lag, narrow enough not to override
# yfinance for old splits it has long since absorbed.
RECENT_SPLIT_FROM = (_dt.date.today() - _dt.timedelta(days=45)).isoformat()

rows, drop, flags = [], {}, []
def rej(w): drop[w] = drop.get(w, 0) + 1

for f in (HERE/"submissions").glob("*.json"):
    d = json.load(open(f))
    if not d: rej("empty submission"); continue
    cik = int(d["cik"])
    if d.get("entityType") != "operating": rej("entityType not operating"); continue
    exch = d.get("exchanges") or []
    if not any(e in ("Nasdaq","NYSE","NYSE American","NYSEAmerican","CBOE") for e in exch):
        rej("not on a major exchange"); continue
    forms = set(d.get("forms") or [])
    if "20-F" in forms or "40-F" in forms: rej("foreign filer (20-F/40-F)"); continue
    # NOTE: a positive "must file 10-K/10-Q" test cannot be applied here. The stored
    # form list is the most recent 120 filings only, and heavy filers (JPMorgan,
    # Bank of America, Goldman) issue hundreds of 424B2/FWP notes, pushing their
    # annual and quarterly reports outside that window. Requiring 10-K/10-Q dropped
    # the entire large-cap banking sector. The 20-F/40-F exclusion above is a
    # positive test on a short list and is unaffected; whether a company actually
    # has usable quarterly data is settled at panel-build time, where it belongs.
    soi = (d.get("stateOfIncorporation") or "").strip()
    if soi and soi not in US:
        # Home-country test. FTSE Russell does not exclude on charter alone: a company
        # chartered offshore but headquartered and traded in the US is assigned to the
        # US. SLB (Curacao charter, Houston HQ), Flex, Carnival and LyondellBasell are
        # the canonical cases. The SPAC/partnership name filter and the 20-F/40-F test
        # above still apply, which is what keeps Cayman blank-cheque shells and true
        # foreign issuers out -- both are heavily represented in this group.
        hq = ((ADDR.get(cik) or {}).get("business") or {}).get("stateOrCountry") or ""
        if hq not in US:                    rej("foreign charter, non-US HQ"); continue
        foreign_charter = True
    else:
        foreign_charter = False
    try: sic = int(d.get("sic") or 0)
    except ValueError: sic = 0
    if sic in SIC_EXCLUDE:                  rej(f"excluded structure (SIC {sic})"); continue
    name = d.get("name") or ""
    if NAME_EXCLUDE.search(name):           rej("partnership / trust / SPAC by name"); continue
    tks = [t.upper() for t in (d.get("tickers") or []) if t]
    if not tks:                             rej("no ticker"); continue
    # Prefer a ticker yfinance reports a SHARE COUNT for: it does so only for
    # common equity, not for baby bonds, notes or preferreds. Without this the
    # alphabetically-first rule picked DTE Energy's bond (DTB) over its stock
    # (DTE) and paired a $15.98 bond price with 208m common shares, printing a
    # $3.3bn market cap for a $29bn company. Prudential (PFH vs PRU) and
    # Hercules (HCXY vs HTGC) failed the same way. Position in the SEC list is
    # not a fix -- it is right for DTE but wrong for Mid-America (MAA vs MAAI).
    equity_lines = [t for t in tks if t in yfsh]
    pool = equity_lines or tks
    plain = [t for t in pool if "-" not in t]
    if plain:
        tk = min(plain, key=lambda t: (len(t), t))
    elif equity_lines:
        cls = [t for t in pool if not DERIV.search(t)]
        tk = min(cls, key=lambda t: (t[-1] != "B", t)) if cls else pool[0]
    else:
        # Berkshire and Brown-Forman have no dashless line at all. Take the share
        # class, never a preferred/warrant/right/unit; yfinance reports whole-company
        # shares in that class's units, so either class yields the same market cap.
        cls = [t for t in tks if not DERIV.search(t)]
        if not cls:                         rej("only derivative tickers"); continue
        cls.sort(key=lambda t: (t[-1] != "B", t))
        tk = cls[0]
    if tk not in prices:                    rej("no price"); continue

    yf_s, sec_s = yfsh.get(tk), split_corrected(tk, cik)
    ratio = (sec_s / yf_s) if (yf_s and sec_s) else None

    # An ADR's SEC count is ordinary shares while its quote is per ADS. Blank
    # stateOfIncorporation cannot catch this; the ratio can.
    if ratio and ratio > ADR_RATIO and not soi:
        rej("ADR signature (blank domicile, shares ratio)"); continue

    # yfinance is normally the better count, but it lags a split by days or
    # weeks, and during that window it reports the pre-split number against a
    # post-split price. The SEC path is split-corrected by construction, so
    # after a recent split it is the one to trust.
    recent_split = any(d >= RECENT_SPLIT_FROM for d, _ in (splits.get(tk) or []))
    if recent_split and sec_s:
        shares, src = sec_s, "sec-split-corrected (recent split)"
    elif recent_split:
        # Split on the record but no SEC count to carry through it, so the only
        # available count is the third-party one, which may or may not have
        # caught up. A reverse split not caught here inflates market cap by the
        # ratio and pushes a shell-scale company up the ranking. Drop it rather
        # than publish a number that cannot be checked.
        rej("recent split, no SEC count to correct"); continue
    else:
        shares, src = (yf_s, "yfinance") if yf_s else (sec_s, "sec-split-corrected")
    if not shares:                          rej("no share count"); continue
    if ratio and (ratio > 1.15 or ratio < 0.87):
        flags.append(dict(ticker=tk, name=name, sec=sec_s, yf=yf_s, ratio=ratio))

    px = prices[tk]["price"]
    rows.append(dict(cik=cik, ticker=tk, name=name, sic=sic,
                     sector=sector_for_ticker(sic, tk), soi=soi or "(blank)",
                     exch=exch[0], shares=shares, shares_src=src,
                     sec_shares=sec_s, yf_shares=yf_s, sec_yf_ratio=ratio,
                     price=px, mcap=px*shares/1e9, foreign_charter=foreign_charter))

df = pd.DataFrame(rows).sort_values("mcap", ascending=False).reset_index(drop=True)
df["rank"] = range(1, len(df)+1)
df.to_json(HERE/"universe_ranked.json", orient="records", indent=1)
pd.DataFrame(flags).to_json(HERE/"share_disagreements.json", orient="records", indent=1)

print("=== rejections ===")
for k,v in sorted(drop.items(), key=lambda x:-x[1]): print(f"  {k:<42}{v:>5}")
print(f"\neligible: {len(df)}   share source: "
      f"{(df.shares_src=='yfinance').sum()} yfinance / {(df.shares_src!='yfinance').sum()} SEC fallback")
print(f"SEC-vs-yfinance disagreements >15%: {len(flags)}")
print("\n=== TOP 20 ===")
print(df.head(20)[["rank","ticker","name","sector","mcap"]].to_string(index=False))
print("\n=== size ladder ===")
for t in [0.25,0.5,1,2,5,10,50]: print(f"  > ${t:>5}bn : {(df.mcap>t).sum():>5}")
if len(df) > 3000:
    print(f"\nfloor at rank 3000: ${df.iloc[2999].mcap*1000:.0f}m")
print("\n=== sector mix of top 3000 ===")
print(df.head(3000).sector.value_counts().to_string())
