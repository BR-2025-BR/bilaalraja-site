"""Generate the Russell 3000 cross-section dashboard.

Design decisions and why:

* 3,000 overlapping points make simultaneous sector colour unreadable, and the
  palette validator confirms it is also indefensible: 12 categorical hues score a
  worst all-pairs OKLab dE of 2.0, and even four hues only pass with a carefully
  chosen set. So sector is a FILTER, not a simultaneous encoding. The main chart
  is a neutral density cloud; one sector highlights at a time against it, which
  is always a two-category comparison and always separable. Comparing sectors is
  done with small multiples, which is the prescribed route when all-pairs fails.
* Axes are percentile-clipped. Raw ranges are useless here -- EV/Sales runs to
  44,765 and margin to -920,285 on companies with near-zero revenue -- so points
  outside the clip are pinned at the edge and counted rather than dropped
  silently.
* Canvas, not SVG: 3,000 nodes per redraw is too many for the DOM.
"""
import json, math, datetime as _dt
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
rows = json.load(open(HERE/"r3k_scored.json"))

# Optional inputs. The page must still build without them rather than fail, but
# say so, because a column silently full of blanks looks like missing data
# rather than a missing file.
def _optional(name):
    f = HERE / name
    if not f.exists():
        print(f"  note: {name} absent, its column will be blank")
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        # These files are checkpointed by long-running fetchers, so a build
        # started mid-write can catch a truncated one. Better a blank column
        # and a warning than a failed build.
        print(f"  WARNING: {name} is not valid JSON (mid-write?), skipping it")
        return None

skipped = json.load(open(HERE/"r3k_skipped_full.json"))
uni = pd.read_json(HERE/"r3k_universe.json")

METRICS = [
  ("mcap","Market cap ($bn)"),("ev","Enterprise value ($bn)"),("rev","Revenue TTM ($bn)"),
  ("ni","Net income TTM ($bn)"),("ebitda","EBITDA TTM ($bn)"),("cfo","Cash from ops TTM ($bn)"),
  ("fcf","Free cash flow TTM ($bn)"),("capex","Capex TTM ($bn)"),("assets","Total assets ($bn)"),
  ("equity","Equity ($bn)"),("netcash","Net cash ($bn)"),("debt","Total debt ($bn)"),
  ("ps","Price / Sales"),("pe","P/E"),("ev_sales","EV / Sales"),("ev_ebit","EV / EBIT"),
  ("ev_ebitda","EV / EBITDA"),("fcf_yield","FCF yield (%)"),("payout_yield","Payout yield (%)"),
  ("margin","Net margin (%)"),("ebitda_margin","EBITDA margin (%)"),("roe","ROE (%)"),
  ("roic","ROIC (%)"),("growth","Revenue growth YoY (%)"),("capex_rev","Capex / revenue (%)"),
  ("capex_da","Capex / D&A"),("sbc_rev","SBC / revenue (%)"),("fcf_conv","FCF conversion (%)"),
  ("score","Composite score"),("p_value","· Value percentile"),("p_quality","· Quality percentile"),
  ("p_cash","· Cash percentile"),("p_balance","· Balance-sheet percentile"),
  ("p_growth","· Growth percentile"),("roce","Return on capital employed (%)"),
  ("eyp","Earnings yield vs 10-yr (pp)"),
  ("insider_net","Insider net buying, 90d ($m)"),
]

def _drop_metric(key):
    """Remove a metric from the selectable list.

    A column that is mostly blank reads as broken data rather than as data not
    gathered yet, so a partially-filled input is worse than an absent one.
    """
    global METRICS, KEYS
    METRICS = [m for m in METRICS if m[0] != key]
    KEYS = [k for k, _ in METRICS]

KEYS = [k for k,_ in METRICS]

_form4 = _optional("form4.json") or {}
_frames = _optional("frames_check.json") or {}
_rates = _optional("rates.json") or {}
_y10 = _rates.get("y10")

# Insider coverage has to be broad before the column is worth showing: the
# fetch walks every filer's Form 4s and takes hours, so a build during it would
# otherwise ship a column that is blank for most of the market.
_f4_cov = sum(1 for _x in rows if str(_x.get("cik")) in _form4) / max(len(rows), 1)
if _f4_cov < 0.8:
    print(f"  note: Form 4 coverage {_f4_cov:.0%}, holding the insider column back")
    _form4 = {}
    _drop_metric("insider_net")
else:
    print(f"  Form 4 coverage {_f4_cov:.0%}")

for _x in rows:
    # Earnings yield against the risk-free rate. Computed from net income and
    # market cap rather than by inverting P/E, so a loss-making company gets a
    # negative yield instead of being dropped.
    _ni, _mc = _x.get("ni"), _x.get("mcap")
    _x["eyp"] = (round(_ni / _mc * 100 - _y10, 2)
                 if _y10 and _ni is not None and _mc else None)
    _f = _form4.get(str(_x.get("cik")))
    _x["insider_net"] = round(_f["net"] / 1e6, 2) if _f and _f.get("net") is not None else None
    _x["insider_buyers"]  = _f.get("buyers")  if _f else None
    _x["insider_sellers"] = _f.get("sellers") if _f else None
SECTORS = ["Technology","Healthcare","Financials","Industrials","Consumer Disc",
           "Consumer Staples","Energy","Utilities","Materials","Real Estate",
           "Communication Svcs","Unclassified"]

def r(v, n=4):
    if v is None: return None
    try:
        f=float(v)
        return None if not math.isfinite(f) else round(f, n)
    except Exception: return None

