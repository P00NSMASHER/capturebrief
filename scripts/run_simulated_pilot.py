"""Run a deterministic, explicitly fictional CaptureBrief sales-to-delivery pilot.

This is a validation matrix, not customer evidence, revenue, conversion data, or a
forecast. Every customer number and commercial event in this file is simulated.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capturebrief_core.delivery_bundle import build_delivery_bundle
from capturebrief_core.fulfillment_plan import build_fulfillment_plan
from capturebrief_core.intake import IntakeError, build_case_from_intake


PILOT_AT = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)
PILOT_AT_TEXT = PILOT_AT.isoformat()


def _base(customer_number: str, *, route: str, posture: str = "GO") -> dict[str, Any]:
    suffix = customer_number.rsplit("-", 1)[-1]
    return {
        "customer_number": customer_number,
        "route": route,
        "intake": {
            "email": f"buyer-{suffix}@example.invalid",
            "company": f"Fictional Buyer {suffix}",
            "public_opportunity": f"https://sam.gov/opp/simulated-{suffix}/view",
            "current_posture": posture,
            "assumption_1": "The response deadline has not changed.",
            "public_only_confirmation": "yes",
        },
        "expected": "ACCEPTED_FOR_REVIEW",
    }


def scenarios() -> list[dict[str, Any]]:
    rows = [
        _base("SIM-CUST-001", route="DIRECT_CHECKOUT", posture="GO"),
        _base("SIM-CUST-002", route="DIRECT_CHECKOUT", posture="HOLD"),
        _base("SIM-CUST-003", route="DIRECT_CHECKOUT", posture="PASS"),
        _base("SIM-CUST-004", route="DIRECT_CHECKOUT", posture="NO-GO"),
        _base("SIM-CUST-005", route="SCOPE_FIRST", posture="UNSURE"),
        _base("SIM-CUST-006", route="SCOPE_FIRST", posture="GO"),
        _base("SIM-CUST-007", route="DIRECT_CHECKOUT"),
        _base("SIM-CUST-008", route="DIRECT_CHECKOUT"),
        _base("SIM-CUST-009", route="DIRECT_CHECKOUT"),
        _base("SIM-CUST-010", route="SCOPE_FIRST"),
        _base("SIM-CUST-011", route="SCOPE_FIRST"),
        _base("SIM-CUST-012", route="DIRECT_CHECKOUT"),
    ]
    rows[1]["intake"]["assumption_2"] = "The 20-page limit still controls."
    rows[2]["intake"].update({
        "assumption_2": "We can bid as the prime.",
        "assumption_3": "The cited rule edition applies.",
    })
    rows[4]["intake"].update({
        "assumption_2": "The opportunity remains active.",
        "assumption_3": "All referenced files are public.",
        "assumption_4": "The original submission instructions still control.",
        "assumption_5": "The named rule edition remains current.",
    })
    rows[5]["intake"]["public_opportunity"] = "https://www.example.gov/public-opportunity/006"

    rows[6]["intake"]["public_only_confirmation"] = "no"
    rows[6]["expected"] = "REFUND_BEFORE_WORK"
    rows[7]["intake"]["email"] = "not-an-email"
    rows[7]["expected"] = "REFUND_BEFORE_WORK"
    rows[8]["intake"]["public_opportunity"] = "ftp://example.invalid/private"
    rows[8]["expected"] = "REFUND_BEFORE_WORK"
    rows[9]["intake"]["assumption_6"] = "A sixth assumption must not be ignored."
    rows[9]["expected"] = "DECLINED_BEFORE_PAYMENT"
    rows[10]["intake"]["assumption_2"] = "  THE RESPONSE DEADLINE HAS NOT CHANGED.  "
    rows[10]["expected"] = "DECLINED_BEFORE_PAYMENT"
    rows[11]["intake"]["assumption_1"] = "x" * 501
    rows[11]["expected"] = "REFUND_BEFORE_WORK"
    return rows


def _run_intake_matrix() -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for row in scenarios():
        customer_number = row["customer_number"]
        result = {
            "customer_number": customer_number,
            "route": row["route"],
            "expected": row["expected"],
        }
        try:
            case = build_case_from_intake(row["intake"], submitted_at=PILOT_AT_TEXT)
            plan = build_fulfillment_plan(case, now=PILOT_AT)
            actual = "ACCEPTED_FOR_REVIEW"
            result.update({
                "actual": actual,
                "case_id": case["case_id"],
                "normalized_posture": case["current_posture"],
                "assumptions": len(case["assumptions"]),
                "initial_sources": len(case["sources"]),
                "release_state": plan["release_state"],
                "fulfillment_state": plan["fulfillment_state"],
                "external_send_authorized": plan["communications"]["external_send_authorized"],
            })
            if case["sources"] or not plan["release_blocker_codes"]:
                failures.append(f"{customer_number}: fresh intake invented evidence or release authority")
        except IntakeError as exc:
            actual = "REFUND_BEFORE_WORK" if row["route"] == "DIRECT_CHECKOUT" else "DECLINED_BEFORE_PAYMENT"
            result.update({"actual": actual, "validation_message": str(exc)})
        if actual != row["expected"]:
            failures.append(f"{customer_number}: expected {row['expected']}, got {actual}")
        results.append(result)
    return results, failures


def _run_delivery_fixture() -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    case = json.loads((ROOT / "fixtures" / "ready_trace_case.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "simulated-delivery.zip"
        receipt = build_delivery_bundle(case, target, now=PILOT_AT)
        with zipfile.ZipFile(target) as archive:
            names = sorted(archive.namelist())
            manifest = json.loads(archive.read("delivery-manifest.json"))
            combined = b"\n".join(archive.read(name) for name in names)
        required = {
            "brief.md", "decision-evidence.md", "decision-evidence.html",
            "decision-summary.json", "source-version-manifest.json",
            "watch-baseline.json", "delivery-manifest.json",
        }
        if set(names) != required:
            failures.append("golden delivery fixture did not contain the exact seven buyer-safe files")
        if manifest.get("external_send_authorized") is not False:
            failures.append("delivery fixture incorrectly authorized an external send")
        if manifest.get("contains_raw_case") is not False or manifest.get("contains_restricted_source_bytes") is not False:
            failures.append("delivery fixture exposed raw case or restricted source bytes")
        if b"buyer@example.com" in combined or b"Example Buyer" in combined:
            failures.append("delivery fixture exposed intake identity")
        return {
            "fixture_only": True,
            "case_id": receipt["case_id"],
            "release_state": receipt["release_state"],
            "trace_state": receipt["trace_state"],
            "files": names,
            "file_count": len(names),
            "bundle_sha256": receipt["bundle_sha256"],
            "bundle_bytes": receipt["bundle_bytes"],
            "contains_raw_case": manifest["contains_raw_case"],
            "contains_restricted_source_bytes": manifest["contains_restricted_source_bytes"],
            "external_send_authorized": manifest["external_send_authorized"],
        }, failures


def run_simulation() -> dict[str, Any]:
    intake_results, failures = _run_intake_matrix()
    delivery, delivery_failures = _run_delivery_fixture()
    failures.extend(delivery_failures)

    counts: dict[str, int] = {}
    for row in intake_results:
        counts[row["actual"]] = counts.get(row["actual"], 0) + 1
    direct = [row for row in intake_results if row["route"] == "DIRECT_CHECKOUT"]
    scope = [row for row in intake_results if row["route"] == "SCOPE_FIRST"]
    return {
        "schema_version": "1.0",
        "pilot_id": "CAPTUREBRIEF-SIMULATED-PILOT-2026-09-23",
        "simulated": True,
        "fictional_customer_numbers": True,
        "not_customer_evidence": True,
        "not_revenue_or_conversion_data": True,
        "generated_at": PILOT_AT_TEXT,
        "passed": not failures,
        "failures": failures,
        "customers_tested": len(intake_results),
        "intake_outcomes": counts,
        "route_stress_test": {
            "direct_checkout": {
                "customers": len(direct),
                "accepted_for_review": sum(row["actual"] == "ACCEPTED_FOR_REVIEW" for row in direct),
                "refund_before_work": sum(row["actual"] == "REFUND_BEFORE_WORK" for row in direct),
            },
            "scope_first": {
                "customers": len(scope),
                "accepted_for_review": sum(row["actual"] == "ACCEPTED_FOR_REVIEW" for row in scope),
                "declined_before_payment": sum(row["actual"] == "DECLINED_BEFORE_PAYMENT" for row in scope),
            },
            "interpretation": "Deliberately failure-heavy validation mix; not a forecast or funnel benchmark.",
        },
        "customer_results": intake_results,
        "golden_delivery_check": delivery,
        "release_decisions": [
            "Expose direct checkout while retaining the free pre-purchase scope check.",
            "Promise a full refund when a paid request is declined before work begins.",
            "Require public-only confirmation and no more than five distinct assumptions.",
            "Accept customer-facing PASS and normalize the legacy NO-GO label.",
            "Never treat payment, intake, or a built bundle as authority to send or decide for the buyer.",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    direct = report["route_stress_test"]["direct_checkout"]
    scope = report["route_stress_test"]["scope_first"]
    lines = [
        "# CaptureBrief simulated pilot",
        "",
        "**Status:** " + ("PASS" if report["passed"] else "FAIL"),
        "",
        "> This is a deterministic validation exercise using fictional customer numbers. It is not real customer evidence, revenue, conversion data, or a market forecast.",
        "",
        "## Pilot coverage",
        "",
        f"- {report['customers_tested']} fictional customer records tested",
        f"- {report['intake_outcomes'].get('ACCEPTED_FOR_REVIEW', 0)} accepted for human review",
        f"- {report['intake_outcomes'].get('REFUND_BEFORE_WORK', 0)} direct-checkout records correctly routed to refund before work",
        f"- {report['intake_outcomes'].get('DECLINED_BEFORE_PAYMENT', 0)} scope-first records correctly declined before payment",
        f"- {report['golden_delivery_check']['file_count']} buyer-safe files built in the golden delivery check",
        "",
        "## Direct-checkout stress route",
        "",
        f"The intentionally failure-heavy mix sent {direct['customers']} fictional buyers through direct checkout: {direct['accepted_for_review']} passed intake and {direct['refund_before_work']} triggered the pre-work refund rule. The scope-first route tested {scope['customers']} more records: {scope['accepted_for_review']} passed and {scope['declined_before_payment']} were stopped before payment.",
        "",
        "These ratios are test coverage, not expected conversion or refund rates.",
        "",
        "## Hardening decisions",
        "",
    ]
    lines.extend(f"- {item}" for item in report["release_decisions"])
    lines += [
        "",
        "## Customer matrix",
        "",
        "| Customer number | Route | Expected | Actual |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| {row['customer_number']} | {row['route']} | {row['expected']} | {row['actual']} |"
        for row in report["customer_results"]
    )
    lines += [
        "",
        "## Delivery safety check",
        "",
        f"The golden fixture built a `{report['golden_delivery_check']['release_state']}` bundle with a `{report['golden_delivery_check']['trace_state']}` trace. The bundle excludes the raw case and restricted source bytes, and it does not authorize an external send.",
        "",
    ]
    if report["failures"]:
        lines += ["## Failures", ""] + [f"- {item}" for item in report["failures"]] + [""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="simulated-pilot")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = run_simulation()
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({
        "passed": report["passed"],
        "customers_tested": report["customers_tested"],
        "intake_outcomes": report["intake_outcomes"],
        "delivery_files": report["golden_delivery_check"]["file_count"],
        "output_dir": str(output_dir),
    }, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
