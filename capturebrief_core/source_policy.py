from __future__ import annotations

from urllib.parse import urlparse


class SourcePolicyError(RuntimeError):
    """Raised when code attempts automated collection from a non-approved SAM surface."""


APPROVED_AUTOMATION_CLASSES = {
    "SAM_PUBLIC_API",
    "SAM_DATA_SERVICES_EXTRACT",
    "SAM_API_RESOURCE_LINK",
}


def classify_sam_url(url: str) -> str:
    """Classify SAM/GSA URLs by the collection contract CaptureBrief is allowed to automate.

    CaptureBrief intentionally does not treat a technically public web-UI endpoint as an
    approved automation source. Public APIs and Data Services extracts are separate contracts.
    """
    p = urlparse(str(url or ""))
    host = (p.hostname or "").lower()
    path = p.path or ""

    if p.scheme != "https":
        return "UNAPPROVED"

    if host == "api.sam.gov" and (
        path.startswith("/opportunities/v2/")
        or path.startswith("/prod/opportunities/v2/")
        or path.startswith("/prod/opportunities/v1/noticedesc")
    ):
        return "SAM_PUBLIC_API"

    if host == "sam.gov" and path.startswith("/api/prod/fileextractservices/v1/api/download/Contract%20Opportunities/"):
        return "SAM_DATA_SERVICES_EXTRACT"

    # Attachment URLs returned by the documented Opportunities API may currently use this
    # host/path family. They are allowed only when explicitly bound to an approved API receipt.
    if host == "sam.gov" and path.startswith("/api/prod/opps/v3/opportunities/resources/files/") and path.endswith("/download"):
        return "SAM_API_RESOURCE_LINK"

    if host == "sam.gov" and path.startswith("/api/prod/opps/v3/opportunities/"):
        return "SAM_WEB_UI_UNDOCUMENTED"

    if host == "sam.gov" and path.startswith("/data-services/"):
        return "SAM_DATA_SERVICES_UI"

    return "UNAPPROVED"


def require_approved_automation(url: str, *, expected: str | None = None) -> str:
    cls = classify_sam_url(url)
    if cls not in APPROVED_AUTOMATION_CLASSES:
        raise SourcePolicyError(f"automated collection disabled for source class {cls}: {url}")
    if expected and cls != expected:
        raise SourcePolicyError(f"source class {cls} does not match required class {expected}")
    return cls
