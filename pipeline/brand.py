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
body{color:var(--ink);font-family:var(--serif);
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;
  font-feature-settings:"kern" 1;
  /* ambient wash: a faint bloom the frosted glass has depth to sit over */
  background:
    radial-gradient(72vw 72vw at 6% -12%, color-mix(in srgb,var(--ember) 13%,transparent), transparent 60%),
    radial-gradient(62vw 62vw at 102% 6%, color-mix(in srgb,var(--pos) 11%,transparent), transparent 60%),
    radial-gradient(58vw 58vw at 50% 116%, color-mix(in srgb,var(--ink3) 12%,transparent), transparent 62%),
    var(--paper);
  background-attachment:fixed}
/* keep the data crisp; reading text takes the serif */
.num,.mono,code,kbd{font-family:var(--mono)}
a{color:inherit}
.num,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
"""

# The masthead is the one repeated element across every page type, so it is the
# thing that makes the site feel like one site rather than four.
MASTHEAD_CSS = """
/* Liquid-glass tokens, bundled with the masthead so every page that shows it
   resolves them regardless of its own palette block. */
:root{--glass:rgba(251,250,247,.72);--glass-brd:rgba(20,17,14,.13);
  --glass-gloss:rgba(255,255,255,.60);--glass-glare:rgba(180,83,30,.16)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --glass:rgba(18,16,14,.58);--glass-brd:rgba(245,242,236,.14);
  --glass-gloss:rgba(255,255,255,.08);--glass-glare:rgba(224,118,47,.20)}}
:root[data-theme="dark"]{--glass:rgba(18,16,14,.58);--glass-brd:rgba(245,242,236,.14);
  --glass-gloss:rgba(255,255,255,.08);--glass-glare:rgba(224,118,47,.20)}
.mast{position:relative;isolation:isolate;display:flex;align-items:center;
  justify-content:space-between;gap:16px;padding:10px 16px;margin-bottom:26px;
  border-radius:14px;border:1px solid var(--glass-brd);background:var(--glass);
  -webkit-backdrop-filter:blur(16px) saturate(180%);backdrop-filter:blur(16px) saturate(180%);
  box-shadow:0 1px 0 var(--glass-gloss) inset,0 8px 26px -14px rgba(0,0,0,.40)}
.mast::before{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;
  border-radius:inherit;background:linear-gradient(135deg,var(--glass-gloss) 0%,transparent 46%)}
@media (min-width:641px){.mast{position:sticky;top:8px;z-index:50}}
/* Chromium-only refraction: default stays plain glass; the .lg-refract class is
   added by feature-detection (see REFRACT_DEFS) only where SVG filters work in
   backdrop-filter. Safari / iOS / Firefox never get the class, so they keep the
   blur and nothing breaks. */
