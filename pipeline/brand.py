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
  letter-spacing:-.014em;text-decoration:none;line-height:1;color:var(--ink)}
.mast .wm i{font-style:normal;color:var(--ember)}
.mast nav{display:flex;gap:17px;font-family:var(--mono);font-size:11px;
  letter-spacing:.09em;text-transform:uppercase}
.mast nav a{color:var(--ink3);text-decoration:none;padding-bottom:2px;
  border-bottom:1px solid transparent}
.mast nav a:hover{color:var(--ink);border-bottom-color:var(--ember)}
.mast nav a[aria-current]{color:var(--ink);border-bottom-color:var(--ember)}
@media (max-width:640px){
  /* wordmark plus four nav items needs ~410px and never wrapped, which is what
     actually pushed the document past the phone's width */
  .mast{flex-wrap:wrap;gap:8px 14px;padding-bottom:10px;margin-bottom:18px}
  .mast .wm{font-size:18px}
  .mast nav{flex-wrap:wrap;gap:10px 14px;width:100%;font-size:10.5px}
}
"""


def masthead(current=""):
    """current: '', 'russell3000', 'commentary' or 'methodology'."""
    # Trailing slashes are canonical. Cloudflare 308s the bare path, and a
    # redirected navigation is the most fragile fetch on the site: Safari will
    # not accept a redirected response for a navigation, and the service worker
    # then falls into its offline path for a page that is perfectly available.
    items = [("/russell3000/", "russell3000", "Cross-section"),
             ("/commentary/",  "commentary",  "Commentary"),
             ("/learn/",       "learn",       "Case study"),
             ("/methodology/", "methodology", "Method")]
    CUR = ' aria-current="page"'
    nav = "".join(
        '<a href="%s"%s>%s</a>' % (href, CUR if key == current else "", label)
        for href, key, label in items)
    return (f'<header class="mast"><a class="wm" href="/">Bilaal<i>.</i>Raja</a>'
            f'<nav>{nav}</nav></header>')


# ---------------------------------------------------------------- live ticker
# A strip of 8-K filings by companies in the panel, straight from SEC. It stays
# hidden unless something actually matches, so a failed fetch or a quiet
# afternoon leaves no empty furniture on the page.

TICKER_CSS = """
.tkr{border-bottom:1px solid var(--rule);overflow:hidden;display:none;
  margin-bottom:22px;position:relative}
.tkr.on{display:block}
.tkr-i{font-family:var(--mono);font-size:10px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink3);padding:0 0 6px}
.tkr-i b{color:var(--ember);font-weight:500}
.tkr-i .dot{display:inline-block;width:7px;height:7px;border-radius:50%;
  background:var(--neg);margin-right:7px;
  animation:tkrblink 1.5s ease-in-out infinite}
@keyframes tkrblink{0%,100%{opacity:1}50%{opacity:.2}}
@media (prefers-reduced-motion:reduce){.tkr-i .dot{animation:none;opacity:1}}
.tkr-w{overflow:hidden;padding-bottom:10px}
.tkr-t{display:flex;gap:30px;width:max-content;
  animation:tkr 70s linear infinite}
