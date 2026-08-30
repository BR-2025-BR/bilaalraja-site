#!/usr/bin/env python3
"""One definition of the site's identity, imported everywhere that renders a page.

The landing page, methodology, company pages and dashboard each carried their
own copy of the palette. That is how they drift: a colour changes in one place
and the site quietly stops matching itself. They all read from here now.

The palette is ink on paper rather than black on white. Pure #000 on #fff is
what you get when nobody chose, and the single saturated accent on near-black
is the most over-used look on the web. The neutrals here are warm-biased
towards the accent, so they read as selected rather than inherited.
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&'
         'family=IBM+Plex+Sans:wght@400;500;600&'
         'family=IBM+Plex+Mono:wght@400;500&display=swap">')

TOKENS = """
:root{
  /* paper and ink, both warm, so neither reads as a default */
  --paper:#FBFAF7; --raise:#F3F0E9; --ink:#14110E; --ink2:#4A443C; --ink3:#8A8177;
  --rule:#E3DED3; --rule2:#EFEBE2;
  /* one accent, used sparingly; semantic colours stay separate from it */
  --ember:#B4531E; --ember2:#8F3F14;
  --pos:#1F6F4A; --neg:#A32B1F;
  /* aliases: the older pages address these names, so they map onto the new
     palette rather than every rule being rewritten and risking a miss */
  --bg:#FBFAF7; --panel:#F3F0E9; --s1:#B4531E;
  --serif:"Newsreader",Georgia,"Times New Roman",serif;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#12100E; --raise:#1C1917; --ink:#F5F2EC; --ink2:#C0B8AC; --ink3:#8A8177;
  --rule:#2E2A26; --rule2:#232019;
  --ember:#E0762F; --ember2:#F0A268;
  --pos:#5FBE8C; --neg:#E8705F;
  --bg:#12100E; --panel:#1C1917; --s1:#E0762F;
}}
:root[data-theme="dark"]{
  --paper:#12100E; --raise:#1C1917; --ink:#F5F2EC; --ink2:#C0B8AC; --ink3:#8A8177;
  --rule:#2E2A26; --rule2:#232019;
  --ember:#E0762F; --ember2:#F0A268;
  --pos:#5FBE8C; --neg:#E8705F;
  --bg:#12100E; --panel:#1C1917; --s1:#E0762F;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;
  font-feature-settings:"kern" 1}
a{color:inherit}
.num,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
"""

# The masthead is the one repeated element across every page type, so it is the
# thing that makes the site feel like one site rather than four.
MASTHEAD_CSS = """
.mast{display:flex;align-items:baseline;justify-content:space-between;gap:16px;
  padding-bottom:13px;border-bottom:1.5px solid var(--ink);margin-bottom:26px}
.mast .wm{font-family:var(--serif);font-size:20px;font-weight:600;
  letter-spacing:-.014em;text-decoration:none;line-height:1}
.mast .wm i{font-style:normal;color:var(--ember)}
.mast nav{display:flex;gap:17px;font-family:var(--mono);font-size:11px;
  letter-spacing:.09em;text-transform:uppercase}
.mast nav a{color:var(--ink3);text-decoration:none;padding-bottom:2px;
  border-bottom:1px solid transparent}
.mast nav a:hover{color:var(--ink);border-bottom-color:var(--ember)}
.mast nav a[aria-current]{color:var(--ink);border-bottom-color:var(--ember)}
"""


def masthead(current=""):
    """current: '', 'russell3000', 'commentary' or 'methodology'."""
    items = [("/russell3000", "russell3000", "Cross-section"),
             ("/commentary",  "commentary",  "Commentary"),
             ("/learn",       "learn",       "Case study"),
             ("/methodology", "methodology", "Method")]
    CUR = ' aria-current="page"'
    nav = "".join(
        '<a href="%s"%s>%s</a>' % (href, CUR if key == current else "", label)
        for href, key, label in items)
    return (f'<header class="mast"><a class="wm" href="/">Bilaal<i>.</i>Raja</a>'
            f'<nav>{nav}</nav></header>')
