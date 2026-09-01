#!/usr/bin/env python3
"""Find the auth scheme Trading 212 wants for an API-key-ID / secret pair.

The app issues two values, so the earlier single-header attempts were malformed.
This walks the standard ways a service combines an id and a secret and reports
which one stops returning 401.

    T212_ID='...' T212_SECRET='...' python3 tools/t212_authmatrix.py
"""
import base64, os, sys, time, urllib.request, urllib.error

ID  = os.environ.get("T212_ID", "")
SEC = os.environ.get("T212_SECRET", "")
if not ID or not SEC:
    sys.exit("Set T212_ID and T212_SECRET in the environment.")

HOST = os.environ.get("T212_HOST", "https://demo.trading212.com")
PATH = "/api/v0/equity/account/cash"

b64 = base64.b64encode(f"{ID}:{SEC}".encode()).decode()

SCHEMES = [
    ("Basic base64(id:secret)",   {"Authorization": "Basic " + b64}),
    ("Authorization id:secret",   {"Authorization": f"{ID}:{SEC}"}),
    ("Bearer secret",             {"Authorization": "Bearer " + SEC}),
    ("Bearer id",                 {"Authorization": "Bearer " + ID}),
    ("split headers x-api-key",   {"X-API-Key-ID": ID, "X-API-Secret": SEC}),
    ("split headers api-key",     {"API-Key-ID": ID, "API-Secret-Key": SEC}),
    ("auth=secret, id header",    {"Authorization": SEC, "X-API-Key-ID": ID}),
    ("auth=id, secret header",    {"Authorization": ID, "X-API-Secret": SEC}),
    ("secret then id joined",     {"Authorization": SEC + ID}),
    ("id-dash-secret",            {"Authorization": f"{ID}-{SEC}"}),
]

print(f"host {HOST}\n")
hit = None
for label, headers in SCHEMES:
    req = urllib.request.Request(HOST + PATH, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(200).decode(errors="replace")
            print(f"  {label:26} HTTP {r.status}   {body[:70]}")
            if r.status == 200 and hit is None:
                hit = label
    except urllib.error.HTTPError as e:
        print(f"  {label:26} HTTP {e.code}")
        if e.code == 429:
            print("      rate limited, pausing 35s")
            time.sleep(35)
    except Exception as e:
        print(f"  {label:26} ERROR {e}")
    time.sleep(1.5)   # the API is rate limited; do not hammer it

print(f"\nworking scheme: {hit}" if hit else
      "\nNothing authenticated. If the secret was only shown once at creation "
      "and was not saved, generate a new key and capture the secret then.")
