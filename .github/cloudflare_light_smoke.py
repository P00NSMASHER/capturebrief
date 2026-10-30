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
import urllib.error
import urllib.parse
import urllib.request

from cloudflare_company_live_qa import (
    BASE, EXPECTED_SHA, fetch, current_release, assert_private_not_published,
)
from cloudflare_edge_integrity import verify_public_html_bytes

SOURCES = (
    "index.html", "assets/capturebrief.js", "assets/capturebrief.css",
    "privacy.html", "terms.html", "data-handling.html",
    "pursuit-qa-v2.html", "assets/v2-report.css", "assets/v2-report.js",
    "samples/FAA-SAVES-CaptureBrief-2.0.txt",
)



class _DoNotFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify_live_sample_aliases(info: dict) -> dict:
    """Verify the exact source-pinned redirects, then inspect actual target bytes.

    Do this only after current_release has confirmed this gh-pages commit.
    Redirects are static Pages artifacts, not user-controlled browser scripts.
    """
    expected_rules = [
        "/sample /decision-evidence 301",
        "/sample.html /decision-evidence 301",
        "/decision-evidence-sample /decision-evidence 301",
        "/decision-evidence-sample.html /decision-evidence 301",
    ]
    raw = (Path("dist") / "_redirects").read_bytes()
    rules = raw.decode("utf-8").strip().splitlines()
    if rules != expected_rules:
        raise AssertionError("Company sample redirect policy differs from approved aliases")
    manifests = {item.get("path"): item for item in info.get("files", [])
                 if isinstance(item, dict)}
    if ("_redirects" not in manifests
            or hashlib.sha256(raw).hexdigest() != manifests["_redirects"].get("sha256")):
        raise AssertionError("Deployed redirect rules missing exact-source fingerprint")
    target_expected = (Path("dist") / "decision-evidence.html").read_bytes()
    target_observed, _ = fetch("decision-evidence")
    if target_observed != target_expected:
        verify_public_html_bytes(target_expected, target_observed)
    opener = urllib.request.build_opener(_DoNotFollow())
    for source in ("sample", "sample.html", "decision-evidence-sample",
                   "decision-evidence-sample.html"):
        request = urllib.request.Request(
            BASE + source,
            headers={"User-Agent": "CaptureBrief-redirect-readonly/1.0",
                     "Cache-Control": "no-cache"},
        )
        try:
            with opener.open(request, timeout=18) as response:
                status, location = response.status, response.headers.get("Location")
        except urllib.error.HTTPError as error:
            status, location = error.code, error.headers.get("Location")
        if status != 301 or not location:
            raise AssertionError("Old sample link did not return expected permanent redirect")
        actual_url = urllib.parse.urljoin(BASE, location)
        parsed = urllib.parse.urlsplit(actual_url)
        if (parsed.scheme != "https" or parsed.hostname != "capturebrief.retallyrecovery.com"
                or parsed.path != "/decision-evidence"):
            raise AssertionError("Sample alias redirects outside the approved public example")
    return {"aliases_verified": 4, "target_verified": True,
            "external_send_authorized": False, "payment_authorized": False}

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
    redirects=verify_live_sample_aliases(info)
    return {
        "status":"CAPTUREBRIEF_PRODUCTION_EXACT_COMMIT_AND_EDGE_INTEGRITY_VERIFIED",
        "commit":EXPECTED_SHA, "source_count":len(SOURCES),
        "content_modes":modes, "sample_aliases":redirects,
        "browser_interaction_in_this_job":False,
        "form_posts":0, "direct_checkout_authorized":False,
        "customer_release_authorized":False, "external_send_authorized":False,
    }


if __name__=="__main__":
    info=current_release()
    print(json.dumps(inspect_release(info),indent=2,sort_keys=True))
