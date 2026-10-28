"""Read-only acceptance for CaptureBrief's actual Cloudflare production website.

Runs only on gh-pages pushes after a GitHub PR merge. All buyer inputs are
fictional and never sent, persisted, mailed, enrolled or billed. The clipboard
API is intercepted in-page before clicking the no-send Copy request action.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://capturebrief.retallyrecovery.com/"
HOST = "capturebrief.retallyrecovery.com"
EXPECTED_SHA = os.environ["GITHUB_SHA"]
BROWSER = os.environ.get("QA_BROWSER", "chromium")
NOTICE = "c20a138049b94add92f0f32a41856585"


def fetch(path: str, *, maximum: int = 5 * 1024 * 1024) -> tuple[bytes, dict]:
    url = BASE + path + ("&" if "?" in path else "?") + "source_check=" + EXPECTED_SHA[:16]
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CaptureBrief-release-readonly/1.0",
                 "Cache-Control": "no-cache", "Accept-Encoding": "identity"},
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        if response.status != 200 or urllib.parse.urlsplit(response.geturl()).hostname != HOST:
            raise AssertionError("Production URL was redirected or unavailable")
        payload = response.read(maximum + 1)
        if len(payload) > maximum:
            raise AssertionError("Production asset exceeded inspection bound")
        return payload, dict(response.headers.items())


def current_release():
    last_error = "unavailable"
    for attempt in range(19):
        try:
            data, _ = fetch("build-info.json", maximum=512 * 1024)
            info = json.loads(data)
            if info.get("sourceCommit") == EXPECTED_SHA:
                return info
            last_error = "stale source revision, not an exact-commit production release"
        except (ValueError, KeyError, urllib.error.URLError, AssertionError) as exc:
            last_error = type(exc).__name__
        if attempt < 18:
            time.sleep(8)
    raise AssertionError("Cloudflare production exact-commit verification failed: " + last_error)


def assert_private_not_published(path: str) -> None:
    try:
        fetch(path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return
        raise AssertionError("Unexpected response for private path") from None
    raise AssertionError("A private or unrelated repository path is publicly served")


def verify_browser() -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser_type = getattr(playwright, BROWSER)
        browser = browser_type.launch(headless=True)
        page = browser.new_page()
        posts: list[str] = []
        page.on("request", lambda request: posts.append(request.url) if request.method == "POST" else None)
        try:
            response = page.goto(BASE + "?release_probe=" + EXPECTED_SHA[:16],
                                 wait_until="domcontentloaded", timeout=30000)
            assert response is not None and response.status == 200
            page.locator('a[data-request-type="FREE_CHECK"]').first.click()
            assert page.locator("#purchase-status").input_value() == "FREE_CHECK"
            page.evaluate("""() => {
                Object.defineProperty(navigator, 'clipboard', {
                    configurable: true,
                    value: {writeText: async text => {window.__qaDraft = text;}}
                });
            }""")
            page.locator("#company").fill("Example Federal QA")
            page.locator("#work-email").fill("fictional@example.com")
            page.locator("#current-posture").select_option("HOLD")
            page.locator("#assumptions").fill("The public response deadline has not changed.")
            page.locator("#public-only").check()
            page.locator("#opportunity-url").fill("https://example.org/unsupported")
            page.locator("#copy-request").click()
            assert "exact public SAM.gov" in page.locator("#request-status").inner_text()
            page.locator("#opportunity-url").fill("https://sam.gov/opp/" + NOTICE + "/view")
            page.locator("#copy-request").click()
            page.wait_for_function("() => typeof window.__qaDraft === 'string'",
                                   timeout=10000)
            draft = page.evaluate("window.__qaDraft")
            assert "To: jay@retallyrecovery.com" in draft
            assert "Subject: CaptureBrief free assumption check request" in draft
            assert "Free assumption check requested" in draft
            assert "no automatic upgrade" in draft
            assert "fictional@example.com" in draft
            assert not posts, "The inquiry composer attempted a network POST"
            assert page.url.startswith(BASE) and not page.url.startswith("mailto:")
            page.locator("#assumptions").fill("A different fictional question.")
            assert "Request copied" not in page.locator("#request-status").inner_text()
            return {"browser": BROWSER, "fictional_local_draft_verified": True,
                    "form_posts": len(posts)}
        finally:
            browser.close()


def main() -> None:
    assert len(EXPECTED_SHA) == 40 and all(c in "0123456789abcdef" for c in EXPECTED_SHA)
    info = current_release()
    assert info.get("sourceBranch") == "gh-pages", "Wrong Cloudflare source branch"
    assert info.get("sourceRepository") == "P00NSMASHER/capturebrief"
    assert info.get("canonical") == BASE
    assert info.get("purchasePolicy") == "SCOPE_FIRST_PENDING_SOURCE_READINESS"
    manifest = info.get("files")
    assert isinstance(manifest, list) and info.get("publicFileCount") == len(manifest)
    by_path = {item["path"]: item for item in manifest}
    assert len(by_path) == len(manifest), "Duplicate public file manifest path"
    checked = []
    for path in ("index.html", "assets/capturebrief.js", "assets/capturebrief.css",
                 "privacy.html", "terms.html", "data-handling.html"):
        assert path in by_path, "Public release manifest omitted a required source"
        payload, _ = fetch(path)
        assert hashlib.sha256(payload).hexdigest() == by_path[path]["sha256"], \
            "Served production bytes differ from reviewed build manifest: " + path
        checked.append(path)
        if path == "index.html":
            assert b"at most ten businesses" in payload
            assert b"Preparing an email draft does not send an inquiry" in payload
    assert_private_not_published("capturebrief_core/scoped_source.py")
    assert_private_not_published("abvm/game/index.html")
    browser_result = verify_browser()
    print(json.dumps({
        "status": "EXACT_COMMIT_PRODUCTION_INQUIRY_VERIFIED_NO_SEND",
        "commit": EXPECTED_SHA, "purchase_policy": info["purchasePolicy"],
        "verified_assets": checked, **browser_result,
        "source_history_complete": False,
        "customer_delivery_authorized": False,
        "payment_authorized": False,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
