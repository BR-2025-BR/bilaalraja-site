#!/usr/bin/env python3
"""Generate the interactive US rates page from rates_history.json.

Reuses the research pages' design system (fonts + tokens lifted from
beta_book.html) so it matches the rest of the site, and embeds the data so the
page is fully static -- the API calls happen at build time in
fetch_rates_history.py, never in the browser.

    python3 make_rates.py      # writes rates.html
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "rates_history.json").read_text())
STYLE = re.search(r"<style>.*?</style>", (HERE / "beta_book.html").read_text(), re.S).group(0)

EXTRA_CSS = """
<style>
:root{--r-ffr:#c96a17;--r-2y:#2f7fd0;--r-10y:#1f8a56;--r-30y:#8a58cc}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--r-ffr:#e58a3c;--r-2y:#5aa2e8;--r-10y:#54c088;--r-30y:#a982e6}}
:root[data-theme="dark"]{--r-ffr:#e58a3c;--r-2y:#5aa2e8;--r-10y:#54c088;--r-30y:#a982e6}
.rwrap{position:relative;margin:10px 0 4px}
.rchart{width:100%;height:300px;display:block}
.rvline{position:absolute;width:1px;background:var(--ink3);opacity:.5;pointer-events:none;display:none;top:0}
.rlegend{display:flex;gap:16px;flex-wrap:wrap;font-size:.85rem;color:var(--ink2);margin:10px 0 2px;align-items:center}
.rlegend i{display:inline-block;width:16px;height:3px;vertical-align:middle;margin-right:6px;border-radius:2px}
.rstats{display:flex;gap:18px;flex-wrap:wrap;font-size:.85rem;color:var(--ink2);margin:6px 0}
.rstats b{color:var(--ink);font-family:var(--mono);font-weight:500}
</style>"""

CHART_JS = r"""
<script>
(function(){
  const R=__DATA__;
  const svg=document.getElementById("rchart"), wrap=svg.parentElement;
  svg.setAttribute("preserveAspectRatio","none");
  wrap.style.touchAction="pan-y";
  const S=[
    {k:"ffr",label:"Fed funds (EFFR)",c:"var(--r-ffr)",w:2.6},
    {k:"y2", label:"2-year",  c:"var(--r-2y)", w:1.6},
    {k:"y10",label:"10-year", c:"var(--r-10y)",w:1.6},
    {k:"y30",label:"30-year", c:"var(--r-30y)",w:1.6},
  ];
  const D=R.dates, N=D.length, H=300, P={l:40,r:12,t:12,b:24};
  let W,x,y,hi;
  const tip=document.createElement("div");
  Object.assign(tip.style,{position:"absolute",display:"none",flexDirection:"column",gap:"2px",
    background:"var(--raise)",border:"1px solid var(--line)",borderRadius:"6px",padding:"7px 10px",
    fontFamily:"var(--mono)",fontSize:"11px",color:"var(--ink2)",whiteSpace:"nowrap",
    pointerEvents:"none",zIndex:"6",boxShadow:"0 6px 18px rgba(0,0,0,.3)"});
  wrap.appendChild(tip);
  const vline=document.createElement("div"); vline.className="rvline"; wrap.appendChild(vline);
  const fmt=v=>v==null?"—":v.toFixed(2)+"%";
  const seg=(k,c,w)=>{let d="",pen=false;for(let i=0;i<N;i++){const v=R[k][i];
    if(v==null){pen=false;continue;} d+=(pen?"L":"M")+x(i).toFixed(1)+" "+y(v).toFixed(1)+" ";pen=true;}
    return `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linejoin="round"/>`;};
  function render(){
    W=Math.max(300, wrap.clientWidth||wrap.getBoundingClientRect().width||900);
    svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
    let mx=0; S.forEach(s=>R[s.k].forEach(v=>{if(v!=null&&v>mx)mx=v;}));
    hi=Math.ceil(mx+0.4);
    x=i=>P.l+(W-P.l-P.r)*i/(N-1); y=v=>H-P.b-(H-P.t-P.b)*v/hi;
    let g="";
    for(let t=0;t<=hi;t++){const yy=y(t);
      g+=`<line class="ax-line" x1="${P.l}" y1="${yy.toFixed(1)}" x2="${(W-P.r).toFixed(1)}" y2="${yy.toFixed(1)}"/>`
        +`<text class="ax-text" x="${P.l-6}" y="${(yy+4).toFixed(1)}" text-anchor="end">${t}%</text>`;}
    let lastYr="";
    for(let i=0;i<N;i++){const yr=D[i].slice(0,4);
      if(yr!==lastYr){lastYr=yr;
        g+=`<text class="ax-text" x="${x(i).toFixed(1)}" y="${H-8}" text-anchor="middle">${yr}</text>`;}}
    S.forEach(s=>g+=seg(s.k,s.c,s.w));
    svg.innerHTML=g;
    readout(N-1,false);
  }
  const idxAt=cx=>{const r=svg.getBoundingClientRect();
    const frac=((cx-r.left)/r.width*W-P.l)/(W-P.l-P.r);
    return Math.max(0,Math.min(N-1,Math.round(frac*(N-1))));};
  const rstats=()=>document.getElementById("rstats");
  const lastVal=k=>{for(let j=N-1;j>=0;j--)if(R[k][j]!=null)return R[k][j];return null;};
  function readout(i,scrub){
    const val=k=>scrub?R[k][i]:lastVal(k);
    const a=val("y10"),b=val("y2"), sp=(a!=null&&b!=null)?(a-b):null;
    const spTxt=sp==null?"":`  ·  <span>10y–2y </span><b style="color:${sp<0?'var(--neg)':'var(--pos)'}">${(sp>0?'+':'')+(sp*100).toFixed(0)}bp</b>`;
    rstats().innerHTML=`<span>${scrub?D[i]:'Latest '+D[i]}</span>`
      +S.map(s=>`<span style="color:${s.c}">■</span> ${s.label.split(' ')[0]} <b>${fmt(val(s.k))}</b>`).join("  ")
      +spTxt;
  }
  let scrub=false;
  function show(cx){const i=idxAt(cx); scrub=true;
    vline.style.display="block"; vline.style.left=(x(i)/W*100)+"%"; vline.style.height=((H-P.b)/H*100)+"%";
    readout(i,true);
    tip.style.display="flex";
    const rows=S.map(s=>`<span style="color:${s.c}">■ ${s.label.split(' ')[0]} ${fmt(R[s.k][i])}</span>`).join("");
    tip.innerHTML=`<b style="color:var(--ink)">${D[i]}</b>${rows}`;
    const fr=x(i)/W; tip.style.top="4px"; tip.style.left=(fr*100)+"%";
    tip.style.transform=fr>0.55?"translate(calc(-100% - 8px),0)":"translate(8px,0)";}
  const end=()=>{if(!scrub)return;scrub=false;tip.style.display="none";vline.style.display="none";readout(N-1,false);};
  wrap.addEventListener("pointerdown",e=>{show(e.clientX);e.preventDefault();});
  wrap.addEventListener("pointermove",e=>{if(scrub){show(e.clientX);e.preventDefault();}});
  wrap.addEventListener("pointerup",end); wrap.addEventListener("pointercancel",end);
  render();
  if(window.ResizeObserver){new ResizeObserver(()=>render()).observe(wrap);}
  let rt;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(render,150);});
  addEventListener("orientationchange",()=>setTimeout(render,300));
})();
</script>"""


def main():
    legend = "".join(
        f'<span><i style="background:var(--r-{k})"></i>{lab}</span>'
        for k, lab in [("ffr", "Fed funds rate (EFFR)"), ("y2", "2-year Treasury"),
                       ("y10", "10-year Treasury"), ("y30", "30-year Treasury")])
    body = f"""<div class="wrap">
