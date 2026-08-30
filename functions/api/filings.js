// Live 8-K feed, proxied.
//
// SEC sends no CORS headers, so a browser cannot read its Atom feed directly.
// This runs at the edge instead: it fetches, keeps only 8-K entries, and hands
// back JSON the page can use. 8-K is the filing a company makes when something
// has actually happened, which is why it is the only form worth a ticker.
//
// The response is cached for two minutes at the edge. SEC's fair access policy
// asks for a real User-Agent and reasonable volume, and a site polling once per
// visitor per minute would be neither.

const FEED = "https://www.sec.gov/cgi-bin/browse-edgar" +
  "?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=60&output=atom";

const UA = "bilaalraja.com filings ticker (bilaal.raja4567@gmail.com)";

function tag(block, name) {
  const m = block.match(new RegExp("<" + name + "[^>]*>([\\s\\S]*?)</" + name + ">"));
  return m ? m[1].trim() : "";
}

export async function onRequest() {
  const headers = {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "public, max-age=120",
    "access-control-allow-origin": "*",
  };

  let res;
  try {
    res = await fetch(FEED, {
      headers: { "User-Agent": UA, "Accept": "application/atom+xml" },
      cf: { cacheTtl: 120, cacheEverything: true },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: "fetch failed", items: [] }),
                        { status: 502, headers });
  }
  if (!res.ok) {
    return new Response(JSON.stringify({ error: "sec " + res.status, items: [] }),
                        { status: 502, headers });
  }

  const xml = await res.text();
  const items = [];
  const entries = xml.match(/<entry>[\s\S]*?<\/entry>/g) || [];

  for (const e of entries) {
    const title = tag(e, "title");
    // "8-K - COMPANY NAME (0001234567) (Filer)" - the CIK sits in brackets
    const cik = (title.match(/\((\d{7,10})\)/) || [])[1];
    const form = title.split(" - ")[0].trim();
    if (!cik || form !== "8-K") continue;
    const href = (e.match(/<link[^>]*href="([^"]+)"/) || [])[1] || "";
    items.push({
      cik: Number(cik),
      form,
      filed: tag(e, "updated"),
      href: href.startsWith("http") ? href : "https://www.sec.gov" + href,
    });
  }

  return new Response(JSON.stringify({
    fetched: new Date().toISOString(),
    count: items.length,
    items,
  }), { headers });
}
