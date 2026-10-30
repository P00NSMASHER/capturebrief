"""Encrypted, content-addressed backup transport to CaptureBrief's PRIVATE GitHub state.

Follows PermitPlate's existing private-GitHub storage model, but NEVER writes
CaptureBrief evidence into P00NSMASHER/permitplate-state or public repositories.

Operator-initiated only: no Actions secrets required for CI, no customer data
in GitHub Actions, no background uploads, no payments, and no external messages.
Only encrypted .cbak bytes are uploaded, in an independent private repository.

This transport cannot authenticate an AES-GCM backup without the separate
recovery key. Run the existing full_case_backup.py verify on the trusted source
workstation first. A remote byte hash is NOT an independent-device restore.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import struct
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from capturebrief_core.accepted_case_release import _root, _reject_private_path_links
from capturebrief_core.atomic_io import atomic_write_bytes
from scripts.full_case_backup import MAGIC, MAX_HEADER, MAX_PLAIN, SCHEMA
from scripts.scoped_private_backup import KDF_N, KDF_R, KDF_P, _canon, _unique

# Same EXISTING GitHub private-cloud provider as PermitPlate; never its dataset.
# A dedicated private repository is essential because GitHub tokens have
# repository-level, not folder-level, Contents permissions.
DESTINATION_REPOSITORY = "P00NSMASHER/capturebrief-state"
FORBIDDEN_REPOSITORIES = {
    "P00NSMASHER/permitplate-state",
    "P00NSMASHER/permitplate-nyc",
    "P00NSMASHER/capturebrief",
}
API_PREFIX = "/repos/" + DESTINATION_REPOSITORY
MAX_ENCRYPTED_BYTES = 900_000  # GitHub Contents API bounded <= 1MB readback
MAX_API_RESPONSE = 2_200_000
MAX_REPOSITORY_KB = 40_000  # No silent unbounded paid/cloud consumption
# A prospective Git commit consumes more than the ciphertext payload alone.
# GitHub's repository size is approximate and can lag; this is a conservative
# pre-upload budget gate, NOT evidence of provider billing or account quota.
NEW_COMMIT_OVERHEAD_KB = 128
NEW_COMMIT_PAYLOAD_FACTOR = 2
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PrivateStorageBlocked(ValueError):
    """Fail closed before writing, or when remote verification is incomplete."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PrivateStorageBlocked("Private provider redirected unexpectedly")


def github_request(
    method: str, path: str, token: str, document: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any] | None]:
    """A strict api.github.com-only transport. Never prints token or raw errors."""
    if (method not in {"GET", "PUT"} or not path.startswith(API_PREFIX)
            or not re.fullmatch(r"[A-Za-z0-9_./?=&-]+", path)
            or not isinstance(token, str) or not token.strip()):
        raise PrivateStorageBlocked("Invalid private provider request contract")
    data = (json.dumps(document, separators=(",", ":")).encode()
            if document is not None else None)
    if method == "GET" and data is not None:
        raise PrivateStorageBlocked("Unexpected GET payload")
    url = "https://api.github.com" + path
    request = Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CaptureBrief-Private-Ciphertext-Custody",
        **({"Content-Type": "application/json"} if data is not None else {}),
    })
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            payload = response.read(MAX_API_RESPONSE + 1)
            if len(payload) > MAX_API_RESPONSE:
                raise PrivateStorageBlocked("Private provider returned oversized data")
            return response.status, json.loads(payload.decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return 404, None
        # GitHub API errors can contain path, credential or private state.
        raise PrivateStorageBlocked("Private GitHub operation refused") from None
    except (URLError, UnicodeError, ValueError, OSError):
        raise PrivateStorageBlocked("Private GitHub operation unavailable") from None


def _call(
    transport: Callable[..., tuple[int, dict[str, Any] | None]],
    method: str, path: str, token: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any] | None]:
    try:
        return transport(method, path, token, body)
    except PrivateStorageBlocked:
        raise
    except Exception:
        raise PrivateStorageBlocked("Private provider operation could not be verified") from None


