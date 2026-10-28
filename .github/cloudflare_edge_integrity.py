"""Strict Cloudflare Pages HTML edge transformations for public-release integrity.

The real deployed HTML differs from the built artifact because Cloudflare
removes its recognized <!--email_off--> comments and auto-injects its Web
Analytics beacon. Prove *all other bytes* still exactly match the reviewed
build, rather than blanket-ignoring HTML checks or stripping arbitrary tags.

The analytics token below is a PUBLIC site identifier, not a private key.
Any beacon update or edge format change must fail until separately reviewed.
"""
from __future__ import annotations

import re

EMAIL_START = b"<!--email_off-->"
EMAIL_END = b"<!--/email_off-->"
ANALYTICS_SITE_TOKEN = b"a6de879d36884dcbb647a94cbd50d3be"
ANALYTICS_SRI = b"UKNk8GbxkABxKcXYuLkO16EleLGUkcvJWtpSNmExE0Too3ZaFAxTscNWEc1OdAv5/BikHawapSCaiD2XCmp+Bw=="

BEACON = re.compile(
    rb'<script type="module" src="https://static\.cloudflareinsights\.com/beacon\.min\.js/v'
    rb'[a-f0-9]{32}[0-9]{13}" integrity="sha512-'
    + re.escape(ANALYTICS_SRI)
    + rb'" data-cf-beacon='
    + rb"""'{"version":"2024.11.0","token":""""
    + ANALYTICS_SITE_TOKEN
    + rb"""","r":1,"spa":2}' crossorigin="anonymous"></script>"""
)


def verify_public_html_bytes(expected: bytes, observed: bytes) -> str:
    """Return narrow evidence state or fail on ANY unknown source mutation."""
    if not isinstance(expected, bytes) or not isinstance(observed, bytes):
        raise ValueError("Public content comparisons require raw bytes")
    if expected == observed:
        return "EXACT_BYTES"
    if (expected.count(EMAIL_START) != 1 or expected.count(EMAIL_END) != 1
            or observed.count(EMAIL_START) or observed.count(EMAIL_END)):
        raise ValueError("Cloudflare email-marker transition is not expected")
    beacons = list(BEACON.finditer(observed))
    if len(beacons) != 1:
        raise ValueError("Unknown, duplicate or altered edge-injected analytics script")
    beacon = beacons[0]
    if observed.find(b"</body>", beacon.end()) < 0:
        raise ValueError("Beacon is not before the final body close")
    # The beacon must be inserted at the trailing body boundary. Its position
    # is not an allowlist for unknown third-party scripts elsewhere in HTML.
    after = observed[beacon.end():]
    if after not in (b"</body>", b"\n</body>", b"</body>\n", b"\n</body>\n", b"</body></html>",
                     b"\n</body></html>", b"</body>\n</html>", b"\n</body>\n</html>",
                     b"</body></html>\n", b"\n</body></html>\n"):
        raise ValueError("Beacon is not confined to the closing body boundary")
    original = expected.replace(EMAIL_START, b"").replace(EMAIL_END, b"")
    clean = observed[:beacon.start()] + observed[beacon.end():]
    if clean == original:
        return "PINNED_CLOUDFLARE_EDGE_TRANSFORMS"
    # Cloudflare contributes exactly one line feed adjacent to the beacon in
    # production. Remove ONLY that single byte next to the verified tag.
    if beacon.start() > 0 and observed[beacon.start()-1:beacon.start()] == b"\n":
        if observed[:beacon.start()-1] + observed[beacon.end():] == original:
            return "PINNED_CLOUDFLARE_EDGE_TRANSFORMS"
    if observed[beacon.end():beacon.end()+1] == b"\n":
        if observed[:beacon.start()] + observed[beacon.end()+1:] == original:
            return "PINNED_CLOUDFLARE_EDGE_TRANSFORMS"
    raise ValueError("Served HTML differs from signed build beyond approved edge transforms")
