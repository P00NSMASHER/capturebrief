"""CaptureBrief buyer-path checks. Never open mailto, checkout, or transmit data."""
from __future__ import annotations

import functools
import hashlib
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("SITE_ROOT", ".")).resolve()
OUT = Path(os.environ.get("QA_OUTPUT", ".qa-output/buyer")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get("QA_BASE_URL", "").rstrip("/")
WIDTHS = [1440, 1024, 768, 390, 320]
REPORT = {"mode": "live" if BASE else "build", "assertions": 0, "errors": [], "viewports": [], "actions_sent": 0}


def check(condition, message):
    REPORT["assertions"] += 1
    if not condition:
        REPORT["errors"].append(message)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = BASE + "/" if BASE else f"http://127.0.0.1:{server.server_port}/"


def navigate(page, path):
    response = page.goto(base + path, wait_until="domcontentloaded", timeout=30000)
    check(response is not None and response.status == 200, f"{path}: HTTP 200")


try:
    manifest = json.loads((ROOT / "examples/manifest.json").read_text())
    check(manifest["fictional"] is True and manifest["government_source"] is False, "Manifest labels invented evidence")
    expected_paths = {
        "examples/original.txt", "examples/amendment-02.txt", "examples/incorporation.txt",
        "examples/rule-2025.txt", "examples/rule-2026.txt",
    }
    check({r["path"] for r in manifest["files"]} == expected_paths, "Exactly five example files")
    hashes = {}
    for row in manifest["files"]:
        # Git can check text fixtures out with CRLF on Windows. The published
        # manifest fingerprints canonical repository bytes, which use LF.
        raw_data = (ROOT / row["path"]).read_bytes()
        data = raw_data.replace(b"\r\n", b"\n")
        hashes[row["path"]] = hashlib.sha256(data).hexdigest()
        check(hashes[row["path"]] == row["sha256"] and len(data) == row["bytes"], row["path"] + ": hash and length")
        check(data.decode().startswith("FICTIONAL EXAMPLE ONLY"), row["path"] + ": fictional label")

    with sync_playwright() as pw:
        options = {"headless": True}
        if os.environ.get("QA_CHROMIUM_PATH"):
            options["executable_path"] = os.environ["QA_CHROMIUM_PATH"]
        browser = pw.chromium.launch(**options)
        try:
            for enabled in [True, False]:
                context = browser.new_context(java_script_enabled=enabled, viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                navigate(page, "index.html")

                check(page.locator('a[href="decision-evidence.html"]').count() >= 3, "Home has prominent example links")
                check(page.locator('a[href="https://book.stripe.com/cNi7sLbRp95BbpR7Pb9sk01"]').count() == 4, "Direct checkout is available without a scope gate")
                check(page.locator('.checkout-link').count() == 4, "Direct checkout placements use the explicit checkout label")
                check("full refund" in page.locator("main").inner_text().lower(), "Pre-work out-of-scope refund promise is visible")
                check(page.locator('a[href="privacy.html"]').count() >= 1, "Home links privacy")
                check(page.locator('a[href="terms.html"]').count() >= 1, "Home links terms")
                check(page.locator('a[href="data-handling.html"]').count() >= 1, "Home links data handling")
                check(page.locator('input[type="file"]').count() == 0, "No upload control")

                mail = page.locator("#contact-email")
                mail_href = urlsplit(mail.get_attribute("href"))
                check(mail_href.scheme == "mailto" and mail_href.path == "jayp19386@gmail.com", "Fallback email recipient")

                if enabled:
                    form = page.locator("#request-builder")
                    check(form.is_visible(), "Local request builder visible with JavaScript")
                    check(form.get_attribute("action") is None, "Builder has no network action")
                    requests_before = []
                    page.on("request", lambda req: requests_before.append(req.url))
                    page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async t=>{window.__qaCopied=t}},configurable:true})")
                    page.locator("#purchase-status").select_option("PAID")
                    page.locator("#opportunity-url").fill("https://sam.gov/opp/fictional-public-demo")
                    page.locator("#current-posture").select_option("HOLD")
                    page.locator("#assumptions").fill("The deadline has not changed.\nWe can submit 20 pages.\nThe cited edition applies.")
                    page.locator("#public-only").check()
                    loaded_requests = len(requests_before)
                    page.locator("#copy-request").click()
                    page.wait_for_function("() => window.__qaCopied && window.__qaCopied.includes('Current posture: HOLD')")
                    copied = page.evaluate("window.__qaCopied")
                    check("Purchase status: Already purchased" in copied, "Paid order status enters draft")
                    check("Public opportunity link: https://sam.gov/opp/fictional-public-demo" in copied, "Public link enters draft")
                    check("1. The deadline has not changed." in copied and "3. The cited edition applies." in copied, "Assumptions numbered")
                    check("only public, non-sensitive information" in copied, "Safety confirmation enters draft")
                    check("refunded before work begins" in copied, "Paid intake carries refund boundary")
                    check(len(requests_before) == loaded_requests, "Copying draft makes no network request")
                    check("Nothing was sent" not in page.locator("#request-status").inner_text(), "Copy status does not claim submission")

                    page.locator("#assumptions").fill("One\nTwo\nThree\nFour\nFive\nSix")
                    page.locator("#copy-request").click()
                    check("five assumptions or fewer" in page.locator("#request-status").inner_text(), "Sixth assumption is blocked")

                    navigate(page, "index.html?checkout=complete#request")
                    check(page.locator("#purchase-status").input_value() == "PAID", "Checkout return selects paid intake")
                    check("verified separately" in page.locator("#request-status").inner_text(), "Checkout return avoids an unverified payment claim")
                else:
                    check(not page.locator("#request-builder").is_visible(), "No-JS builder is hidden")
                    check(page.locator(".noscript-note").is_visible(), "No-JS fallback is visible")

                page.locator("#full-evidence-link").click()
                check(urlsplit(page.url).path.endswith("/decision-evidence.html"), "Full example navigation works")
                page.locator("h1").wait_for(state="visible")
                check(page.locator("h1").count() == 1, "Example has one H1")
                check("Fictional example" in page.locator(".fiction-label").inner_text(), "Fictional warning visible")
                check(page.locator("form, input, script").count() == 0, "Example has no submission surface or script")

                for details in page.locator("details").all():
                    if details.get_attribute("open") is None:
                        details.locator(":scope > summary").click()
                for quote in page.locator("blockquote[data-source]").all():
                    check(quote.is_visible(), "Quoted passage visible after disclosure")
                    source = quote.get_attribute("data-source")
                    line = int(quote.get_attribute("data-line"))
                    check(quote.inner_text() == (ROOT / source).read_text().splitlines()[line - 1], "Exact quote " + source + ":" + str(line))
                for code in page.locator("[data-hash-for]").all():
                    check(code.is_visible(), "Fingerprint visible after disclosure")
                    check(code.inner_text() == hashes[code.get_attribute("data-hash-for")], "Displayed fingerprint matches file")
                check(page.locator(".finding-card").count() == 3, "Three bounded example findings")

                for width in WIDTHS:
                    page.set_viewport_size({"width": width, "height": 900})
                    for details in page.locator("details").all():
                        if details.get_attribute("open") is None:
                            details.locator(":scope > summary").click()
                    dims = page.evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth})")
                    check(dims["scroll"] <= width + 1 and dims["body"] <= width + 1, f"{width}/JS={enabled}: no overflow with evidence expanded")
                    REPORT["viewports"].append({**dims, "javascript_enabled": enabled})
                    if enabled and width in [1440, 768, 390, 320]:
                        page.evaluate("window.scrollTo(0,0)")
                        page.screenshot(path=str(OUT / f"evidence-expanded-{width}.png"), full_page=True)
                    for details in reversed(page.locator("details").all()):
                        if details.get_attribute("open") is not None:
                            details.locator(":scope > summary").click()
                    check(page.locator("details[open]").count() == 0, "Disclosure controls close")

                if enabled:
                    summary = page.locator("#pages > details > summary")
                    summary.focus()
                    page.keyboard.press("Enter")
                    check(page.locator("#pages > details").get_attribute("open") is not None, "Keyboard opens evidence")
                    page.keyboard.press("Enter")
                    check(page.locator("#pages > details").get_attribute("open") is None, "Keyboard closes evidence")

                for path in sorted(expected_paths | {"examples/manifest.json"}):
                    response = context.request.get(base + path)
                    expected = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
                    served = response.body().replace(b"\r\n", b"\n")
                    check(response.status == 200 and served == expected, "Served source bytes match " + path)

                page.locator(".evidence-cta a").click()
                check(urlsplit(page.url).fragment == "request", "Example returns buyer to scope request")

                for legal_path, heading in [
                    ("privacy.html", "Privacy information"),
                    ("data-handling.html", "Keep the input public"),
                    ("terms.html", "Service terms and boundaries"),
                ]:
                    navigate(page, legal_path)
                    check(heading in page.locator("h1").inner_text(), legal_path + ": correct heading")
                    check("JP Enterprises" in page.locator("footer").inner_text(), legal_path + ": operator in footer")
                    check(page.locator('link[rel="canonical"]').count() == 1, legal_path + ": canonical")

                check(not errors, "No browser errors: " + repr(errors))
                context.close()
        finally:
            browser.close()
except Exception as exc:
    REPORT["errors"].append(type(exc).__name__ + ": " + str(exc))
finally:
    server.shutdown()
    REPORT["passed"] = not REPORT["errors"]
    (OUT / "report.json").write_text(json.dumps(REPORT, indent=2) + "\n")
    print(json.dumps(REPORT, indent=2))

raise SystemExit(0 if REPORT["passed"] else 1)
