"""CaptureBrief executable product core."""
from .audit import audit_case
from .authority import validate_current_action_receipts
from .history import make_history_receipt, validate_history_receipts
from .manifest import download_public_resource, fetch_manifest, normalize_manifest_payload, validate_manifest_receipts
from .packet import build_resource_union, diff_manifest_receipts, validate_reference_closure
from .render import render_markdown
from .watch import compare_cases

__all__=[
    "audit_case","validate_current_action_receipts","make_history_receipt","validate_history_receipts",
    "download_public_resource","fetch_manifest","normalize_manifest_payload","validate_manifest_receipts",
    "build_resource_union","diff_manifest_receipts","validate_reference_closure","render_markdown","compare_cases"
]
