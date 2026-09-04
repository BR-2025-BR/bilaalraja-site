const V="r3k-2026-09-04-05c5716e8f-r2";

// Cloudflare Pages 308s /russell3000 to /russell3000/. A response that followed
// a redirect carries redirected:true, and Safari refuses to accept one of those
// for a navigation request. So: precache the canonical trailing-slash paths, and
// rebuild every response before it is cached or returned, which clears the flag.
const SHELL=["/","/russell3000/","/learn/","/methodology/","/manifest.webmanifest",
             "/icon-192.png","/icon-512.png","/apple-touch-icon.png"];

async function plain(res){
  if(!res) return res;
  const body=await res.arrayBuffer();
  return new Response(body,{status:res.status,statusText:res.statusText,
                            headers:res.headers});
}

self.addEventListener("install",e=>{
  e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys()
    .then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k))))
    .then(()=>self.clients.claim()));
});

async function navigate(req){
  try{
    const res=await fetch(req);
    const fixed=await plain(res);
    const c=await caches.open(V);
    c.put(req,fixed.clone());
    return fixed;
  }catch(err){
    // Offline. Look for this page under both spellings of its path, since the
    // shell is precached with a trailing slash and a link may omit it.
    //
    // What must not happen is falling back to "/". Returning the landing page
    // for a different URL does not read as an offline page, it reads as the
    // link being broken: following the cross-section and arriving back at the
    // front page looks like a loop, and it hides the real cause. Fail honestly
    // instead and let the browser show its own offline page.
    const u=new URL(req.url);
    const alt=u.pathname.endsWith("/") ? u.pathname.slice(0,-1) : u.pathname+"/";
    const hit=await caches.match(req)
           || await caches.match(u.pathname)
           || await caches.match(alt);
    return hit ? await plain(hit) : Response.error();
  }
}

async function asset(req){
  const hit=await caches.match(req);
  const net=fetch(req).then(async res=>{
    if(res && res.status===200){
      const fixed=await plain(res);
      const c=await caches.open(V);
      c.put(req,fixed.clone());
      return fixed;
    }
    return res;
  }).catch(()=>hit);
  return hit || net;
}

self.addEventListener("fetch",e=>{
  const r=e.request;
  if(r.method!=="GET") return;
  const u=new URL(r.url);
  if(u.origin!==location.origin) return;
  if(u.pathname.startsWith("/commentary")) return;   // 12MB, not worth caching
  // The freshness check must never be answered from this cache. asset() is
  // stale-while-revalidate, so serving version.json from here would compare a
  // stale page against a stale version file and conclude all was well.
  if(u.pathname==="/version.json"||u.pathname==="/update.js") return;
  e.respondWith(r.mode==="navigate" ? navigate(r) : asset(r));
});
