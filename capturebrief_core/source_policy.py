from __future__ import annotations

import re
from urllib.parse import urlparse, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


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
    try:
        p = urlparse(str(url or ""))
        # Exact approved hosts are not enough: credentials and nonstandard
        # ports must never enter an automated first-party collection route.
        if p.username is not None or p.password is not None or p.fragment or p.port not in (None, 443):
            return "UNAPPROVED"
        host = (p.hostname or "").lower()
        path = p.path or ""
    except (ValueError, TypeError):
        return "UNAPPROVED"

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
        # The rejected URL may contain embedded credentials, signed-query
        # tokens or private resource IDs. Never echo it in logs/exceptions.
        raise SourcePolicyError(f"automated collection disabled for source class {cls}")
    if expected and cls != expected:
        raise SourcePolicyError(f"source class {cls} does not match required class {expected}")
    return cls


# This is intentionally NOT a blanket allowlist for S3 or SAM's undocumented
# web UI. Official SAM.gov Data Services may redirect a documented public
# extract URL to the exact falextracts S3 object publicly listed by SAM.gov.
# Retain the SAM entrypoint as the source and validate EACH redirected hop.
_EXTRACT_ROOT = "/api/prod/fileextractservices/v1/api/download/"
_ORIGINAL = re.compile(
    r"^Contract%20Opportunities/(?:datagov/ContractOpportunitiesFullCSV[.]csv|"
    r"Archived%20Data/FY[0-9]{4}_archived_opportunities[.]csv)$"
)


def require_approved_extract_delivery(entrypoint: str, delivered_url: str) -> str:
    """Verify exact SAM->SAM or SAM->official-object path binding.

    Returns a non-sensitive delivery host, NEVER an accepted source authority
    for independent publisher authenticity or private SAM API membership.
    The final resource is an approved transport destination, not permission to
    automate arbitrary s3.amazonaws.com URLs.
    """
    require_approved_automation(entrypoint, expected="SAM_DATA_SERVICES_EXTRACT")
    try:
        start = urlsplit(entrypoint)
        final = urlsplit(delivered_url)
        # The official fetch contract is the public version of exactly one
        # active or archived Contract Opportunities CSV.
        suffix = start.path.removeprefix(_EXTRACT_ROOT)
        if (
            start.path == suffix or
            start.scheme != "https" or (start.hostname or "").lower() != "sam.gov"
            or start.username is not None or start.password is not None
            or start.port not in (None, 443) or start.fragment
            or start.query != "privacy=Public"
            or _ORIGINAL.fullmatch(suffix) is None
        ):
            raise SourcePolicyError("unapproved SAM Data Services starting contract")
        if final.scheme != "https" or final.username is not None or final.password is not None:
            raise SourcePolicyError("unapproved extract redirect destination")
        if final.port not in (None, 443) or final.fragment:
            raise SourcePolicyError("unapproved extract redirect destination")
        if delivered_url == entrypoint:
            return "sam.gov"
        if (
            (final.hostname or "").lower() == "s3.amazonaws.com"
            and final.path == "/falextracts/" + suffix
            and not final.query
        ):
            return "s3.amazonaws.com"
    except (TypeError, ValueError) as exc:
        raise SourcePolicyError("unapproved extract transport contract") from exc
    raise SourcePolicyError("unapproved extract redirect destination")


class _OfficialExtractRedirectGuard(HTTPRedirectHandler):
    def __init__(self, entrypoint: str) -> None:
        self._entrypoint = entrypoint
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Block EVERY unapproved hop BEFORE urllib opens it. A final-only
        # check cannot protect against an intermediate malicious redirect.
        require_approved_extract_delivery(self._entrypoint, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_approved_extract(request, *, timeout: float, source_url: str, opener=None):
    """Use a redirect-guarded production transport; allow injected test I/O."""
    require_approved_extract_delivery(source_url, source_url)
    if opener is not None:
        return opener(request, timeout=timeout)
    return build_opener(_OfficialExtractRedirectGuard(source_url)).open(request, timeout=timeout)
