"""Companion page: management's own results commentary for the Russell 3000 universe.

3,000 entries and ~13MB of text cannot all be in the DOM at once, so the page
renders only what matches the current search and paginates the rest.
"""
import json, re
from pathlib import Path

import brand
import pandas as pd

HERE = Path(__file__).resolve().parent
slices = json.load(open(HERE/"mdna_slices.json"))
panel  = {r["ticker"]: r for r in json.load(open(HERE/"r3k_scored.json"))}
uni    = pd.read_json(HERE/"r3k_universe.json").set_index("ticker")

LIMIT = 2200          # trimmed from 2600 to keep the page inside the artifact cap
def trim(t):
    if not t: return None
    t = t.strip()
    if len(t) <= LIMIT: return t
    cut = t[:LIMIT]; dot = cut.rfind(". ")
    return (cut[:dot+1] if dot > LIMIT*0.6 else cut).strip()

rows = []
for cik, v in slices.items():
    tk = v["ticker"]
    if not (v.get("q") or v.get("a")): continue
    p = panel.get(tk, {})
    u = uni.loc[tk] if tk in uni.index else None
    d = {"t": tk, "n": v["name"], "s": v["sector"], "cik": int(cik),
         "mc": round(float(u.mcap), 2) if u is not None else None,
         "rk": int(u["rank"]) if u is not None else None}
    for k, m in (("mcap","mcap"),("rev","rev"),("growth","g"),("margin","mg"),
                 ("fcf_yield","fy"),("ev_ebit","ee"),("score","sc")):
        val = p.get(k)
        d[m] = round(float(val), 2) if isinstance(val,(int,float)) else None
    for src, key in (("q","q"), ("a","a")):
        node = v.get(src)
        if node and node.get("text"):
            d[key] = {"x": trim(node["text"]), "p": node.get("period"),
                      "f": node.get("filed"), "fm": node.get("form")}
    rows.append(d)
rows.sort(key=lambda r: -(r.get("mcap") or 0))

meta = {"n": len(rows),
        "q": sum(1 for r in rows if r.get("q")),
        "a": sum(1 for r in rows if r.get("a")),
        "chars": sum(len((r.get(k) or {}).get("x","")) for r in rows for k in ("q","a"))}