<h1>US Treasury yields &amp; the Fed</h1>
<p class="sub">Daily since {DATA['start']} &middot; updated {DATA['updated']}</p>
<p class="lede">The policy rate the Federal Reserve sets, against what the market charges the US
government to borrow across the curve. Drag along the chart to read any day.</p>
<div class="rstats" id="rstats"></div>
<div class="rwrap"><svg class="rchart" id="rchart" role="img"
  aria-label="US Treasury 2, 10 and 30-year yields and the effective federal funds rate over time"></svg></div>
<div class="rlegend">{legend}</div>
<p class="foot">Yields are the US Treasury daily par yield curve (constant maturity); the policy rate is
the effective federal funds rate published by the Federal Reserve Bank of New York. Both are pulled at
build time &mdash; the page itself makes no external calls. The 10y&ndash;2y figure is the classic
recession-watch spread: negative means the curve is inverted.</p>
</div>"""
    html = ("<!doctype html>\n<html lang=\"en-GB\"><head><meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
            "<title>US Treasury Yields &amp; the Fed</title>\n"
            "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\"><link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
            "<link href=\"https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap\" rel=\"stylesheet\">\n"
            + STYLE + EXTRA_CSS + "\n</head><body>\n" + body
            + CHART_JS.replace("__DATA__", json.dumps({k: DATA[k] for k in
                ("dates", "y2", "y10", "y30", "ffr")}, separators=(",", ":")))
            + "\n</body></html>\n")
    (HERE / "rates.html").write_text(html)
    print(f"  wrote rates.html ({len(html)/1024:.0f} KB, {DATA['n']} days "
          f"{DATA['start']}..{DATA['end']})")


if __name__ == "__main__":
    main()