def _token(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrivateStorageBlocked("Dedicated CaptureBrief private GitHub token unavailable")
    return value


def inspect_private_destination(
    token: str, *, transport: Callable[..., tuple[int, dict[str, Any] | None]] = github_request
) -> dict[str, Any]:
    """Verify the dedicated, separately permissioned private repo, no mutations."""
    token = _token(token)
    if DESTINATION_REPOSITORY in FORBIDDEN_REPOSITORIES:
        raise PrivateStorageBlocked("Customer datasets must not share PermitPlate or public Git")
    code, data = _call(transport, "GET", API_PREFIX, token)
    if code == 404:
        raise PrivateStorageBlocked("Dedicated CaptureBrief private state repository not provisioned")
    if (code != 200 or not isinstance(data, dict)
            or data.get("full_name") != DESTINATION_REPOSITORY
            or data.get("private") is not True
            or data.get("visibility") != "private"
            or data.get("default_branch") != "main"
            or data.get("archived") is True
            or data.get("disabled") is True
            or data.get("fork") is True):
        raise PrivateStorageBlocked("Private provider ownership, visibility or branch not approved")
    size = data.get("size")
    if type(size) is not int or not 0 <= size <= MAX_REPOSITORY_KB:
        raise PrivateStorageBlocked("Private repository storage exceeds bounded free pilot allowance")
    permissions = data.get("permissions")
    if permissions is not None and (
        not isinstance(permissions, dict) or permissions.get("push") is not True
    ):
        raise PrivateStorageBlocked("Dedicated private repository write permission unverified")
    return {
        "status": "CAPTUREBRIEF_PRIVATE_GITHUB_DESTINATION_VERIFIED",
        "destination": DESTINATION_REPOSITORY,
        "same_provider_as_permitplate": True,
        "separate_from_permitplate_state": True,
        "private_repo_verified": True,
        "observed_repository_kb": size,
        "production_backup_present": False,
        "independent_device_restore_verified": False,
        "recovery_key_custody_verified": False,
        "customer_release_authorized": False,
    }



def _validate_complete_case_envelope(raw: bytes) -> None:
    """Bounded keyless format validation, NOT AES-GCM authentication.

    Only full_case_backup.py verify with the separately retained recovery
    phrase authenticates the original encrypted sources and the GCM tag.
    This catches plaintext prepended with the public format magic before any
    remote write and rejects malformed files on retrieval.
    """
    start = len(MAGIC)
    if (not isinstance(raw, bytes) or not raw.startswith(MAGIC)
            or len(raw) < start + 4 + 16):
        raise PrivateStorageBlocked("Incomplete full-case encrypted envelope")
    head_length = struct.unpack(">I", raw[start:start + 4])[0]
    end = start + 4 + head_length
    if not 0 < head_length <= MAX_HEADER or len(raw) < end + 16:
        raise PrivateStorageBlocked("Full-case encrypted envelope header missing")
    head = raw[start + 4:end]
    try:
        header = json.loads(head.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeError, ValueError, TypeError):
        raise PrivateStorageBlocked("Full-case encrypted envelope metadata invalid") from None
    fields = {
        "schema", "cipher", "kdf", "n", "r", "p", "salt_b64",
        "nonce_b64", "plaintext_sha256", "plaintext_bytes",
    }
    if (not isinstance(header, dict) or set(header) != fields
            or _canon(header) != head
            or header["schema"] != SCHEMA
            or header["cipher"] != "AES-256-GCM"
            or header["kdf"] != "scrypt"
            or any(type(header[k]) is not int for k in ("n", "r", "p"))
            or (header["n"], header["r"], header["p"]) != (KDF_N, KDF_R, KDF_P)
            or type(header["plaintext_bytes"]) is not int
            or not 0 < header["plaintext_bytes"] <= MAX_PLAIN
            or not isinstance(header["plaintext_sha256"], str)
            or not HEX64.fullmatch(header["plaintext_sha256"])
            or len(raw) != end + header["plaintext_bytes"] + 16):
        raise PrivateStorageBlocked("Full-case encrypted envelope is inconsistent")
    try:
        salt = base64.b64decode(header["salt_b64"], validate=True)
        nonce = base64.b64decode(header["nonce_b64"], validate=True)
    except (TypeError, ValueError, binascii.Error):
        raise PrivateStorageBlocked("Full-case encrypted envelope salt/nonce invalid") from None
    if (len(salt) != 16 or len(nonce) != 12
            or base64.b64encode(salt).decode("ascii") != header["salt_b64"]
            or base64.b64encode(nonce).decode("ascii") != header["nonce_b64"]):
        raise PrivateStorageBlocked("Full-case encrypted envelope salt/nonce malformed")

def _remote_path(digest: str) -> str:
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        raise PrivateStorageBlocked("Exact encrypted backup SHA-256 required")
    return f"{API_PREFIX}/contents/encrypted/complete-case/v1/{digest[:2]}/{digest}.cbak?ref=main"


def _put_path(digest: str) -> str:
    return _remote_path(digest).split("?")[0]


def _read_remote(
    digest: str, token: str,
    transport: Callable[..., tuple[int, dict[str, Any] | None]]
) -> bytes | None:
    code, result = _call(transport, "GET", _remote_path(digest), token)
    if code == 404:
        return None
    if (code != 200 or not isinstance(result, dict)
            or result.get("type") != "file"
            or result.get("path") != _remote_path(digest).split("/contents/")[1].split("?")[0]
            or result.get("encoding") != "base64"
            or not isinstance(result.get("content"), str)
            or type(result.get("size")) is not int
            or not 0 < result["size"] <= MAX_ENCRYPTED_BYTES):
        raise PrivateStorageBlocked("Remote encrypted file metadata inconsistent")
    try:
        raw = base64.b64decode(
            "".join(result["content"].split()), validate=True
        )
    except (ValueError, TypeError):
        raise PrivateStorageBlocked("Remote ciphertext encoding invalid") from None
    if (len(raw) != result["size"] or
            hashlib.sha256(raw).hexdigest() != digest or
            not raw.startswith(MAGIC)):
        raise PrivateStorageBlocked("Remote ciphertext does not match content-addressed identity")
    _validate_complete_case_envelope(raw)
    return raw


def _source_bytes(path: str | Path) -> bytes:
    target = Path(path).expanduser().absolute()
    _reject_private_path_links(target)
    _root(target.parent)
    if target.suffix != ".cbak" or not target.is_file():
        raise PrivateStorageBlocked("Verified encrypted .cbak input required")
    before = target.stat()
    if (os.name != "nt" and before.st_mode & 0o077
            or not 0 < before.st_size <= MAX_ENCRYPTED_BYTES):
        raise PrivateStorageBlocked("Ciphertext must be owner-only and under the pilot size cap")
    raw = target.read_bytes()
    after = target.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ):
        raise PrivateStorageBlocked("Encrypted file changed during inspection")
    if len(raw) != before.st_size or not raw.startswith(MAGIC):
        raise PrivateStorageBlocked("Source is not a complete-case encrypted backup")
    _validate_complete_case_envelope(raw)
    return raw


