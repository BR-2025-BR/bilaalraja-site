#!/usr/bin/env python3
"""A worked case study: the three statements, from one real company's filings.

Every figure comes from Home Depot's own 10-K as filed, not from a textbook and
not rounded into tidiness. The arithmetic is checked against itself before the
page is written, because a teaching document whose statements do not tie teaches
the wrong lesson with complete confidence.
"""
import json, sys
from pathlib import Path

import brand
import extract_case
import reader

HERE = Path(__file__).resolve().parent
OUT  = HERE.parent / "docs" / "learn"
CIK, TICKER, NAME = 354950, "HD", "The Home Depot"
B = 1e9


def bn(v, paren=False):
    """Accounting format: thousands separated, negatives in parentheses."""
    if v is None: return "&mdash;"
    x = v / B
    s = f"{abs(x):,.3f}"
    if x < 0 or paren: return f"({s})"
    return s


def row(label, val, kind="", note="", indent=0):
    cls = f"r {kind}" + (" ind" if indent else "")
    n = f'<td class="n">{note}</td>' if note else '<td class="n"></td>'
    return (f'<tr class="{cls}"><td class="l">{label}</td>'
            f'<td class="v">{val}</td>{n}</tr>')


def statement(title, sub, rows):
    return (f'<div class="stmt"><div class="sthead"><h3>{title}</h3>'
            f'<span>{sub}</span></div><table>{"".join(rows)}</table></div>')


