"""Contract test: a REAL rendered website copy draft enters the Python core.

Tests two immutable, separate GitHub review candidates:
- Python core at the current branch head (this PR).
- GitHub Pages candidate pinned via SITE_CHECKOUT to PR #50 head.
No email, payment, SAM API, third-party submission, or customer data.
"""
from __future__ import annotations

import functools
import json
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from capturebrief_core.intake import IntakeError
from capturebrief_core.request_draft import (
    PAID_CLAIM, SCOPE_CLAIM, create_unverified_case,
    parse_customer_draft,
)

ROOT = Path(os.environ["SITE_CHECKOUT"]).resolve(strict=True)
assert (ROOT / "assets" / "capturebrief.js").is_file()
assert (ROOT / "index.html").is_file()
NOTICE = "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def check(value, label):
    if not value:
        raise AssertionError(label)


def copy_request(page):
    page.evaluate("""() => {
        window.__capturebriefCopied = null;
        Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: {writeText: async (value) => {window.__capturebriefCopied = value;}}
        });
    }""")
    page.locator("#copy-request").click()
    page.wait_for_function("window.__capturebriefCopied !== null", timeout=5000)
    return page.evaluate("window.__capturebriefCopied")


def fill(page, *, purchase="SCOPE_FIRST", assumptions=None):
    page.locator("#purchase-status").select_option(purchase)
    page.locator("#company-name").fill("Fictional Federal Testing LLC")
    page.locator("#work-email").fill("test-buyer@example.com")
    page.locator("#opportunity-url").fill(NOTICE)
    page.locator("#current-posture").select_option("HOLD")
    page.locator("#assumptions").fill(
        assumptions if assumptions is not None
        else "The original deadline is unchanged.\nThe offer has no later amendments."
    )
    page.locator("#public-only").check()


def assert_case(draft, *, claim, count):
    parsed = parse_customer_draft(draft)
    check(parsed.purchase_claim == claim, "purchase claim mismatch")
    check(parsed.envelope_present, "missing clipboard envelope")
    check(parsed.intake["company"] == "Fictional Federal Testing LLC",
          "company missing from received backend request")
    check(parsed.intake["email"] == "test-buyer@example.com",
          "customer email missing from received backend request")
    check(parsed.intake["public_opportunity"] == NOTICE,
          "SAM.gov URL changed in website->core path")
    check(parsed.intake["current_posture"] == "HOLD",
          "current posture changed in website->core path")
    case, status = create_unverified_case(
        draft, submitted_at="2026-10-19T12:15:00Z",
    )
    check(len(case["assumptions"]) == count, "assumption count not preserved")
    check(all(row["evidence_state"] == "UNPROVEN" for row in case["assumptions"]),
          "website created unsupported source evidence")
    check(not case["sources"] and not case["current_action_receipts"],
          "case incorrectly contains official publisher receipts")
    check(not status["purchase_claim_verified"] and
          not status["ready_to_start_work"] and
          not status["external_send_authorized"],
          "buyer-selected purchase value bypassed release/payment boundaries")
    return case


def run():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(QuietHandler, directory=str(ROOT)),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks = []
    errors = []
    try:
        base = f"http://127.0.0.1:{server.server_port}/"
        with sync_playwright() as playwright:
            for browser_name in ("chromium", "webkit"):
                browser = getattr(playwright, browser_name).launch(headless=True)
                try:
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 900},
                        reduced_motion="reduce",
                    )
                    page = context.new_page()
                    outbound = []
                    page.on("request", lambda r: outbound.append((r.method, r.url)))
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    response = page.goto(base + "index.html", wait_until="domcontentloaded")
                    check(response is not None and response.status == 200,
                          browser_name + ": website failed to render")
                    page.locator("#copy-request").wait_for(state="visible")
                    fill(page)
                    draft = copy_request(page)
                    case = assert_case(draft, claim=SCOPE_CLAIM, count=2)
                    check(case["assumptions"][0]["text"] == "The original deadline is unchanged.",
                          "first assumption changed in transit")
                    checks.append(browser_name + ": fictional scope copy => unproven backend case")

                    fill(page, purchase="PAID")
                    paid = copy_request(page)
                    assert_case(paid, claim=PAID_CLAIM, count=2)
                    check("payment verification needed" in paid.lower(),
                          "paid buyer claim not labeled unverified")
                    checks.append(browser_name + ": PAID claim remains unverified")

                    lines = [chr(65+i)*500 for i in range(5)]
                    fill(page, assumptions="\n".join(lines))
                    check(page.locator("#assumptions").input_value() == "\n".join(lines),
                          "website truncated 2500 buyer assumption characters")
                    long_draft = copy_request(page)
                    long_case = assert_case(long_draft, claim=PAID_CLAIM, count=5)
                    check([row["text"] for row in long_case["assumptions"]] == lines,
                          "frontend/back-end lost 500-char assumptions")
                    checks.append(browser_name + ": 5 x 500 assumptions survive exact parser")

                    # Email clients may reject long mailto URLs. The site must
                    # not navigate or attempt a send when the draft is too long.
                    old_url = page.url
                    page.locator("#request-builder").evaluate("(node) => node.requestSubmit()")
                    check(page.url == old_url and
                          "too long" in page.locator("#request-status").inner_text().lower(),
                          "oversized draft failed safe copy-only fallback")
                    checks.append(browser_name + ": long mailto refused; copy still works")

                    # Browser must not produce a draft that core would reject.
                    invalids = [
                        ("https://192.168.1.1/private", "private addresses"),
                        ("https://company.internal/secret", "private addresses"),
                    ]
                    for url, expected in invalids:
                        fill(page)
                        page.locator("#opportunity-url").fill(url)
                        page.evaluate("window.__capturebriefCopied = null")
                        page.locator("#copy-request").click()
                        check(page.evaluate("window.__capturebriefCopied") is None,
                              "unsafe URL unexpectedly copied")
                        check(expected in page.locator("#request-status").inner_text(),
                              "UI missing private URL refusal")
                    checks.append(browser_name + ": private URL rejected before draft")

                    # A checkout success query string is user-editable and not
                    # an authenticated Stripe purchase record.
                    response = page.goto(
                        base + "index.html?checkout=complete#request",
                        wait_until="domcontentloaded",
                    )
                    check(response.status == 200, "return URL navigation failed")
                    check(page.locator("#purchase-status").input_value() == "PAID",
                          "checkout return posture not reflected")
                    check("does not verify a payment"
                          in page.locator("#request-status").inner_text(),
                          "website asserted unverified payment")
                    checks.append(browser_name + ": forged checkout return is unverified")

                    check(not errors, "browser JavaScript errors: " + "; ".join(errors))
                    check(all(method == "GET" and
                              urlsplit(url).hostname == "127.0.0.1"
                              for method, url in outbound),
                          "website attempted an external request or data POST")
                    checks.append(browser_name + ": no external/post requests")
                    context.close()
                finally:
                    browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    result = {
        "schema": "capturebrief-cross-branch-intake-e2e-v1",
        "tests": checks,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "browser_errors": errors,
        "external_emails_sent": 0,
        "stripe_charges": 0,
        "customer_records_used": False,
        "backend_persists_customer_data": False,
        "approved_to_accept_paid_pilot": False,
        "cross_branch_contract_passed": bool(checks) and not errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    check(result["cross_branch_contract_passed"], "cross-branch contract did not pass")


if __name__ == "__main__":
    run()
