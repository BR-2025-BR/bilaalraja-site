#!/usr/bin/env python3
"""Local Trading 212 dashboard: a caching proxy plus the page that reads it.

The credentials stay in this process. They are never sent to the browser, so
the page holds nothing worth stealing and nothing that survives a screenshot.
That is also the only arrangement that works: Trading 212 sends no CORS headers,
so a page calling the API directly is blocked by the browser regardless.

Trading 212 rate limits hard — measured at roughly one request per five seconds
per endpoint, returning 429 for anything faster. The browser therefore polls
this server freely and this server polls Trading 212 on a leash: every endpoint
has a minimum interval, responses are cached, and concurrent requests for the
same path collapse into one upstream call.

    T212_ID='...' T212_SECRET='...' python3 tools/t212_server.py

Then open http://127.0.0.1:8212 . Ctrl-C to stop.
"""
import base64, hmac, json, os, secrets, socket, sys, threading, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ID  = os.environ.get("T212_ID", "")
SEC = os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET in the environment.\n"
             "  T212_ID='...' T212_SECRET='...' python3 tools/t212_server.py")

HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
LIVE = "demo" not in HOST
PORT = int(os.environ.get("T212_PORT", "8212"))
AUTH = "Basic " + base64.b64encode(f"{ID}:{SEC}".encode()).decode()
HERE = Path(__file__).resolve().parent

# Placing orders is refused unless the operator opts in for this run. The demo
# account is play money, but the same code against a live key is not.
ALLOW_ORDERS = "--allow-orders" in sys.argv

# path -> minimum seconds between upstream calls. Anything not listed is not
# proxied at all: an allowlist, so a typo in the page cannot reach a live
# endpoint nobody intended to expose.
READ = {
    "/api/v0/equity/account/cash":        6,
    "/api/v0/equity/account/info":       120,
    "/api/v0/equity/portfolio":            6,
    "/api/v0/equity/orders":               6,
    "/api/v0/equity/history/orders":      30,
    "/api/v0/equity/history/dividends":  120,
    "/api/v0/equity/metadata/instruments": 3600,
    "/api/v0/equity/metadata/exchanges":  3600,
}
WRITE = {
    "/api/v0/equity/orders/market": 2,
    "/api/v0/equity/orders/limit":  2,
}
# Cancelling is a DELETE on /orders/{id}. Matched by prefix rather than exact
# path, and still gated behind --allow-orders: pulling a working order is a
# trading decision like any other.
CANCEL_PREFIX = "/api/v0/equity/orders/"

_cache = {}                      # path -> (fetched_at, status, body)
_locks = {}                      # path -> Lock, so duplicate polls collapse
_guard = threading.Lock()


def _lock_for(key):
    with _guard:
        return _locks.setdefault(key, threading.Lock())


def upstream(path, query="", payload=None, method="GET"):
    url = HOST + path + (("?" + query) if query else "")
    data = json.dumps(payload).encode() if payload is not None else None
    hdr = {"Authorization": AUTH}
    if data:
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read()
            return r.status, (raw or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read(600) or b'""'
    except Exception as e:
        return 599, json.dumps({"error": str(e)[:200]}).encode()


def cached_get(path, query):
    """One upstream call per interval per path, shared by every caller."""
    ttl = READ[path]
    key = path + "?" + query
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1], hit[2], True

    with _lock_for(key):
        hit = _cache.get(key)                      # recheck: someone may have
        now = time.time()                          # refreshed while we waited
        if hit and now - hit[0] < ttl:
            return hit[1], hit[2], True
        status, body = upstream(path, query)
        if status == 429 and hit:
            # Rate limited with something stale in hand: serve the stale copy
            # rather than blanking a panel the user is looking at.
            return hit[1], hit[2], True
        if status == 200:
            _cache[key] = (time.time(), status, body)
        return status, body, False


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # This server is for one machine. Refuse to be embedded anywhere.
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass                                        # the page polls; stay quiet

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            page = (HERE / "t212_dashboard.html").read_bytes()
            return self._send(200, page, "text/html; charset=utf-8")
        if u.path == "/api/meta":
            return self._send(200, json.dumps({
                "host": HOST, "live": LIVE, "orders_enabled": ALLOW_ORDERS,
                "server_time": time.time()}).encode())
        if u.path in READ:
            status, body, cached = cached_get(u.path, u.query)
            return self._send(status, body, extra={"X-Cache": "hit" if cached else "miss"})
        return self._send(404, b'{"error":"not proxied"}')

    def do_DELETE(self):
        u = urlparse(self.path)
        oid = u.path[len(CANCEL_PREFIX):] if u.path.startswith(CANCEL_PREFIX) else ""
        if not oid.isdigit():
            return self._send(404, b'{"error":"not proxied"}')
        if not ALLOW_ORDERS:
            return self._send(403, json.dumps({
                "error": "Order cancellation is disabled. Restart with "
                         "--allow-orders to enable it."}).encode())
        status, body = upstream(u.path, method="DELETE")
        self._bust()
        return self._send(status, body)

    def _bust(self):
        """Expire cached account state after a write, without discarding it.

        Deleting the entry outright leaves nothing to fall back on: a write is
        immediately followed by a read, that read is the most likely moment to
        meet the rate limit, and the panel would blank just as the user wants to
        see what their order did. Marking it stale forces a refetch while
        keeping the old copy as a fallback for the 429 path.
        """
        for k in ("/api/v0/equity/portfolio", "/api/v0/equity/orders",
                  "/api/v0/equity/account/cash"):
            for ck, v in list(_cache.items()):
                if ck.startswith(k):
                    _cache[ck] = (0.0, v[1], v[2])

    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in WRITE:
            return self._send(404, b'{"error":"not proxied"}')
        if not ALLOW_ORDERS:
            return self._send(403, json.dumps({
                "error": "Order placement is disabled. Restart the server with "
                         "--allow-orders to enable it."}).encode())
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, b'{"error":"bad JSON"}')

        if not isinstance(payload.get("ticker"), str):
            return self._send(400, b'{"error":"ticker required"}')
        try:
            qty = float(payload.get("quantity"))
        except (TypeError, ValueError):
            return self._send(400, b'{"error":"numeric quantity required"}')
        if qty == 0:
            return self._send(400, b'{"error":"quantity must be non-zero"}')
        # The API rejects finer precision anyway; round here so the page cannot
        # produce a confusing 400 from a float artefact.
        payload["quantity"] = round(qty, 2)

        status, body = upstream(u.path, payload=payload, method="POST")
        self._bust()
        return self._send(status, body)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"  Trading 212 dashboard   http://127.0.0.1:{PORT}")
    print(f"  account   {'LIVE — real money' if LIVE else 'demo'}  ({HOST})")
    print(f"  orders    {'ENABLED' if ALLOW_ORDERS else 'read-only (--allow-orders to enable)'}")
    print("  bound to 127.0.0.1, so nothing outside this machine can reach it")
    if LIVE and ALLOW_ORDERS:
        print("\n  !! live account with order placement enabled !!\n")
    print("  Ctrl-C to stop\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
