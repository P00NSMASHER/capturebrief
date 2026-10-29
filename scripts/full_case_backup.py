"""Encrypt and restore a COMPLETE bounded CaptureBrief case inventory.

Reuses the established pinned AES-256-GCM/scrypt implementation but, unlike
the legacy scoped-source backup, includes report, original history, reviewed
resource/rule files, business/scope evidence, reservation registry snapshot,
and the shared one-use authorization-ledger snapshot. Every input file must
already exist in an approved owner-only private workspace. No network,
external key custody, mail, payment, approval or production-state mutation.

This tool creates an encrypted portable file. It does NOT prove an off-device
copy, separately held production recovery key, independent human review or
customer delivery. Restores always require a NEW private directory.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.accepted_case_release import (
    _file as verified_private_file, _json_file as private_json, _root as private_root,
)
from capturebrief_core.atomic_io import atomic_write_bytes, exclusive_path_lock
from scripts.scoped_private_backup import (
    _bytes, _canon, _crypto, _key, _new_file, _unique,
    KDF_N, KDF_R, KDF_P,
)

SCHEMA = "capturebrief-complete-case-encrypted-backup-v1"
INPUT_SCHEMA = "capturebrief-complete-case-backup-inventory-v1"
MAGIC = b"CAPTUREBRIEF-FULL-CASE-AESGCM-V1\x00"
MAX_HEADER = 2048
MAX_ITEMS = 100
MAX_PER_FILE = 64 * 1024 * 1024
MAX_PLAIN = 256 * 1024 * 1024
MAX_CONTAINER = MAX_PLAIN + 1024 * 1024
SHA = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$")
REQUIRED = {
    "CASE", "HISTORY", "RESOURCE_INVENTORY", "ACTION_ORIGINAL",
    "RESOURCE_ORIGINAL", "BUSINESS_EVIDENCE", "INBOUND_RECEIPT",
    "SCOPE_AGREEMENT", "REPORT", "REPORT_RECEIPT",
    "REGISTRY_SNAPSHOT", "AUTHORIZATION_LEDGER_SNAPSHOT", "MESSAGE_BODY",
}
OPTIONAL = {"INCORPORATED_RULE"}
REPEATABLE = {"ACTION_ORIGINAL", "RESOURCE_ORIGINAL", "INCORPORATED_RULE"}


def _relative(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise ValueError("Case inventory path must be a short relative file path")
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value
            or any(segment in ("", ".", "..") for segment in value.split("/"))
            or "\\" in value or ":" in value):
        raise ValueError("Case inventory path traversal refused")
    return value


def _validated_inventory(inv: dict[str, Any]) -> list[dict[str, Any]]:
    if (not isinstance(inv, dict) or set(inv) != {
            "schema", "case_id", "files", "customer_release_authorized",
            "external_send_authorized"
        } or inv.get("schema") != INPUT_SCHEMA
            or inv.get("customer_release_authorized") is not False
            or inv.get("external_send_authorized") is not False
            or not isinstance(inv.get("case_id"), str)
            or not 2 <= len(inv["case_id"]) <= 120):
        raise ValueError("Inventory has unsupported shape or claims customer release")
    items = inv.get("files")
    if not isinstance(items, list) or not len(REQUIRED) <= len(items) <= MAX_ITEMS:
        raise ValueError("Complete bounded private-case file inventory missing")
    ids: set[str] = set()
    paths: set[str] = set()
    kinds: dict[str, int] = {}
    checked: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "kind", "path", "sha256"}:
            raise ValueError("Inventory contains unknown or missing fields")
        fid,kind,relative,sha = (
            item["id"], item["kind"], _relative(item["path"]), item["sha256"]
        )
        if (not isinstance(fid,str) or not ID.fullmatch(fid)
                or fid in ids or relative in paths
                or kind not in REQUIRED|OPTIONAL
                or not isinstance(sha,str) or not SHA.fullmatch(sha)):
            raise ValueError("Duplicate, unknown or malformed inventory original")
        ids.add(fid);paths.add(relative)
        kinds[kind] = kinds.get(kind,0)+1
        checked.append(item)
    if (any(kinds.get(k,0) < 1 for k in REQUIRED)
            or any(v != 1 for k,v in kinds.items() if k not in REPEATABLE)):
        raise ValueError("Complete case requires exactly one of every singleton and originals")
    return sorted(checked, key=lambda item: item["id"])


def _collect(root: Path, input_file: Path) -> tuple[str,list[tuple[dict[str,Any],bytes]]]:
    if not input_file.is_relative_to(root):
        raise ValueError("Case source inventory must be inside the private case root")
    inv = private_json(input_file)
    entries = _validated_inventory(inv)
    loaded = []
    total = 0
    for item in entries:
        content = verified_private_file(root, item["path"], item["sha256"],
                                        limit=MAX_PER_FILE)
        total += len(content)
        if total > MAX_PLAIN - 1024 * 1024:
            raise ValueError("Complete case source bytes exceed secure backup limit")
        loaded.append((item,content))
    return inv["case_id"], loaded


def _plain(case_id: str, loaded: list[tuple[dict[str,Any],bytes]]) -> bytes:
    manifest = {
        "schema": SCHEMA, "case_id": case_id,
        "files": [{**row, "bytes":len(content)} for row,content in loaded],
        "source_history_approval_inferred": False,
        "independent_offdevice_restore_proven": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_STORED,
                         allowZip64=False) as archive:
        archive.writestr("manifest.json",_canon(manifest))
        for index,(_,content) in enumerate(loaded):
            archive.writestr(f"payload/{index:04d}.bin",content)
    output = buffer.getvalue()
    if len(output)>MAX_PLAIN:
        raise ValueError("Encrypted original inventory exceeds capped memory footprint")
    return output


def create_complete_backup(
    root_path: str|Path, inventory_file: str|Path, output_file: str|Path,
    passphrase: bytes,
) -> dict[str,Any]:
    root = private_root(root_path)
    case_id,loaded = _collect(root,Path(inventory_file).expanduser().absolute())
    target = _new_file(output_file)
    plain = _plain(case_id,loaded)
    AESGCM,_ = _crypto()
    salt,nonce = os.urandom(16),os.urandom(12)
    header = {
        "schema":SCHEMA, "cipher":"AES-256-GCM", "kdf":"scrypt",
        "n":KDF_N,"r":KDF_R,"p":KDF_P,
        "salt_b64":base64.b64encode(salt).decode("ascii"),
        "nonce_b64":base64.b64encode(nonce).decode("ascii"),
        "plaintext_sha256":hashlib.sha256(plain).hexdigest(),
        "plaintext_bytes":len(plain),
    }
    head = _canon(header)
    if len(head)>MAX_HEADER:
        raise ValueError("Complete case backup header is oversized")
    prefix = MAGIC+struct.pack(">I",len(head))+head
    ciphertext = AESGCM(_key(passphrase,salt)).encrypt(nonce,plain,prefix)
    atomic_write_bytes(target,prefix+ciphertext,overwrite=False,mode=0o600)
    return {
        "status":"FULL_CASE_LOCAL_ENCRYPTED_BACKUP_CREATED",
        "backup_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
        "file_count":len(loaded),
        "offdevice_copy_verified":False,
        "independent_restore_verified":False,
        "recovery_key_custody_verified":False,
        "customer_release_authorized":False,
        "external_send_authorized":False,
    }


def _open_complete(
    source: str|Path,passphrase: bytes,
) -> tuple[str,list[tuple[dict[str,Any],bytes]]]:
    backup = Path(source).expanduser().absolute()
    private_root(backup.parent)
    if backup.suffix != ".cbak" or backup.is_symlink() or not backup.is_file():
        raise ValueError("Encrypted case archive must be an existing private .cbak file")
    if os.name != "nt" and backup.stat().st_mode & 0o077:
        raise ValueError("Encrypted backup file cannot be accessible by other users")
    raw = _bytes(backup, MAX_CONTAINER+MAX_HEADER+len(MAGIC)+128)
    offset=len(MAGIC)
    if not raw.startswith(MAGIC) or len(raw)<offset+4+16:
        raise ValueError("Unsupported or truncated complete-case backup")
    head_length=struct.unpack(">I",raw[offset:offset+4])[0]
    if not 0<head_length<=MAX_HEADER or len(raw)<offset+4+head_length+16:
        raise ValueError("Encrypted backup header length invalid")
    head=raw[offset+4:offset+4+head_length]
    header=json.loads(head.decode("utf-8"),object_pairs_hook=_unique)
    if (not isinstance(header,dict) or set(header)!={
        "schema","cipher","kdf","n","r","p","salt_b64","nonce_b64",
        "plaintext_sha256","plaintext_bytes"
    } or _canon(header)!=head or header["schema"]!=SCHEMA
        or header["cipher"]!="AES-256-GCM" or header["kdf"]!="scrypt"
        or (header["n"],header["r"],header["p"])!=(KDF_N,KDF_R,KDF_P)
        or type(header["plaintext_bytes"]) is not int
        or not 0<header["plaintext_bytes"]<=MAX_PLAIN):
        raise ValueError("Unsupported complete backup authenticated header")
    try:
        salt=base64.b64decode(header["salt_b64"],validate=True)
        nonce=base64.b64decode(header["nonce_b64"],validate=True)
    except (ValueError,TypeError):
        raise ValueError("Backup salt/nonce encoding invalid") from None
    if len(salt)!=16 or len(nonce)!=12:
        raise ValueError("Backup KDF salt/nonce size invalid")
    AESGCM,_ = _crypto()
    start=offset+4+head_length
    plain=AESGCM(_key(passphrase,salt)).decrypt(nonce,raw[start:],raw[:start])
    if (len(plain)!=header["plaintext_bytes"]
            or hashlib.sha256(plain).hexdigest()!=header["plaintext_sha256"]):
        raise ValueError("Decrypted backup original content hash invalid")
    with zipfile.ZipFile(io.BytesIO(plain)) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or not 1+len(REQUIRED)<=len(names)<=MAX_ITEMS+1:
            raise ValueError("Encrypted backup ZIP has duplicate or missing entries")
        if archive.getinfo("manifest.json").file_size>128*1024:
            raise ValueError("Encrypted case manifest is oversized")
        manifest=json.loads(archive.read("manifest.json"),object_pairs_hook=_unique)
        if (not isinstance(manifest,dict) or set(manifest)!={
            "schema","case_id","files","source_history_approval_inferred",
            "independent_offdevice_restore_proven","customer_release_authorized",
            "external_send_authorized"
        } or manifest["schema"]!=SCHEMA
            or any(manifest[key] is not False for key in (
                "source_history_approval_inferred","independent_offdevice_restore_proven",
                "customer_release_authorized","external_send_authorized"
            ))):
            raise ValueError("Backup claims unproved history or customer release")
        rows=manifest.get("files")
        if not isinstance(rows,list):
            raise ValueError("Invalid backup original inventory")
        input_inv={
            "schema":INPUT_SCHEMA,"case_id":manifest.get("case_id"),
            "files":[{k:row.get(k) for k in ("id","kind","path","sha256")}
                     for row in rows if isinstance(row,dict)],
            "customer_release_authorized":False,"external_send_authorized":False,
        }
        expected=_validated_inventory(input_inv)
        if len(expected)!=len(rows) or len(names)!=1+len(rows):
            raise ValueError("Backup manifest differs from archived original set")
        if set(names)!={"manifest.json"} | {
            f"payload/{i:04d}.bin" for i in range(len(rows))
        }:
            raise ValueError("Backup has unexpected filenames or paths")
        loaded=[]
        total=0
        for i,row in enumerate(rows):
            if (not isinstance(row,dict) or set(row)!={"id","kind","path","sha256","bytes"}
                    or type(row["bytes"]) is not int or not 0<row["bytes"]<=MAX_PER_FILE
                    or row["id"]!=expected[i]["id"]):
                raise ValueError("Backup row metadata malformed")
            name=f"payload/{i:04d}.bin"
            info=archive.getinfo(name)
            if (info.compress_type!=zipfile.ZIP_STORED or info.file_size!=row["bytes"]
                    or info.compress_size!=row["bytes"]):
                raise ValueError("Encrypted ZIP has incompatible or oversized source member")
            total+=row["bytes"]
            if total>MAX_PLAIN:
                raise ValueError("Backup restored total exceeds security bound")
            data=archive.read(name)
            if hashlib.sha256(data).hexdigest()!=row["sha256"]:
                raise ValueError("Backup's original source hash mismatch")
            loaded.append((expected[i],data))
    return manifest["case_id"],loaded


def verify_complete_backup(source: str|Path,passphrase:bytes) -> dict[str,Any]:
    case_id,loaded=_open_complete(source,passphrase)
    return {
        "status":"FULL_CASE_ENCRYPTED_BYTES_REVERIFIED",
        "case_tag":hashlib.sha256(case_id.encode()).hexdigest()[:16],
        "file_count":len(loaded),
        "offdevice_restore_proven":False,
        "customer_release_authorized":False,"external_send_authorized":False,
    }


def restore_complete_backup(
    source: str|Path,destination: str|Path,passphrase:bytes,
) -> dict[str,Any]:
    case_id,loaded=_open_complete(source,passphrase)
    target=Path(destination).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("Restore destination must be a new private directory")
    parent=private_root(target.parent)
    with exclusive_path_lock(target,timeout_seconds=5,suffix=".full-restore.lock"):
        if target.exists() or target.is_symlink():
            raise ValueError("Concurrent restore destination already exists")
        temp=Path(tempfile.mkdtemp(prefix=".complete-restore-",dir=parent))
        try:
            for row,data in loaded:
                relative=_relative(row["path"])
                dest=temp.joinpath(*PurePosixPath(relative).parts)
                dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                atomic_write_bytes(dest,data,overwrite=False,mode=0o600)
            os.rename(temp,target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    return {
        "status":"FULL_CASE_LOCALLY_RESTORED_NEW_DIRECTORY_RECONCILIATION_REQUIRED",
        "case_tag":hashlib.sha256(case_id.encode()).hexdigest()[:16],
        "file_count":len(loaded),
        "restored_files":{row["id"]:hashlib.sha256(data).hexdigest()
                          for row,data in loaded},
        "independent_offdevice_restore_proven":False,
        "production_key_custody_verified":False,
        "customer_release_authorized":False,"external_send_authorized":False,
    }


def main(argv: list[str]|None=None) -> int:
    import getpass
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    create=sub.add_parser("create")
    create.add_argument("--private-root",required=True)
    create.add_argument("--inventory",required=True)
    create.add_argument("--backup-file",required=True)
    check=sub.add_parser("verify")
    check.add_argument("--backup-file",required=True)
    restore=sub.add_parser("restore")
    restore.add_argument("--backup-file",required=True)
    restore.add_argument("--output-dir",required=True)
    args=parser.parse_args(argv)
    # Never take a passphrase from argv, env, GitHub secrets or chat.
    phrase=getpass.getpass("Independently held complete-case recovery phrase: ").encode("utf-8")
    try:
        if args.action=="create":
            result=create_complete_backup(args.private_root,args.inventory,args.backup_file,phrase)
        elif args.action=="verify":
            result=verify_complete_backup(args.backup_file,phrase)
        else:
            result=restore_complete_backup(args.backup_file,args.output_dir,phrase)
    except Exception:
        # Customer paths, contact fields, signed URLs or the phrase may exist
        # in exception context. Print a fixed fail-closed response only.
        print(json.dumps({"status":"FULL_CASE_BACKUP_OR_RESTORE_BLOCKED",
                          "customer_release_authorized":False,
                          "external_send_authorized":False}))
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
