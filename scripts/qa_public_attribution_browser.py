"""Offline Chromium QA of the real public CaptureBrief intake and attribution script.

Uses a loopback HTTP server for production-like pathnames. All non-loopback
requests are aborted; no customer form is submitted and no external traffic
is required. Call from an isolated checkout: python scripts/qa_public_attribution_browser.py
"""
from __future__ import annotations

import contextlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote, urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *_args):
        pass

    def do_POST(self):
        self.send_error(405, "QA must not submit forms")


def run() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    cases = [
        ("/", "?utm_source=Google-Ads&utm_campaign=Fall+Launch_2026",
         ("/", "Google-Ads", "Fall Launch_2026")),
        ("/index.html", "?utm_source=newsletter&utm_campaign=a.b%2Bc",
         ("/index.html", "newsletter", "a.b+c")),
        ("/", "?utm_source=" + quote("x" * 4096) + "&utm_campaign=" + quote("person@example.com"),
         ("/", "", "")),
        ("/index.html", "?utm_source=" + quote("https://outside.example/private", safe="")
         + "&utm_campaign=" + quote("bad\nheader", safe=""),
         ("/index.html", "", "")),
    ]
    checked = 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for width in (375, 1280):
                    page = browser.new_page(viewport={"width": width, "height": 820})
                    failures = []
                    external_attempts = []
                    post_attempts = []
                    page.on("pageerror", lambda error: failures.append(str(error)))
                    page.on("request", lambda request: (
                        post_attempts.append(request.url) if request.method == "POST" else None
                    ))

                    def allow_loopback(route):
                        destination = urlsplit(route.request.url)
                        if destination.scheme in {"http", "https"} and destination.hostname not in {
                            "127.0.0.1", "localhost"
                        }:
                            external_attempts.append(route.request.url)
                            route.abort()
                        else:
                            route.continue_()

                    page.route("**/*", allow_loopback)
                    for path, query, expected in cases:
                        page.goto(origin + path + query + "#request", wait_until="load")
                        form = page.locator('form[name="pursuit-qa-intake"]')
                        assert form.count() == 1, "Live HTML lost the public intake form"
                        actual = tuple(form.locator(f'input[name="{key}"]').input_value()
                                       for key in ("source_page", "utm_source", "utm_campaign"))
                        assert actual == expected, f"Attribution mismatch: {actual!r} != {expected!r}"
                        assert form.get_attribute("method").upper() == "POST"
                        assert form.get_attribute("action") == "/thanks.html"
                        assert form.locator('input[name="public_only_confirmation"]').count() == 1
                        checked += 1
                    # Exercise the real browser limit for all five assumption
                    # fields. Product intake accepts 500 characters; the
                    # public form must neither clip character 241 nor 501.
                    form = page.locator('form[name="pursuit-qa-intake"]')
                    for number in range(1, 6):
                        field = form.locator(f'input[name="assumption_{number}"]')
                        full = chr(64 + number) * 500
                        field.fill(full)
                        assert field.input_value() == full, f"Assumption {number} clipped before 500"
                        field.press("End")
                        field.press("Z")
                        assert field.input_value() == full, f"Assumption {number} exceeded 500"
                    if width == 375:
                        toggle = page.locator(".menu-toggle")
                        toggle.click()
                        assert toggle.get_attribute("aria-expanded") == "true"
                        page.keyboard.press("Escape")
                        assert toggle.get_attribute("aria-expanded") == "false"
                    assert not post_attempts, f"QA attempted an unauthorized POST: {post_attempts}"
                    assert not failures, f"Public JS browser error: {failures}"
                    # External resources (if any) were blocked, not requested from the internet.
                    print(f"viewport={width}, rendered_cases={len(cases)}, external_blocked={len(external_attempts)}")
                    page.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
    print(f"PASS: {checked} Chromium public-intake cases, zero POSTs, no external egress")


if __name__ == "__main__":
    run()
