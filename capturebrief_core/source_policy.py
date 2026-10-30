from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlparse, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


class SourcePolicyError(RuntimeError):
    """Raised when code attempts automated collection from a non-approved SAM surface."""


APPROVED_AUTOMATION_CLASSES = {
    "SAM_PUBLIC_API",
    "SAM_DATA_SERVICES_EXTRACT",
    "SAM_API_RESOURCE_LINK",
}

# Only these TWO first-party CSV families are permitted to support an
# automated historical-extract source contract, always in PUBLIC mode.
_EXTRACT_ROOT = "/api/prod/fileextractservices/v1/api/download/"
_ORIGINAL = re.compile(
    r"^Contract%20Opportunities/(?:datagov/ContractOpportunitiesFullCSV[.]csv|"
    r"Archived%20Data/FY[0-9]{4}_archived_opportunities[.]csv)$"
)


def classify_sam_url(url: str) -> str:
    """Classify SAM/GSA URLs by the collection contract CaptureBrief is allowed to automate.

    CaptureBrief intentionally does not treat a technically public web-UI endpoint as an
    approved automation source. Public APIs and Data Services extracts are separate contracts.
    """
    # urllib.parse silently discards leading C0/space and embedded CR/LF/TAB.
    # Never authorize a reconstructed URL as the original publisher source.
    # First-party HTTP URLs are ASCII; non-ASCII data must be percent-encoded.
    if (not isinstance(url, str) or not url or not url.isascii()
            or any(ord(char) < 0x21 or ord(char) >= 0x7f or char == "\\" for char in url)):
        return "UNAPPROVED"
    try:
        p = urlparse(url)
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

    if (host == "sam.gov" and path.startswith(_EXTRACT_ROOT)
            and p.query == "privacy=Public"
            and _ORIGINAL.fullmatch(path.removeprefix(_EXTRACT_ROOT)) is not None):
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


# The live first-party SAM.gov Data Services endpoint was observed to
# return HTTP 303 to an Amazon S3 Signature V4 *presigned* object, rather than
# the earlier unsigned public listing URL. Scope this to the exact official
# bucket, exact source-relative file path, known temporary signing fields,
# S3 request scope and a currently valid short-lived signature. This is
# transport verification only; publisher/authenticity and catalog approval
# remain separate immutable source-review requirements.
_PRESIGNED_FIELDS = frozenset({
    "X-Amz-Algorithm", "X-Amz-Date", "X-Amz-SignedHeaders",
    "X-Amz-Credential", "X-Amz-Expires", "X-Amz-Signature",
})


def _authorized_falextracts_presigned_redirect(final, *, source_suffix: str) -> bool:
    if (final.hostname or "").lower() != "falextracts.s3.amazonaws.com":
        return False
    if final.path != "/" + source_suffix:
        return False
    try:
        fields = parse_qsl(final.query, keep_blank_values=True,
                           strict_parsing=True, max_num_fields=8)
        values = dict(fields)
        if len(fields) != 6 or set(values) != _PRESIGNED_FIELDS:
            return False
        if (values["X-Amz-Algorithm"] != "AWS4-HMAC-SHA256" or
                values["X-Amz-SignedHeaders"] != "host" or
                re.fullmatch(r"[0-9a-f]{64}", values["X-Amz-Signature"]) is None):
            return False
        raw_date = values["X-Amz-Date"]
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", raw_date):
            return False
        signed_at = datetime.strptime(raw_date, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc)
        raw_expires = values["X-Amz-Expires"]
        if not raw_expires.isdecimal() or len(raw_expires) > 6:
            return False
        lifespan = int(raw_expires)
        if not 1 <= lifespan <= 3600:
            return False
        credentials = values["X-Amz-Credential"].split("/")
        if (len(credentials) != 5 or
                re.fullmatch(r"[A-Z0-9]{16,64}", credentials[0]) is None or
                credentials[1] != raw_date[:8] or
                re.fullmatch(r"[a-z0-9-]{4,24}", credentials[2]) is None or
                credentials[3:] != ["s3", "aws4_request"]):
            return False
        now = datetime.now(timezone.utc)
        if signed_at > now + timedelta(minutes=5):
            return False
        if signed_at + timedelta(seconds=lifespan, minutes=5) < now:
            return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


# This is intentionally NOT a blanket allowlist for S3 or SAM's undocumented
# web UI. Official SAM.gov Data Services may redirect a documented public
# extract URL to the exact falextracts S3 object publicly listed by SAM.gov.
# Retain the SAM entrypoint as the source and validate EACH redirected hop.
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
        if _authorized_falextracts_presigned_redirect(final, source_suffix=suffix):
            return "falextracts.s3.amazonaws.com"
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