.tkr:hover .tkr-t{animation-play-state:paused}
@keyframes tkr{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.tkr a{display:inline-flex;align-items:baseline;gap:8px;text-decoration:none;
  white-space:nowrap;font-size:13px}
.tkr a .s{font-family:var(--mono);font-weight:500;color:var(--ember)}
.tkr a .n{color:var(--ink2)}
.tkr a .t{font-family:var(--mono);font-size:11px;color:var(--ink3)}
.tkr a:hover .n{color:var(--ink)}
.tkr-l{list-style:none;margin:2px 0 11px;padding:0;display:grid;gap:1px}
.tkr-l li{display:flex;align-items:baseline;gap:9px;font-size:12.5px;
  padding:3px 0;min-width:0}
.tkr-l a{display:flex;align-items:baseline;gap:9px;text-decoration:none;
  min-width:0;width:100%}
.tkr-l .ar{font-family:var(--mono);font-size:12px;flex:0 0 auto;width:12px;
  text-align:center}
.tkr-l .ar.dn{color:var(--neg)} .tkr-l .ar.up{color:var(--pos)}
.tkr-l .ar.fl{color:var(--ink3);opacity:.55}
.tkr-l .s{font-family:var(--mono);font-weight:500;color:var(--ember);
  flex:0 0 auto;min-width:52px}
.tkr-l .n{color:var(--ink2);flex:0 1 auto;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;max-width:31ch}
.tkr-l .d{color:var(--ink);flex:1 1 auto;min-width:0}
.tkr-l .d.warn{color:var(--neg);font-weight:500}
.tkr-l .t{font-family:var(--mono);font-size:10.5px;color:var(--ink3);
  flex:0 0 auto;margin-left:auto;white-space:nowrap}
.tkr-l a:hover .n,.tkr-l a:hover .d{color:var(--ink)}
@media (max-width:640px){.tkr-l .n{display:none}}
@media (prefers-reduced-motion:reduce){
  .tkr-t{animation:none}
  .tkr-w{overflow-x:auto}
}
"""

TICKER_HTML = ('<div class="tkr" id="tkr"><div class="tkr-i">'
               '<span class="dot" aria-hidden="true"></span>'
               '<b>Live</b> &middot; 8-K filings by companies in the panel</div>'
               '<div class="tkr-w"><div class="tkr-t" id="tkrt"></div></div>'
               '<ul class="tkr-l" id="tkrl"></ul></div>')

TICKER_JS = """<script>
(function(){
  var strip=document.getElementById("tkr"), track=document.getElementById("tkrt"),
      list=document.getElementById("tkrl");
  if(!strip||!track) return;

  // SEC's own 8-K item numbers, in plain words. This is what separates a
  // routine press release from a company saying its past accounts were wrong.
  var ITEM={
    "1.01":"material agreement",      "1.02":"agreement terminated",
    "1.03":"bankruptcy",              "2.01":"acquisition or disposal",
    "2.02":"results announced",       "2.03":"new debt",
    "2.04":"debt acceleration",       "2.05":"restructuring costs",
    "2.06":"material impairment",     "3.01":"delisting notice",
    "3.02":"unregistered share sale", "3.03":"shareholder rights changed",
    "4.01":"auditor changed",         "4.02":"past accounts not reliable",
    "5.01":"change of control",       "5.02":"board or executive change",
    "5.03":"articles amended",        "5.07":"shareholder vote",
    "7.01":"Reg FD disclosure",       "8.01":"other events",
    "9.01":"exhibits"
  };
  // Ranked by how much it tells you. 9.01 rides along with almost every 8-K
  // and says nothing, so it sinks; 4.02 is the loudest thing a filer can say.
  var RANK=["4.02","1.03","3.01","2.04","4.01","2.06","5.01","2.01","2.05",
            "5.02","2.02","1.01","1.02","2.03","3.02","3.03","5.03","5.07",
            "7.01","8.01","9.01"];
  var SEVERE={"4.02":1,"1.03":1,"3.01":1,"2.04":1,"4.01":1,"2.06":1};

  // Direction, where the code itself carries one. Most 8-K items do not.
  // 2.02 "results announced" is deliberately neutral: it says a company
  // reported, not whether the numbers were good, and guessing would be
  // inventing a signal the filing does not contain.
  var DIR={
    "4.02":-1,  // past accounts not reliable
    "1.03":-1,  // bankruptcy
    "3.01":-1,  // delisting notice
    "2.04":-1,  // debt acceleration
    "4.01":-1,  // auditor changed, often a resignation
    "2.06":-1,  // material impairment, writing assets down
    "2.05":-1,  // exit and disposal costs
    "3.02":-1,  // unregistered share sale, dilution
    "5.01": 1   // change of control, usually a bid at a premium
  };
  var ARROW={"-1":"\u2193", "1":"\u2191", "0":"\u2013"};
  function describe(codes){
    if(!codes||!codes.length) return {text:"", severe:false};
    var best=null;
    for(var i=0;i<RANK.length;i++) if(codes.indexOf(RANK[i])>=0){ best=RANK[i]; break; }
    if(!best) best=codes[0];
    var extra=codes.filter(function(c){return c!==best && c!=="9.01";}).length;
    // If any listed item leans a direction, take the strongest lean present.
    var dir=0;
    for(var j=0;j<codes.length;j++){
      var v=DIR[codes[j]];
      if(v===-1){ dir=-1; break; }        // bad news dominates
      if(v===1) dir=1;
    }
    return {text:(ITEM[best]||("item "+best))+(extra?" +"+extra:""),
            severe:!!SEVERE[best], dir:dir};
  }
  function ago(iso){
    var s=(Date.now()-new Date(iso).getTime())/1000;
    if(!isFinite(s)||s<0) return "";
    if(s<3600) return Math.max(1,Math.round(s/60))+"m ago";
    if(s<86400) return Math.round(s/3600)+"h ago";
    return Math.round(s/86400)+"d ago";
  }
  Promise.all([
    fetch("/api/filings").then(function(r){return r.ok?r.json():null;}),
    fetch("/ciks.json").then(function(r){return r.ok?r.json():null;})
  ]).then(function(res){
    var feed=res[0], map=res[1];
    if(!feed||!map||!feed.items) return;
    var out=[], rows=[];
    for(var i=0;i<feed.items.length;i++){
      var f=feed.items[i], m=map[String(f.cik)];
      if(!m) continue;                       // not one of ours, skip it
      // Straight to the filing on SEC, not to our own page: if you click an
      // 8-K you want the 8-K. Only accept a URL that is actually SEC's, since
      // it arrives from a parsed feed and ends up in an href.
      var href = (typeof f.href === "string" &&
                  f.href.indexOf("https://www.sec.gov/") === 0)
                 ? f.href : ("/c/" + m[0] + "/");
      var off = href.indexOf("http") === 0;
      out.push('<a href="'+href+'"'+(off?' target="_blank" rel="noopener"':'')+'>'+
               '<span class="s">'+m[0]+'</span>'+
               '<span class="n">'+m[1]+'</span>'+
               '<span class="t">8-K &middot; '+ago(f.filed)+'</span></a>');
      var d=describe(f.items);
      rows.push({tk:m[0], name:m[1], desc:d.text||"8-K", severe:d.severe,
                 dir:d.dir, href:href, off:off, ago:ago(f.filed)});
    }
    if(!out.length) return;                  // nothing matched: leave it hidden
    if(list){
      list.innerHTML = rows.slice(0,7).map(function(r){
        var dcls = r.dir<0 ? "dn" : (r.dir>0 ? "up" : "fl");
        var dttl = r.dir<0 ? "the filing type itself is negative"
                 : (r.dir>0 ? "a bid or change of control, usually at a premium"
                            : "no direction implied by the filing type");
        return '<li><a href="'+r.href+'"'+(r.off?' target="_blank" rel="noopener"':'')+'>'+
               '<span class="ar '+dcls+'" title="'+dttl+'">'+ARROW[String(r.dir)]+'</span>'+
               '<span class="s">'+r.tk+'</span>'+
               '<span class="n">'+r.name+'</span>'+
               '<span class="d'+(r.severe?' warn':'')+'">'+r.desc+'</span>'+
               '<span class="t">'+r.ago+'</span></a></li>';
      }).join("");
    }
    // the list is laid down twice so the loop has no visible seam
    track.innerHTML=out.join("")+out.join("");
    strip.classList.add("on");
  }).catch(function(){});
})();
</script>"""


# ------------------------------------------------------------ page transitions
# Cross-document view transitions: the browser snapshots the outgoing page and
# animates to the new one, so this needs no click interception and leaves the
# back button working. Browsers without support just navigate, losing the
# animation and nothing else.
#
# Kept separate from TOKENS because the dashboard carries its own palette and
# does not include the token sheet, but still needs these rules.

TRANSITION_CSS = """
@view-transition{navigation:auto}
@keyframes vt-in-right{from{transform:translateX(100%)}to{transform:translateX(0)}}
@keyframes vt-out-left{from{transform:translateX(0)}to{transform:translateX(-28%)}}
@keyframes vt-in-left{from{transform:translateX(-28%)}to{transform:translateX(0)}}
@keyframes vt-out-right{from{transform:translateX(0)}to{transform:translateX(100%)}}
@keyframes vt-dim{from{opacity:1}to{opacity:.55}}
@keyframes vt-undim{from{opacity:.55}to{opacity:1}}
::view-transition-group(root){animation-duration:.34s;
  animation-timing-function:cubic-bezier(.32,.72,0,1)}
::view-transition-old(root),::view-transition-new(root){
  animation-duration:.34s;animation-timing-function:cubic-bezier(.32,.72,0,1)}
::view-transition-new(root){animation-name:vt-in-right}
::view-transition-old(root){animation-name:vt-out-left,vt-dim}
html[data-nav="traverse"]::view-transition-new(root){animation-name:vt-in-left,vt-undim}
html[data-nav="traverse"]::view-transition-old(root){animation-name:vt-out-right}
@media (prefers-reduced-motion:reduce){
  ::view-transition-group(root),::view-transition-old(root),
  ::view-transition-new(root){animation:none!important}
}
"""

NAV_JS = """<script>
// Tag the document with how it was reached, so a back gesture animates as a pop
// rather than another push. Guarded throughout: these APIs are recent and their
// absence must not break the page.
(function(){
  function tag(){
    try{
      var t=(window.navigation&&navigation.activation&&
             navigation.activation.navigationType)||"push";
      document.documentElement.dataset.nav=t;
    }catch(e){}
  }
  if("onpagereveal" in window) window.addEventListener("pagereveal",tag);
  if("onpageswap"   in window) window.addEventListener("pageswap",tag);
  tag();
})();
</script>"""


# ------------------------------------------------------- add to home screen
# iOS has no install prompt of its own: Safari only offers it through the share
# sheet, and nothing tells the user it is there. This says so, once, and only
# where it is actually possible.

A2HS_CSS = """
.a2hs{display:none;align-items:flex-start;gap:11px;margin:0 0 18px;padding:12px 13px;
  background:var(--raise);border:1px solid var(--rule);border-radius:9px;
  font-size:13.5px;line-height:1.45;color:var(--ink2)}
.a2hs.on{display:flex}
.a2hs svg{flex:0 0 auto;width:19px;height:19px;color:var(--ember);margin-top:1px}
.a2hs b{color:var(--ink);font-weight:600}
.a2hs .x{margin-left:auto;flex:0 0 auto;background:none;border:0;cursor:pointer;
  color:var(--ink3);font-size:17px;line-height:1;padding:2px 4px}
.a2hs .x:hover{color:var(--ink)}
.a2hs .g{display:inline-flex;vertical-align:-4px;margin:0 2px}
.a2hs .g svg{width:15px;height:15px;margin:0}
"""

# The iOS share glyph: a tray with an arrow leaving through the top.
_SHARE_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
              'aria-hidden="true"><path d="M12 15V3"/><path d="M8.5 6.5 12 3l3.5 3.5"/>'
              '<path d="M8 9H6.5A1.5 1.5 0 0 0 5 10.5v9A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 '
              '1.5-1.5v-9A1.5 1.5 0 0 0 17.5 9H16"/></svg>')

A2HS_HTML = ('<div class="a2hs" id="a2hs">' + _SHARE_SVG +
             '<div><b>Add this to your home screen.</b> Tap '
             '<span class="g">' + _SHARE_SVG + '</span> in Safari, then '
             '<b>Add to Home Screen</b>, and it opens full screen like an app.</div>'
             '<button class="x" id="a2hsX" aria-label="Dismiss">&times;</button></div>')

A2HS_JS = """<script>
(function(){
  var el=document.getElementById("a2hs");
  if(!el) return;
  var ua=navigator.userAgent;
  // iPadOS reports as a Mac, so touch points are the only reliable tell
  var iOS=/iPad|iPhone|iPod/.test(ua) ||
          (navigator.platform==="MacIntel" && navigator.maxTouchPoints>1);
  // only Safari can add to the home screen; Chrome and Firefox on iOS cannot
  var safari=/^((?!chrome|android|crios|fxios|edgios).)*safari/i.test(ua);
  var installed = window.navigator.standalone===true ||
                  (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
  var hidden=false;
  try{ hidden = localStorage.getItem("a2hs-dismissed")==="1"; }catch(e){}
  if(iOS && safari && !installed && !hidden) el.classList.add("on");
  var x=document.getElementById("a2hsX");
  if(x) x.addEventListener("click",function(){
    el.classList.remove("on");
    try{ localStorage.setItem("a2hs-dismissed","1"); }catch(e){}
  });
})();
</script>"""
