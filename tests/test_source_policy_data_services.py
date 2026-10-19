import io
import unittest
from urllib.request import Request

from capturebrief_core.current_api import (
    SEARCH_URL,
    CurrentApiError,
    download_resource_from_api_observation,
    make_current_action_receipt,
)
from capturebrief_core.data_services import (
    ACTIVE_DOWNLOAD,
    ARCHIVE_DOWNLOAD,
    FamilyAmbiguous,
    download_extract,
    DataServicesError,
    issue_history_receipt_from_snapshots,
    scan_extract_bytes,
)
from capturebrief_core.manifest import (
    fetch_manifest,
    normalize_manifest_payload,
)
from capturebrief_core.source_policy import (
    SourcePolicyError,
    _OfficialExtractRedirectGuard,
    classify_sam_url,
    require_approved_automation,
    require_approved_extract_delivery,
)

NOW = "2026-09-21T13:00:00+00:00"

HEADER = (
    "NoticeId,Title,Sol#,Department/Ind.Agency,CGAC,Sub-Tier,FPDS Code,Office,AAC Code,"
    "PostedDate,Type,BaseType,ArchiveType,ArchiveDate,SetASideCode,SetASide,"
    "ResponseDeadLine,NaicsCode,ClassificationCode,PopStreetAddress,PopCity,PopState,"
    "PopZip,PopCountry,Active,AwardNumber,AwardDate,Award$,Awardee,PrimaryContactTitle,"
    "PrimaryContactFullname,PrimaryContactEmail,PrimaryContactPhone,PrimaryContactFax,"
    "SecondaryContactTitle,SecondaryContactFullname,SecondaryContactEmail,"
    "SecondaryContactPhone,SecondaryContactFax,OrganizationType,State,City,ZipCode,"
    "CountryCode,AdditionalInfoLink,Link,Description\n"
)


def row(notice, sol, aac="AAC1", active="Yes"):
    values = [
        notice, "Title", sol, "Dept", "", "Sub", "FPDS", "Office", aac,
        "09/20/2026", "Solicitation", "Solicitation", "", "", "", "",
        "09/30/2026", "541512", "D", "", "", "", "", "", active,
        "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
        "", "", "", "", "", "https://sam.gov/opp/x/view", "desc",
    ]
    return ",".join(values) + "\n"


