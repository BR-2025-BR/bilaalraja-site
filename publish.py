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
<title>Bilaal Raja</title>
<meta name="description" content="Equity research and quantitative work built from primary SEC filings.">
<style>
:root{{--bg:#f6f6f4;--panel:#fff;--ink:#14140f;--ink2:#4a4a42;--ink3:#87867c;
 --rule:#e0dfd8;--s1:#2a78d6;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
 --bg:#131312;--panel:#1c1c1a;--ink:#f4f3ee;--ink2:#c0bfb6;--ink3:#8b8a80;
 --rule:#2e2e2a;--s1:#3987e5;}}}}
:root[data-theme="dark"]{{--bg:#131312;--panel:#1c1c1a;--ink:#f4f3ee;--ink2:#c0bfb6;
 --ink3:#8b8a80;--rule:#2e2e2a;--s1:#3987e5;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
 line-height:1.55;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:760px;margin:0 auto;padding:64px 22px 80px}}
h1{{font-size:26px;letter-spacing:-.01em;margin-bottom:4px}}
.sub{{color:var(--ink3);font-family:var(--mono);font-size:12.5px;margin-bottom:30px}}
.lede{{color:var(--ink2);margin-bottom:34px;max-width:60ch}}
.card{{display:block;text-decoration:none;color:inherit;background:var(--panel);
 border:1px solid var(--rule);border-left:3px solid var(--s1);border-radius:3px;
 padding:17px 19px;margin-bottom:12px}}
.card:hover{{border-left-color:var(--ink)}}
.card h2{{font-size:16.5px;margin-bottom:4px}}
.card p{{color:var(--ink2);font-size:14px}}
.card .m{{font-family:var(--mono);font-size:11.5px;color:var(--ink3);margin-top:8px}}
footer{{margin-top:40px;padding-top:18px;border-top:1px solid var(--rule);
 font-family:var(--mono);font-size:12px;color:var(--ink3)}}
footer a{{color:var(--s1)}}
</style></head><body><div class="wrap">
<h1>Bilaal Raja</h1>
<div class="sub">Equity research &middot; quantitative analysis &middot; Liverpool</div>
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
Built from SEC XBRL company facts and market prices. SEC filing data is public
domain; the analysis is my own.<br>
<a href="https://linkedin.com/in/bilaalraja">linkedin.com/in/bilaalraja</a>
</footer>
</div></body></html>
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
        d = SITE / path
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(html)
        mb = len(html) / 1e6
        total += mb
        print(f"  /{path:<14} {mb:6.2f} MB   {n} artifact link(s) localised")

    if not meta:
        sys.exit("could not read META from the dashboard — landing page not written")
    pretty = dict(meta, n=f"{meta['n']:,}")
    (SITE / "index.html").write_text(LANDING.format(**pretty))
    print(f"  /              {len(LANDING)/1e3:6.2f} KB   landing page")

    # CNAME: GitHub Pages custom domain.  _headers: Netlify/Cloudflare.
    # .nojekyll: stops Pages trying to process the files as a Jekyll site.
    (SITE / "CNAME").write_text(DOMAIN + "\n")
    (SITE / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n")
    (SITE / ".nojekyll").write_text("")

    print(f"\nstaged {total:.2f} MB in {SITE}")
    print(f"data through {meta['latest_filing']} · rebuilt {meta['built_human']}"
          f" · {meta['n']} companies")
    print(f"\nlive at  https://{DOMAIN}/russell3000  once pushed")
    print("next:    git add -A && git commit -m 'refresh' && git push")


if __name__ == "__main__":
    main()
