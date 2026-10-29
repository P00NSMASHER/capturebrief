"""Lightweight fail-closed production proof on EVERY gh-pages commit.

No browser runtime, network writes, customer data or API secrets. Run only
after building this exact commit's standalone dist and validating its contract.
Cloudflare's pinned HTML beacon changes may be accepted, never other changes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from cloudflare_company_live_qa import (
    BASE, EXPECTED_SHA, fetch, current_release, assert_private_not_published,
)
from cloudflare_edge_integrity import verify_public_html_bytes

SOURCES = (
    "index.html", "assets/capturebrief.js", "assets/capturebrief.css",
    "privacy.html", "terms.html", "data-handling.html",
)


def inspect_release(info: dict) -> dict:
    if info.get("sourceCommit") != EXPECTED_SHA or info.get("sourceBranch") != "gh-pages":
        raise AssertionError("Cloudflare is not serving the exact checked-out production commit")
    if (info.get("canonical") != BASE or
            info.get("sourceRepository") != "P00NSMASHER/capturebrief" or
            info.get("purchasePolicy") != "SCOPE_FIRST_PENDING_SOURCE_READINESS"):
        raise AssertionError("Cloudflare release identifies an unapproved product or payment policy")
    files = info.get("files")
    if not isinstance(files,list) or len(files)!=info.get("publicFileCount"):
        raise AssertionError("Cloudflare public-file manifest is incomplete")
    by_path = {item.get("path"): item for item in files if isinstance(item,dict)}
    if len(by_path)!=len(files):
        raise AssertionError("Cloudflare public-file manifest contains duplicate paths")
    modes={}
    for path in SOURCES:
        expected = (Path("dist")/path).read_bytes()
        if path not in by_path or hashlib.sha256(expected).hexdigest()!=by_path[path].get("sha256"):
            raise AssertionError("Cloudflare's release manifest does not match this source: "+path)
        observed, _ = fetch(path)
        if observed == expected:
            modes[path] = "EXACT_BYTES"
        elif path.endswith(".html"):
            modes[path] = verify_public_html_bytes(expected, observed)
        else:
            raise AssertionError("Executable or stylesheet drift: "+path)
        if path=="index.html":
            if (b"at most ten businesses" not in observed or
                    b"Preparing an email draft does not send an inquiry" not in observed):
                raise AssertionError("No-card trial intake or no-send boundary is missing")
    for forbidden in ("capturebrief_core/scoped_source.py","scripts/scoped_private_backup.py",
                      "abvm/game/index.html"):
        assert_private_not_published(forbidden)
    return {
        "status":"CAPTUREBRIEF_PRODUCTION_EXACT_COMMIT_AND_EDGE_INTEGRITY_VERIFIED",
        "commit":EXPECTED_SHA, "source_count":len(SOURCES),
        "content_modes":modes, "browser_interaction_in_this_job":False,
        "form_posts":0, "direct_checkout_authorized":False,
        "customer_release_authorized":False, "external_send_authorized":False,
    }


if __name__=="__main__":
    info=current_release()
    print(json.dumps(inspect_release(info),indent=2,sort_keys=True))
