const V="r3k-2026-08-25";
const SHELL=["/","/russell3000","/methodology","/manifest.webmanifest",
             "/icon-192.png","/icon-512.png","/apple-touch-icon.png"];

self.addEventListener("install",e=>{
  e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));
});

self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys()
    .then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k))))
    .then(()=>self.clients.claim()));
});

self.addEventListener("fetch",e=>{
  const r=e.request;
  if(r.method!=="GET") return;
  const u=new URL(r.url);
  if(u.origin!==location.origin) return;
  if(u.pathname.startsWith("/commentary")) return;   // too large to cache

  // Stale while revalidate: instant from cache, refreshed in the background,
  // so a rebuilt dashboard is picked up on the next open rather than never.
  e.respondWith(caches.match(r).then(hit=>{
    const net=fetch(r).then(res=>{
      if(res && res.status===200)
        caches.open(V).then(c=>c.put(r,res.clone()));
      return res;
    }).catch(()=>hit);
    return hit || net;
  }));
});
