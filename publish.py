#!/usr/bin/env python3
"""Rebuild the site from the current R3000 data and stage it for deploy.

  python3 publish.py            rebuild dashboard from data, then stage
  python3 publish.py --no-build stage the existing HTML without regenerating

Everything under site/ is what gets uploaded. Nothing else does.
"""
import argparse, json, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

HERE   = Path(__file__).resolve().parent
SITE   = HERE / "docs"      # GitHub Pages serves from root or /docs only
DOMAIN = "bilaalraja.com"
SRC    = HERE / "pipeline"   # build inputs, kept here so nothing depends on scratch dirs
PY     = "/Users/bilaa/Downloads/pitquant/.venv/bin/python"

PAGES = [                      # source file, url path, human title
    (SRC / "r3k_dashboard.html", "russell3000", "Russell 3000 Cross-Section"),
    (SRC / "commentary.html",    "commentary",  "Results Commentary"),
]

# Any Claude artifact link becomes a local path, so the site stands alone.
ARTIFACT_MAP = {
    "0c2545da-ee53-41ec-8763-583958244c94": "/commentary",
    "ae70a1e5": "/russell3000",
}


def meta_from_dashboard(html: str) -> dict:
    """Pull the META object the generator embedded, so the landing page shows
    exactly the same figures as the dashboard rather than its own guess."""
    m = re.search(r"META=(\{.*?\}), METRICS=", html, re.S)
    return json.loads(m.group(1)) if m else {}


def rewrite_links(html: str) -> tuple[str, int]:
    n = 0
    for uid, local in ARTIFACT_MAP.items():
        pat = re.compile(r'https://claude\.ai/code/artifact/' + uid + r'[^"\']*')
        html, k = pat.subn(local, html)
        n += k
    return html, n


PWA_HEAD = """
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#000000">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="R3000">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon-192.png" type="image/png">
<script>
if("serviceWorker" in navigator)
  addEventListener("load",()=>navigator.serviceWorker.register("/sw.js").catch(e=>e));
</script>
"""