HTML = """<meta charset="utf-8">
<title>Russell 3000 Results Commentary</title>
__FONTS__
<style>
__BRANDCSS__
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15.5px;line-height:1.6}
.wrap{max-width:940px;margin:0 auto;padding:32px 18px 70px;display:flex;flex-direction:column;gap:20px}
header{border-bottom:2px solid var(--ink);padding-bottom:13px}
h1{font-family:var(--serif);font-size:clamp(26px,5vw,38px);letter-spacing:-.021em;
  line-height:1.05;font-weight:600;text-wrap:balance}
.dek{color:var(--ink2);margin-top:9px;max-width:64ch}
.stat{display:flex;gap:22px;flex-wrap:wrap;font-family:var(--mono);font-size:11.5px;
  color:var(--ink3);margin-top:11px}
.stat b{color:var(--ink);font-weight:600}
.controls{position:sticky;top:0;z-index:9;background:var(--bg);padding:11px 0 12px;
  border-bottom:1px solid var(--rule);display:flex;gap:11px;flex-wrap:wrap;align-items:center}
input[type=search],select{font:inherit;font-size:14px;padding:9px 11px;border:1px solid var(--rule);
  border-radius:8px;background:var(--card);color:var(--ink)}
input[type=search]{flex:1;min-width:210px}
input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px}
.hits{font-family:var(--mono);font-size:11.5px;color:var(--ink3);white-space:nowrap}
.co{background:var(--card);border:1px solid var(--rule);border-radius:11px;padding:17px 19px;
  display:flex;flex-direction:column;gap:11px}
.hd{display:flex;justify-content:space-between;gap:13px;align-items:baseline;flex-wrap:wrap}
.tk{font-family:var(--mono);font-size:17px;font-weight:700;letter-spacing:-.02em}
.nm{color:var(--ink2);font-size:14px}
.sec{font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--accent);background:var(--accent-bg);padding:3px 8px;border-radius:999px}
.mx{display:flex;gap:15px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;color:var(--ink3);
  border-top:1px solid var(--rule2);border-bottom:1px solid var(--rule2);padding:8px 0}
.mx span b{color:var(--ink);font-weight:600}
.blk{display:flex;flex-direction:column;gap:5px}
.lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  display:flex;gap:9px;align-items:baseline}
.lbl.q{color:var(--q)} .lbl.a{color:var(--a)}
.lbl em{font-style:normal;color:var(--ink3);letter-spacing:0;text-transform:none;font-size:11px}
.txt{font-size:14.5px;color:var(--ink2);line-height:1.62}
.txt mark{background:var(--accent-bg);color:var(--ink);padding:0 2px;border-radius:3px}
.src{font-size:12px}
.src a{color:var(--accent)}
.more{align-self:center;font:inherit;font-size:14px;font-weight:600;padding:10px 22px;
  border:1px solid var(--rule);border-radius:9px;background:var(--card);color:var(--ink);cursor:pointer}
.more:hover{border-color:var(--accent);color:var(--accent)}
.empty{text-align:center;color:var(--ink3);padding:38px 0}
details{border-top:1px solid var(--rule);padding-top:13px}
summary{cursor:pointer;font-weight:600;color:var(--ink2);font-size:14px}
details .body{margin-top:10px;font-size:14px;color:var(--ink2);display:flex;flex-direction:column;gap:9px}
details .body b{color:var(--ink)}

.byline{display:flex;justify-content:space-between;align-items:baseline;gap:14px;flex-wrap:wrap;
  border-top:1px solid var(--rule);margin-top:11px;padding-top:9px;font-size:13px;color:var(--ink3)}
.byline b{color:var(--ink);font-weight:640}
.byline a{color:var(--accent,#1b6ea8);text-decoration:none}
.byline a:hover{text-decoration:underline}
.byline .meth{font-size:12px}
footer{border-top:1px solid var(--rule);padding-top:13px;font-family:var(--mono);font-size:11.5px;
  color:var(--ink3);line-height:1.75}
</style>
<div class="wrap">
__MASTHEAD__
<header>
  <h1>What management actually said</h1>
  <p class="dek">Results commentary lifted from each company&rsquo;s own 10-Q and 10-K &mdash;
    the passages where they explain what moved, and why. Not generated text.</p>
  <div class="stat" id="stat"></div>
  <div class="byline">
    <span>Built by <b>Bilaal Raja</b> &middot;
      <a href="https://linkedin.com/in/bilaalraja" target="_blank" rel="noopener">linkedin.com/in/bilaalraja</a></span>
    <span class="meth">Data and method: SEC EDGAR, own pipeline &middot; August 2026</span>
  </div>

</header>

<div class="controls">
  <input type="search" id="q" placeholder="Search ticker, company, or the commentary itself — e.g. NVDA, tariffs, pricing pressure" autocomplete="off">
  <select id="sec"></select>
  <select id="sort">
    <option value="mcap">Sort: market cap</option>
    <option value="score">Sort: composite score</option>
    <option value="growth">Sort: revenue growth</option>
    <option value="ticker">Sort: ticker A–Z</option>
  </select>
  <span class="hits" id="hits"></span>
</div>

<div id="list"></div>
<button class="more" id="more" hidden>Show more</button>

<details>
  <summary>How this was extracted, and where it fails</summary>
  <div class="body" id="method"></div>
</details>
<footer id="foot"></footer>
</div>
<script>
const D=__DATA__, META=__META__;
const $=i=>document.getElementById(i);
const PAGE=25; let shown=PAGE, cur=D;

const secs=[...new Set(D.map(d=>d.s))].sort();
$("sec").innerHTML='<option value="">All sectors</option>'+secs.map(s=>`<option>${s}</option>`).join("");

const esc=s=>s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function hl(t,q){
  if(!q) return esc(t);
  const re=new RegExp("("+q.replace(/[.*+?^${}()|[\\]\\\\]/g,"\\\\$&")+")","ig");
  return esc(t).replace(re,"<mark>$1</mark>");
}
const num=(v,s,d)=>v==null?"—":(s||"")+v.toFixed(d==null?1:d);

function card(d,q){
  const m=[];
  if(d.mcap!=null) m.push(`<span>mkt cap <b>$${d.mcap>=100?d.mcap.toFixed(0):d.mcap.toFixed(2)}bn</b></span>`);
  if(d.rev!=null)  m.push(`<span>revenue <b>$${d.rev.toFixed(2)}bn</b></span>`);
  if(d.g!=null)    m.push(`<span>growth <b>${d.g.toFixed(1)}%</b></span>`);
  if(d.mg!=null)   m.push(`<span>margin <b>${d.mg.toFixed(1)}%</b></span>`);
  if(d.fy!=null)   m.push(`<span>FCF yld <b>${d.fy.toFixed(1)}%</b></span>`);
  if(d.sc!=null)   m.push(`<span>score <b>${d.sc.toFixed(1)}</b></span>`);
  const blk=(o,cls,name)=>o?`<div class="blk">
      <div class="lbl ${cls}">${name}<em>${o.fm} · period ended ${o.p} · filed ${o.f}</em></div>
      <p class="txt">${hl(o.x,q)}</p></div>`:"";
  return `<div class="co">
    <div class="hd"><div><span class="tk">${d.t}</span> <span class="nm">${esc(d.n)}</span></div>
      <span class="sec">${d.s}</span></div>
    ${m.length?`<div class="mx">${m.join("")}</div>`:""}
    ${blk(d.q,"q","Quarterly")}${blk(d.a,"a","Annual")}
    <p class="src"><a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${String(d.cik).padStart(10,"0")}&type=10-&dateb=&owner=include&count=10" target="_blank" rel="noopener">Read the filings on SEC EDGAR &rarr;</a></p>
  </div>`;
}

function render(){
  const q=$("q").value.trim();
  $("list").innerHTML = cur.length
    ? cur.slice(0,shown).map(d=>card(d,q)).join("")
    : `<p class="empty">Nothing matches that.</p>`;
  $("more").hidden = shown>=cur.length;
  $("more").textContent=`Show more (${Math.min(PAGE,cur.length-shown)} of ${cur.length-shown} remaining)`;
  $("hits").textContent=`${cur.length} of ${D.length}`;
}
function apply(){
  const q=$("q").value.trim().toLowerCase(), s=$("sec").value, so=$("sort").value;
  cur=D.filter(d=>{
    if(s && d.s!==s) return false;
    if(!q) return true;
    if(d.t.toLowerCase().includes(q)||d.n.toLowerCase().includes(q)) return true;
    return ((d.q&&d.q.x)||"").toLowerCase().includes(q)||((d.a&&d.a.x)||"").toLowerCase().includes(q);
  });
  const key={mcap:d=>-(d.mcap??-1),score:d=>-(d.sc??-1),growth:d=>-(d.g??-1e9),ticker:d=>d.t}[so];
  cur=[...cur].sort((a,b)=>{const x=key(a),y=key(b);return x<y?-1:x>y?1:0;});
  shown=PAGE; render();
}
let t; $("q").oninput=()=>{clearTimeout(t);t=setTimeout(apply,180);};
$("sec").onchange=apply; $("sort").onchange=apply;
$("more").onclick=()=>{shown+=PAGE;render();};

$("stat").innerHTML=`<span><b>${META.n}</b> companies</span>
  <span><b>${META.q}</b> quarterly</span><span><b>${META.a}</b> annual</span>
  <span><b>${(META.chars/1e6).toFixed(1)}M</b> characters of filed commentary</span>`;
$("method").innerHTML=`
 <p><b>Where it comes from.</b> The SEC's structured data API carries numbers only &mdash; not one
  narrative field. This text was extracted from the filing documents themselves: the latest 10-Q and
  latest 10-K for each company, HTML stripped, the Management's Discussion section located, and the
  sentences that report a change with a reason selected from within it. Raw filings averaged 3.4MB
  each and were discarded after extraction.</p>
 <p><b>Coverage.</b> ${META.q} of 3,000 companies have quarterly commentary and ${META.a} have annual.
  65% open on revenue or sales; the remainder open on margin, earnings or another line management chose
  to lead with.</p>
 <p><b>Where it fails.</b> Section headings are not standardised &mdash; Wells Fargo's 10-Q contains no
  instance of "Management's Discussion and Analysis" at all, calling it "Financial Review" instead, and
  a handful of filers match nothing and are absent. An earlier version of this extractor returned
  financial-statement footnotes for roughly a third of companies, because notes are dense in
  "X decreased due to Y" language and beat the real section on any naive scoring. That is fixed, but
  the underlying difficulty is real: <b>treat any single entry as a pointer to the filing, not a
  substitute for it.</b> Every card links to the source.</p>
 <p><b>The text is theirs, unedited.</b> Sentences are selected, never rewritten or summarised, so the
  emphasis and any spin are the company's own.</p>`;
$("foot").innerHTML=`Extracted from SEC EDGAR 10-Q and 10-K filings ·
  ${META.n} companies · ${META.q} quarterly and ${META.a} annual passages ·
  companion to the Russell 3000 cross-section dashboard`;
apply();
</script>
"""
out = (HTML.replace("__BRANDCSS__",
                    brand.TOKENS + brand.TRANSITION_CSS + brand.MASTHEAD_CSS
                    + """
/* this page was written against its own names; map them onto the brand tokens
   rather than rewriting every rule and risking a miss */
:root{--card:var(--raise);--accent:var(--ember);--accent-bg:var(--raise);
  --q:var(--ember);--a:var(--ink3)}
""")
           .replace("__FONTS__", brand.FONTS)
           .replace("__MASTHEAD__", brand.masthead("commentary"))
           .replace("__DATA__", json.dumps(rows, separators=(",",":")))
           .replace("__META__", json.dumps(meta)))
p = HERE/"commentary.html"
out = out + brand.NAV_JS
p.write_text(out)
print(f"wrote {p}  ({len(out)/1e6:.2f} MB)")
print(f"  companies {meta['n']} · quarterly {meta['q']} · annual {meta['a']}")
print(f"  commentary {meta['chars']/1e6:.1f}M chars")
