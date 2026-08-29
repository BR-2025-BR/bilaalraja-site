#!/usr/bin/env python3
"""One page per company: /c/<TICKER>/.

The dashboard is a single URL, which means the whole site competes for one set
of search terms and every visitor lands on the same view. A page per company
gives each name its own address, its own title, and somewhere for the detail
that will not fit on a scatter plot: the filing it was built from, what
management said, and who has been buying.

Pages are deliberately small and self-contained. There is no shared stylesheet
because 2,500 pages each fetching one is 2,500 extra requests, and the CSS is
smaller than the request that would fetch it.
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT  = HERE.parent / "docs" / "c"
DOMAIN = "bilaalraja.com"

def esc(s):
    return (str(s).replace("&","&amp;").replace("<","&lt;")
            .replace(">","&gt;").replace('"',"&quot;"))

def num(v, dp=2, suf="", pre=""):
    if v is None: return "&mdash;"
    try: f = float(v)
    except (TypeError, ValueError): return "&mdash;"
    return f"{pre}{f:,.{dp}f}{suf}"

def money_bn(v):
    if v is None: return "&mdash;"
    f = float(v)
    return f"${f:,.1f}bn" if abs(f) >= 1 else f"${f*1000:,.0f}m"

CSS = """*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#fff;--panel:#f4f4f4;--ink:#000;--ink2:#3d3d3d;--ink3:#7a7a7a;
--rule:#d8d8d8;--acc:#ff9900;--good:#0a7d3f;--bad:#b3261e;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#000;--panel:#1b1b1b;
--ink:#fff;--ink2:#c4c4c4;--ink3:#8a8a8a;--rule:#2f2f2f;--acc:#ff9900;
--good:#4ade80;--bad:#ff6b6b}}
:root[data-theme=dark]{--bg:#000;--panel:#1b1b1b;--ink:#fff;--ink2:#c4c4c4;
--ink3:#8a8a8a;--rule:#2f2f2f;--acc:#ff9900;--good:#4ade80;--bad:#ff6b6b}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);
line-height:1.5;padding:28px 20px 60px}
.wrap{max-width:860px;margin:0 auto}
a{color:inherit}
.back{font:600 11px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--ink3);text-decoration:none;display:inline-block;margin-bottom:22px}
.back:hover{color:var(--acc)}
h1{font-size:31px;letter-spacing:-.02em;line-height:1.1}
h1 .tk{font-family:var(--mono);color:var(--acc)}
.sub{color:var(--ink2);font-size:14px;margin-top:5px}
.badge{display:inline-block;font:600 10.5px/1 var(--mono);letter-spacing:.1em;
text-transform:uppercase;background:var(--panel);color:var(--ink2);
padding:5px 9px;border-radius:4px;margin-top:9px}
h2{font-size:11px;font-family:var(--mono);letter-spacing:.14em;text-transform:uppercase;
color:var(--ink3);margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;
background:var(--rule);border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.cell{background:var(--bg);padding:11px 13px}
.k{font-size:10.5px;font-family:var(--mono);letter-spacing:.07em;text-transform:uppercase;
color:var(--ink3)}
.v{font-size:19px;font-family:var(--mono);margin-top:3px;font-variant-numeric:tabular-nums}
.v.pos{color:var(--good)}.v.neg{color:var(--bad)}
.note{font-size:13px;color:var(--ink2);margin-top:9px}
blockquote{background:var(--panel);border-left:3px solid var(--acc);padding:13px 15px;
border-radius:0 5px 5px 0;font-size:14px;color:var(--ink2);margin-top:4px}
blockquote cite{display:block;margin-top:9px;font-size:11.5px;font-family:var(--mono);
color:var(--ink3);font-style:normal}
footer{margin-top:34px;padding-top:14px;border-top:1px solid var(--rule);
font-size:12px;color:var(--ink3)}
footer a{color:var(--acc)}"""

def cell(k, v, cls=""):
    return f'<div class="cell"><div class="k">{k}</div><div class="v {cls}">{v}</div></div>'

def page(r, mdna, meta, y10):
    tk, nm = r["ticker"], r.get("name") or r["ticker"]
    sector = r.get("sector") or "Unclassified"
    title = f"{tk} &middot; {esc(nm)} fundamentals"
    desc = (f"{esc(nm)} ({tk}): trailing-twelve-month fundamentals rebuilt from SEC "
            f"filings as filed. Market cap {money_bn(r.get('mcap'))}, "
            f"revenue {money_bn(r.get('rev'))}. Period ended {r.get('end')}.")

    eyp = r.get("eyp")
    ins = r.get("insider_net")
    core = "".join([
        cell("Market cap", money_bn(r.get("mcap"))),
        cell("Revenue TTM", money_bn(r.get("rev"))),
        cell("Net income TTM", money_bn(r.get("ni"))),
        cell("Free cash flow", money_bn(r.get("fcf"))),
        cell("Composite score", num(r.get("score"), 1)),
        cell("Sector rank", f'#{r["rank"]}' if r.get("rank") else "&mdash;"),
    ])
    val = "".join([
        cell("P / E", num(r.get("pe"), 1)),
        cell("EV / EBITDA", num(r.get("ev_ebitda"), 1)),
        cell("EV / sales", num(r.get("ev_sales"), 1)),
        cell("FCF yield", num(r.get("fcf_yield"), 2, "%")),
        cell("Earnings yield vs 10-yr", num(eyp, 2, "pp"),
             "pos" if (eyp or 0) > 0 else "neg" if eyp is not None else ""),
    ])
    qual = "".join([
        cell("Net margin", num(r.get("margin"), 1, "%")),
        cell("EBITDA margin", num(r.get("ebitda_margin"), 1, "%")),
        cell("ROE", num(r.get("roe"), 1, "%")),
        cell("ROIC", num(r.get("roic"), 1, "%")),
        cell("Revenue growth", num(r.get("growth"), 1, "%")),
    ])

    insider = ""
    if ins is not None:
        insider = f"""<h2>Insider activity, last 90 days</h2><div class="grid">
{cell("Net open-market", num(ins, 2, "m", "$"), "pos" if ins > 0 else "neg" if ins < 0 else "")}
{cell("Buyers", r.get("insider_buyers") if r.get("insider_buyers") is not None else "&mdash;")}
{cell("Sellers", r.get("insider_sellers") if r.get("insider_sellers") is not None else "&mdash;")}
</div><p class="note">Open-market purchases and sales only. Grants, option
exercises, gifts and shares withheld for tax are excluded: they are how people
are paid, not what they think.</p>"""

    commentary = ""
    if mdna and mdna.get("text"):
        t = mdna["text"].strip()
        truncated = len(t) > 700
        if truncated:
            cut = t[:700]; dot = cut.rfind(". ")
            t = (cut[:dot+1] if dot > 420 else cut).rstrip()
        commentary = f"""<h2>What management said</h2>
<blockquote>{esc(t)}{" &hellip;" if truncated else ""}<cite>{esc(nm)}, {mdna.get('form','filing')},
period ended {mdna.get('period','&mdash;')}, filed {mdna.get('filed','&mdash;')}</cite></blockquote>
<p class="note"><a href="/commentary">Read the full passage &rarr;</a></p>"""

    ld = json.dumps({"@context":"https://schema.org","@type":"Corporation",
        "name":nm,"tickerSymbol":tk,"url":f"https://{DOMAIN}/c/{tk}/"},
        separators=(",",":"))

    return f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://{DOMAIN}/c/{tk}/">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://{DOMAIN}/c/{tk}/">
<meta property="og:image" content="https://{DOMAIN}/og.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{ld}</script>
<style>{CSS}</style></head><body><div class="wrap">
<a class="back" href="/russell3000?q={tk}">&larr; Russell 3000 cross-section</a>
<h1><span class="tk">{tk}</span> {esc(nm)}</h1>
<div class="sub">Trailing twelve months to {r.get('end','&mdash;')} &middot;
as filed {r.get('filed','&mdash;')}, not restated</div>
<div class="badge">{esc(sector)}</div>

<h2>Scale</h2><div class="grid">{core}</div>
<h2>Valuation</h2><div class="grid">{val}</div>
<p class="note">Earnings yield vs 10-yr compares what the business earns per
pound invested against the {y10}% a 10-year US Treasury note pays for no equity
risk. Negative means you are paying up front for growth not yet delivered.</p>
<h2>Quality and growth</h2><div class="grid">{qual}</div>
{insider}{commentary}
<footer>Built from SEC EDGAR filings, computed point in time &middot;
prices {meta.get('price_date','')} &middot;
<a href="/methodology">method and known defects</a> &middot;
<a href="/">bilaalraja.com</a></footer>
</div></body></html>"""


def main():
    rows = json.loads((HERE/"r3k_scored.json").read_text())
    rates = json.loads((HERE/"rates.json").read_text()) if (HERE/"rates.json").exists() else {}
    y10 = rates.get("y10", "")

    # eyp and the insider fields are derived by the dashboard builder in memory
    # and never written back to r3k_scored.json, so they have to be recomputed
    # here. Reading them off the scored file silently yields blanks.
    f4 = HERE/"form4.json"
    form4 = json.loads(f4.read_text()) if f4.exists() else {}
    for r in rows:
        ni, mc = r.get("ni"), r.get("mcap")
        r["eyp"] = (round(ni / mc * 100 - y10, 2)
                    if y10 and ni is not None and mc else None)
        v = form4.get(str(r.get("cik")))
        r["insider_net"] = round(v["net"]/1e6, 2) if v and v.get("net") is not None else None
        r["insider_buyers"]  = v.get("buyers")  if v else None
        r["insider_sellers"] = v.get("sellers") if v else None
    slices = {}
    f = HERE/"mdna_slices.json"
    if f.exists():
        for v in json.loads(f.read_text()).values():
            if v and v.get("ticker"):
                slices[v["ticker"]] = v.get("q") or v.get("a")
    dash = (HERE/"r3k_dashboard.html")
    meta = {}
    if dash.exists():
        m = re.search(r"META\s*=\s*(\{.*?\})\s*,\s*METRICS\s*=", dash.read_text(errors="replace"), re.S)
        if m: meta = json.loads(m.group(1))

    only = sys.argv[1:] or None
    OUT.mkdir(parents=True, exist_ok=True)
    n = total = 0
    written = []
    for r in rows:
        tk = r.get("ticker")
        if not tk or not re.fullmatch(r"[A-Z0-9.\-]{1,10}", tk): continue
        if only and tk not in only: continue
        html = page(r, slices.get(tk), meta, y10)
        d = OUT / tk
        d.mkdir(parents=True, exist_ok=True)
        (d/"index.html").write_text(html)
        n += 1; total += len(html); written.append(tk)
    print(f"  wrote {n} company pages  {total/1e6:.2f} MB  mean {total/max(n,1)/1024:.1f} KB")
    return written


if __name__ == "__main__":
    main()
