"""Diagnose exact Cloudflare HTML-byte drift without changing release validation.

Read-only network requests to our own public host; emits hashes and bounded
public-source difference context, never a request form or customer data.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

BASE = "https://capturebrief.retallyrecovery.com/"
FILES = ("index.html", "assets/capturebrief.js", "privacy.html", "terms.html")
EXPECTED_ROOT = Path("dist")

def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def printable(raw: bytes) -> str:
    # Do not publish arbitrary source bytes from live pages or any addresses.
    value = raw.decode("utf-8", errors="replace")
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[EMAIL]", value)
    return re.sub(r"[^\x20-\x7e]", "?", value)[:130]

def inspect(path: str) -> dict:
    url = BASE + path + "?compare=" + os.environ.get("GITHUB_SHA", "read-only")[:16]
    req = Request(url, headers={"Cache-Control": "no-cache", "Accept-Encoding": "identity",
                               "User-Agent": "CaptureBrief-readonly-fingerprint/1"})
    with urlopen(req, timeout=25) as response:
        observed = response.read(5 * 1024 * 1024 + 1)
        headers = {x.lower(): y for x, y in response.headers.items()}
        status = response.status
    expected = (EXPECTED_ROOT / path).read_bytes()
    first = next((i for i in range(min(len(expected), len(observed)))
                  if expected[i] != observed[i]), min(len(expected), len(observed)))
    # Only public file content, kept bounded. SHA-only output is not enough
    # to locate middleware rewrites.
    span_start = max(0, first - 32)
    span_end = first + 110
    signals = ("cdn-cgi/scripts", "email-decode.min.js", "data-cfemail",
               "__cf_bm", "cloudflareinsights.com", "beacon.min.js",
               "rocket-loader", "cf-email", "<!--email_off-->", "<!--/email_off-->")
    return {
        "file": path, "status": status, "expected_sha256": digest(expected),
        "served_sha256": digest(observed),
        "expected_bytes": len(expected), "served_bytes": len(observed),
        "first_byte_difference": first, "match": expected == observed,
        "expected_excerpt": printable(expected[span_start:span_end]),
        "served_excerpt": printable(observed[span_start:span_end]),
        "signals": {s:{"expected":expected.lower().count(s.encode()),
                       "served":observed.lower().count(s.encode())} for s in signals},
        "headers": {k: headers.get(k) for k in ("server","cf-cache-status","content-encoding",
                     "content-type", "content-length", "x-content-type-options")
                    if headers.get(k) is not None},
    }

def main() -> None:
    print(json.dumps({"diagnostics":[inspect(p) for p in FILES],
                      "release_gate_not_modified":True}, indent=2))

if __name__ == "__main__":
    main()