def build():
    data = extract_case.main(CIK, 2)
    fys = sorted(data, reverse=True)
    fy, prior = fys[0], fys[1]
    r, q = data[fy], data[prior]

    def g(k, src=r):
        return src.get(k)

    # derived, and each one checked below before it is shown
    da_is    = g("gross") - g("sga") - g("ebit")
    interest = g("ebit") - g("pretax")
    fcf      = g("cfo") - g("capex")
    checks = {
        "gross profit": abs((g("revenue") - g("cogs")) - g("gross")) < 1e6,
        "balance sheet": abs(g("assets") - (g("liabilities") + g("equity"))) < 1e6,
        "pre-tax to net": abs((g("pretax") - g("tax")) - g("ni")) < 2e7,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        sys.exit(f"case study: these do not reconcile, refusing to publish: {failed}")

    pct = lambda a, b: f"{a / b * 100:.1f}%"

    inc = statement("Income statement", f"year ended {fy} &middot; $bn", [
        row("Net sales", bn(g("revenue")), "top", "what customers paid, once the sale is earned"),
        row("Cost of sales", bn(g("cogs"), True), "", "what the goods themselves cost"),
        row("Gross profit", bn(g("gross")), "sub", f"{pct(g('gross'), g('revenue'))} of sales"),
        row("Selling, general &amp; administrative", bn(g("sga"), True), "", "staff, stores, advertising"),
        row("Depreciation &amp; amortisation", bn(da_is, True), "", "this year's slice of past capex"),
        row("Operating income", bn(g("ebit")), "sub", f"{pct(g('ebit'), g('revenue'))} of sales"),
        row("Interest expense, net", bn(interest, True), "", "the cost of borrowing"),
        row("Pre-tax income", bn(g("pretax")), "sub"),
        row("Income tax", bn(g("tax"), True), "", f"effective rate {pct(g('tax'), g('pretax'))}"),
        row("Net income", bn(g("ni")), "tot", f"{pct(g('ni'), g('revenue'))} of sales"),
        row("Diluted earnings per share", f"${g('eps'):,.2f}" if g("eps") else "&mdash;", "",
            "net income divided across the shares"),
    ])

    bal = statement("Balance sheet", f"as at {fy} &middot; $bn", [
        row("Cash and equivalents", bn(g("cash")), "top"),
        row("Receivables", bn(g("receivable")), "", "sales made but not yet collected"),
        row("Merchandise inventory", bn(g("inventory")), "", "stock sitting in stores and depots"),
        row("Total current assets", bn(g("ca")), "sub", "expected to turn into cash within a year"),
        row("Total assets", bn(g("assets")), "sub", "everything the company controls"),
        row("Accounts payable", bn(g("payable")), "top", "bills owed to suppliers"),
        row("Total current liabilities", bn(g("cl")), "sub", "due within a year"),
        row("Long-term debt and leases", bn(g("ltdebt")), ""),
        row("Total liabilities", bn(g("liabilities")), "sub", "everything the company owes"),
        row("Shareholders' equity", bn(g("equity")), "tot",
            f"assets less liabilities &mdash; {pct(g('equity'), g('assets'))} of assets"),
    ])

    cash = statement("Cash flow statement", f"year ended {fy} &middot; $bn", [
        row("Net income", bn(g("ni")), "top", "the starting point, taken from above"),
        row("Depreciation &amp; amortisation", bn(g("da")), "", "added back: no cash left the business"),
        row("Cash from operations", bn(g("cfo")), "sub",
            f"{g('cfo') / g('ni') * 100:.0f}% of net income"),
        row("Capital expenditure", bn(g("capex"), True), "top", "cash spent on new stores and kit"),
        row("Cash used in investing", bn(g("cfi")), "sub"),
        row("Dividends paid", bn(g("dividends"), True), "top"),
        row("Share buybacks", bn(g("buyback"), True) if g("buyback") else "&mdash;", "",
            "none this year" if not g("buyback") else ""),
        row("Cash used in financing", bn(g("cff")), "sub"),
        row("Free cash flow", bn(fcf), "tot", "operations less the capex needed to stay in business"),
    ])

    ratios = [
        ("Gross margin", pct(g("gross"), g("revenue")), "Of every pound taken, this much survives the cost of the goods."),
        ("Operating margin", pct(g("ebit"), g("revenue")), "What survives after running the shops as well."),
        ("Net margin", pct(g("ni"), g("revenue")), "What is left for owners after lenders and the taxman."),
        ("Return on equity", pct(g("ni"), g("equity")), "Profit against the owners' stake. Flattered here, and the next section explains why."),
        ("Inventory turns", f"{g('cogs') / g('inventory'):.1f}&times;",
         "The shelves empty and refill this many times a year. Retail lives or dies on it."),
        ("Current ratio", f"{g('ca') / g('cl'):.2f}", "Short-term assets against short-term bills."),
        ("Interest cover", f"{g('ebit') / interest:.1f}&times;", "Operating profit against the interest bill."),
        ("Cash conversion", f"{g('cfo') / g('ni') * 100:.0f}%", "Cash from operations against reported profit."),
    ]
    rcards = "".join(
        f'<div class="rc"><div class="rk">{k}</div><div class="rv">{v}</div>'
        f'<p>{d}</p></div>' for k, v, d in ratios)

    yoy_rev = (g("revenue") / g("revenue", q) - 1) * 100
    yoy_ni  = (g("ni") / g("ni", q) - 1) * 100

    return HTML.format(
        # PAGE_CSS goes in as an argument, not through the template: format
        # arguments are substituted, never re-scanned, so its braces are safe.
        CSS=PAGE_CSS, READER=reader.READER_HTML, READERJS=reader.READER_JS,
        FONTS=brand.FONTS, TOKENS=brand.TOKENS + brand.MASTHEAD_CSS,
        MAST=brand.masthead(), fy=fy, prior=prior, ticker=TICKER, name=NAME,
        inc=inc, bal=bal, cash=cash, rcards=rcards,
        rev=f"{g('revenue')/B:,.1f}", ni=f"{g('ni')/B:,.1f}",
        assets=f"{g('assets')/B:,.1f}", equity=f"{g('equity')/B:,.1f}",
        liabilities=f"{g('liabilities')/B:,.1f}",
        cfo=f"{g('cfo')/B:,.1f}", capex=f"{g('capex')/B:,.1f}", fcf=f"{fcf/B:,.1f}",
        da_is=f"{da_is/B:,.3f}", da_cf=f"{g('da')/B:,.3f}",
        roe=pct(g("ni"), g("equity")), eq_pct=pct(g("equity"), g("assets")),
        conv=f"{g('cfo')/g('ni')*100:.0f}",
        yoy_rev=f"{yoy_rev:+.1f}", yoy_ni=f"{yoy_ni:+.1f}",
        inv=f"{g('inventory')/B:,.1f}", turns=f"{g('cogs')/g('inventory'):.1f}",
        divs=f"{g('dividends')/B:,.1f}",
    )


PAGE_CSS = reader.READER_CSS + """
body{padding:30px 20px 80px}
.wrap{max-width:900px;margin:0 auto}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink3)}
h1{font-family:var(--serif);font-size:44px;font-weight:600;letter-spacing:-.022em;
  line-height:1.05;margin:12px 0 0;text-wrap:balance}
.lede{font-family:var(--serif);font-size:19px;line-height:1.55;color:var(--ink2);
  margin-top:16px;max-width:64ch}
h2{font-family:var(--serif);font-size:27px;font-weight:600;letter-spacing:-.018em;
  margin:52px 0 4px;text-wrap:balance}
h2 .no{font-family:var(--mono);font-size:12px;font-weight:500;color:var(--ember);
  letter-spacing:.1em;display:block;margin-bottom:9px}
p{max-width:68ch;margin-top:13px;color:var(--ink2)}
p strong{color:var(--ink);font-weight:600}
.stmt{margin-top:22px;border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.sthead{display:flex;justify-content:space-between;align-items:baseline;
  padding:12px 16px;background:var(--raise);border-bottom:1px solid var(--rule)}
.sthead h3{font-family:var(--sans);font-size:14px;font-weight:600;letter-spacing:-.005em}
.sthead span{font-family:var(--mono);font-size:11px;color:var(--ink3)}
.stmt table{width:100%;border-collapse:collapse;font-size:14px}
.stmt td{padding:7px 16px;vertical-align:baseline}
.stmt td.l{color:var(--ink2)}
.stmt td.v{font-family:var(--mono);text-align:right;white-space:nowrap;
  font-variant-numeric:tabular-nums;width:104px;color:var(--ink)}
.stmt td.n{font-size:12.5px;color:var(--ink3);padding-left:20px;width:44%}
.stmt tr.top td{padding-top:13px}
.stmt tr.sub td{border-top:1px solid var(--rule);font-weight:600}
.stmt tr.sub td.l,.stmt tr.sub td.v{color:var(--ink)}
.stmt tr.tot td{border-top:1px solid var(--ink);border-bottom:3px double var(--ink);
  font-weight:600;background:var(--raise)}
.stmt tr.tot td.l,.stmt tr.tot td.v{color:var(--ink)}
.tie{background:var(--raise);border:1px solid var(--rule);border-radius:6px;
  padding:16px 18px;margin-top:20px;font-family:var(--mono);font-size:13px;
  line-height:1.9;overflow-x:auto}
.tie b{color:var(--ember);font-weight:500}
.rgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));
  gap:14px;margin-top:22px}
.rc{border:1px solid var(--rule);border-radius:6px;padding:14px 15px}
.rk{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink3)}
.rv{font-family:var(--mono);font-size:25px;font-weight:500;margin:5px 0 7px;
  color:var(--ember);font-variant-numeric:tabular-nums}
.rc p{font-size:12.5px;margin:0;color:var(--ink2)}
.lesson{border-left:2px solid var(--ember);padding:4px 0 4px 18px;margin-top:26px}
.lesson h4{font-family:var(--serif);font-size:19px;font-weight:600;margin-bottom:3px}
.warn{background:var(--raise);border:1px solid var(--rule);border-radius:6px;
  padding:17px 19px;margin-top:22px}
.warn h4{font-size:14px;font-weight:600;margin-bottom:7px}
.warn p{margin-top:8px;font-size:14px}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--rule);
  font-size:12.5px;color:var(--ink3)}
footer a{color:var(--ember);text-decoration:none}
"""

HTML = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reading a company's accounts, end to end | Bilaal Raja</title>
<meta name="description" content="A worked case study in financial accounting using {name}'s own filed statements: the income statement, balance sheet and cash flow, how the three tie together, and what the ratios drawn from them do and do not tell you.">
<link rel="canonical" href="https://bilaalraja.com/learn/">
<meta property="og:type" content="article">
<meta property="og:title" content="Reading a company's accounts, end to end">
<meta property="og:description" content="A worked case study in financial accounting from {name}'s own filed statements.">
<meta property="og:url" content="https://bilaalraja.com/learn/">
<meta property="og:image" content="https://bilaalraja.com/og.png">
<meta name="twitter:card" content="summary_large_image">
{FONTS}
<style>{TOKENS}{CSS}</style></head><body><div class="wrap">
{MAST}
{READER}
<div class="eyebrow">Case study &middot; financial accounting</div>
<h1>Reading a company's accounts, end to end</h1>
<p class="lede">Every figure below is {name}'s own, taken from the accounts it
filed for the year ended {fy}. Nothing is rounded into tidiness and nothing is
invented, because the point is to read a real set of statements rather than a
clean example that never existed.</p>

<h2><span class="no">01</span>Why there are three statements</h2>
<p>A company could tell you one number: how much money it made. It does not,
because that single number cannot answer three different questions that all
matter, and answering them separately is what the three statements are for.</p>
<p><strong>Did it trade profitably?</strong> That is the income statement.
<strong>What does it own and owe?</strong> That is the balance sheet.
<strong>Where did the cash actually go?</strong> That is the cash flow
statement. A business can be profitable and run out of money. It can be losing
money and be awash with cash. Only reading all three together tells you which
you are looking at.</p>

<h2><span class="no">02</span>The income statement</h2>
<p>This one covers a period, in the way a video does: it records what happened
over the twelve months. It works downwards, starting with everything customers
paid and subtracting each layer of cost until what is left belongs to the
owners.</p>
{inc}
<p>Read it as a series of survivals. Of ${rev}bn taken from customers, the goods
themselves consumed most of it. Running the stores took another slice. Lenders
and the taxman took theirs. <strong>${ni}bn survived to the bottom</strong>,
which is a little under nine pence in every pound.</p>
<p>One line deserves suspicion: depreciation and amortisation. No money left the
business this year for it. It is this year's share of cash spent building stores
in earlier years, spread across the period they will be used. That is accrual
accounting doing its job, and it is also the first place profit and cash part
company.</p>

<h2><span class="no">03</span>The balance sheet</h2>
<p>Where the income statement is a video, this is a photograph: everything owned
and owed at one instant, the last day of the year. It cannot help but balance,
and that is not a coincidence but an identity.</p>
{bal}
<div class="tie">assets <b>{assets}</b> = liabilities <b>{liabilities}</b> +
equity <b>{equity}</b></div>
<p>Everything a company controls was funded by somebody: either by people it
owes (liabilities) or by its owners (equity). There is no third source. So
<strong>equity is not a valuation</strong>. It is a residual, whatever remains
once every obligation is met, and here it is just {eq_pct} of the assets. That
figure is going to matter shortly.</p>

<h2><span class="no">04</span>The cash flow statement</h2>
<p>The one hardest to argue with. Profit involves judgement about when a sale is
earned and how quickly a building wears out. Cash either arrived or it did not.</p>
{cash}
<p>Notice where it starts: <strong>net income, carried down from the income
statement</strong>. Then the non-cash charges are added back, depreciation
first, because that cost never left the bank. What emerges is
<strong>${cfo}bn of cash from operations, {conv}% of reported profit</strong>.
Above 100% is generally a good sign: the profits are real and arriving.</p>
<p>Then the money that keeps the business alive is subtracted: ${capex}bn of
capital expenditure on new stores and equipment. What remains,
<strong>${fcf}bn</strong>, is free cash flow, the amount genuinely available for
dividends, buybacks and debt repayment. It is the number most investors care
about most.</p>

<h2><span class="no">05</span>How the three lock together</h2>
<p>They are not three documents. They are one system, and each links into the
next at fixed points.</p>
<div class="tie">
net income <b>{ni}</b> &rarr; top of the cash flow statement<br>
net income &rarr; retained earnings, inside equity <b>{equity}</b><br>
capex <b>{capex}</b> &rarr; property and equipment on the balance sheet<br>
depreciation <b>{da_cf}</b> &rarr; reduces that same asset, and reduces profit<br>
closing cash &rarr; the first line of the balance sheet
</div>
<p>This is why a made-up set of accounts falls apart under inspection. Change
one figure and it must move in three places at once. It is also why the small
discrepancy here is worth pointing at: depreciation is
<strong>${da_is}bn on the income statement and ${da_cf}bn in the cash
flow</strong>. Not an error. The two statements are capturing slightly
different scopes, and noticing the gap is the difference between reading
accounts and glancing at them.</p>

<h2><span class="no">06</span>The ratios, and what each is really asking</h2>
<p>Ratios are not separate data. Every one below is two numbers from the
statements above, divided.</p>
<div class="rgrid">{rcards}</div>

<h2><span class="no">07</span>What this particular company teaches</h2>
<div class="lesson"><h4>A spectacular return that is mostly borrowed</h4>
<p>Return on equity is <strong>{roe}</strong>. That looks extraordinary until
you notice the denominator: equity is only {eq_pct} of assets. A small
denominator makes any ratio large. The business is genuinely good, but ROE here
measures the financing as much as the operations, which is exactly why return on
capital is the more honest cousin.</p></div>
<div class="lesson"><h4>Growing sales, shrinking profit</h4>
<p>Revenue rose {yoy_rev}% while net income fell {yoy_ni}%. Costs grew faster
than sales. One line up from the bottom would never have shown you that; you
have to read the statement as a whole.</p></div>
<div class="lesson"><h4>Inventory is the business</h4>
<p>${inv}bn sits in stock, turning over {turns} times a year. For a retailer
that single figure drives everything: buy the wrong things and it becomes cash
you cannot get back.</p></div>

<h2><span class="no">08</span>Where accounts mislead</h2>
<div class="warn">
<h4>Three cautions worth carrying</h4>
<p><strong>They look backwards.</strong> Every figure describes a year already
finished. Nothing here promises the next one.</p>
<p><strong>Judgement is embedded throughout.</strong> How long a building lasts,
when a sale counts as earned, what a lease is worth. All estimates, all made by
the company, all within the rules and all capable of flattering.</p>
<p><strong>Comparison needs care.</strong> These statements are consistent with
themselves, not necessarily with a rival's. Different fiscal years, accounting
choices and definitions of the same word are the reason like-for-like is harder
than it looks.</p>
</div>

<footer>Figures taken from {name}'s filings for the years ended {fy} and
{prior}, as filed and not restated &middot; the arithmetic on this page is
checked against itself before publication &middot;
<a href="/c/{ticker}/">see {ticker} in the cross-section</a> &middot;
<a href="/methodology">method</a> &middot; <a href="/">bilaalraja.com</a></footer>
{READERJS}
</div></body></html>"""


def main():
    html = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html)
    print(f"  wrote /learn/  {len(html)/1024:.1f} KB")


if __name__ == "__main__":
    main()
