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
.card{{display:block;text-decoration:none;color:inherit;background:var(--panel);
 border:1px solid var(--rule);border-left:3px solid var(--s1);border-radius:14px;
 padding:18px 20px;margin-bottom:12px}}
.card:hover{{border-left-color:var(--ink)}}
.card h2{{font-size:16.5px;margin-bottom:4px}}
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
<p class="lede">Work built from primary sources. The universe, the factor
construction and the validation below are my own, assembled from SEC XBRL
company facts rather than a vendor feed.</p>

<a class="card" href="/russell3000">
  <h2>Russell 3000 Cross-Section</h2>
  <p>{n} companies with computable trailing-twelve-month fundamentals, screened on
  35 metrics with sector-neutral percentile ranking and a composite score.</p>
  <div class="m">data through {latest_filing} &middot; rebuilt {built_human}</div>
</a>

<a class="card" href="/commentary">
  <h2>Results Commentary</h2>
  <p>Management's own discussion of results, extracted from 10-Q and 10-K
  filings and matched to the reported figures.</p>
  <div class="m">data through {latest_filing} &middot; rebuilt {built_human}</div>
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
   "3000, with key financial metrics computed point in time. 2,544 companies, "
   "35 metrics, sector-neutral percentile ranking."),
 "commentary": ("Russell 3000 Results Commentary | Bilaal Raja",
   "Management's own discussion of results, parsed from 10-Q and 10-K filings "
   "for thousands of US listed companies and matched to the reported figures."),
}


def inject_meta(html: str, path: str, domain: str) -> str:
    if path not in DESCRIPTIONS:
        return html
    title, desc = DESCRIPTIONS[path]
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
"""
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
        html = inject_meta(html, path, DOMAIN)
        d = SITE / path
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html)
        mb = len(html) / 1e6
        total += mb
        print(f"  /{path:<14} {mb:6.2f} MB   {n} artifact link(s) localised")

    if not meta:
        sys.exit("could not read META from the dashboard — landing page not written")
    pretty = dict(meta, n=f"{meta['n']:,}", year=meta["built"][:4])
    (SITE / "index.html").write_text(LANDING.format(**pretty))
    print(f"  /              {len(LANDING)/1e3:6.2f} KB   landing page")

    # CNAME: GitHub Pages custom domain.  _headers: Netlify/Cloudflare.
    # .nojekyll: stops Pages trying to process the files as a Jekyll site.
    (SITE / "CNAME").write_text(DOMAIN + "\n")
    (SITE / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n")
    (SITE / ".nojekyll").write_text("")
    write_sitemap(SITE, DOMAIN,
                  [("", "1.0"), ("russell3000", "0.9"), ("commentary", "0.8")],
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
    print(f"data through {meta['latest_filing']} · rebuilt {meta['built_human']}"
          f" · {meta['n']} companies")
    print(f"\nlive at  https://{DOMAIN}/russell3000  once pushed")
    print("next:    git add -A && git commit -m 'refresh' && git push")


if __name__ == "__main__":
    main()
