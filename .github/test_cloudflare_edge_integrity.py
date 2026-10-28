"""Cloudflare edge mutation policy: exact built HTML plus only known service transforms."""
import unittest

from cloudflare_edge_integrity import verify_public_html_bytes

BEACON = (
    b'<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js/v'
    + b"a" * 32 + b"1792088814092"
    + b'" integrity="sha512-UKNk8GbxkABxKcXYuLkO16EleLGUkcvJWtpSNmExE0Too3ZaFAxTscNWEc1OdAv5/BikHawapSCaiD2XCmp+Bw=="'
    + b' data-cf-beacon=\'{"version":"2024.11.0","token":"a6de879d36884dcbb647a94cbd50d3be","r":1,"spa":2}\''
    + b' crossorigin="anonymous"></script>'
)
EXPECTED = (b'<html><body class="capture">\n<!--email_off-->\n'
            b'<main><h1>CaptureBrief protected public copy</h1></main>\n'
            b'<!--/email_off-->\n</body></html>')
CLEAN = EXPECTED.replace(b"<!--email_off-->",b"").replace(b"<!--/email_off-->",b"")

class EdgeBytesTests(unittest.TestCase):
    def test_exact_unmodified_build_passes(self):
        self.assertEqual(verify_public_html_bytes(EXPECTED, EXPECTED), "EXACT_BYTES")

    def test_verified_beacon_and_marker_removal_pass(self):
        html = CLEAN.replace(b"</body>", BEACON + b"</body>")
        self.assertEqual(verify_public_html_bytes(EXPECTED, html), "PINNED_CLOUDFLARE_EDGE_TRANSFORMS")
        # A single edge-inserted line feed adjacent to beacon is also permitted.
        html = CLEAN.replace(b"</body>", b"\n" + BEACON + b"</body>")
        self.assertEqual(verify_public_html_bytes(EXPECTED, html), "PINNED_CLOUDFLARE_EDGE_TRANSFORMS")

    def test_unrelated_byte_tamper_stays_blocked(self):
        html = CLEAN.replace(b"CaptureBrief", b"MaliciousBrand").replace(b"</body>", BEACON+b"</body>")
        with self.assertRaises(ValueError):
            verify_public_html_bytes(EXPECTED, html)

    def test_unapproved_script_or_token_is_rejected(self):
        for tag in (
            BEACON.replace(b"a6de879d36884dcbb647a94cbd50d3be", b"0"*32),
            BEACON.replace(b"integrity=",b"onerror=\"alert(1)\" integrity="),
            BEACON.replace(b"static.cloudflareinsights.com",b"evil.cloudflareinsights.com"),
            BEACON.replace(b"UKNk8Gbx", b"XKNk8Gbx"),
        ):
            with self.subTest(tag=tag[:90]), self.assertRaises(ValueError):
                verify_public_html_bytes(EXPECTED, CLEAN.replace(b"</body>",tag+b"</body>"))

    def test_double_injection_and_relocated_beacon_are_blocked(self):
        with self.assertRaises(ValueError):
            verify_public_html_bytes(EXPECTED, CLEAN.replace(b"</body>", BEACON+BEACON+b"</body>"))
        with self.assertRaises(ValueError):
            verify_public_html_bytes(EXPECTED, CLEAN.replace(b"<main>", BEACON + b"<main>"))

    def test_unknown_comment_stripping_is_not_accepted(self):
        bad = CLEAN.replace(b"<main>", b"<main><!-- unexpected removed -->").replace(b"</body>", BEACON+b"</body>")
        with self.assertRaises(ValueError):
            verify_public_html_bytes(EXPECTED, bad)

if __name__ == "__main__":
    unittest.main()