.lg-refract .mast{-webkit-backdrop-filter:url(#lg-refract) blur(3px) saturate(160%);
  backdrop-filter:url(#lg-refract) blur(3px) saturate(160%)}
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


# The refraction filter + a conservative feature-detect, shipped with the
# masthead so it lands on every page that shows glass. The displacement map is
# an edge-neutral R/G gradient (flat centre, ramps near the borders) so the
# backdrop bends like a lens only at the panel's edges. scale is tunable.
REFRACT_DEFS = (
  '<svg width="0" height="0" aria-hidden="true" style="position:absolute">'
  '<filter id="lg-refract" x="-20%" y="-20%" width="140%" height="140%" '
  'color-interpolation-filters="sRGB">'
  '<feImage preserveAspectRatio="none" result="map" href="data:image/svg+xml,'
  "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='120'><defs>"
  "<linearGradient id='r' x1='0' y1='0' x2='1' y2='0'>"
  "<stop offset='0%25' stop-color='%23ff0000'/><stop offset='33%25' stop-color='%23800000'/>"
  "<stop offset='67%25' stop-color='%23800000'/><stop offset='100%25' stop-color='%23000000'/>"
  "</linearGradient><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
  "<stop offset='0%25' stop-color='%2300ff00'/><stop offset='33%25' stop-color='%23008000'/>"
  "<stop offset='67%25' stop-color='%23008000'/><stop offset='100%25' stop-color='%23000000'/>"
  "</linearGradient></defs><rect width='100%25' height='100%25' fill='%23000000'/>"
  "<rect width='100%25' height='100%25' fill='url(%23r)'/>"
  "<rect width='100%25' height='100%25' fill='url(%23g)' style='mix-blend-mode:screen'/></svg>"
  '"/><feDisplacementMap in="SourceGraphic" in2="map" scale="26" '
  'xChannelSelector="R" yChannelSelector="G"/></filter></svg>'
  '<script>(function(){try{var u=navigator.userAgent;'
  'var ios=/iPhone|iPad|iPod|CriOS|FxiOS|EdgiOS/i.test(u);'
  'var cr=/Chrome|Chromium|Edg\\//.test(u)&&!ios;'
  'if(cr)document.documentElement.classList.add("lg-refract");}catch(e){}})();</script>'
)


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
    return (REFRACT_DEFS
            + f'<header class="mast"><a class="wm" href="/">Bilaal<i>.</i>Raja</a>'
            f'<nav>{nav}</nav></header>')


# ---------------------------------------------------------------- live ticker
# A strip of 8-K filings by companies in the panel, straight from SEC. It stays
# hidden unless something actually matches, so a failed fetch or a quiet
# afternoon leaves no empty furniture on the page.

TICKER_CSS = """
.tkr{overflow:hidden;display:none;margin-bottom:22px;position:relative;
  border:1px solid var(--glass-brd);border-radius:12px;padding:10px 14px 4px;background:var(--glass);
  -webkit-backdrop-filter:blur(10px) saturate(160%);backdrop-filter:blur(10px) saturate(160%);
  box-shadow:0 1px 0 var(--glass-gloss) inset}
.lg-refract .tkr{-webkit-backdrop-filter:url(#lg-refract) blur(3px) saturate(150%);
  backdrop-filter:url(#lg-refract) blur(3px) saturate(150%)}
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

// ---- first-visit disclaimer --------------------------------------------
// Lives here rather than on one page because a disclaimer a direct link can
// skip is not a disclaimer: every generator includes NAV_JS, so every page type
// is covered. Bump KEY to ask again after changing the wording.
(function(){
  var KEY="brDisclaimer.v1";
  try{ if(localStorage.getItem(KEY)==="agreed") return; }catch(e){ return; }

  var css=document.createElement("style");
  css.textContent=
    ".dscrim{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;"+
    "justify-content:center;padding:20px;background:rgba(10,8,6,.62);"+
    "-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}"+
    ".dsc{background:var(--glass,var(--paper,#fff));color:var(--ink,#111);"+
    "border:1px solid var(--glass-brd,var(--rule,#ddd));"+
    "-webkit-backdrop-filter:blur(20px) saturate(180%);backdrop-filter:blur(20px) saturate(180%);"+
    "border-radius:16px;max-width:520px;width:100%;max-height:88vh;overflow:auto;"+
    "padding:24px 26px;box-shadow:0 1px 0 var(--glass-gloss) inset,0 18px 60px rgba(0,0,0,.4)}"+
    ".dsc h2{font-family:var(--serif);font-size:23px;line-height:1.2;margin-bottom:10px;"+
    "font-weight:600;text-wrap:balance}"+
    ".dsc p{color:var(--ink2,#444);font-size:14px;line-height:1.6;margin-bottom:12px}"+
    ".dsc ul{list-style:none;margin:0 0 4px;display:flex;flex-direction:column;gap:9px}"+
    ".dsc li{color:var(--ink2,#444);font-size:13.5px;line-height:1.55;padding-left:15px;"+
    "position:relative}"+
    ".dsc li:before{content:'';position:absolute;left:0;top:8px;width:5px;height:5px;"+
    "border-radius:50%;background:var(--ember,var(--s1,#b4531e))}"+
    ".dsc li b{color:var(--ink,#111);font-weight:600}"+
    // the host pages style `label` as an uppercase, letter-spaced form caption;
    // inherited here it reads as shouting, so the dialog states its own type
    ".dsc,.dsc *{text-transform:none;letter-spacing:normal;font-family:var(--sans)}"+
    ".dsc h2{font-family:var(--serif)}"+
    ".dsc .agree{display:flex;align-items:flex-start;gap:10px;margin:18px 0 16px;"+
    "padding-top:15px;border-top:1px solid var(--rule,#ddd);cursor:pointer;font-size:14px;"+
    "color:var(--ink,#111);font-weight:500}"+
    ".dsc .agree input{flex:0 0 auto;width:17px;height:17px;margin-top:1px;"+
    "accent-color:var(--ember,var(--s1,#b4531e));cursor:pointer}"+
    ".dsc button{width:100%;padding:11px 16px;border-radius:9px;"+
    "border:1px solid var(--ember,var(--s1,#b4531e));background:var(--ember,var(--s1,#b4531e));color:#fff;font:inherit;"+
    "font-size:14.5px;font-weight:600;cursor:pointer}"+
    ".dsc button:disabled{opacity:.42;cursor:not-allowed}"+
    ".dsc button:not(:disabled):hover{background:var(--ember2,var(--s1,#8f3f14));border-color:var(--ember2,var(--s1,#8f3f14))}"+
    ".dsc :focus-visible{outline:2px solid var(--ember,var(--s1,#b4531e));outline-offset:2px}"+
    "@media (prefers-reduced-motion:no-preference){.dsc{animation:dscin .22s ease-out}}"+
    "@keyframes dscin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}";
  document.head.appendChild(css);

  var w=document.createElement("div");
  w.className="dscrim";
  w.innerHTML=
    '<div class="dsc" role="dialog" aria-modal="true" aria-labelledby="dsch">'+
    '<h2 id="dsch">Before you look around</h2>'+
    '<p>This is a personal research project, not a financial service, and not the '+
    'work of any firm.</p><ul>'+
    '<li>Every figure is rebuilt from SEC filings by my own code. It is a '+
    '<b>reconstruction</b> of the Russell 3000, not the licensed index, and it '+
    'will contain mistakes.</li>'+
    '<li>Backtested returns are <b>hypothetical</b>. The method was designed while '+
    'looking at the same data it is tested on, so it is not evidence of what it '+
    'would do next.</li>'+
    '<li>Nothing here is <b>investment advice</b> or a recommendation to buy or '+
    'sell anything.</li>'+
    '<li>No warranty of accuracy or completeness. Check anything that matters '+
    'against the filings themselves.</li></ul>'+
    '<label class="agree"><input type="checkbox" id="dscok">'+
    '<span>I understand this is research, not advice.</span></label>'+
    '<button type="button" id="dscgo" disabled>Continue</button></div>';
  document.body.appendChild(w);

  var prev=document.body.style.overflow;
  document.body.style.overflow="hidden";
  var box=w.querySelector(".dsc"),
      ok=w.querySelector("#dscok"),
      go=w.querySelector("#dscgo");
  ok.addEventListener("change",function(){ go.disabled=!ok.checked; });
  go.addEventListener("click",function(){
    if(!ok.checked) return;
    try{ localStorage.setItem(KEY,"agreed"); }catch(e){}
    w.remove(); css.remove(); document.body.style.overflow=prev;
  });
  // keep focus inside: the point is that it cannot be tabbed past
  w.addEventListener("keydown",function(e){
    if(e.key!=="Tab") return;
    var f=box.querySelectorAll("input,button"), a=f[0], z=f[f.length-1];
    if(e.shiftKey && document.activeElement===a){ e.preventDefault(); z.focus(); }
    else if(!e.shiftKey && document.activeElement===z){ e.preventDefault(); a.focus(); }
  });
  ok.focus();
})();
</script>"""


# ------------------------------------------------------- add to home screen
# iOS has no install prompt of its own: Safari only offers it through the share
# sheet, and nothing tells the user it is there. This says so, once, and only
# where it is actually possible.

A2HS_CSS = """
.a2hs{display:none;align-items:flex-start;gap:11px;margin:0 0 18px;padding:12px 14px;
  background:var(--glass);border:1px solid var(--glass-brd);border-radius:12px;
  -webkit-backdrop-filter:blur(10px) saturate(160%);backdrop-filter:blur(10px) saturate(160%);
  box-shadow:0 1px 0 var(--glass-gloss) inset;
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

# Phone layout. Two things the desktop rules do not cover.
#
# The notch. Without viewport-fit=cover Safari letterboxes the page away from
# it, which on a dark site leaves visible bars down one side in landscape. With
# it the background reaches the edges, and the content has to be padded clear of
# the sensor housing by hand -- hence the env() insets. The @supports guard is
# there because a browser that does not know env() would otherwise drop the whole
# declaration.
#
# Landscape height. Portrait on an iPhone gives ~844px of height and landscape
# gives ~390px, so in landscape the scarce resource is vertical space, not width.
# Padding tuned for a desktop column spends a quarter of a landscape screen
# before any content appears, and a 25-row table scrolls its own header off the
# top almost immediately -- so the header sticks.
RESPONSIVE_CSS = """
@supports (padding: max(0px)) {
  /* viewport-fit=cover hands the page the whole screen, including the parts
     hardware sits in front of. Left and right matter in landscape, where the
     sensor housing is on one side. Top matters in portrait -- that is where the
     Dynamic Island is, and without this the masthead runs underneath it. Bottom
     clears the home indicator. max() so a device with no inset still gets the
     site's own spacing rather than zero. */
  body { padding-left:  env(safe-area-inset-left);
         padding-right: env(safe-area-inset-right);
         padding-top:   env(safe-area-inset-top);
         padding-bottom: env(safe-area-inset-bottom); }
  /* The splash deliberately does NOT inset: it is position:fixed inset:0 and
     should reach the edges, behind the Island, the way a launch screen does. */
}
/* iOS zooms the page whenever a focused input is under 16px, and every control
   on the screen panel is 12.5-13.5px -- so tapping a threshold box zoomed the
   layout and left you pinching back out. 16px only on phones; the desktop sizes
   are unaffected. */
@media (max-width: 640px) {
  /* !important is warranted here and nowhere else in this file. The screen
     panel styles its number boxes with a more specific selector, so an
     unqualified `input` rule loses on specificity no matter where it sits in
     the cascade -- and what is being overridden is not a design choice but an
     iOS behaviour that makes the control unusable. */
  input, select, textarea { font-size: 16px !important; }
}
/* Safari inflates text when a phone rotates to landscape, which would undo the
   type scale set for that orientation below. */
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
/* No grey flash on tap, and no double-tap-zoom delay on things you press. */
a, button, input, select, summary, [role="button"] {
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}
/* The tables scroll inside themselves now that they are height-capped, so stop
   a flick at the end of one rubber-banding the page behind it. */
.scroll { overscroll-behavior: contain; }
@media (orientation: landscape) and (max-height: 520px) {
  .wrap { padding-top: 20px; padding-bottom: 34px; }
  h1 { font-size: 1.62rem; line-height: 1.14; }
  h2 { margin-top: 26px; }
  .lede { font-size: 15px; }
  .chart { height: 172px; }
  .ctl { padding: 9px 12px; }
  .kv { gap: 14px; }
}
@media (max-height: 560px) {
  .scroll { max-height: 74vh; overflow-y: auto; }
  .scroll thead th { position: sticky; top: 0; z-index: 2;
                     background: var(--paper, var(--bg, #12100E)); }
}
"""

# Splash screen: the app icon drawing itself.
#
# The icon is a scatter plot -- axes, eight orange points, four grey. Every
# coordinate below was read off icon-512.png rather than eyeballed, so the last
# frame of the animation is the icon exactly: axes at x=85 (y 71-428) and y=425
# (x 83-440) in #333333 at 6px, orange #FF9900 at r=21, grey #474747 at r=15.
#
# It animates the thing the site actually does: the axes draw from the origin,
# then the points land left to right, which is a cross-section being plotted.
#
# Shown only in standalone mode. A splash on an ordinary web visit is an
# obstacle, not a welcome, and @media (display-mode: standalone) settles it in
# CSS so there is no flash of it on a normal page load while JS decides.
SPLASH_CSS = """
#splash { display: none; }
@media (display-mode: standalone) {
  #splash { display: grid; place-items: center; position: fixed; inset: 0;
             z-index: 10000; background: #000; pointer-events: none;
             /* the disclaimer modal is also 9999 and is appended at runtime,
                so on a tie it would draw over the splash */
             animation: splashOut .45s ease 1.5s forwards; }
  /* Ambient wash fades UP from the black launch frame. The native launch image
     (axes on black) is therefore still frame 0 -- the glass materialises after
     the handoff, so the seam holds without regenerating the launch images. */
  #splash::before { content: ""; position: absolute; inset: 0; opacity: 0;
    background:
      radial-gradient(60vmax 60vmax at 12% -6%, rgba(224,118,47,.22), transparent 60%),
      radial-gradient(52vmax 52vmax at 100% 20%, rgba(111,178,206,.16), transparent 60%),
      radial-gradient(48vmax 48vmax at 55% 112%, rgba(95,190,140,.13), transparent 62%);
    animation: splashFade .6s ease .15s forwards; }
  #splash .stage { position: relative; display: grid; place-items: center;
    width: min(60vw, 268px); aspect-ratio: 1 / 1; }
  /* the frosted card materialises behind the logo */
  #splash .card { position: absolute; inset: 0; border-radius: 30px; opacity: 0;
    transform: scale(.94); overflow: hidden;
    background: rgba(26,23,21,.34); border: 1px solid rgba(245,242,236,.16);
    -webkit-backdrop-filter: blur(16px) saturate(165%); backdrop-filter: blur(16px) saturate(165%);
    box-shadow: 0 1px 0 rgba(255,255,255,.12) inset, 0 26px 64px -26px rgba(0,0,0,.7);
    animation: cardIn .55s cubic-bezier(.34,1.2,.64,1) .12s forwards; }
  /* real refraction wherever SVG filters work in backdrop-filter (Chromium);
     WebKit keeps the frosted blur above. */
  .lg-refract #splash .card { -webkit-backdrop-filter: url(#lg-refract) blur(3px) saturate(165%);
                               backdrop-filter: url(#lg-refract) blur(3px) saturate(165%); }
  #splash .card::before { content: ""; position: absolute; inset: 0; border-radius: inherit;
    pointer-events: none; background: linear-gradient(135deg, rgba(255,255,255,.16), transparent 46%); }
  /* a specular highlight sweeps across once, like light catching glass */
  #splash .card::after { content: ""; position: absolute; top: -20%; bottom: -20%; width: 55%;
    pointer-events: none; background: linear-gradient(100deg, transparent, rgba(255,255,255,.22), transparent);
    transform: translateX(-190%) skewX(-12deg);
    animation: splashSheen 1.05s ease .5s forwards; }
  #splash svg { position: relative; width: 64%; height: auto; }
  /* axes stay #333333 -- identical to the launch image, so frame 0 matches */
  #splash .ax { fill: none; stroke: #333333; stroke-width: 6;
                 stroke-linecap: round; stroke-linejoin: round; }
  #splash .d { transform-box: fill-box; transform-origin: center;
                transform: scale(0);
                animation: dotIn .28s cubic-bezier(.34,1.56,.64,1) forwards;
                animation-delay: calc(.42s + var(--i) * .04s); }
  #splash .o { fill: #E0762F; }
  #splash .g { fill: #8a8177; }
  @media (prefers-reduced-motion: reduce) {
    #splash::before   { animation: none; opacity: 1; }
    #splash .card     { animation: none; opacity: 1; transform: none; }
    #splash .card::after { display: none; }
    #splash .d        { animation: none; transform: scale(1); }
    #splash           { animation: splashOut .3s ease .7s forwards; }
  }
}
@keyframes dotIn      { to { transform: scale(1); } }
@keyframes splashFade { to { opacity: 1; } }
@keyframes cardIn     { to { opacity: 1; transform: scale(1); } }
@keyframes splashSheen{ to { transform: translateX(360%) skewX(-12deg); } }
@keyframes splashOut  { to { opacity: 0; visibility: hidden; } }
"""

SPLASH_HTML = """
<div id="splash" aria-hidden="true">
<div class="stage">
<div class="card"></div>
<svg viewBox="0 0 512 512" role="presentation" focusable="false">
  <path class="ax" d="M85 71 V425 H440"/>
  <circle class="d g" cx="150" cy="339" r="15" style="--i:0"/>
  <circle class="d o" cx="175" cy="378" r="21" style="--i:1"/>
  <circle class="d o" cx="195" cy="268" r="21" style="--i:2"/>
  <circle class="d o" cx="237" cy="300" r="21" style="--i:3"/>
  <circle class="d g" cx="262" cy="195" r="15" style="--i:4"/>
  <circle class="d g" cx="276" cy="351" r="15" style="--i:5"/>
  <circle class="d o" cx="299" cy="244" r="21" style="--i:6"/>
  <circle class="d o" cx="329" cy="150" r="21" style="--i:7"/>
  <circle class="d g" cx="352" cy="207" r="15" style="--i:8"/>
  <circle class="d o" cx="357" cy="300" r="21" style="--i:9"/>
  <circle class="d o" cx="385" cy="124" r="21" style="--i:10"/>
  <circle class="d o" cx="403" cy="244" r="21" style="--i:11"/>
</svg>
</div>
</div>
<script>setTimeout(function(){var s=document.getElementById("splash");if(s)s.remove();},2400);</script>
"""
