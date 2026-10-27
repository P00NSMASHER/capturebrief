"""Adversarial, offline prior-award context admission. No real customer or API claims."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest

from capturebrief_core.award_context import (
    AwardContextHold, approved_request, evaluate_award_context, MAX_RECORDS,
)


def jsonbytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def award(identifier="1001", **changes):
    row = {
        "Award ID": "47QTCA26D0001",
        "Recipient Name": "Example Systems LLC",
        "Awarding Agency": "General Services Administration",
        "Awarding Agency Code": "047",
        "Base Obligation Date": "2026-09-15",
        "Award Amount": 123456.78,
        "NAICS": "541512",
        "generated_internal_id": identifier,
    }
    row.update(changes)
    return row


def scenario(*, rows=None, next_page=False, messages=None, limit=25):
    request = approved_request(
        start_date="2025-01-01", end_date="2026-09-30",
        awarding_agency_name="General Services Administration",
        naics="541512", limit=limit)
    response = {
        "spending_level": "awards",
        "limit": limit,
        "page_metadata": {"hasNext": next_page},
        "results": [award()] if rows is None else rows,
        "messages": [] if messages is None else messages,
    }
    return request, response


def analyze(request, response, **kwargs):
    options = {
        "observed_at": "2026-10-27T18:00:00Z",
        "pursuit_as_of": "2026-10-27T18:01:00Z",
        "target_agency_code": "047",
        "target_agency_name": "General Services Administration",
        "target_naics": "541512",
    }
    options.update(kwargs)
    return evaluate_award_context(
        jsonbytes(request), jsonbytes(response), **options)


class AwardContextTest(unittest.TestCase):
    def test_official_query_constrained_no_global_all_award_aggregation(self):
        request = approved_request(start_date="2025-01-01", end_date="2026-09-30",
                                   awarding_agency_name="General Services Administration",
                                   naics="541512")
        self.assertEqual(request["page"], 1)
        self.assertEqual(request["limit"], MAX_RECORDS)
        self.assertEqual(request["sort"], "Base Obligation Date")
        self.assertEqual(request["order"], "desc")
        self.assertEqual(request["filters"]["time_period"],
                         [{"start_date": "2025-01-01", "end_date": "2026-09-30"}])
        self.assertEqual(request["filters"]["award_type_codes"], ["A", "B", "C", "D"])
        self.assertEqual(request["filters"]["agencies"], [
            {"type": "awarding", "tier": "toptier",
             "name": "General Services Administration"}])
        self.assertEqual(request["filters"]["naics_codes"],
                         {"require": ["541512"], "exclude": []})
        for change in (
            {"limit": 26}, {"limit": 0}, {"limit": True},
            {"start_date": "2026-10-01", "end_date": "2026-09-30"},
            {"start_date": "2026-99-01", "end_date": "2026-09-30"},
        ):
            with self.subTest(change=change), self.assertRaises(AwardContextHold):
                approved_request(
                    start_date=change.get("start_date", "2025-01-01"),
                    end_date=change.get("end_date", "2026-09-30"),
                    awarding_agency_name="General Services Administration",
                    naics="541512",
                    limit=change.get("limit", 25),
                )


    def test_agency_name_cannot_be_omitted_or_changed_by_observer(self):
        req, res = scenario()
        for field in ("", " ", "Fake\tDepartment"):
            with self.subTest(field=field), self.assertRaises(AwardContextHold):
                approved_request(start_date="2025-01-01",
                                 end_date="2026-09-30",
                                 awarding_agency_name=field)
        with self.assertRaises(AwardContextHold):
            analyze(req, res, target_agency_name="Department of Defense")
        other = deepcopy(res)
        other["results"][0]["Awarding Agency"] = "Department of Defense"
        self.assertEqual(analyze(req, other)["excluded_row_counts"]["other_agency"], 1)

    def test_unscoped_agency_and_naics_dropped_by_attacker(self):
        req, res = scenario()
        for name, mutate in (
            ("no_agency", lambda d: d["filters"].pop("agencies")),
            ("no_naics", lambda d: d["filters"].pop("naics_codes")),
            ("extra_agency", lambda d: d["filters"]["agencies"].append(
                {"type": "funding", "tier": "toptier", "name": "All"})),
        ):
            altered = deepcopy(req)
            mutate(altered)
            with self.subTest(name=name), self.assertRaises(AwardContextHold):
                analyze(altered, res)

    def test_valid_prior_award_is_context_only_not_incumbent(self):
        req, res = scenario()
        actual = analyze(req, res)
        self.assertEqual(len(actual["award_context_candidates"]), 1)
        row = actual["award_context_candidates"][0]
        self.assertEqual(row["award_id"], "47QTCA26D0001")
        self.assertEqual(row["recipient_name"], "Example Systems LLC")
        self.assertEqual(row["award_amount_as_observed_not_historical_cash"], "123456.78")
        self.assertEqual(row["base_obligation_date"], "2026-09-15")
        self.assertEqual(row["evidence_class"], "PRIOR_AWARD_CONTEXT_REVIEW_ONLY")
        self.assertFalse(row["incumbent_for_requested_pursuit_verified"])
        self.assertFalse(row["current_award_amount_as_of_past_date_verified"])
        self.assertIsNone(row["customer_fit_or_win_probability"])
        self.assertFalse(actual["incumbent_identification_verified"])
        self.assertFalse(actual["award_amount_is_cash_received"])
        self.assertFalse(actual["customer_pursuit_readiness_certified"])
        self.assertFalse(actual["commercial_customer_scoring_approved"])
        self.assertFalse(actual["source_verified_by_independent_publisher_receipt"])
        self.assertFalse(actual["no_matching_awards_claimed"])
        self.assertEqual(actual["query_scope"],
                         "AWARDING_AGENCY_AND_OPTIONAL_NAICS_BOUNDED_SEARCH_ONLY")
        self.assertEqual(actual["pagination_status"], "BOUNDED_SEARCH_ONLY")
        self.assertEqual(actual["query_agency_name"], "General Services Administration")
        self.assertEqual(actual["query_naics_exact"], "541512")
        self.assertEqual(actual["request_sha256"],
                         hashlib.sha256(jsonbytes(req)).hexdigest())
        self.assertEqual(actual["response_sha256_LOCAL_INTEGRITY_NOT_PUBLISHER_PROOF"],
                         hashlib.sha256(jsonbytes(res)).hexdigest())

    def test_paginated_results_never_masquerade_as_complete_market(self):
        req, res = scenario(next_page=True)
        answer = analyze(req, res)
        self.assertEqual(answer["pagination_status"], "PAGE_INCOMPLETE")
        self.assertFalse(answer["no_matching_awards_claimed"])
        self.assertEqual(len(answer["award_context_candidates"]), 1)

    def test_provider_warning_demotes_even_single_page(self):
        req, res = scenario(messages=["Some results are delayed"])
        answer = analyze(req, res)
        self.assertEqual(answer["pagination_status"], "SOURCE_WARNING_REVIEW_REQUIRED")
        self.assertFalse(answer["customer_pursuit_readiness_certified"])

    def test_future_or_wrong_agency_rows_are_review_excluded(self):
        req, res = scenario(rows=[
            award("1", **{"Base Obligation Date": "2026-11-02"}),
            award("2", **{"Awarding Agency Code": "097"}),
            award("3", **{"NAICS": "541330"}),
            award("4", **{"Recipient Name": None}),
            award("5"),
        ])
        report = analyze(req, res)
        self.assertEqual(report["excluded_row_counts"], {
            "future_base_date": 1, "other_agency": 1, "other_naics": 1,
            "missing_linkage_fields": 1,
        })
        self.assertEqual([x["generated_internal_id"] for x in report["award_context_candidates"]],
                         ["5"])

    def test_no_rows_never_certs_no_competition(self):
        req, res = scenario(rows=[])
        report = analyze(req, res)
        self.assertEqual(report["award_context_candidates"], [])
        self.assertFalse(report["no_matching_awards_claimed"])
        self.assertFalse(report["incumbent_identification_verified"])

    def test_as_of_2025_with_2026_observation_is_retrospective_not_forecast(self):
        req, res = scenario(rows=[award()])
        report = analyze(req, res, pursuit_as_of="2025-10-01T00:00:00Z")
        self.assertEqual(report["temporal_basis"],
                         "RETROSPECTIVE_ONLY_NO_AS_OF_CLAIM")
        self.assertEqual(report["award_context_candidates"], [])
        self.assertEqual(report["excluded_row_counts"]["future_base_date"], 1)
        self.assertFalse(report["customer_pursuit_readiness_certified"])

    def test_source_query_scope_cannot_be_widened(self):
        req, res = scenario()
        mutations = (
            ("filters", lambda x: x["filters"].update(
                {"awarding_agencies": [{"tier": "toptier", "name": "X"}]})),
            ("date", lambda x: x["filters"]["time_period"][0].update(
                {"extra": "ignore"})),
            ("page", lambda x: x.update(page=2)),
            ("sort", lambda x: x.update(sort="Award Amount")),
            ("fields", lambda x: x.update(fields=["Award ID"])),
            ("limit", lambda x: x.update(limit=200)),
            ("subawards", lambda x: x.update(subawards=True)),
            ("types", lambda x: x["filters"].update(award_type_codes=["S"])),
            ("inject", lambda x: x.update(authorize_cash_payment=True)),
            ("agency", lambda x: x["filters"]["agencies"][0].update(name="Other Department")),
            ("agency_type", lambda x: x["filters"]["agencies"][0].update(type="funding")),
            ("naics", lambda x: x["filters"]["naics_codes"].update(require=["541330"])),
        )
        for label, mutate in mutations:
            q = deepcopy(req)
            mutate(q)
            with self.subTest(label=label), self.assertRaises(AwardContextHold):
                analyze(q, res)

    def test_false_source_completion_and_duplicate_ids_rejected(self):
        req, res = scenario()
        for label, mutation in (
            ("dupe", lambda r: r["results"].append(deepcopy(r["results"][0]))),
            ("missing", lambda r: r.pop("page_metadata")),
            ("notbool", lambda r: r["page_metadata"].update(hasNext="false")),
            ("wronglevel", lambda r: r.update(spending_level="subawards")),
            ("wronglimit", lambda r: r.update(limit=100)),
            ("too_many", lambda r: r.update(results=[award(str(n)) for n in range(26)])),
            ("malformed", lambda r: r.update(results=[None])),
            ("unvalidated_id", lambda r: r["results"][0].update(generated_internal_id="a\nb")),
        ):
            response = deepcopy(res)
            mutation(response)
            with self.subTest(label=label), self.assertRaises(AwardContextHold):
                analyze(req, response)

    def test_hazardous_money_never_numeric_cash_claim(self):
        req, res = scenario()
        for value in (True, "NaN", "Infinity", float("inf"), {}, "1e9999"):
            response = deepcopy(res)
            response["results"][0]["Award Amount"] = value
            with self.subTest(value=str(value)), self.assertRaises(AwardContextHold):
                analyze(req, response)

    def test_malformed_fields_and_unverified_award_link_rejected_or_excluded(self):
        req, res = scenario()
        for name, value in (
            ("Award ID", "x\nInjected: true"),
            ("Recipient Name", "  "),
            ("Recipient Name", "x" * 220),
        ):
            response = deepcopy(res)
            response["results"][0][name] = value
            if name == "Recipient Name" and value == "  ":
                self.assertEqual(analyze(req, response)["award_context_candidates"], [])
            else:
                with self.subTest(field=name), self.assertRaises(AwardContextHold):
                    analyze(req, response)

    def test_bytes_limit_bad_date_and_bad_naics_fail_closed(self):
        req, res = scenario()
        base = dict(observed_at="2026-10-27T18:00:00Z",
                    pursuit_as_of="2026-10-27T18:01:00Z",
                    target_agency_code="047",
                    target_agency_name="General Services Administration",
                    target_naics="541512")
        for bad in (
            (b"", jsonbytes(res), base),
            (b"{}\n", jsonbytes(res), base),
            (jsonbytes(req), b"", base),
            (jsonbytes(req), b"[" * 2_000_001, base),
            (jsonbytes(req), jsonbytes(res), {**base, "observed_at": "2026-13-01"}),
            (jsonbytes(req), jsonbytes(res), {**base, "target_naics": "54151"}),
            (jsonbytes(req), jsonbytes(res), {**base, "target_agency_code": "foo:secret"}),
        ):
            with self.subTest(v=repr(bad)[:60]), self.assertRaises(AwardContextHold):
                evaluate_award_context(bad[0], bad[1], **bad[2])


if __name__ == "__main__":
    unittest.main()