data=[]
for x in rows:
    d={"t":x["ticker"],"n":x["name"],"s":x["sector"],"e":x["end"],"f":x["filed"],
       "rk":x["rank"],"bank":1 if x.get("rev_src","").startswith("bank") else 0,
       "m":"F" if x.get("model")=="financial" else "O", "nf":x.get("nfac")}
    for k in KEYS: d[k]=r(x.get(k))
    d["ib"]=x.get("insider_buyers"); d["is_"]=x.get("insider_sellers")
    data.append(d)
data.sort(key=lambda d:-(d.get("mcap") or 0))

ends=pd.to_datetime([x["end"] for x in rows])
meta={
 "n":len(data),"universe":len(uni),"skipped":len(skipped),
 "price_date":json.load(open(HERE/"prices_snapshot.json"))["AAPL"]["date"],
 "q2":int((ends>=pd.Timestamp("2026-04-01")).sum()),
 "median_end":str(pd.Series(ends).median().date()),
 "banks":sum(d["bank"] for d in data),
 "total_mcap":round(sum((d.get("mcap") or 0) for d in data)),
 "floor":round(uni.mcap.min()*1000),
 # Data currency and build stamp. Derived from the data itself so the page
 # cannot claim to be fresher than the filings behind it.
 "latest_filing":max(x["filed"] for x in rows if x.get("filed")),
 "latest_end":max(x["end"] for x in rows if x.get("end")),
 "built":_dt.datetime.now().strftime("%Y-%m-%d"),
 "built_human":_dt.datetime.now().strftime("%-d %B %Y"),
 "metrics":len(METRICS),
 "y10":_y10, "rates_date":_rates.get("date"),
 "fchk_n":_frames.get("compared"), "fchk_bad":_frames.get("disagreed"),
 "insiders":sum(1 for v in _form4.values() if v and v.get("bought",0)>0),
 "insider_window":90,
 "sectors":len(SECTORS),
}

