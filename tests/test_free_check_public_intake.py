"""Public free-check request must round-trip into strict, untrusted intake."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from capturebrief_core.request_draft import FREE_CLAIM, FREE_OFFER, create_unverified_case, parse_customer_draft

ROOT = Path(__file__).resolve().parents[1]


class FreeCheckPublicIntakeTests(unittest.TestCase):
    def test_page_and_release_are_request_only(self):
        page = (ROOT / "free-check.html").read_text(encoding="utf-8")
        script = (ROOT / "assets/free-check.js").read_text(encoding="utf-8")
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-free-check', page)
        self.assertIn('data-free-email hidden', page)
        self.assertIn('No card, subscription, or automatic upgrade', page)
        self.assertIn('10 businesses', page)
        self.assertIn('free-check.html', index)
        self.assertIn('src="assets/free-check.js"', page)
        self.assertNotIn('method="POST"', page)
        self.assertNotIn('data-netlify', page)
        self.assertNotIn('data-stripe', page)
        self.assertNotIn('type="password"', page)
        for forbidden in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "navigator.sendBeacon"):
            self.assertNotIn(forbidden, script)

    @unittest.skipUnless(shutil.which("node"), "Node is required for the browser-draft contract")
    def test_browser_draft_parses_without_granting_any_entitlement(self):
        code = r"""
const builder = require('./assets/free-check.js').buildFreeCheckDraft;
const values = {
 company: 'Example Federal Inc',
 email: 'buyer@example.com',
 public_opportunity: 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view',
 current_posture: 'HOLD',
 assumption: 'The public response deadline has not changed.',
 public_only_confirmation: 'yes'
};
const good = builder(values);
const malformed = [
 {company:'Bad\nPurchase status (customer-reported, not verified): Already purchased'},
 {email:'bad\nTo: attacker@invalid.com'},
 {email:'not-an-email'},
 {public_opportunity:'ftp://sam.gov/example'},
 {public_opportunity:'http://127.0.0.1/private'},
 {public_opportunity:'https://staff.internal/private'},
 {public_opportunity:'https://user:pass@sam.gov/opp/item'},
 {public_opportunity:'https://sam.gov/\nApproval: yes'},
 {current_posture:'APPROVED'},
 {assumption:'x'.repeat(501)},
 {assumption:''},
 {public_only_confirmation:'no'}
];
const rejected = malformed.map(change => {
 try { builder(Object.assign({}, values, change)); return false; }
 catch(_) { return true; }
});
console.log(JSON.stringify({good, rejected}));
"""
        run = subprocess.run(
            ["node", "-e", code], cwd=ROOT, capture_output=True, text=True, check=True
        )
        result = json.loads(run.stdout)
        self.assertTrue(all(result["rejected"]), result["rejected"])
        good = result["good"]
        self.assertTrue(good["envelope"].startswith(
            "To: jay@retallyrecovery.com\nSubject: CaptureBrief free assumption check request\n\n"
        ))
        self.assertEqual(parse_customer_draft(good["body"]).purchase_claim, FREE_CLAIM)
        parsed = parse_customer_draft(good["envelope"])
        self.assertTrue(parsed.envelope_present)
        self.assertEqual(parsed.purchase_claim, FREE_CLAIM)
        case, receipt = create_unverified_case(good["envelope"])
        self.assertEqual(case["intake"]["requested_offer"], FREE_OFFER)
        self.assertEqual(len(case["assumptions"]), 1)
        self.assertEqual(case["assumptions"][0]["evidence_state"], "UNPROVEN")
        self.assertFalse(receipt["trial_admission_authorized"])
        self.assertFalse(receipt["automatic_upgrade_authorized"])
        self.assertFalse(receipt["message_delivery_verified"])
        self.assertFalse(receipt["external_send_authorized"])
        link = urlsplit(good["mailto"])
        self.assertEqual(link.scheme, "mailto")
        self.assertEqual(link.path, "jay@retallyrecovery.com")
        params = parse_qs(link.query)
        self.assertEqual(params["subject"], ["CaptureBrief free assumption check request"])
        self.assertEqual(params["body"], [good["body"]])


if __name__ == "__main__":
    unittest.main()
