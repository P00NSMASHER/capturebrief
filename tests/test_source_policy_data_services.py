import io
import unittest

from capturebrief_core.current_api import (
    CurrentApiError,
    download_resource_from_api_observation,
    make_current_action_receipt,
)
from capturebrief_core.data_services import (
    ACTIVE_DOWNLOAD,
    ARCHIVE_DOWNLOAD,
    FamilyAmbiguous,
    issue_history_receipt_from_snapshots,
    scan_extract_bytes,
)
from capturebrief_core.manifest import (
    fetch_manifest,
    normalize_manifest_payload,
)
from capturebrief_core.source_policy import (
    SourcePolicyError,
    classify_sam_url,
    require_approved_automation,
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
            "source_url": "https://api.sam.gov/opportunities/v2/search",
            "observed_at": NOW,
            "payload_sha256": "a" * 64,
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
            "resource_links": [link],
            "payload_sha256": "a" * 64,
        }
        data = b"abc123"

        receipt, content = download_resource_from_api_observation(
            observation,
            link,
            opener=lambda req, timeout=30: FakeResponse(data),
        )
        self.assertEqual(content, data)
        self.assertEqual(receipt["automation_mode"], "APPROVED_API")

        with self.assertRaises(CurrentApiError):
            download_resource_from_api_observation(
                observation,
                link + "x",
                opener=lambda *args, **kwargs: FakeResponse(data),
            )


if __name__ == "__main__":
    unittest.main()