def store_encrypted_backup(
    path: str | Path, token: str, *,
    transport: Callable[..., tuple[int, dict[str, Any] | None]] = github_request
) -> dict[str, Any]:
    """Immutable upload, followed by authenticated same-provider readback."""
    token = _token(token)
    inspect_private_destination(token, transport=transport)
    raw = _source_bytes(path)
    digest = hashlib.sha256(raw).hexdigest()
    old = _read_remote(digest, token, transport)
    if old is None:
        # Recheck immediately before the prospective mutation: initial
        # preflight only establishes that the repo is currently under budget.
        # Metadata may lag or race with unrelated writers, so it cannot be
        # treated as a guarantee against cloud-billing or quota changes.
        fresh = inspect_private_destination(token, transport=transport)
        reserved_kb = NEW_COMMIT_OVERHEAD_KB + (
            NEW_COMMIT_PAYLOAD_FACTOR * len(raw) + 1023
        ) // 1024
        if fresh["observed_repository_kb"] + reserved_kb > MAX_REPOSITORY_KB:
            raise PrivateStorageBlocked(
                "Insufficient verified private GitHub repository headroom"
            )
        body = {
            "message": "CaptureBrief immutable encrypted backup " + digest[:12],
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": "main",
        }
        code, response = _call(transport, "PUT", _put_path(digest), token, body)
        if (code != 201 or not isinstance(response, dict) or
                not isinstance(response.get("content"), dict) or
                response["content"].get("path") !=
                _put_path(digest).split("/contents/")[1]):
            raise PrivateStorageBlocked("Remote immutable ciphertext commit was not confirmed")
    # A successful PUT alone is insufficient; re-read actual GitHub bytes.
    replay = _read_remote(digest, token, transport)
    if replay != raw:
        raise PrivateStorageBlocked("Remote encrypted backup byte-for-byte readback failed")
    return {
        "status": "ENCRYPTED_PRIVATE_GITHUB_READBACK_VERIFIED",
        "sha256": digest, "bytes": len(raw),
        "new_write": old is None,
        "private_destination": DESTINATION_REPOSITORY,
        "permitplate_records_untouched": True,
        "production_restore_verified": False,
        "independent_key_custody_verified": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def retrieve_encrypted_backup(
    digest: str, destination: str | Path, token: str, *,
    transport: Callable[..., tuple[int, dict[str, Any] | None]] = github_request
) -> dict[str, Any]:
    """Only writes ciphertext to a fresh owner-only local path, never decrypts."""
    token = _token(token)
    inspect_private_destination(token, transport=transport)
    output = Path(destination).expanduser().absolute()
    _reject_private_path_links(output)
    _root(output.parent)
    if output.suffix != ".cbak" or output.exists() or output.is_symlink():
        raise PrivateStorageBlocked("Retrieval requires a new private .cbak destination")
    raw = _read_remote(digest, token, transport)
    if raw is None:
        raise PrivateStorageBlocked("Content-addressed encrypted backup absent")
    atomic_write_bytes(output, raw, overwrite=False, mode=0o600)
    return {
        "status": "PRIVATE_GITHUB_CIPHERTEXT_RETRIEVED",
        "sha256": digest, "bytes": len(raw),
        "independent_device_restore_verified": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("preflight")
    upload = actions.add_parser("upload")
    upload.add_argument("--encrypted-case", required=True)
    upload.add_argument("--approve-upload", action="store_true",
                        help="Explicitly commit only encrypted bytes to dedicated private storage")
    retrieve = actions.add_parser("retrieve")
    retrieve.add_argument("--sha256", required=True)
    retrieve.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        token = _token(os.environ.get("CAPTUREBRIEF_STATE_TOKEN", ""))
        if args.action == "preflight":
            result = inspect_private_destination(token)
        elif args.action == "upload":
            if args.approve_upload is not True:
                raise PrivateStorageBlocked("Encrypted private-cloud write requires explicit approval")
            result = store_encrypted_backup(args.encrypted_case, token)
        else:
            result = retrieve_encrypted_backup(args.sha256, args.output, token)
    except (PrivateStorageBlocked, OSError, ValueError, TypeError):
        print(json.dumps({
            "status": "PRIVATE_CLOUD_BACKUP_BLOCKED",
            "customer_release_authorized": False,
            "external_send_performed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
