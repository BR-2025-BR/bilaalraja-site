// Tells a page that it is out of date, and offers a way out.
//
// An installed PWA on iOS can be resumed without ever performing a navigation,
// so nothing refetches and nothing checks for a new service worker. The page
// then sits on whatever data it loaded the first time, with no reload control
// anywhere in the standalone UI. That is how a refreshed panel stayed invisible
// on a phone while the server had been serving the new numbers for hours.
//
// So: compare the build this page was stamped with against the one the server
// is publishing now, on load and every time the tab or app becomes visible.
(function(){
  var el = document.querySelector('meta[name="x-build"]');
  var mine = el ? el.content : "";
  var shown = false;

  function offerReload(){
    if (shown) return;
    shown = true;
    var bar = document.createElement("div");
    bar.setAttribute("role", "status");
    bar.style.cssText =
      "position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#111;" +
      "color:#fff;font:14px/1.4 -apple-system,system-ui,sans-serif;" +
      "padding:12px 14px;display:flex;gap:12px;align-items:center;" +
      "justify-content:center;box-shadow:0 -2px 12px rgba(0,0,0,.35)";
    var msg = document.createElement("span");
    msg.textContent = "Newer data is available.";
    var btn = document.createElement("button");
    btn.textContent = "Reload";
    btn.style.cssText =
      "background:#ff9900;color:#000;border:0;border-radius:6px;padding:7px 14px;" +
      "font:600 14px -apple-system,system-ui,sans-serif;cursor:pointer";
    btn.onclick = function(){
      btn.disabled = true;
      btn.textContent = "Reloading";
      var go = function(){ location.reload(); };
      // Drop every cache first, or the service worker just serves the same page
      // back and the banner returns.
      if (window.caches) {
        caches.keys().then(function(keys){
          return Promise.all(keys.map(function(k){ return caches.delete(k); }));
        }).then(go, go);
      } else { go(); }
    };
    bar.appendChild(msg);
    bar.appendChild(btn);
    document.body.appendChild(bar);
  }

  function check(){
    if (!mine) return;
    fetch("/version.json", {cache: "no-store"})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(v){ if (v && v.build && v.build !== mine) offerReload(); })
      .catch(function(){});
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").then(function(reg){
      if (reg.update) reg.update();
      document.addEventListener("visibilitychange", function(){
        if (!document.hidden && reg.update) reg.update();
      });
    }).catch(function(){});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", check);
  } else { check(); }
  document.addEventListener("visibilitychange", function(){
    if (!document.hidden) check();
  });
})();


// ---- data-refresh indicator ------------------------------------------------
// While a pipeline rebuild is running, /status.json holds {"refreshing":true};
// this shows a small badge until it flips back to false, polling so it clears
// itself with no second deploy. Fails silent if status.json is absent.
(function(){
  var el=null, styled=false;
  function ensureStyle(){
    if(styled) return; styled=true;
    var s=document.createElement("style");
    s.textContent=
      '#nl-refresh{position:fixed;left:16px;bottom:16px;z-index:9998;display:flex;align-items:center;gap:9px;'+
      'font:500 13px/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;'+
      'padding:9px 15px;border-radius:999px;color:var(--ink,#f5f2ec);max-width:calc(100vw - 32px);'+
      'background:var(--panel,var(--raise,#1c1917));border:1px solid var(--rule,rgba(255,255,255,.15));'+
      'box-shadow:0 10px 28px -10px rgba(0,0,0,.55);opacity:0;transform:translateY(6px);'+
      'transition:opacity .3s ease,transform .3s ease;pointer-events:none}'+
      '#nl-refresh.in{opacity:1;transform:none}'+
      '#nl-refresh .sp{width:13px;height:13px;flex:0 0 auto;border-radius:50%;'+
      'border:2px solid var(--s1,#E0762F);border-top-color:transparent;animation:nlspin .8s linear infinite}'+
      '#nl-refresh b{color:var(--s1,#E0762F);font-weight:600}'+
      '@keyframes nlspin{to{transform:rotate(360deg)}}'+
      '@media(prefers-reduced-motion:reduce){#nl-refresh .sp{animation:none;border-top-color:var(--s1,#E0762F)}'+
      '#nl-refresh{transition:opacity .3s ease}}';
    document.head.appendChild(s);
  }
  function show(){
    ensureStyle();
    if(el) return;
    el=document.createElement("div"); el.id="nl-refresh"; el.setAttribute("role","status"); el.setAttribute("aria-live","polite");
    el.innerHTML='<span class="sp" aria-hidden="true"></span><span><b>Refreshing</b> the dataset… figures may change shortly</span>';
    document.body.appendChild(el); requestAnimationFrame(function(){el.classList.add("in");});
  }
  function hide(){ if(!el) return; el.classList.remove("in"); var e=el; el=null; setTimeout(function(){if(e&&e.parentNode)e.parentNode.removeChild(e);},350); }
  function poll(){
    fetch("/status.json?t="+Date.now(),{cache:"no-store"})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(j){ (j&&j.refreshing)?show():hide(); })
      .catch(function(){hide();});
  }
  if(document.body) poll(); else addEventListener("DOMContentLoaded",poll);
  setInterval(poll,45000);
})();
