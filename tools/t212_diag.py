#!/usr/bin/env python3
"""Sanity-check the Trading 212 endpoint before blaming a key.

A 401 only means "rejected" if we can show the service distinguishes cases:
that a nonsense path 404s (routing works), and that a deliberately fake key
also 401s (the header is read and judged). Without those, a 401 might just be
what the host says to everything.
"""
import json, urllib.request, urllib.error

HOST = "https://demo.trading212.com"
CASES = [
    ("real path, no auth header", "/api/v0/equity/account/cash", None),
    ("real path, obvious fake key", "/api/v0/equity/account/cash", "0000fake0000"),
    ("nonsense path, no auth", "/api/v0/equity/not-a-real-endpoint", None),
    ("root", "/", None),
]

for label, path, key in CASES:
    headers = {"Authorization": key} if key else {}
    req = urllib.request.Request(HOST + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(120)
            print(f"  {label:28} HTTP {r.status}  {body[:60]!r}")
    except urllib.error.HTTPError as e:
        body = e.read(120)
        print(f"  {label:28} HTTP {e.code}  {body[:60]!r}")
    except Exception as e:
        print(f"  {label:28} ERROR {e}")