class FakeResponse:
    def __init__(self, data: bytes, url="https://objects.example/file"):
        self._io = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))}
        self._url = url

    def read(self, n=-1):
        return self._io.read(n)

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SourcePolicyDataServicesTests(unittest.TestCase):
    def test_source_classes(self):
        self.assertEqual(
            classify_sam_url("https://api.sam.gov/opportunities/v2/search"),
            "SAM_PUBLIC_API",
        )
        self.assertEqual(
            classify_sam_url(ACTIVE_DOWNLOAD),
            "SAM_DATA_SERVICES_EXTRACT",
        )
        self.assertEqual(
            classify_sam_url(
                "https://sam.gov/api/prod/opps/v3/opportunities/abc/resources"
            ),
            "SAM_WEB_UI_UNDOCUMENTED",
        )
        with self.assertRaises(SourcePolicyError):
            require_approved_automation(
                "https://sam.gov/api/prod/opps/v3/opportunities/abc/resources"
            )

    def test_source_policy_rejects_credentials_fragments_and_nonstandard_ports(self):
        approved = ACTIVE_DOWNLOAD
        self.assertEqual(classify_sam_url(approved), "SAM_DATA_SERVICES_EXTRACT")
        self.assertEqual(classify_sam_url(ARCHIVE_DOWNLOAD.format(fy=2027)),
                         "SAM_DATA_SERVICES_EXTRACT")
        bad = [
            approved.replace("https://sam.gov", "https://user:secret@sam.gov"),
            approved.replace("https://sam.gov", "https://sam.gov:8443"),
            approved + "#client-secret",
            approved + "&extra=private",
            approved.replace("privacy=Public", "privacy=Private"),
            approved.replace("ContractOpportunitiesFullCSV.csv", "file.csv"),
            approved.replace("ContractOpportunitiesFullCSV.csv", "file.csv/../ContractOpportunitiesFullCSV.csv"),
            "https://[not-a-host",
            "https://api.sam.gov:badport/opportunities/v2/search",
        ]
        for value in bad:
            with self.subTest(url=value):
                self.assertEqual(classify_sam_url(value), "UNAPPROVED")
                with self.assertRaises(SourcePolicyError):
                    require_approved_automation(value)

    def test_rejected_urls_cannot_leak_signed_query_or_userinfo(self):
        sensitive = ("https://user:password-value@sam.gov/api/prod/opps/v3/"
                     "opportunities/secret-id/resources?api_key=do-not-print&signature=another-secret")
        with self.assertRaises(SourcePolicyError) as caught:
            require_approved_automation(sensitive)
        error = str(caught.exception)
        for secret in ("password-value", "do-not-print", "another-secret", "secret-id", "api_key"):
            self.assertNotIn(secret, error)
        self.assertIn("UNAPPROVED", error)

    def test_official_sam_extract_redirect_is_exact_resource_bound_only(self):
        active_s3 = ("https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
                     "datagov/ContractOpportunitiesFullCSV.csv")
        archive_s3 = ("https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
                      "Archived%20Data/FY2027_archived_opportunities.csv")
        self.assertEqual(require_approved_extract_delivery(ACTIVE_DOWNLOAD, ACTIVE_DOWNLOAD), "sam.gov")
        self.assertEqual(require_approved_extract_delivery(ACTIVE_DOWNLOAD, active_s3), "s3.amazonaws.com")
        self.assertEqual(require_approved_extract_delivery(ARCHIVE_DOWNLOAD.format(fy=2027), archive_s3),
                         "s3.amazonaws.com")
        self.assertEqual(classify_sam_url(active_s3), "UNAPPROVED",
                         "S3 is a guarded redirect target, not a new direct collection surface")
        for bad in (
            "https://evil.example/redirect",
            "https://s3.amazonaws.com/other-bucket/Contract%20Opportunities/"
            "Archived%20Data/FY2027_archived_opportunities.csv",
            archive_s3.replace("FY2027_", "FY2026_"),
            archive_s3.replace("https://", "http://"),
            archive_s3.replace("s3.amazonaws.com", "s3.amazonaws.com.evil.example"),
            archive_s3 + "?api_key=leak-me",
            archive_s3 + "#fragment",
            archive_s3.replace("s3.amazonaws.com", "user:pw@s3.amazonaws.com"),
            "https://s3.amazonaws.com:8443" + archive_s3.split("s3.amazonaws.com")[1],
        ):
            with self.subTest(bad=bad), self.assertRaises(SourcePolicyError) as result:
                require_approved_extract_delivery(ARCHIVE_DOWNLOAD.format(fy=2027), bad)
            self.assertNotIn("leak-me", str(result.exception))
            self.assertNotIn("user:pw", str(result.exception))

    def test_every_http_redirect_hop_is_guarded_before_following(self):
        start = ARCHIVE_DOWNLOAD.format(fy=2027)
        guard = _OfficialExtractRedirectGuard(start)
        request = Request(start)
        for bad in (
            "https://evil.example/temporary-redirect",
            "https://sam.gov/api/prod/fileextractservices/v1/api/download/"
            "Contract%20Opportunities/Archived%20Data/FY2026_archived_opportunities.csv?privacy=Public",
            "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
            "Archived%20Data/FY2028_archived_opportunities.csv",
        ):
            with self.subTest(bad=bad), self.assertRaises(SourcePolicyError):
                guard.redirect_request(request, None, 302, "Found", {}, bad)
        approved = ("https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
                    "Archived%20Data/FY2027_archived_opportunities.csv")
        redirected = guard.redirect_request(request, None, 302, "Found", {}, approved)
        self.assertEqual(redirected.full_url, approved)

    def test_in_memory_download_accepts_only_explicit_sam_binding_and_bytes(self):
        original = (HEADER + row("notice1", "SOL-123")).encode("utf-8")
        source = ARCHIVE_DOWNLOAD.format(fy=2027)
        official = ("https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
                    "Archived%20Data/FY2027_archived_opportunities.csv")
        result = download_extract(
            source, opener=lambda req, timeout=60: FakeResponse(original, url=official),
        )
        self.assertEqual(result, original)
        touched = []
        def no_read_if_redirect_bad(req, timeout=60):
            class Dangerous(FakeResponse):
                def read(self, n=-1):
                    touched.append(True)
                    return super().read(n)
            return Dangerous(original, url="https://evil.example/data?password=SECRET")
        with self.assertRaises(SourcePolicyError):
            download_extract(source, opener=no_read_if_redirect_bad)
        self.assertEqual(touched, [], "Unapproved redirect bytes must not even be read")
        class WrongLength(FakeResponse):
            def __init__(self):
                super().__init__(original, url=official)
                self.headers = {"Content-Length": str(len(original) + 10)}
        with self.assertRaises(DataServicesError):
            download_extract(source, opener=lambda req, timeout=60: WrongLength())

    def test_automated_ui_manifest_is_disabled(self):
        with self.assertRaises(SourcePolicyError):
            fetch_manifest("abc")

        raw = {
            "_embedded": {
                "opportunityAttachmentList": [
                    {
                        "attachments": [
                            {
                                "resourceId": "r1",
                                "name": "x.pdf",
                                "size": 1,
                                "accessStatus": "public",
                                "exportControlled": "0",
                                "deletedFlag": "0",
                                "fileExists": "1",
                                "type": "file",
                            }
                        ]
                    }
                ]
            }
        }
        receipt = normalize_manifest_payload(
            "a1",
            raw,
            observed_at=NOW,
            observation_mode="HUMAN_SUPERVISED",
        )
        self.assertEqual(receipt["observation_mode"], "HUMAN_SUPERVISED")

    def test_data_services_scan_and_complete_scope_receipt(self):
        active = (HEADER + row("a2", "SOL-1", active="Yes")).encode()
        archive = (HEADER + row("a1", "SOL-1", active="No")).encode()

        s1 = scan_extract_bytes(
            active,
            source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",
            solicitation_number="SOL-1",
        )
        s2 = scan_extract_bytes(
            archive,
            source_url=ARCHIVE_DOWNLOAD.format(fy=2026),
            source_kind="ARCHIVE",
            solicitation_number="SOL-1",
            fiscal_year=2026,
        )

        receipt = issue_history_receipt_from_snapshots(
            [s1, s2],
            solicitation_number="SOL-1",
            seed_notice_id="a2",
            scope_start_fy=2026,
            scope_end_fy=2026,
            scope_confirmed=True,
            observed_at=NOW,
        )

        self.assertEqual(receipt["status"], "COMPLETE")
        self.assertEqual(set(receipt["action_ids"]), {"a1", "a2"})
        self.assertEqual(receipt["automation_mode"], "APPROVED_EXTRACT")
        self.assertFalse(receipt["evidence_payload"]["ordering_authoritative"])
        self.assertFalse(receipt["evidence_payload"]["current_action_authoritative"])

    def test_unconfirmed_or_missing_archive_scope_is_not_complete(self):
        active = (HEADER + row("a2", "SOL-1")).encode()
        s1 = scan_extract_bytes(
            active,
            source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",
            solicitation_number="SOL-1",
        )
        receipt = issue_history_receipt_from_snapshots(
            [s1],
            solicitation_number="SOL-1",
            scope_start_fy=2026,
            scope_end_fy=2026,
            scope_confirmed=True,
            observed_at=NOW,
        )
        self.assertEqual(receipt["status"], "OBSERVED_ONLY")
        self.assertEqual(
            receipt["evidence_payload"]["scope"]["missing_archive_fys"],
            [2026],
        )

    def test_same_solnum_multiple_offices_is_ambiguous_without_seed(self):
        active = (
            HEADER
            + row("a2", "SOL-1", aac="AAC1")
            + row("z9", "SOL-1", aac="AAC2")
        ).encode()
        snapshot = scan_extract_bytes(
            active,
            source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",
            solicitation_number="SOL-1",
        )
        with self.assertRaises(FamilyAmbiguous):
            issue_history_receipt_from_snapshots(
                [snapshot],
                solicitation_number="SOL-1",
                observed_at=NOW,
            )

    def test_current_receipt_must_bind_to_history(self):
        observation = {
            "record": {
                "noticeId": "a2",
                "solicitationNumber": "SOL-1",
                "postedDate": "2026-09-20",
                "active": "Yes",
            },
            "source_url": SEARCH_URL,
            "observed_at": NOW,
            "payload_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "pagination": {
                "total_records": 1,
                "returned_records": 1,
                "limit": 100,
                "offset": 0,
                "complete": True,
            },
            "source_contract": "SAM_GET_OPPORTUNITIES_V2",
            "automation_mode": "APPROVED_API",
            "resource_links": [],
        }
        receipt = make_current_action_receipt(
            observation,
            history_action_ids=["a1", "a2"],
        )
        self.assertEqual(receipt["asserted_action_id"], "a2")
        self.assertEqual(receipt["automation_mode"], "APPROVED_API")

        with self.assertRaises(CurrentApiError):
            make_current_action_receipt(
                observation,
                history_action_ids=["a1"],
            )

    def test_api_resource_download_must_be_bound_to_api_observation(self):
        link = (
            "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/"
            "rid/download"
        )
        observation = {
            "record": {
                "noticeId": "a2",
                "solicitationNumber": "SOL-1",
                "resourceLinks": [link],
            },
            "source_url": SEARCH_URL,
            "observed_at": NOW,
            "payload_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "source_contract": "SAM_GET_OPPORTUNITIES_V2",
            "automation_mode": "APPROVED_API",
            "resource_links": [link],
            "pagination": {
                "total_records": 1,
                "returned_records": 1,
                "limit": 100,
                "offset": 0,
                "complete": True,
            },
        }
        data = b"abc123"

        receipt, content = download_resource_from_api_observation(
            observation,
            link,
            opener=lambda req, timeout=30: FakeResponse(data),
        )
        self.assertEqual(content, data)
        self.assertEqual(receipt["automation_mode"], "APPROVED_API")
        self.assertFalse(receipt["final_url_retained"])
        self.assertNotIn("final_url", receipt)

        with self.assertRaises(CurrentApiError):
            download_resource_from_api_observation(
                observation,
                link + "x",
                opener=lambda *args, **kwargs: FakeResponse(data),
            )


if __name__ == "__main__":
    unittest.main()
