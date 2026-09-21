"""CaptureBrief executable product core."""
from .audit import audit_case
from .authority import validate_current_action_receipts
from .history import make_history_receipt, validate_history_receipts
from .manifest import fetch_manifest, normalize_manifest_payload, validate_manifest_receipts
from .current_api import download_resource_from_api_observation, fetch_latest_active, make_current_action_receipt
from .data_services import collect_history_from_files, issue_history_receipt_from_snapshots, scan_extract_bytes
from .source_policy import SourcePolicyError, classify_sam_url, require_approved_automation
from .packet import build_resource_union, diff_manifest_receipts, validate_reference_closure
from .render import render_markdown
from .intake import IntakeError, build_case_from_intake
from .workqueue import build_work_queue
from .watch import compare_cases

__all__=[
    "audit_case","validate_current_action_receipts","make_history_receipt","validate_history_receipts",
    "fetch_manifest","normalize_manifest_payload","validate_manifest_receipts",
    "download_resource_from_api_observation","fetch_latest_active","make_current_action_receipt",
    "collect_history_from_files","issue_history_receipt_from_snapshots","scan_extract_bytes",
    "SourcePolicyError","classify_sam_url","require_approved_automation",
    "IntakeError","build_case_from_intake","build_work_queue",
    "build_resource_union","diff_manifest_receipts","validate_reference_closure","render_markdown","compare_cases"
]
