"""CaptureBrief executable product core."""
from .archive_catalog import catalog_snapshot
from .audit import audit_case
from .authority import validate_current_action_receipts
from .history import make_history_receipt, validate_history_receipts
from .manifest import fetch_manifest, normalize_manifest_payload, validate_manifest_receipts
from .current_api import download_resource_from_api_observation, fetch_latest_active, make_current_action_receipt
from .case_current import CaseCurrentError, apply_current_api_observation
from .data_services import collect_history_from_files, issue_history_receipt_from_snapshots, scan_extract_bytes
from .history_index import (
    fetch_and_ingest_slot, index_status, ingest_extract_file,
    issue_history_receipt_from_index, sync_plan,
)
from .history_sync import sync_missing_slots
from .opportunity_ref import OpportunityReferenceError, parse_opportunity_reference
from .resolver import attach_history_resolution, resolve_reference_from_index
from .source_policy import SourcePolicyError, classify_sam_url, require_approved_automation
from .packet import build_resource_union, diff_manifest_receipts, validate_reference_closure
from .references import ReferenceReviewError, confirm_reference_scan, propose_reference_scan
from .render import render_markdown
from .intake import IntakeError, build_case_from_intake
from .workqueue import build_work_queue
from .watch import compare_cases

__all__=[
    "catalog_snapshot","audit_case","validate_current_action_receipts","make_history_receipt","validate_history_receipts",
    "fetch_manifest","normalize_manifest_payload","validate_manifest_receipts",
    "download_resource_from_api_observation","fetch_latest_active","make_current_action_receipt","CaseCurrentError","apply_current_api_observation",
    "collect_history_from_files","issue_history_receipt_from_snapshots","scan_extract_bytes",
    "fetch_and_ingest_slot","index_status","ingest_extract_file","issue_history_receipt_from_index","sync_plan","sync_missing_slots",
    "OpportunityReferenceError","parse_opportunity_reference","attach_history_resolution","resolve_reference_from_index",
    "SourcePolicyError","classify_sam_url","require_approved_automation",
    "IntakeError","build_case_from_intake","build_work_queue",
    "build_resource_union","diff_manifest_receipts","validate_reference_closure",
    "ReferenceReviewError","confirm_reference_scan","propose_reference_scan",
    "render_markdown","compare_cases"
]