LANDING = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilaal Raja | Equity Research and Quantitative Analysis</title>
<meta name="description" content="Bilaal Raja. Cross-sectional equity screening built from primary SEC EDGAR filings: the full Russell 3000, metrics computed point in time, management commentary parsed alongside.">
<meta name="author" content="Bilaal Raja">
<link rel="canonical" href="https://bilaalraja.com/">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="Bilaal Raja">
<meta property="og:title" content="Bilaal Raja | Equity Research and Quantitative Analysis">
<meta property="og:description" content="Cross-sectional equity screening built from primary SEC EDGAR filings. The full Russell 3000, metrics computed point in time, management commentary parsed alongside.">
<meta property="og:url" content="https://bilaalraja.com/">
<meta property="og:image" content="https://bilaalraja.com/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Bilaal Raja | Equity Research and Quantitative Analysis">
<meta name="twitter:description" content="Cross-sectional equity screening built from primary SEC EDGAR filings.">
<meta name="twitter:image" content="https://bilaalraja.com/og.png">
""" + PWA_HEAD + """
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Person","name":"Bilaal Raja",
"url":"https://bilaalraja.com/","image":"https://bilaalraja.com/og.png",
"jobTitle":"Quality Scientist","description":"Equity research and quantitative analysis built from primary SEC filings.",
"alumniOf":{{"@type":"CollegeOrUniversity","name":"University of Manchester"}},
"knowsAbout":["Equity research","Quantitative analysis","SEC EDGAR filings","Factor investing","Financial data engineering"],
"sameAs":["https://linkedin.com/in/bilaalraja"]}}
</script>
<style>
:root{{--bg:#ffffff;--panel:#f4f4f4;--ink:#000000;--ink2:#3d3d3d;--ink3:#7a7a7a;
 --rule:#d8d8d8;--s1:#ff9900;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
 --bg:#000000;--panel:#1b1b1b;--ink:#ffffff;--ink2:#c4c4c4;--ink3:#8a8a8a;
 --rule:#2f2f2f;--s1:#ff9900;}}}}
:root[data-theme="dark"]{{--bg:#000000;--panel:#1b1b1b;--ink:#ffffff;--ink2:#c4c4c4;
 --ink3:#8a8a8a;--rule:#2f2f2f;--s1:#ff9900;}}
*{{box-sizing:border-box;margin:0;padding:0}}
#dots{{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}}
.wrap{{position:relative;z-index:1}}
@supports (corner-shape: squircle){{.card{{corner-shape:squircle}}}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
 line-height:1.55;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:760px;margin:0 auto;padding:64px 22px 80px}}
h1{{font-size:26px;letter-spacing:-.01em;margin-bottom:4px}}
.sub{{color:var(--ink3);font-family:var(--mono);font-size:12.5px;margin-bottom:30px}}
.lede{{color:var(--ink2);margin-bottom:34px;max-width:60ch}}
.stats{{display:flex;flex-wrap:wrap;gap:34px;margin:4px 0 30px;
 padding:18px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}}
.stats b{{display:block;font-family:var(--mono);font-size:25px;font-weight:500;
 letter-spacing:-.02em;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1.15}}
.stats span{{font-family:var(--mono);font-size:10.5px;letter-spacing:.13em;
 text-transform:uppercase;color:var(--ink3)}}
.card{{display:block;text-decoration:none;color:inherit;background:var(--panel);
 border:1px solid var(--rule);border-left:3px solid var(--s1);border-radius:14px;
 padding:18px 20px;margin-bottom:12px}}
.card:hover{{border-left-color:var(--ink)}}
.card h2{{font-size:16.5px;margin-bottom:4px}}
.chead{{display:flex;align-items:center;gap:11px;margin-bottom:4px}}
.chead h2{{margin-bottom:0}}
.ico{{flex:0 0 auto;width:34px;height:34px;border-radius:10px;
 display:grid;place-items:center;background:var(--panel);
 border:1px solid var(--rule);color:var(--s1)}}
.card:hover .ico{{border-color:var(--s1)}}
.ico svg{{width:19px;height:19px;stroke:currentColor;fill:none;
 stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}}
.card p{{color:var(--ink2);font-size:14px}}
.card .m{{font-family:var(--mono);font-size:11.5px;color:var(--ink3);margin-top:8px}}
footer{{margin-top:40px;padding-top:18px;border-top:1px solid var(--rule);
 font-family:var(--mono);font-size:12px;color:var(--ink3)}}
footer a{{color:var(--s1)}}
.rights{{display:block;margin-top:12px;padding-top:12px;border-top:1px solid var(--rule);
 max-width:76ch;line-height:1.7;font-size:11.5px}}
</style></head><body><div class="wrap">
<canvas id="dots" aria-hidden="true"></canvas>
<h1>Bilaal Raja</h1>
<div class="sub">Equity research &middot; quantitative analysis</div>
<div class="stats">
  <div><b>{n}</b><span>companies</span></div>
  <div><b>${mcap}tn</b><span>market cap</span></div>
  <div><b>{metrics}</b><span>metrics</span></div>
  <div><b>{sectors}</b><span>sectors</span></div>
</div>

<p class="lede">Work built from primary sources. The universe, the factor
construction and the validation below are my own, assembled from SEC XBRL
company facts rather than a vendor feed.</p>

<a class="card" href="/russell3000">
  <div class="chead"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 3v16a2 2 0 0 0 2 2h15"/>
    <circle cx="9"  cy="15" r="1.5"/><circle cx="13" cy="9"  r="1.5"/>
    <circle cx="17" cy="13" r="1.5"/><circle cx="19" cy="6"  r="1.5"/>
    <circle cx="8"  cy="9"  r="1.5"/>
  </svg></span><h2>Russell 3000 Cross-Section</h2></div>
  <p>{n} companies with computable trailing-twelve-month fundamentals, screened on
  35 metrics with sector-neutral percentile ranking and a composite score.</p>
  <div class="m">filings to {latest_filing} &middot; prices {price_date} &middot; rebuilt {built_human}</div>
</a>

<a class="card" href="/commentary">
  <div class="chead"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M21 12a7 7 0 0 1-7 7H8l-4 3v-4.6A7 7 0 0 1 3 12a7 7 0 0 1 7-7h4a7 7 0 0 1 7 7z"/>
    <path d="M8.5 10.5h7"/><path d="M8.5 13.5h4"/>
  </svg></span><h2>Results Commentary</h2></div>
  <p>Management's own discussion of results, extracted from 10-Q and 10-K
  filings and matched to the reported figures.</p>
  <div class="m">filings to {latest_filing} &middot; prices {price_date} &middot; rebuilt {built_human}</div>
</a>

<a class="card" href="/methodology">
  <div class="chead"><span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 3 3 7.5 12 12l9-4.5L12 3z"/>
    <path d="M3 12.5 12 17l9-4.5"/><path d="M3 17.5 12 22l9-4.5"/>
  </svg></span><h2>How this was built</h2></div>
  <p>Universe construction, point-in-time discipline, metric definitions, and the
  thirteen defects found by checking output against reality.</p>
  <div class="m">methodology</div>
</a>

<footer>
Built from SEC XBRL company facts and market prices.<br>
<a href="https://linkedin.com/in/bilaalraja">linkedin.com/in/bilaalraja</a>
<span class="rights">&copy; {year} Bilaal Raja. The universe construction, factor
definitions, analysis and code on this site are my own work and are not licensed
for reuse. The underlying SEC filing data is public domain. Published as a
personal project; nothing here is investment advice or a recommendation to buy
or sell any security.</span>
</footer>
</div>
<script>
(function(){{
  const c=document.getElementById("dots"), x=c.getContext("2d");
  const calm=matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dark=()=>matchMedia("(prefers-color-scheme: dark)").matches
    || document.documentElement.dataset.theme==="dark";
  let w=0,h=0,dpr=1,dots=[];

  // Three depth layers. Nearer dots are bigger, brighter and shift further
  // under tilt, which is what makes the parallax read as depth.
  const LAYERS=[{{n:70,r:[0.9,1.7],a:[.05,.11],p:6,  v:0.006}},
                {{n:46,r:[1.5,2.6],a:[.08,.16],p:14, v:0.009}},
                {{n:24,r:[2.3,3.6],a:[.11,.21],p:26, v:0.013}}];

  const rand=(lo,hi)=>lo+Math.random()*(hi-lo);

  function seed(){{
    dots=[];
    for(const L of LAYERS) for(let i=0;i<L.n;i++){{
      const ang=Math.random()*6.2832, sp=L.v*rand(.6,1.4);
      dots.push({{
        hx:Math.random(), hy:Math.random(),          // drifting home point
        vx:Math.cos(ang)*sp, vy:Math.sin(ang)*sp,    // units per SECOND
        r:rand(L.r[0],L.r[1]), a:rand(L.a[0],L.a[1]), p:L.p,
        // Two sine components per axis at unrelated periods. Sums of sines are
        // smooth by construction and never settle into a visible loop, which a
        // per-frame random walk cannot manage without looking jittery.
        fx1:rand(.10,.26), fx2:rand(.29,.55), phx1:Math.random()*6.28, phx2:Math.random()*6.28,
        fy1:rand(.10,.26), fy2:rand(.29,.55), phy1:Math.random()*6.28, phy2:Math.random()*6.28,
        ax1:rand(.008,.020), ax2:rand(.003,.009),
        ay1:rand(.008,.020), ay2:rand(.003,.009)
      }});
    }}
  }}

  function size(){{
    dpr=Math.min(devicePixelRatio||1,2);
    w=innerWidth; h=innerHeight;
    c.width=w*dpr; c.height=h*dpr;
    x.setTransform(dpr,0,0,dpr,0,0);
  }}

  let tx=0,ty=0,cx=0,cy=0;
  addEventListener("deviceorientation",e=>{{
    if(e.gamma==null) return;
    tx=Math.max(-1,Math.min(1,e.gamma/35));
    ty=Math.max(-1,Math.min(1,((e.beta||0)-45)/35));
  }},true);
  addEventListener("mousemove",e=>{{
    tx=(e.clientX/w-.5)*2; ty=(e.clientY/h-.5)*2;
  }},{{passive:true}});

  // iOS emits nothing without an explicit grant, and only asks on a gesture.
  function askOnce(){{
    const D=window.DeviceOrientationEvent;
    if(D && typeof D.requestPermission==="function") D.requestPermission().catch(()=>{{}});
    removeEventListener("touchend",askOnce); removeEventListener("click",askOnce);
  }}
  addEventListener("touchend",askOnce,{{passive:true}});
  addEventListener("click",askOnce);

  let last=performance.now(), T=0;
  function frame(now){{
    // Time based, not frame based: a 120Hz phone must not run at double speed.
    // Clamped so a backgrounded tab does not teleport everything on return.
    let dt=Math.min((now-last)/1000, 0.05); last=now;
    if(!calm) T+=dt;

    const k=1-Math.pow(0.001, dt);          // frame-rate independent easing
    cx+=(tx-cx)*k; cy+=(ty-cy)*k;

    x.clearRect(0,0,w,h);
    const base=dark()?"255,255,255":"0,0,0";
    for(const d of dots){{
      if(!calm){{
        d.hx+=d.vx*dt; d.hy+=d.vy*dt;
        if(d.hx<-.05)d.hx=1.05; else if(d.hx>1.05)d.hx=-.05;
        if(d.hy<-.05)d.hy=1.05; else if(d.hy>1.05)d.hy=-.05;
      }}
      const px=(d.hx + Math.sin(T*d.fx1+d.phx1)*d.ax1 + Math.sin(T*d.fx2+d.phx2)*d.ax2)*w
               - cx*d.p;
      const py=(d.hy + Math.sin(T*d.fy1+d.phy1)*d.ay1 + Math.sin(T*d.fy2+d.phy2)*d.ay2)*h
               - cy*d.p;
      x.beginPath();
      x.arc(px,py,d.r,0,6.2832);
      x.fillStyle="rgba("+base+","+d.a+")";
      x.fill();
    }}
    requestAnimationFrame(frame);
  }}

  size(); seed();
  addEventListener("resize",()=>{{size();}},{{passive:true}});
  requestAnimationFrame(n=>{{last=n; frame(n);}});
}})();
</script>
</body></html>
"""



# ----------------------------------------------------------------- metadata
# Open Graph is the one that actually matters here: without it a link pasted
# into LinkedIn or an email renders as a bare URL instead of a card.
DESCRIPTIONS = {
 "russell3000": ("Russell 3000 Cross-Section | Bilaal Raja",
   "Every relevant line item pulled from SEC EDGAR filings for the Russell "
   "3000, with key financial metrics computed point in time. {companies} companies, "
   "35 metrics, sector-neutral percentile ranking."),
 "commentary": ("Russell 3000 Results Commentary | Bilaal Raja",
   "Management's own discussion of results, parsed from 10-Q and 10-K filings "
   "for thousands of US listed companies and matched to the reported figures."),
}


def inject_meta(html: str, path: str, domain: str, companies: str = "") -> str:
    if path not in DESCRIPTIONS:
        return html
    title, desc = DESCRIPTIONS[path]
    # the count is the live one, not a number frozen into the template
    if "{companies}" in desc:
        if not companies:
            sys.exit("inject_meta: no company count for the OG description")
        desc = desc.format(companies=companies)
    url = f"https://{domain}/{path}"
    tags = f"""
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{desc}">
<meta name="author" content="Bilaal Raja">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Bilaal Raja">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://{domain}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="https://{domain}/og.png">
""" + PWA_HEAD
    # insert straight after the existing <title>...</title>
    i = html.find("</title>")
    return html[:i + 8] + tags + html[i + 8:] if i != -1 else tags + html


def write_sitemap(site: Path, domain: str, paths, lastmod: str):
    urls = "".join(
        f"  <url><loc>https://{domain}/{p}</loc><lastmod>{lastmod}</lastmod>"
        f"<changefreq>monthly</changefreq><priority>{pr}</priority></url>\n"
        for p, pr in paths)
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + urls + "</urlset>\n")


# ---------------------------------------------------------------- referrers
# One landing page per contact. Each fires the analytics beacon under its own
# path, then forwards to the dashboard, so "did this person open it" becomes a
# page view you can actually see rather than a guess.
REF_PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<title>Russell 3000 Cross-Section</title>
<meta name="robots" content="noindex,nofollow">
<link rel="canonical" href="https://{domain}{target}">
<style>body{{background:#131312;color:#8b8a80;font:14px -apple-system,sans-serif;
 display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}</style>
</head><body>
<p>Opening&#8230; <a href="{target}">continue</a></p>
<script>
// Delay briefly so the analytics beacon fires before we navigate away.
addEventListener("load",()=>setTimeout(()=>location.replace("{target}"),350));
</script>
</body></html>
"""


def build_referrers(site: Path, domain: str, target: str = "/russell3000") -> list:
    src = Path(__file__).resolve().parent / "contacts.txt"
    if not src.exists():
        return []
    out = []
    for line in src.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split(",")]
        slug = parts[0]
        who = ", ".join(parts[1:]) or "-"
        d = site / "r" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(REF_PAGE.format(domain=domain, target=target))
        out.append((slug, who))
    return out


METHODOLOGY = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Methodology | Bilaal Raja</title>
<meta name="description" content="How the Russell 3000 cross-section is built from SEC EDGAR filings: universe construction, point-in-time discipline, metric definitions, and the defects found along the way.">
<link rel="canonical" href="https://{domain}/methodology">
<meta property="og:type" content="article">
<meta property="og:title" content="Methodology | Bilaal Raja">
<meta property="og:description" content="How the cross-section is built, and the thirteen defects found by checking output against reality.">
<meta property="og:url" content="https://{domain}/methodology">
<meta property="og:image" content="https://{domain}/og.png">
<meta name="twitter:card" content="summary_large_image">
""" + PWA_HEAD + """
<style>
:root{{--bg:#ffffff;--panel:#f4f4f4;--ink:#000000;--ink2:#3d3d3d;--ink3:#7a7a7a;
 --rule:#d8d8d8;--rule2:#ececec;--s1:#ff9900;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
 --bg:#000000;--panel:#1b1b1b;--ink:#ffffff;--ink2:#c4c4c4;--ink3:#8a8a8a;
 --rule:#2f2f2f;--rule2:#212121;--s1:#ff9900;}}}}
:root[data-theme="dark"]{{--bg:#000000;--panel:#1b1b1b;--ink:#ffffff;--ink2:#c4c4c4;
 --ink3:#8a8a8a;--rule:#2f2f2f;--rule2:#212121;--s1:#ff9900;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16px;
 line-height:1.68;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:760px;margin:0 auto;padding:56px 22px 90px}}
a{{color:var(--s1)}}
.back{{font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-decoration:none;
 display:inline-block;margin-bottom:34px}}
h1{{font-size:31px;letter-spacing:-.018em;line-height:1.14;margin-bottom:10px}}
.lede{{color:var(--ink2);font-size:17px;margin-bottom:14px}}
.stamp{{font-family:var(--mono);font-size:12px;color:var(--ink3);
 padding-bottom:26px;border-bottom:1px solid var(--rule);margin-bottom:34px}}
h2{{font-size:20px;letter-spacing:-.012em;margin:40px 0 12px}}
h3{{font-size:15.5px;margin:26px 0 6px}}
p{{margin-bottom:14px;color:var(--ink2)}}
p strong,li strong{{color:var(--ink);font-weight:600}}
ul{{margin:0 0 16px 20px}} li{{margin-bottom:9px;color:var(--ink2)}}
code{{font-family:var(--mono);font-size:.88em;background:var(--panel);
 padding:1px 5px;border-radius:5px;color:var(--ink)}}
.note{{background:var(--panel);border-left:3px solid var(--s1);border-radius:12px;
 padding:15px 18px;margin:22px 0}}
.note p:last-child{{margin-bottom:0}}
ol.defects{{list-style:none;counter-reset:d;margin:0;padding:0}}
ol.defects li{{counter-increment:d;background:var(--panel);border:1px solid var(--rule2);
 border-radius:14px;padding:16px 18px;margin-bottom:10px}}
ol.defects li::before{{content:counter(d,decimal-leading-zero);font-family:var(--mono);
 font-size:11px;color:var(--s1);display:block;margin-bottom:5px;letter-spacing:.08em}}
ol.defects b{{display:block;color:var(--ink);font-size:15.5px;margin-bottom:5px}}
ol.defects p{{margin:0;font-size:14.5px}}
footer{{margin-top:52px;padding-top:20px;border-top:1px solid var(--rule);
 font-family:var(--mono);font-size:11.5px;color:var(--ink3);line-height:1.7}}
</style></head><body><div class="wrap">
<a class="back" href="/">&larr; BILAALRAJA.COM</a>
<h1>How this was built</h1>
<p class="lede">The universe, the point-in-time discipline, the metric definitions,
and the defects I found along the way.</p>
<div class="stamp">{n} companies &middot; filings to {latest_filing} &middot;
prices {price_date} &middot; rebuilt {built_human}</div>

<h2>What this is, and what it is not</h2>
<p>It is a <strong>reconstruction</strong>, not the licensed index. Constituents are
the top 3,000 US-listed companies by market capitalisation on the price date,
rebuilt from SEC filings using Russell's own published rule. It is not a
membership list, and where FTSE Russell's actual reconstitution differs, mine
will differ with it.</p>
<p>Of {universe} candidates, <strong>{n} carry enough filed data</strong> to compute a
trailing twelve month figure. The remaining {skipped} are absent, not zero. That
distinction matters: dropping them silently would bias every cross-sectional
statistic on the page.</p>

<h2>Point in time</h2>
<p>Every figure is <strong>as filed</strong>, not as later restated. A company that
revised its June quarter in October shows what it originally reported.</p>
<ul>
<li>TTM is reconstructed from <strong>four contiguous quarters</strong>, accepted
only where the window spans 240 to 300 days. Anything outside that is a gap, and
a gap is a null rather than a guess.</li>
<li>Filers on a 52/53 week calendar produce two quarters ending days apart.
Those are <strong>deduplicated by period end</strong>, otherwise a quarter is
double counted.</li>
<li>Concept selection is <strong>duration-aware</strong>. An instantaneous balance
sheet fact and a quarterly flow carry the same tag in places, and taking either
without checking the period type silently mixes stocks with flows.</li>
<li>Prices are a <strong>single dated snapshot</strong>. Fundamentals are as
filed. The two are not contemporaneous and the page says so.</li>
</ul>

<h2>Metric definitions worth stating</h2>
<h3>Return on capital employed, not invested capital</h3>
<p>ROCE uses equity plus debt. Subtracting cash to reach invested capital
collapses the denominator on cash-rich balance sheets and produces returns in
the thousands of percent, which is arithmetic rather than insight. Capital
employed is guarded at a floor so a near-zero denominator cannot manufacture a
ranking.</p>
<h3>Banks do not report revenue</h3>
<p><strong>{banks} banks carry no revenue tag at all.</strong> They use net
interest income plus non-interest income instead. Anyone screening the full
market on a revenue multiple without handling this is quietly excluding an
entire sector, and will not notice.</p>
<h3>Winsorisation and sector-neutral ranking</h3>
<p>Raw cross-sectional ranges are unusable. Percentiles are computed within
sector so a utility is compared with utilities, and extreme values are clipped
rather than dropped, so the company stays in the ranking without dominating it.</p>

<h2>Sector is a filter, not a colour</h2>
<p>Twelve categorical hues on three thousand overlapping points is not a design
preference, it is a measurable failure. Run through a colourblind separation
check, twelve hues score a worst all-pairs OKLab distance of <strong>2.0</strong>
against a threshold of 8. Even four hues only pass with a carefully chosen set.</p>
<p>So the main chart is a neutral density cloud and one sector highlights at a
time, which is always a two-category comparison and always separable. Comparing
sectors is done with small multiples, which is the prescribed route when
all-pairs separation fails.</p>

<h2>Thirteen defects, and how they were found</h2>
<div class="note"><p>Every one of these was caught by checking output against
reality, not by reading code. None of them raised an error. That is the point
worth taking from this section: a pipeline that runs cleanly and reports success
can still be wrong in ways only a sanity check will surface.</p></div>
<ol class="defects">
<li><b>American depositary receipts valued at the ordinary share count</b>
<p>One company appeared at a $555bn market capitalisation. The share count was
ordinary shares; the price was per ADS. Fixed by cross-checking counts against
an independent source and excluding on an ADR signature.</p></li>
<li><b>Reverse splits left share counts unadjusted</b>
<p>545 names carried pre-split counts against post-split prices. Fixed by
applying a cumulative split factor from the period end forward.</p></li>
<li><b>Multi-class filers were invisible</b>
<p>Several of the largest companies in the market never became candidates,
because their share counts are dimensioned by class and do not appear in the
undimensioned cover-page data. Fixed by broadening the candidate pool to every
tickered filer rather than trusting one tag.</p></li>
<li><b>A truncated filing history deleted the banking sector</b>
<p>The stored form list holds only the most recent filings. Testing "does this
company file a 10-K" against it excluded frequent filers whose annual report had
scrolled off the end. Fixed by removing the positive form test entirely.</p></li>
<li><b>Ticker selection preferred baby bonds to common stock</b>
<p>A utility resolved to its preferred note rather than its common line, valuing
it at $3.3bn instead of $29.1bn. Fixed by preferring the ticker that carries a
reported share count, which only common equity does.</p></li>
<li><b>Cash flow read from the wrong accessor</b>
<p>Operating cash flow resolved for 18 quarters where a different accessor found
71. Free cash flow coverage rose from 0.8% to 81.7% once corrected.</p></li>
<li><b>Tag migration produced negative quarters</b>
<p>A revenue standard change mid-history produced negative implied quarters when
differencing cumulative figures. Now guarded: a negative quarter inside a TTM
window invalidates the window rather than propagating.</p></li>
<li><b>Log axes on raw percentiles</b>
<p>A second-percentile value near 1e-9 stretched an axis across nine decades and
compressed every real observation into a line. Found only by rendering the page
and looking at it.</p></li>
<li><b>A grouped operation silently misaligned</b>
<p>A pandas grouped apply returned results in a different order than the frame it
was assigned to, so a large-cap growth name scored 85.9 on a cheapness screen.
Caught by a sanity anchor; fixed by ranking within group directly.</p></li>
<li><b>Footnotes returned instead of commentary</b>
<p>The first extraction scored 93% on a structural check while returning
accounting footnotes for roughly a third of companies. Measured against a second
version on identical companies, the rate of passages leading with results went
from 42.8% to 65.0%.</p></li>
<li><b>One filer's commentary collapsed to boilerplate</b>
<p>A 171,000 character section reduced to 5,598 characters of front matter across
that filer's entire history, because the heading anchor matched too early. Fixed
with tiered anchors and a minimum-length test before accepting a narrower slice.</p></li>
<li><b>Background work killed by a foreground timeout</b>
<p>A polling loop hit a timeout, and the resulting signal took the whole process
group with it, losing thousands of in-memory results. Fixed by detaching the
session and checkpointing to disk.</p></li>
<li><b>A stale tier file silently narrowed a queue</b>
<p>A priority filter read tiering written by an earlier run and queued 5,874 items
instead of 25,548. It completed successfully, which is what made it dangerous.</p></li>
</ol>

<h2>What it cannot tell you</h2>
<ul>
<li>It is a <strong>snapshot</strong>. There is no history and no time series, so
nothing here supports a trend or a backtest.</li>
<li>Prices and fundamentals are <strong>not contemporaneous</strong>.</li>
<li>Companies report on <strong>different calendars</strong>. A comparison across
the cross-section compares quarters ending at different dates.</li>
<li>Business development companies and a small number of other structures are
<strong>excluded or misclassified</strong> by the SIC-derived sector mapping.</li>
<li>A metric that is null is <strong>missing, not zero</strong>, and is excluded
from ranking rather than treated as the worst value.</li>
</ul>

<footer>
Built from SEC XBRL company facts and market prices.
&copy; {year} Bilaal Raja. The universe construction, factor definitions, analysis
and code are my own work and are not licensed for reuse. The underlying SEC
filing data is public domain. Published as a personal project; nothing here is
investment advice or a recommendation to buy or sell any security.
</footer>
</div></body></html>
"""


NOT_FOUND = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Not found | Bilaal Raja</title>
<meta name="robots" content="noindex">
<style>
:root{{--bg:#ffffff;--ink:#000000;--ink3:#7a7a7a;--s1:#ff9900;
 --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
 --bg:#000000;--ink:#ffffff;--ink3:#8a8a8a;}}}}
:root[data-theme="dark"]{{--bg:#000000;--ink:#ffffff;--ink3:#8a8a8a;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);
 min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}}
.c{{max-width:38ch}}
h1{{font-size:26px;letter-spacing:-.015em;margin-bottom:8px}}
p{{color:var(--ink3);font-size:15px;line-height:1.6;margin-bottom:20px}}
.n{{font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;color:var(--s1);
 margin-bottom:14px}}
a{{color:var(--s1);font-family:var(--mono);font-size:12.5px}}
</style></head><body><div class="c">
<div class="n">404</div>
<h1>Nothing here</h1>
<p>That page does not exist. It may have been renamed, or the link may have been
mistyped.</p>
<a href="/">&larr; BILAALRAJA.COM</a>
</div></body></html>
"""


# ---------------------------------------------------------------------- PWA
# iOS has honoured web app manifests since 16.4, so this installs as a real
# standalone app rather than a bookmark. The apple-* tags stay for older iOS.

MANIFEST = """{{
  "name": "Russell 3000 Cross-Section",
  "short_name": "R3000",
  "description": "Cross-sectional screening for the Russell 3000, built from SEC EDGAR filings.",
  "start_url": "/russell3000/",
  "scope": "/",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#000000",
  "theme_color": "#000000",
  "icons": [
    {{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}},
    {{"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}},
    {{"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}}
  ]
}}"""

# The commentary page is 12MB and is deliberately not precached; caching it
# would blow past what iOS is willing to keep for a web app.
SW = """const V="r3k-{built}-r2";

// Cloudflare Pages 308s /russell3000 to /russell3000/. A response that followed
// a redirect carries redirected:true, and Safari refuses to accept one of those
// for a navigation request. So: precache the canonical trailing-slash paths, and
// rebuild every response before it is cached or returned, which clears the flag.
const SHELL=["/","/russell3000/","/methodology/","/manifest.webmanifest",
             "/icon-192.png","/icon-512.png","/apple-touch-icon.png"];

async function plain(res){{
  if(!res) return res;
  const body=await res.arrayBuffer();
  return new Response(body,{{status:res.status,statusText:res.statusText,
                            headers:res.headers}});
}}

self.addEventListener("install",e=>{{
  e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));
}});

self.addEventListener("activate",e=>{{
  e.waitUntil(caches.keys()
    .then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k))))
    .then(()=>self.clients.claim()));
}});

async function navigate(req){{
  try{{
    const res=await fetch(req);
    const fixed=await plain(res);
    const c=await caches.open(V);
    c.put(req,fixed.clone());
    return fixed;
  }}catch(err){{
    const hit=await caches.match(req) || await caches.match(req.url+"/")
              || await caches.match("/");
    return hit ? await plain(hit) : Response.error();
  }}
}}

async function asset(req){{
  const hit=await caches.match(req);
  const net=fetch(req).then(async res=>{{
    if(res && res.status===200){{
      const fixed=await plain(res);
      const c=await caches.open(V);
      c.put(req,fixed.clone());
      return fixed;
    }}
    return res;
  }}).catch(()=>hit);
  return hit || net;
}}

self.addEventListener("fetch",e=>{{
  const r=e.request;
  if(r.method!=="GET") return;
  const u=new URL(r.url);
  if(u.origin!==location.origin) return;
  if(u.pathname.startsWith("/commentary")) return;   // 12MB, not worth caching
  e.respondWith(r.mode==="navigate" ? navigate(r) : asset(r));
}});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true",
                    help="stage existing HTML without regenerating from data")
    a = ap.parse_args()

    if not a.no_build:
        print("rebuilding dashboard from current data ...")
        r = subprocess.run([PY, str(SRC / "make_r3k_dash.py")],
                           capture_output=True, text=True, cwd=SRC)
        sys.stdout.write(r.stdout)
        if r.returncode:
            sys.stderr.write(r.stderr)
            sys.exit("build failed — nothing staged, site/ left untouched")

    SITE.mkdir(exist_ok=True)
    meta, total = {}, 0
    for src, path, title in PAGES:
        if not src.exists():
            print(f"  SKIP {title}: {src} not found")
            continue
        html = src.read_text(errors="replace")
        if "dashboard" in src.name:
            meta = meta_from_dashboard(html)
        html, n = rewrite_links(html)
        html = inject_meta(html, path, DOMAIN, f"{meta['n']:,}")
        d = SITE / path
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html)
        mb = len(html) / 1e6
        total += mb
        print(f"  /{path:<14} {mb:6.2f} MB   {n} artifact link(s) localised")

    if not meta:
        sys.exit("could not read META from the dashboard — landing page not written")
    pretty = dict(meta, n=f"{meta['n']:,}", year=meta["built"][:4], domain=DOMAIN,
                  universe=f"{meta['universe']:,}", skipped=f"{meta['skipped']:,}",
                  mcap=f"{meta['total_mcap']/1000:.1f}",
                  banks=f"{meta['banks']:,}")
    (SITE / "index.html").write_text(LANDING.format(**pretty))
    print(f"  /              {len(LANDING)/1e3:6.2f} KB   landing page")

    # CNAME: GitHub Pages custom domain.  _headers: Netlify/Cloudflare.
    # .nojekyll: stops Pages trying to process the files as a Jekyll site.
    (SITE / "CNAME").write_text(DOMAIN + "\n")
    (SITE / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n")
    (SITE / ".nojekyll").write_text("")
    (SITE / "manifest.webmanifest").write_text(MANIFEST.format())
    (SITE / "sw.js").write_text(SW.format(built=meta["built"]))
    # Without this, Cloudflare Pages answers unknown paths with the landing page
    # and a 200, which Google reads as a soft 404 and may index as a duplicate.
    (SITE / "404.html").write_text(NOT_FOUND.format())
    (SITE / "methodology").mkdir(parents=True, exist_ok=True)
    (SITE / "methodology" / "index.html").write_text(METHODOLOGY.format(**pretty))
    print(f"  /methodology   {len(METHODOLOGY)/1e3:6.2f} KB")
    write_sitemap(SITE, DOMAIN,
                  [("", "1.0"), ("russell3000", "0.9"), ("commentary", "0.8"),
                   ("methodology", "0.85")],
                  meta["built"])
    (SITE / "robots.txt").write_text(
        "User-agent: *\nDisallow: /r/\nAllow: /\n"
        f"Sitemap: https://{DOMAIN}/sitemap.xml\n")

    refs = build_referrers(SITE, DOMAIN)
    if refs:
        print(f"\n{len(refs)} tracked link(s):")
        for slug, who in refs:
            print(f"   https://{DOMAIN}/r/{slug:<10}  {who}")

    print(f"\nstaged {total:.2f} MB in {SITE}")
    print(f"filings to {meta['latest_filing']} · prices {meta['price_date']}"
          f" · rebuilt {meta['built_human']} · {meta['n']} companies")
    print(f"\nlive at  https://{DOMAIN}/russell3000  once pushed")
    print("next:    git add -A && git commit -m 'refresh' && git push")


if __name__ == "__main__":
    main()
