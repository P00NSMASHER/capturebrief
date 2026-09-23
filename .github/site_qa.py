"""Read-only rendered checks: never send email, submit external data, or activate checkout."""
import functools
import hashlib
import json
import os
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("SITE_ROOT", ".")).resolve()
OUT = Path(os.environ.get("QA_OUTPUT", ".qa-output")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
PUBLIC_BASE = os.environ.get("QA_BASE_URL", "")
BROWSER = os.environ.get("QA_BROWSER", "chromium")
WIDTHS = [1440, 1024, 768, 390, 320]
PAGES = {
    "index.html": {
        "headline": "Know what your bid decision rests on.",
        "release": "2026-09-23-enterprise-1",
        "images": 5,
        "menu_target": "#deliverables",
    },
    "permitplate/index.html": {
        "headline": "Sell to restaurants?",
        "release": "2026-09-21-clarity-3",
        "images": 7,
        "menu_target": "#sample",
    },
    "freightrecovery/index.html": {
        "headline": "Check your freight bills.",
        "release": "2026-09-21-clarity-3",
        "images": 7,
        "menu_target": "#sample",
    },
}
RESULT = {
    "mode": "public-deployment" if PUBLIC_BASE else "committed-site-build",
    "browser": BROWSER,
    "pages": [],
    "errors": [],
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(
    ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(ROOT))
)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = PUBLIC_BASE.rstrip("/") + "/" if PUBLIC_BASE else f"http://127.0.0.1:{server.server_port}/"


def check(condition, message):
    if not condition:
        RESULT["errors"].append(message)


def images_ready(page, label, expected):
    for img in page.locator("img").all():
        img.scroll_into_view_if_needed(timeout=5000)
        try:
            img.evaluate(
                "i => Promise.race([i.decode(), new Promise((_,reject) => "
                "setTimeout(() => reject(new Error('image timeout')), 20000))])"
            )
        except Exception as exc:
            check(False, f"{label}: image decode failed: {str(exc)[:160]}")
    images = page.eval_on_selector_all(
        "img",
        "els => els.map(i => ({src:i.currentSrc,loaded:i.complete&&i.naturalWidth>0,"
        "naturalWidth:i.naturalWidth,naturalHeight:i.naturalHeight,"
        "renderedWidth:i.getBoundingClientRect().width,renderedHeight:i.getBoundingClientRect().height}))",
    )
    check(len(images) == expected, f"{label}: expected {expected} content images")
    check(all(i["loaded"] for i in images), f"{label}: all content images must load")
    check(
        all(i["renderedWidth"] > 80 and i["renderedHeight"] > 80 for i in images),
        f"{label}: content images must be visible",
    )
    return images


def contrast_check(page):
    return page.evaluate(
        """() => {
        const lum = rgb => rgb.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4)).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
        const rgb = s => (s.match(/[\\d.]+/g)||[]).map(Number);
        return [...document.querySelectorAll('.mark,.button,.number,.tag,.verdict,.state span,.mobile-cta b')]
          .filter(e=>e.getBoundingClientRect().width>0).map(e=>{
            const s=getComputedStyle(e),f=rgb(s.color),b=rgb(s.backgroundColor);
            if(b.length===4&&b[3]<1) return null;
            const a=lum(f),z=lum(b),ratio=(Math.max(a,z)+.05)/(Math.min(a,z)+.05);
            return {text:e.textContent.trim().slice(0,60),ratio:Number(ratio.toFixed(2))};
          }).filter(Boolean);
    }"""
    )


legacy = ROOT / "assets/site.css"
if legacy.exists():
    # Git may check text out with CRLF on Windows. Hash the canonical LF bytes
    # so the unchanged tracked stylesheet has the same identity on every OS.
    data = legacy.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    check(digest == "d61e21c4edae7a741a5c7abf015aa1af4b4090f8", "Keep the legacy stylesheet unchanged")
else:
    check(False, "Legacy stylesheet missing")

with sync_playwright() as pw:
    launch_options = {"headless": True}
    if os.environ.get("QA_CHROMIUM_PATH") and BROWSER == "chromium":
        launch_options["executable_path"] = os.environ["QA_CHROMIUM_PATH"]
    browser = getattr(pw, BROWSER).launch(**launch_options)
    try:
        for name, contract in PAGES.items():
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + name, wait_until="domcontentloaded", timeout=45000)
            check(response and response.status == 200, f"{name}: HTTP 200")
            check(
                page.locator('meta[name="site-release"]').get_attribute("content") == contract["release"],
                f"{name}: current release marker",
            )
            check(page.locator("h1").count() == 1, f"{name}: one H1")
            summary = {"page": name, "headline": page.locator("h1").inner_text(), "viewports": []}
            check(contract["headline"] in summary["headline"], f"{name}: correct headline")
            check(page.locator("img").count() == contract["images"], f"{name}: expected content-image count")
            if contract["images"]:
                urls = page.locator("img").evaluate_all("els=>els.map(i=>i.getAttribute('src'))")
                unique = {urlsplit(url).path for url in urls}
                summary["unique_photos"] = len(unique)
                check(len(unique) == contract["images"], f"{name}: no repeated photos")
                check(page.locator('img:not([alt]),img[alt=""]').count() == 0, f"{name}: image alternative text")
                check(page.locator("img:not([width]),img:not([height]),img:not([srcset])").count() == 0, f"{name}: responsive image dimensions")
                check(page.locator('img[fetchpriority="high"]').count() == 1, f"{name}: one prioritized hero")
                check(page.locator('img[loading="lazy"]').count() == contract["images"] - 1, f"{name}: secondary photos lazy loaded")
            check(page.locator('link[rel="canonical"]').count() == 1, f"{name}: canonical URL")
            missing = page.eval_on_selector_all(
                'a[href^="#"]',
                "els=>els.map(a=>a.getAttribute('href').slice(1)).filter(id=>!document.getElementById(id))",
            )
            check(not missing, f"{name}: broken anchors {missing}")
            check(page.locator('input[type="file"]').count() == 0, f"{name}: no file upload")
            text = page.locator("main").inner_text()
            lead = page.locator(".lead").inner_text()
            summary["lead_words"] = len(re.findall(r"[\w'-]+", lead))
            check(summary["lead_words"] <= 50, f"{name}: opening explanation is short")
            banned = [
                "source lineage", "gate posture", "canonical scoring", "realized recovery",
                "invoice population", "full disposition", "fail closed", "materially changed",
            ]
            check(not any(term in text.lower() for term in banned), f"{name}: unexplained internal jargon")

            if name == "index.html":
                check(page.locator(".brief-preview").count() == 1, "CaptureBrief: visible deliverable preview")
                check(page.locator(".hero-assurance span").count() == 3, "CaptureBrief: concise service assurances")
                check(page.locator(".brand-lockup").count() >= 2, "CaptureBrief: complete brand lockup")
                check(page.locator("#request-builder").is_visible(), "CaptureBrief: local request builder is available")
                check(page.locator('#request-builder[action]').count() == 0, "CaptureBrief: request form has no network action")
                check(page.locator('a[href="privacy.html"]').count() >= 1, "CaptureBrief: privacy link")
                check(page.locator('a[href="terms.html"]').count() >= 1, "CaptureBrief: terms link")
                check(page.locator('a[href="data-handling.html"]').count() >= 1, "CaptureBrief: data-handling link")
                page.locator("#deliverables").scroll_into_view_if_needed()
                page.wait_for_timeout(150)
                check(page.locator(".header").evaluate("e=>e.classList.contains('is-scrolled')"), "CaptureBrief: compact scrolled navigation")
                check(float(page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--page-progress') || 0")) > 0, "CaptureBrief: reading progress updates")
                page.evaluate("window.scrollTo(0,0)")
            else:
                check(page.locator("form").count() == 0, f"{name}: no intake form")
                check(
                    page.locator(".photo-cards .card").first.evaluate("e=>getComputedStyle(e).overflow") == "hidden",
                    f"{name}: clarity stylesheet applied",
                )

            for width in WIDTHS:
                page.set_viewport_size({"width": width, "height": 1000 if width > 800 else 844})
                page.evaluate("window.scrollTo(0,0)")
                page.wait_for_timeout(100)
                image_states = images_ready(page, f"{name}@{width}", contract["images"]) if width in [1440, 390] else None
                page.evaluate("window.scrollTo(0,0)")
                dims = page.evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth})")
                check(dims["scroll"] <= width + 1 and dims["body"] <= width + 1, f"{name}@{width}: horizontal overflow {dims}")
                summary["viewports"].append(dims)
                if width <= 800:
                    menu = page.locator(".menu")
                    menu.locator("summary").click()
                    check(menu.evaluate("e=>e.open"), f"{name}@{width}: menu opens")
                    menu.locator(f'a[href="{contract["menu_target"]}"]').click()
                    check(not menu.evaluate("e=>e.open"), f"{name}@{width}: menu closes after selection")
                    menu.locator("summary").click()
                    page.keyboard.press("Escape")
                    check(not menu.evaluate("e=>e.open"), f"{name}@{width}: Escape closes menu")
                    check(menu.locator("summary").evaluate("e=>e===document.activeElement"), f"{name}@{width}: focus returns")
                if width in [1440, 390]:
                    page.evaluate("window.scrollTo(0,0)")
                    slug = name.split("/")[0].replace(".html", "")
                    page.screenshot(path=str(OUT / f"{slug}-{width}.png"), full_page=True)
                    page.screenshot(path=str(OUT / f"{slug}-{width}-top.png"))
                    summary[f"images_{width}"] = image_states

            question = page.locator(".faq details").first
            question.locator("summary").click()
            check(question.evaluate("e=>e.open"), f"{name}: FAQ opens")
            question.locator("summary").click()
            check(not question.evaluate("e=>e.open"), f"{name}: FAQ closes")

            page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async t=>{window.__qaCopied=t}},configurable:true})")
            if name == "index.html":
                page.locator("#purchase-status").select_option("SCOPE_FIRST")
                page.locator("#opportunity-url").fill("https://sam.gov/opp/demo")
                page.locator("#current-posture").select_option("GO")
                page.locator("#assumptions").fill("The deadline has not changed.\nWe can bid as prime.")
                page.locator("#public-only").check()
                page.locator("#copy-request").click()
                page.wait_for_function("() => window.__qaCopied && window.__qaCopied.includes('Public opportunity link:')")
                copied_request = page.evaluate("window.__qaCopied")
                check("Current posture: GO" in copied_request, "CaptureBrief: request posture copied")
                check("1. The deadline has not changed." in copied_request, "CaptureBrief: numbered assumptions copied")
                check("Request copied" in page.locator("#request-status").inner_text(), "CaptureBrief: honest local-copy status")

            page.locator("[data-copy-email]").click()
            check(page.evaluate("window.__qaCopied") == "jayp19386@gmail.com", f"{name}: correct copied email")
            check("Nothing has been sent" in page.locator("#copy-status").inner_text(), f"{name}: no false send confirmation")
            page.evaluate("Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true})")
            page.locator("[data-copy-email]").click()
            check("selected address" in page.locator("#copy-status").inner_text(), f"{name}: clipboard fallback")
            check(page.evaluate("getSelection().toString()") == "jayp19386@gmail.com", f"{name}: fallback selects address")

            summary["solid_color_contrast"] = contrast_check(page)
            check(all(x["ratio"] >= 4.5 for x in summary["solid_color_contrast"]), f"{name}: targeted text contrast")
            summary["javascript_errors"] = errors
            check(not errors, f"{name}: JavaScript errors {errors}")
            if name == "index.html":
                check("$149" in text and "14-day" in text, "CaptureBrief offer preserved")
                check(page.locator('a[href="https://book.stripe.com/cNi7sLbRp95BbpR7Pb9sk01"]').count() == 4, "Direct checkout is visible in four intentional placements")
                check(page.locator('.checkout-link').count() == 4, "Every direct checkout placement is labeled")
            elif name.startswith("permitplate"):
                check("$79" in text and "per month" in text, "PermitPlate offer preserved")
            else:
                check("free 20-invoice" in text and "Do not attach confidential" in text, "Freight offer and privacy boundary preserved")
            RESULT["pages"].append(summary)
            context.close()

            context = browser.new_context(java_script_enabled=False, viewport={"width": 320, "height": 844})
            page = context.new_page()
            page.goto(base + name, wait_until="domcontentloaded", timeout=45000)
            page.locator(".menu summary").click()
            check(page.locator(".menu-panel").is_visible(), f"{name}: no-JS navigation")
            page.locator(".menu summary").click()
            page.locator(".faq summary").first.click()
            check(page.locator(".faq details").first.locator("p").is_visible(), f"{name}: no-JS FAQ")
            check(not page.locator("[data-copy-email]").is_visible(), f"{name}: dead copy button hidden without JS")
            if name == "index.html":
                check(not page.locator("#request-builder").is_visible(), "CaptureBrief: dead builder hidden without JS")
                check(page.locator(".noscript-note").is_visible(), "CaptureBrief: no-JS email fallback")
            context.close()
    except Exception as exc:
        RESULT["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        browser.close()
        server.shutdown()
        RESULT["passed"] = not RESULT["errors"]
        (OUT / "report.json").write_text(json.dumps(RESULT, indent=2), encoding="utf-8")
        print(json.dumps(RESULT, indent=2))

raise SystemExit(0 if RESULT["passed"] else 1)