HTML = """<meta charset="utf-8">
<title>Russell 3000 Cross-Section</title>
<style>
:root{
  --bg:#ffffff; --panel:#f4f4f4; --ink:#000000; --ink2:#3d3d3d; --ink3:#7a7a7a;
  --rule:#d8d8d8; --rule2:#ececec; --grid:#e6e6e6;
  --s1:#ff9900; --s2:#000000; --s3:#c47400; --s4:#6b6b6b;
  --dot:#9a9a9a; --accentbg:#fff3e0;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#000000; --panel:#1b1b1b; --ink:#ffffff; --ink2:#c4c4c4; --ink3:#8a8a8a;
  --rule:#2f2f2f; --rule2:#212121; --grid:#282828;
  --s1:#ff9900; --s2:#ffffff; --s3:#ffb84d; --s4:#8a8a8a;
  --dot:#6d6d6d; --accentbg:#2a1c05;
}}
:root[data-theme="dark"]{
  --bg:#000000; --panel:#1b1b1b; --ink:#ffffff; --ink2:#c4c4c4; --ink3:#8a8a8a;
  --rule:#2f2f2f; --rule2:#212121; --grid:#282828;
  --s1:#ff9900; --s2:#ffffff; --s3:#ffb84d; --s4:#8a8a8a;
  --dot:#6d6d6d; --accentbg:#2a1c05;
}
*{box-sizing:border-box;margin:0;padding:0}
@supports (corner-shape: squircle){
  button,select,input[type=search],.panel,.updated,.warn,.sm figure,.tscroll,
  a[href*="commentary"],.tip,canvas{corner-shape:squircle}
}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.5;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:20px 18px 64px;display:flex;flex-direction:column;gap:13px}
header{border-bottom:2px solid var(--ink);padding-bottom:12px;display:flex;
  justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap}
h1{font-size:clamp(21px,4vw,30px);letter-spacing:-.02em;line-height:1.08;font-weight:650}
.sub{color:var(--ink2);font-size:14px;margin-top:4px;max-width:62ch}
.stamp{font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:var(--ink3);text-align:right;
  white-space:nowrap}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:14px;padding:16px 18px}
.phead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;
  margin-bottom:10px}
h2{font-size:15px;font-weight:650;letter-spacing:-.01em}
.note{font-size:13px;color:var(--ink2);max-width:74ch}
.count{font-family:var(--mono);font-size:11.5px;color:var(--ink3);white-space:nowrap}
.ctrls{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;margin:4px 0 12px}
.fld{display:flex;flex-direction:column;gap:4px;min-width:190px}
a.tk{color:var(--s1);text-decoration:none;font-weight:600}
a.tk:hover{text-decoration:underline}
.tip .go{color:var(--s1)}
label{font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink3);font-weight:600}
select,input[type=search]{font:inherit;font-size:13.5px;padding:7px 9px;border:1px solid var(--rule);
  border-radius:10px;background:var(--panel);color:var(--ink);width:100%}
select:focus,input:focus{outline:2px solid var(--s1);outline-offset:1px}
.toggles{display:flex;gap:6px}
button{font:inherit;font-size:12.5px;font-weight:600;padding:7px 13px;border:1px solid var(--rule);
  border-radius:10px;background:var(--panel);color:var(--ink2);cursor:pointer}
button[aria-pressed="true"]{background:var(--s1);border-color:var(--s1);color:#fff}
button:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
.chartbox{position:relative;width:100%}
canvas{width:100%;height:auto;display:block;border-radius:10px;cursor:crosshair}
.tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--rule);
  border-radius:12px;padding:9px 12px;font-size:12.5px;box-shadow:0 4px 14px rgba(0,0,0,.13);
  opacity:0;transition:opacity .1s;min-width:172px;z-index:5}
.tip.on{opacity:1}
.tip b{display:block;font-size:13px;margin-bottom:1px}
.tip .nm{color:var(--ink3);font-size:11.5px;display:block;margin-bottom:5px;font-weight:400}
.tip .kv{display:flex;justify-content:space-between;gap:14px;font-family:var(--mono);font-size:11.5px}
.tip .kv span:first-child{color:var(--ink3)}
.legend{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;padding:5px 10px;
  border:1px solid var(--rule);border-radius:999px;cursor:pointer;background:var(--panel);color:var(--ink2)}
.chip[aria-pressed="true"]{background:var(--accentbg);border-color:var(--s1);color:var(--ink)}
.chip i{width:9px;height:9px;border-radius:50%;background:var(--dot);display:inline-block}
.chip[aria-pressed="true"] i{background:var(--s1)}
.chip small{font-family:var(--mono);font-size:10.5px;color:var(--ink3)}
.sm{display:grid;grid-template-columns:repeat(auto-fill,minmax(178px,1fr));gap:12px;margin-top:6px}
.sm figure{border:1px solid var(--rule2);border-radius:12px;padding:8px 8px 4px;background:var(--panel)}
.sm figcaption{font-size:12px;font-weight:600;margin-bottom:5px;display:flex;justify-content:space-between;
  align-items:baseline;gap:6px}
.sm figcaption em{font-style:normal;font-family:var(--mono);font-size:10.5px;color:var(--ink3);font-weight:400}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--rule2);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);font-weight:600;
  position:sticky;top:0;background:var(--panel)}
td.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
.tscroll{max-height:390px;overflow:auto;border:1px solid var(--rule2);border-radius:12px}
details{border-top:1px solid var(--rule);padding-top:12px}
summary{cursor:pointer;font-size:13.5px;font-weight:600;color:var(--ink2)}
details .body{margin-top:10px;font-size:13.5px;color:var(--ink2);display:flex;flex-direction:column;gap:9px}
details .body b{color:var(--ink)}
details .body ul{margin-left:17px;display:flex;flex-direction:column;gap:5px}
.warn{background:var(--accentbg);border-left:3px solid var(--s1);padding:10px 13px;border-radius:0 12px 12px 0;
  font-size:13.5px;color:var(--ink2)}

.byline{display:flex;justify-content:space-between;align-items:baseline;gap:14px;flex-wrap:wrap;
  border-top:1px solid var(--rule);margin-top:11px;padding-top:9px;font-size:13px;color:var(--ink3)}
.byline b{color:var(--ink);font-weight:640}
.byline a{color:var(--s1);text-decoration:none}
.byline a:hover{text-decoration:underline}
.byline .meth{font-size:12px}
.rights{display:block;margin-top:9px;padding-top:9px;border-top:1px solid var(--rule2);
  max-width:96ch;line-height:1.65}
footer{font-size:11.5px;color:var(--ink3);font-family:var(--mono);border-top:1px solid var(--rule);
  padding-top:11px;line-height:1.7}
</style>

<div class="wrap">
<header>
  <div>
    <h1>Russell 3000 &mdash; Cross-Section</h1>
    <p class="sub">One point per company, at its own most recently filed quarter.
      Where the US market sits right now.</p>
  </div>
  <div class="stamp" id="stamp"></div>
  <div class="byline">
    <span>Built by <b>Bilaal Raja</b> &middot;
      <a href="https://linkedin.com/in/bilaalraja" target="_blank" rel="noopener">linkedin.com/in/bilaalraja</a></span>
    <span class="meth" id="meth"></span>
  </div>

</header>

<div class="warn" id="warnbox"></div>

<section class="panel" style="display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap">
  <div><h2 style="margin-bottom:3px">What management actually said</h2>
    <p class="note">Results commentary lifted from 2,954 companies&rsquo; own 10-Q and 10-K filings &mdash;
      searchable across 11.3M characters of what they wrote about their own quarters.</p></div>
  <a href="https://claude.ai/code/artifact/0c2545da-ee53-41ec-8763-583958244c94" target="_blank"
     rel="noopener" style="font-size:13.5px;font-weight:600;padding:9px 16px;border:1px solid var(--s1);
     border-radius:10px;color:var(--s1);text-decoration:none;white-space:nowrap">Open commentary &rarr;</a>
</section>

<section class="panel">
  <div class="phead">
    <div><h2>Cross-section</h2></div>
    <span class="count" id="cnt"></span>
  </div>
  <div class="ctrls">
    <div class="fld"><label for="xs">X axis</label><select id="xs"></select></div>
    <div class="fld"><label for="ys">Y axis</label><select id="ys"></select></div>
    <div class="fld" style="min-width:150px"><label>Scale</label>
      <div class="toggles">
        <button id="lx" aria-pressed="false">Log X</button>
        <button id="ly" aria-pressed="true">Log Y</button>
      </div></div>
    <div class="fld" style="min-width:210px"><label for="q">Find a ticker</label>
      <input type="search" id="q" placeholder="e.g. NVDA, JPM, BRK-B" autocomplete="off"></div>
  </div>
  <div class="chartbox">
    <canvas id="cv" width="1800" height="1040" aria-label="Cross-sectional scatter of Russell 3000 companies"></canvas>
    <div class="tip" id="tip" role="status"></div>
  </div>
  <div class="legend" id="leg"></div>
  <p class="note" style="margin-top:11px">Selecting a sector highlights it against the rest of the market
    rather than colouring all twelve at once &mdash; at this density twelve hues are neither readable nor
    colour-blind separable. Use the panels below to compare sectors.</p>
</section>

<section class="panel">
  <div class="phead">
    <div><h2>Top 25 by composite score</h2>
      <p class="note">Operating companies only. Financials and Real Estate are scored on a separate,
        weaker model and are listed below them &mdash; the two are not comparable.</p></div>
  </div>
  <div class="tscroll" style="max-height:none"><table id="t25"><thead></thead><tbody></tbody></table></div>
  <div class="phead" style="margin-top:18px">
    <div><h3 style="font-size:14px;font-weight:650">Financials &amp; Real Estate &mdash; separate model, read with care</h3>
      <p class="note">Scored on P/E, ROE, growth and payout only: free cash flow and enterprise value
        are meaningless for them. A leveraged mortgage REIT can look cheap on P/E while being the most
        rate-sensitive thing in the index.</p></div>
  </div>
  <div class="tscroll" style="max-height:300px"><table id="tfin"><thead></thead><tbody></tbody></table></div>
</section>

<section class="panel">
  <div class="phead">
    <div><h2>By sector</h2><p class="note">Same axes throughout. Each panel shows one sector against the
      full market in grey, so the panels are directly comparable.</p></div>
  </div>
  <div class="sm" id="sm"></div>
</section>

<section class="panel">
  <div class="phead"><div><h2>Companies</h2><p class="note">Sorted by market cap. Blank means not
    computable from the filings &mdash; never zero.</p></div>
    <span class="count" id="tcnt"></span></div>
  <div class="tscroll"><table id="tbl"><thead></thead><tbody></tbody></table></div>
</section>

<section class="panel">
  <details>
    <summary>How this was built, and what it cannot tell you</summary>
    <div class="body" id="method"></div>
  </details>
</section>

<footer id="foot"></footer>
</div>

<script>
const D=__DATA__, META=__META__, METRICS=__METRICS__, SECTORS=__SECTORS__;
const $=id=>document.getElementById(id);
const HUE=["--s1","--s2","--s3","--s4"];
const cssv=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const st={x:"fcf_yield",y:"ev_sales",lx:false,ly:true,sector:null,hit:null,q:""};

// Shareable views. The chart state lives in the URL so a specific cross-section
// can be sent as a link rather than described in words.
(function readURL(){
  const p=new URLSearchParams(location.search);
  const valid=new Set(METRICS.map(m=>m[0]));
  if(valid.has(p.get("x"))) st.x=p.get("x");
  if(valid.has(p.get("y"))) st.y=p.get("y");
  if(p.has("lx")) st.lx = p.get("lx")==="1";
  if(p.has("ly")) st.ly = p.get("ly")==="1";
  if(p.get("sector") && SECTORS.includes(p.get("sector"))) st.sector=p.get("sector");
  if(p.get("q")) st.q=p.get("q").trim().toUpperCase();
})();

let _urlHold=false;
function writeURL(){
  if(_urlHold) return;
  const p=new URLSearchParams();
  p.set("x",st.x); p.set("y",st.y);
  p.set("lx", st.lx?"1":"0"); p.set("ly", st.ly?"1":"0");
  if(st.sector) p.set("sector", st.sector);
  if(st.q) p.set("q", st.q);
  // replaceState, not pushState: dragging a slider should not fill the
  // back button with fifty near-identical entries.
  history.replaceState(null,"", location.pathname+"?"+p.toString());
}

for(const sel of [$("xs"),$("ys")]){
  METRICS.forEach(([k,l])=>{const o=document.createElement("option");o.value=k;o.textContent=l;sel.appendChild(o);});
}
$("xs").value=st.x; $("ys").value=st.y;
$("xs").onchange=e=>{st.x=e.target.value;writeURL();draw();drawSmall();};
$("ys").onchange=e=>{st.y=e.target.value;writeURL();draw();drawSmall();};
for(const [id,k] of [["lx","lx"],["ly","ly"]]){
  $(id).onclick=()=>{st[k]=!st[k];$(id).setAttribute("aria-pressed",st[k]);
    writeURL();draw();drawSmall();};
}
$("q").oninput=e=>{st.q=e.target.value.trim().toUpperCase();writeURL();draw();};

const lab=k=>(METRICS.find(m=>m[0]===k)||[k,k])[1];

/* Percentile clip. Raw extents are unusable: EV/Sales reaches 44,765 and net
   margin -920,285 on companies with almost no revenue, which would compress
   every real company into one pixel. Points outside are pinned and counted. */
function clip(vals,logMode){
  let v=vals.filter(x=>x!=null&&isFinite(x));
  if(logMode) v=v.filter(x=>x>0);
  if(!v.length) return null;
  // On a log axis the percentiles must be taken in log space. Taken on raw
  // values, a 2nd percentile of ~1e-9 (companies whose enterprise value is
  // near zero because net cash almost cancels market cap) stretched the axis
  // across nine decades and squashed every real company into the top sliver.
  const t=logMode?v.map(Math.log10):v.slice();
  t.sort((a,b)=>a-b);
  const q=p=>t[Math.min(t.length-1,Math.max(0,Math.floor(p*(t.length-1))))];
  let lo=q(0.02), hi=q(0.98);
  if(lo===hi){ lo=t[0]; hi=t[t.length-1]; }
  if(lo===hi){ lo-=1; hi+=1; }
  const pad=(hi-lo)*0.05;
  lo-=pad; hi+=pad;
  return logMode ? [Math.pow(10,lo), Math.pow(10,hi)] : [lo,hi];
}
const proj=(v,d,logMode)=>{
  if(logMode){ const a=Math.log10(Math.max(v,1e-9)),lo=Math.log10(Math.max(d[0],1e-9)),
    hi=Math.log10(Math.max(d[1],1e-9)); return (a-lo)/(hi-lo||1); }
  return (v-d[0])/((d[1]-d[0])||1);
};
function ticks(d,logMode,n){
  const out=[];
  if(logMode){
    const lo=Math.floor(Math.log10(Math.max(d[0],1e-9))), hi=Math.ceil(Math.log10(Math.max(d[1],1e-9)));
    for(let e=lo;e<=hi;e++){ const v=Math.pow(10,e); if(v>=d[0]&&v<=d[1]) out.push(v); }
    if(out.length<3){ out.length=0; for(let e=lo;e<=hi;e+=0.5){const v=Math.pow(10,e);
      if(v>=d[0]&&v<=d[1])out.push(v);} }
  } else {
    const raw=(d[1]-d[0])/n, mag=Math.pow(10,Math.floor(Math.log10(Math.abs(raw)||1)));
    const step=[1,2,2.5,5,10].map(m=>m*mag).find(s=>s>=raw)||mag*10;
    for(let v=Math.ceil(d[0]/step)*step; v<=d[1]; v+=step) out.push(v);
  }
  return out;
}
const fmt=v=>{
  const a=Math.abs(v);
  if(a>=1e4||(a<0.01&&a>0)) return v.toExponential(0).replace("e+","e");
  if(a>=100) return v.toFixed(0);
  if(a>=10) return v.toFixed(1);
  return v.toFixed(2);
};

let PLOT=null;
function draw(){
  const cv=$("cv"), g=cv.getContext("2d"), W=cv.width, H=cv.height;
  const dpr=1, L=104, R=26, T=22, B=74;
  g.clearRect(0,0,W,H);
  const rows=D.filter(d=>d[st.x]!=null&&d[st.y]!=null);
  const dx=clip(rows.map(d=>d[st.x]),st.lx), dy=clip(rows.map(d=>d[st.y]),st.ly);
  $("cnt").textContent=`${rows.length} of ${D.length} plotted · ${D.length-rows.length} missing a value`;
  if(!dx||!dy){ g.fillStyle=cssv("--ink3"); g.font="26px "+cssv("--sans");
    g.fillText("No points for this pair",L+20,H/2); PLOT=null; return; }

  const pw=W-L-R, ph=H-T-B;
  const X=v=>L+proj(Math.min(Math.max(v,dx[0]),dx[1]),dx,st.lx)*pw;
  const Y=v=>T+ph-proj(Math.min(Math.max(v,dy[0]),dy[1]),dy,st.ly)*ph;

  g.strokeStyle=cssv("--grid"); g.lineWidth=1.5; g.fillStyle=cssv("--ink3");
  g.font="21px "+cssv("--mono");
  g.textAlign="right"; g.textBaseline="middle";
  for(const t of ticks(dy,st.ly,6)){ const y=Y(t);
    g.beginPath();g.moveTo(L,y);g.lineTo(W-R,y);g.stroke(); g.fillText(fmt(t),L-12,y); }
  g.textAlign="center"; g.textBaseline="top";
  for(const t of ticks(dx,st.lx,6)){ const x=X(t);
    g.beginPath();g.moveTo(x,T);g.lineTo(x,T+ph);g.stroke(); g.fillText(fmt(t),x,T+ph+11); }

  g.strokeStyle=cssv("--rule"); g.lineWidth=2;
  g.beginPath();g.moveTo(L,T);g.lineTo(L,T+ph);g.lineTo(W-R,T+ph);g.stroke();

  g.fillStyle=cssv("--ink2"); g.font="600 23px "+cssv("--sans");
  g.textAlign="center"; g.textBaseline="alphabetic";
  g.fillText(lab(st.x)+(st.lx?"  (log)":""),L+pw/2,H-20);
  g.save(); g.translate(28,T+ph/2); g.rotate(-Math.PI/2);
  g.fillText(lab(st.y)+(st.ly?"  (log)":""),0,0); g.restore();

  let off=0;
  const pts=rows.map(d=>{
    const xv=d[st.x], yv=d[st.y];
    const o=(xv<dx[0]||xv>dx[1]||yv<dy[0]||yv>dy[1]); if(o)off++;
    return {d,x:X(xv),y:Y(yv),off:o};
  });
  PLOT={pts,dx,dy};

  const sel=st.sector, hue=cssv("--s1"), dot=cssv("--dot");

  // On the first paint only, points materialise left to right. It costs
  // nothing and it makes the volume legible: a static cloud is just there,
  // whereas watching two and a half thousand points arrive conveys scale.
  // ENTER runs 0 -> 1; each point's own progress is offset by its x position.
  const ent=(p)=>{
    if(ENTER>=1) return 1;
    const lead=(p.x-L)/Math.max(pw,1);              // 0 at left, 1 at right
    const t=(ENTER*1.55)-lead*0.55;                 // sweep, then settle
    return t<=0?0:t>=1?1:t*t*(3-2*t);               // smoothstep
  };

  // background layer first so the highlighted sector always sits on top
  for(const p of pts){ if(sel&&p.d.s===sel) continue;
    const e=ent(p); if(e<=0) continue;
    g.globalAlpha=(sel?0.13:0.34)*e; g.fillStyle=dot;
    g.beginPath(); g.arc(p.x,p.y,(sel?4.4:5.2)*(0.35+0.65*e),0,6.284); g.fill(); }
  if(sel){ for(const p of pts){ if(p.d.s!==sel) continue;
      const e=ent(p); if(e<=0) continue;
      g.globalAlpha=0.9*e; g.fillStyle=hue;
      g.beginPath(); g.arc(p.x,p.y,6.4*(0.35+0.65*e),0,6.284); g.fill(); } }
  g.globalAlpha=1;

  if(st.q){
    const hits=pts.filter(p=>p.d.t.startsWith(st.q));
    for(const p of hits){
      g.strokeStyle=cssv("--s4"); g.lineWidth=3.5;
      g.beginPath(); g.arc(p.x,p.y,12,0,6.284); g.stroke();
      g.fillStyle=cssv("--ink"); g.font="600 22px "+cssv("--sans");
      g.textAlign="left"; g.textBaseline="middle";
      g.fillText(p.d.t,p.x+17,p.y);
    }
  }
  const oc=$("cnt");
  if(off) oc.textContent+=` · ${off} outside the 2nd–98th percentile, pinned at the edge`;
  if(sel){
    const inSel=pts.filter(p=>p.d.s===sel).length;
    oc.textContent=`${sel}: ${inSel} plotted · hover limited to this sector · `+
                   `${rows.length} of ${D.length} in view`+
                   (off?` · ${off} pinned at the edge`:"");
  }
}

function drawSmall(){
  const host=$("sm"); host.innerHTML="";
  const rows=D.filter(d=>d[st.x]!=null&&d[st.y]!=null);
  const dx=clip(rows.map(d=>d[st.x]),st.lx), dy=clip(rows.map(d=>d[st.y]),st.ly);
  if(!dx||!dy) return;
  for(const s of SECTORS){
    const mine=rows.filter(d=>d.s===s); if(!mine.length) continue;
    const fig=document.createElement("figure");
    fig.innerHTML=`<figcaption>${s}<em>${mine.length}</em></figcaption>`;
    const c=document.createElement("canvas"); c.width=440; c.height=330;
    c.style.width="100%"; c.style.height="auto"; fig.appendChild(c); host.appendChild(fig);
    const g=c.getContext("2d"), L=8,R=8,T=8,B=8, pw=c.width-L-R, ph=c.height-T-B;
    const X=v=>L+proj(Math.min(Math.max(v,dx[0]),dx[1]),dx,st.lx)*pw;
    const Y=v=>T+ph-proj(Math.min(Math.max(v,dy[0]),dy[1]),dy,st.ly)*ph;
    g.strokeStyle=cssv("--rule2"); g.lineWidth=1;
    g.strokeRect(L,T,pw,ph);
    g.globalAlpha=0.2; g.fillStyle=cssv("--dot");
    for(const d of rows){ g.beginPath(); g.arc(X(d[st.x]),Y(d[st.y]),2.4,0,6.284); g.fill(); }
    g.globalAlpha=0.92; g.fillStyle=cssv("--s1");
    for(const d of mine){ g.beginPath(); g.arc(X(d[st.x]),Y(d[st.y]),3.4,0,6.284); g.fill(); }
    g.globalAlpha=1;
  }
}

$("cv").addEventListener("mousemove",ev=>{
  if(!PLOT) return;
  const cv=$("cv"), r=cv.getBoundingClientRect(), sx=cv.width/r.width, sy=cv.height/r.height;
  const mx=(ev.clientX-r.left)*sx, my=(ev.clientY-r.top)*sy;
  // Hover must obey the sector filter. Searching every point meant a greyed-out
  // company from another sector could claim the tooltip.
  const pool = st.sector ? PLOT.pts.filter(p=>p.d.s===st.sector) : PLOT.pts;
  let best=null,bd=1e9;
  for(const p of pool){ const d2=(p.x-mx)**2+(p.y-my)**2; if(d2<bd){bd=d2;best=p;} }
  // a filtered sector is sparser, so allow a slightly larger grab radius
  const RAD = st.sector ? 2200 : 900;
  const tip=$("tip");
  if(best&&bd<RAD){
    const d=best.d;
    tip.innerHTML=`<b>${d.t}</b><span class="nm">${d.n}</span>`+
      `<div class="kv"><span>Sector</span><span>${d.s}</span></div>`+
      `<div class="kv"><span>${lab(st.x)}</span><span>${d[st.x]==null?"—":fmt(d[st.x])}</span></div>`+
      `<div class="kv"><span>${lab(st.y)}</span><span>${d[st.y]==null?"—":fmt(d[st.y])}</span></div>`+
      `<div class="kv"><span>Quarter end</span><span>${d.e}</span></div>`+
      (best.off?`<div class="kv"><span></span><span>pinned at edge</span></div>`:"")+
      `<div class="kv"><span></span><span class="go">click for ${d.t} &rarr;</span></div>`;
    st.hit=d.t; cv.style.cursor="pointer";
    tip.classList.add("on");
    const px=best.x/sx, py=best.y/sy;
    tip.style.left=Math.min(px+14,r.width-192)+"px";
    tip.style.top=Math.max(py-14,0)+"px";
  } else { tip.classList.remove("on"); st.hit=null; cv.style.cursor="default"; }
});
$("cv").addEventListener("mouseleave",()=>{
  $("tip").classList.remove("on"); st.hit=null; $("cv").style.cursor="default";
});
// The tooltip offers a click, so it has to lead somewhere.
$("cv").addEventListener("click",()=>{ if(st.hit) location.href=`/c/${st.hit}/`; });

const counts={}; for(const d of D) counts[d.s]=(counts[d.s]||0)+1;
const leg=$("leg");
for(const s of SECTORS){
  if(!counts[s]) continue;
  const b=document.createElement("button");
  b.className="chip"; b.setAttribute("aria-pressed","false");
  b.innerHTML=`<i></i>${s}<small>${counts[s]}</small>`;
  b.onclick=()=>{
    st.sector = st.sector===s ? null : s;
    [...leg.children].forEach(c=>c.setAttribute("aria-pressed", c===b && st.sector===s));
    writeURL(); draw();
  };
  leg.appendChild(b);
}

const COLS=[["t","Ticker"],["n","Company"],["s","Sector"],["score","Score"],["mcap","Mkt cap $bn"],
  ["rev","Rev TTM $bn"],["growth","Growth %"],["margin","Margin %"],["ev_sales","EV/Sales"],
  ["fcf_yield","FCF yld %"],["roic","ROIC %"],["e","Qtr end"]];
(function table(){
  const th=$("tbl").querySelector("thead"), tb=$("tbl").querySelector("tbody");
  th.innerHTML="<tr>"+COLS.map(c=>`<th>${c[1]}</th>`).join("")+"</tr>";
  tb.innerHTML=D.slice(0,400).map(d=>"<tr>"+COLS.map(([k])=>{
    const v=d[k]; const num=typeof v==="number";
    // The ticker is the way into a company's own page. Without this the
    // per-company pages exist but nothing on the site points at them.
    if(k==="t") return `<td><a class="tk" href="/c/${v}/">${v}</a></td>`;
    return `<td class="${num?"num":""}">${v==null?"":num?fmt(v):v}</td>`;
  }).join("")+"</tr>").join("");
  $("tcnt").textContent=`showing top 400 of ${D.length} by market cap`;
})();

(function top25(){
  const mk=(el,rows)=>{
    const C=[["t","Ticker"],["n","Company"],["s","Sector"],["mcap","Mkt cap $bn"],
             ["score","Score"],["p_value","Value"],["p_quality","Quality"],["p_cash","Cash"],
             ["p_balance","Bal. sheet"],["p_growth","Growth"],["nf","Factors"]];
    el.querySelector("thead").innerHTML="<tr>"+C.map(c=>`<th>${c[1]}</th>`).join("")+"</tr>";
    el.querySelector("tbody").innerHTML=rows.map((d,i)=>"<tr>"+C.map(([k])=>{
      const v=d[k], num=typeof v==="number";
      if(k==="t") return `<td><a class="tk" href="/c/${v}/"><b>${v}</b></a></td>`;
      const txt = v==null ? "—"
        : !num ? v
        : k==="nf"    ? String(v)
        : k==="score" ? v.toFixed(1)
        : k==="mcap"  ? (v>=100?v.toFixed(0):v.toFixed(2))
        : v.toFixed(1);
      return `<td class="${num?"num":""}">${txt}</td>`;
    }).join("")+"</tr>").join("");
  };
  const scored=D.filter(d=>d.score!=null);
  mk($("t25"),  scored.filter(d=>d.m==="O").sort((a,b)=>b.score-a.score).slice(0,25));
  mk($("tfin"), scored.filter(d=>d.m==="F").sort((a,b)=>b.score-a.score).slice(0,10));
})();

$("stamp").innerHTML=`prices ${META.price_date}<br>${META.n} companies<br>median quarter ${META.median_end}`;
$("meth").innerHTML=`Own construction from SEC filings`
  +` &middot; data through <b>${META.latest_filing}</b>`
  +` &middot; latest period end ${META.latest_end}`
  +` &middot; rebuilt ${META.built_human}`;
$("warnbox").innerHTML=`<b>Reconstruction, not the licensed index.</b> Top 3,000 US companies by
  market cap on ${META.price_date}, rebuilt from filings using Russell's own rule.
  ${META.n} carry enough filed data for a TTM; the other ${META.universe-META.n} are absent, not zero.`;
$("method").innerHTML=`
 <p><b>Universe.</b> Every SEC filer with a ticker (7,994) was ranked by market cap. Eligibility follows
   Russell's rules: operating companies on Nasdaq, NYSE or CBOE, US-incorporated — or offshore-chartered
   with a US headquarters, which is how SLB, Flex, Carnival and LyondellBasell qualify. Closed-end funds,
   BDCs, SPACs, partnerships, royalty trusts and 20-F/40-F foreign filers are excluded. Smallest
   constituent $${META.floor}m.</p>
 <p><b>Share counts</b> come from market data, not SEC cover pages. Cover-page counts are stated as of a
   filing date and break in two ways: an ADR reports <em>ordinary</em> shares while its quote is per ADS
   (BeOne differed by exactly its 13:1 ratio, reaching a fictitious $555bn), and a reverse split after the
   stated date inflates market cap by the split ratio — 545 names in the candidate pool had one.</p>
 <p><b>Fundamentals</b> are TTM, summed from four contiguous quarters spanning 240–300 days. Quarterly
   values come from directly tagged three-month facts where they exist, otherwise by differencing
   year-to-date cumulatives. 52/53-week filers produce twin quarters, which are de-duplicated.
   ${META.banks} banks carry no revenue tag at all and use net interest income plus non-interest income,
   which is what "total revenue" means on a bank income statement.</p>
 <p><b>Insider buying.</b> Officers and directors must report trades in their own
   company to the SEC within two business days, on Form 4. Most of what lands there is
   pay rather than opinion: shares granted, options exercised, or stock sold automatically
   to cover the tax on a vest. Counting all of it makes almost every company look like
   heavy insider selling, which is why the raw figure is close to useless. Only open-market
   purchases and sales are counted here &mdash; the two cases where somebody chose to put
   their own money in or take it out. The column is purchases minus sales over the last
   ${META.insider_window} days, in millions of dollars. The asymmetry is the point: an
   executive buying their own shares has few motives beyond expecting them to rise,
   whereas selling has many innocent explanations, from a divorce to a house.
   ${META.insiders} companies show any open-market buying at all.</p>
 <p><b>Earnings yield against the risk-free rate.</b> A multiple on its own cannot tell you
   whether something is dear. Turn it the other way up: a company on 28 times earnings
   returns about 3.6p a year for every pound of its share price. A 10-year US Treasury note
   pays ${META.y10}% for no equity risk whatsoever. This column is the gap between the two,
   in percentage points. Positive means the business earns you more per pound than lending
   to the US government does; negative means it earns less, and you are paying up front for
   growth you have not been given yet. That is not an argument against owning it &mdash;
   plenty of the best businesses sit well below the line &mdash; but it makes the size of
   the bet explicit. Computed from net income and market cap rather than by inverting P/E,
   so companies losing money show a negative yield instead of quietly dropping out.</p>
 <p><b>Checked against SEC's own arithmetic.</b> Everything above is this pipeline reading
   filings and deciding what each number means, which is exactly the kind of process that can
   be confidently wrong. SEC separately publishes "frames": every filer that reported a given
   tag for a given period, already gathered up. That is a second, independent route to the
   same figure. The panel's total assets and shareholders' equity are compared against it at
   each build &mdash; balance sheet items, because they are a single value at a single date
   and need no reconstruction to compare. At the last run ${META.fchk_n} figures were checked
   and ${META.fchk_bad} disagreed, all of those by rounding in the third decimal of a billion
   on companies worth a few million. It does not prove the rest is right, but it means the
   foundations are not quietly off.</p>
 <p><b>The composite score</b> ranks each company against its own sector on five factors — cheap
   EV/EBIT, high return on capital employed, high FCF yield, net cash relative to market value, and
   revenue growth — weighted 25/20/25/20/10 to tilt toward cash generation and balance sheet, which is
   what decides who is forced to refinance in a rising-rate regime. A name needs four of the five before
   any score is issued; a partial score would quietly reward thin disclosure. Quality uses return on
   capital employed rather than ROIC because ROIC subtracts cash and so explodes for net-cash companies
   (United printed 8,123%). Growth is capped at 50%: above that it stops describing the business.
   Anchors: Tesla 29.6, Axon 28.9, NVIDIA 55.7, Apple 55.2, Marathon Petroleum 88.0.</p>
 <p><b>What it cannot tell you.</b> Sector comes from SIC, a 1930s taxonomy that filers self-report and
   rarely update; large misfits are overridden by hand and the rest are approximate. There is no debt
   maturity schedule, no fixed-versus-floating mix, no hedging and no segment detail. Growth is blank when
   a year-ago TTM is not reconstructible — never zero. And a cross-section is a snapshot: it shows what
   companies look like, not whether they are cheap.</p>
 <ul>
   <li><b>Mixed quarter ends.</b> ${META.q2} of ${META.n} report a quarter ending April 2026 or later;
     the rest have not filed since. Companies are not on a common date.</li>
   <li><b>Prices are a single snapshot</b> (${META.price_date}) while fundamentals are as-filed, so
     multiples pair a current price with a fundamental up to a quarter old.</li>
   <li><b>Percentile clipping.</b> Axes clip to the 2nd–98th percentile. Points outside are pinned at the
     edge and counted, not dropped.</li>
   <li><b>Survivorship.</b> Only companies filing today are present. Nothing that delisted, went private
     or failed appears anywhere.</li>
 </ul>`;
$("foot").innerHTML=`Built from SEC XBRL company facts and market prices · universe ${META.universe} ranked,
  ${META.n} with computable fundamentals, ${META.skipped} without · total market cap
  $${(META.total_mcap/1000).toFixed(1)}tn · prices ${META.price_date}
  · data through ${META.latest_filing} · rebuilt ${META.built_human}
  <span class="rights">&copy; ${new Date(META.built).getFullYear()} Bilaal Raja.
  The universe construction, factor definitions, analysis and code on this page
  are my own work and are not licensed for reuse. The underlying SEC filing data
  is public domain. Published as a personal project; nothing here is investment
  advice or a recommendation to buy or sell any security.</span>`;

addEventListener("resize",()=>{clearTimeout(window._rt);window._rt=setTimeout(()=>{draw();drawSmall();},120);});
matchMedia("(prefers-color-scheme:dark)").addEventListener("change",()=>{draw();drawSmall();});
// Push any state restored from the URL back into the controls, so the page a
// visitor lands on matches the link they followed.
$("q").value=st.q;
$("lx").setAttribute("aria-pressed",st.lx);
$("ly").setAttribute("aria-pressed",st.ly);
if(st.sector){
  const b=[...$("leg").children]
    .find(c=>c.textContent.startsWith(st.sector));
  if(b) b.setAttribute("aria-pressed","true");
}
// Entrance runs once, on first paint, and is skipped for anyone who has asked
// for reduced motion.
let ENTER = matchMedia("(prefers-reduced-motion: reduce)").matches ? 1 : 0;
draw(); drawSmall();
if(ENTER<1){
  const t0=performance.now(), DUR=900;
  (function step(now){
    ENTER=Math.min(1,(now-t0)/DUR);
    draw();
    if(ENTER<1) requestAnimationFrame(step);
  })(t0);
}
</script>
"""

out = (HTML.replace("__DATA__", json.dumps(data, separators=(",",":")))
           .replace("__META__", json.dumps(meta))
           .replace("__METRICS__", json.dumps(METRICS))
           .replace("__SECTORS__", json.dumps(SECTORS)))
p = HERE/"r3k_dashboard.html"
p.write_text(out)
print(f"wrote {p}  ({len(out)/1e6:.2f} MB)")
print(f"  companies embedded : {len(data)}")
print(f"  metrics selectable : {len(METRICS)}")
print(f"  median quarter end : {meta['median_end']}   prices {meta['price_date']}")
