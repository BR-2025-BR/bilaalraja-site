#!/usr/bin/env python3
"""Render the Open Graph share card to docs/og.png.

The counts used to be typed into the card by hand, so the image kept a figure
the panel had moved past. It said 2,544 companies while the panel held 2,543,
and that number is burned into pixels where nothing can catch it. They come
from the build now.

MD&A characters stay a constant: commentary.html is a static artefact that
refresh.py does not rebuild, so the figure only changes when that is
regenerated.
"""
import json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "docs"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MDA_CHARS = "11.3M"


def main():
    dash = (HERE / "r3k_dashboard.html").read_text(errors="replace")
    m = re.search(r'META\s*=\s*(\{.*?\})\s*,\s*METRICS\s*=', dash, re.S)
    if not m:
        sys.exit("make_og: could not read META from the dashboard")
    meta = json.loads(m.group(1))

    n_metrics = len(json.loads(
        re.search(r'METRICS\s*=\s*(\[.*?\])\s*,\s*SECTORS\s*=', dash, re.S).group(1)))

    # plain token substitution: the card is CSS-heavy and str.format would
    # trip over every brace in the stylesheet
    html = ((HERE / "og_card.html").read_text()
            .replace("__COMPANIES__", f"{meta['n']:,}")
            .replace("__METRICS__", str(n_metrics)))
    tmp = HERE / ".og_render.html"
    tmp.write_text(html)

    # 1200x630 is the size Open Graph consumers expect, so the published card
    # stays there. --scale renders the same layout at a higher device pixel
    # ratio for anywhere that wants it sharp: a slide, a print, a retina post.
    # Rendering at scale beats upscaling the 1x file, which only blurs it.
    scale = 1
    dest = SITE / "og.png"
    for i, a in enumerate(sys.argv):
        if a == "--scale" and i + 1 < len(sys.argv):
            scale = max(1, min(4, int(sys.argv[i + 1])))
        if a == "--out" and i + 1 < len(sys.argv):
            dest = Path(sys.argv[i + 1]).expanduser().resolve()

    out = dest
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--window-size=1200,630", "--default-background-color=000000",
                    f"--force-device-scale-factor={scale}",
                    "--virtual-time-budget=8000",
                    f"--screenshot={out}", f"file://{tmp}"],
                   capture_output=True, check=True)
    tmp.unlink()
    if scale != 1 or dest != SITE / "og.png":
        print(f"  {out}  {1200*scale}x{630*scale}")
        return
    print(f"  og.png  {meta['n']:,} companies  {n_metrics} metrics  {MDA_CHARS} MD&A chars")


if __name__ == "__main__":
    main()
