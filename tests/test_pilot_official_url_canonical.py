"""No normalization may silently change an official SAM.gov source URL.

These fictional-only cases reproduce Python urllib.parse stripping leading
spaces and CR/LF/TAB, causing an unreviewed source reference to be accepted.
No network, customer data, authorization or outbound messages are involved.
"""
import unittest

from scripts.pilot_preflight import official_opportunity

NOTICE = "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view"


class OfficialOpportunityCanonicalTests(unittest.TestCase):
    def test_exact_official_notice_is_accepted(self):
        self.assertTrue(official_opportunity(NOTICE))
        self.assertTrue(official_opportunity(NOTICE + "/"))
        self.assertTrue(official_opportunity(NOTICE.replace("sam.gov", "SAM.GOV")))
        self.assertTrue(official_opportunity(NOTICE.replace("sam.gov", "sam.gov:443")))

    def test_python_urlsplit_normalized_control_characters_are_rejected(self):
        # urllib.parse.urlsplit otherwise erases these before parsing. The
        # original source string must remain unmodified and unambiguous.
        for polluted in (
            " " + NOTICE,
            "\t" + NOTICE,
            "\r\n" + NOTICE,
            NOTICE + "\r\n",
            NOTICE + "\t",
            NOTICE.replace("/view", "/\tview"),
            NOTICE.replace("/view", "/\r\nview"),
        ):
            with self.subTest(polluted=repr(polluted)):
                self.assertFalse(official_opportunity(polluted))

    def test_invalid_non_source_inputs_still_fail(self):
        for invalid in (None, "", "https://sam.gov/opp/not-an-id/view",
                        NOTICE + "?token=not-a-source",
                        NOTICE.replace("sam.gov", "sam.gov.example.invalid")):
            with self.subTest(invalid=invalid):
                self.assertFalse(official_opportunity(invalid))


if __name__ == "__main__":
    unittest.main()
