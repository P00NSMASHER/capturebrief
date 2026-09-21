"""Deterministic, self-verifying public release artifact for CaptureBrief."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .atomic_io import fsync_directory
from .model import canonical_json, sha256_hex

RELEASE_SCHEMA="capturebrief-public-release-v1"
FIXED_ZIP_TIME=(1980,1,1,0,0,0)
COMMIT_RE=re.compile(r"^[0-9a-f]{40}$")
PUBLIC_ROOT={
    "404.html",
    "_headers",
    "_redirects",
    "data-handling.html",
    "decision-evidence-sample.html",
    "favicon.svg",
    "index.html",
    "privacy.html",
    "robots.txt",
    "sample.html",
    "site.webmanifest",
    "sitemap.xml",
    "terms.html",
    "thanks.html",
    "assets",
}


class PublicReleaseError(RuntimeError):
    pass


def _file_hash(path: Path) -> tuple[str,int]:
    h=hashlib.sha256(); size=0
    with path.open("rb") as stream:
        while True:
            chunk=stream.read(1024*1024)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    return h.hexdigest(),size


def _scan_dist(dist: Path) -> list[dict[str,Any]]:
    if not dist.is_dir():
        raise PublicReleaseError(f"public dist directory does not exist: {dist}")
    roots={p.name for p in dist.iterdir()}
    if roots != PUBLIC_ROOT:
        missing=sorted(PUBLIC_ROOT-roots)
        unexpected=sorted(roots-PUBLIC_ROOT)
        raise PublicReleaseError(
            f"public dist root differs from whitelist; missing={missing}; unexpected={unexpected}"
        )

    rows:list[dict[str,Any]]=[]
    for path in sorted(dist.rglob("*"),key=lambda p:p.as_posix()):
        if path.is_symlink():
            raise PublicReleaseError(f"public release refuses symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PublicReleaseError(f"public release contains non-regular path: {path}")
        relative=path.relative_to(dist).as_posix()
        digest,size=_file_hash(path)
        rows.append({"path":relative,"sha256":digest,"bytes":size})
    if not rows:
        raise PublicReleaseError("public release contains no files")
    if not any(row["path"].startswith("assets/") for row in rows):
        raise PublicReleaseError("public release assets directory contains no files")
    return rows


def build_manifest(dist_dir: str|Path, *, source_commit: str) -> dict[str,Any]:
    if not isinstance(source_commit,str) or COMMIT_RE.fullmatch(source_commit) is None:
        raise PublicReleaseError("source_commit must be a lowercase 40-character Git SHA")
    rows=_scan_dist(Path(dist_dir))
    tree_digest=sha256_hex(canonical_json(rows))
    return {
        "schema_version":RELEASE_SCHEMA,
        "source_commit":source_commit,
        "public_tree_sha256":tree_digest,
        "files":rows,
        "file_count":len(rows),
        "contains_internal_product_files":False,
        "deployment_target":"netlify-dist",
    }


def _write_release_zip(temp_path: Path, dist: Path, manifest: dict[str,Any]) -> None:
    manifest_bytes=(
        json.dumps(manifest,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
    ).encode("utf-8")
    with zipfile.ZipFile(temp_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
        info=zipfile.ZipInfo("release-manifest.json",date_time=FIXED_ZIP_TIME)
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100644<<16
        zf.writestr(info,manifest_bytes)
        for row in manifest["files"]:
            source=dist/row["path"]
            info=zipfile.ZipInfo("dist/"+row["path"],date_time=FIXED_ZIP_TIME)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            zf.writestr(info,source.read_bytes())
    with temp_path.open("rb") as stream:
        os.fsync(stream.fileno())


def build_public_release(
    dist_dir: str|Path,
    output_zip: str|Path,
    *,
    source_commit: str,
    overwrite: bool=False,
) -> dict[str,Any]:
    dist=Path(dist_dir)
    target=Path(output_zip)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing public release: {target}")

    manifest=build_manifest(dist,source_commit=source_commit)
    fd,temp_name=tempfile.mkstemp(prefix=f".{target.name}.",suffix=".tmp",dir=str(target.parent))
    os.close(fd)
    temp=Path(temp_name)
    try:
        _write_release_zip(temp,dist,manifest)
        if overwrite:
            os.replace(temp,target)
        else:
            try:
                os.link(temp,target)
            except FileExistsError:
                raise FileExistsError(
                    f"refusing to overwrite existing public release: {target}"
                ) from None
            temp.unlink()
        fsync_directory(target.parent)
    finally:
        if temp.exists():
            temp.unlink()

    archive_sha,archive_size=_file_hash(target)
    result={
        **manifest,
        "archive_path":str(target),
        "archive_sha256":archive_sha,
        "archive_bytes":archive_size,
    }
    return result


def _safe_zip_name(name: str) -> bool:
    if not name or name.startswith(("/", "\\")):
        return False
    parts=Path(name).parts
    return ".." not in parts


def verify_public_release(
    archive: str|Path,
    *,
    expected_source_commit: str|None=None,
) -> dict[str,Any]:
    path=Path(archive)
    if not path.is_file():
        raise PublicReleaseError(f"release archive does not exist: {path}")
    archive_sha,archive_size=_file_hash(path)

    with zipfile.ZipFile(path) as zf:
        names=zf.namelist()
        if len(names)!=len(set(names)):
            raise PublicReleaseError("release archive contains duplicate entry names")
        if any(not _safe_zip_name(name) for name in names):
            raise PublicReleaseError("release archive contains unsafe path")
        if names.count("release-manifest.json")!=1:
            raise PublicReleaseError("release archive must contain exactly one manifest")
        try:
            manifest=json.loads(zf.read("release-manifest.json").decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            raise PublicReleaseError("release manifest is invalid JSON") from exc

        if manifest.get("schema_version")!=RELEASE_SCHEMA:
            raise PublicReleaseError("release manifest schema is invalid")
        source_commit=manifest.get("source_commit")
        if not isinstance(source_commit,str) or COMMIT_RE.fullmatch(source_commit) is None:
            raise PublicReleaseError("release manifest source commit is invalid")
        if expected_source_commit is not None and source_commit!=expected_source_commit:
            raise PublicReleaseError("release source commit does not match expected commit")

        rows=manifest.get("files")
        if not isinstance(rows,list) or not rows:
            raise PublicReleaseError("release manifest file inventory is empty")
        if manifest.get("file_count")!=len(rows):
            raise PublicReleaseError("release manifest file_count mismatch")
        if manifest.get("public_tree_sha256")!=sha256_hex(canonical_json(rows)):
            raise PublicReleaseError("release manifest tree digest mismatch")
        if manifest.get("contains_internal_product_files") is not False:
            raise PublicReleaseError("release manifest internal-file boundary is invalid")

        expected_entries={"release-manifest.json"}
        root_names:set[str]=set()
        for row in rows:
            if not isinstance(row,dict):
                raise PublicReleaseError("release manifest row is invalid")
            rel=str(row.get("path") or "")
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                raise PublicReleaseError("release manifest contains unsafe file path")
            root_names.add(rel.split("/",1)[0])
            entry="dist/"+rel
            expected_entries.add(entry)
            try:
                data=zf.read(entry)
            except KeyError as exc:
                raise PublicReleaseError(f"release archive missing manifest file: {rel}") from exc
            if row.get("bytes")!=len(data):
                raise PublicReleaseError(f"release byte length mismatch: {rel}")
            if row.get("sha256")!=hashlib.sha256(data).hexdigest():
                raise PublicReleaseError(f"release SHA-256 mismatch: {rel}")

        if set(names)!=expected_entries:
            raise PublicReleaseError("release archive contains unmanifested files")
        if root_names!=PUBLIC_ROOT:
            raise PublicReleaseError("release public root differs from whitelist")

    return {
        "valid":True,
        "schema_version":RELEASE_SCHEMA,
        "source_commit":source_commit,
        "public_tree_sha256":manifest["public_tree_sha256"],
        "file_count":len(rows),
        "archive_sha256":archive_sha,
        "archive_bytes":archive_size,
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="capturebrief-public-release")
    sub=parser.add_subparsers(dest="cmd",required=True)
    build=sub.add_parser("build")
    build.add_argument("dist_dir")
    build.add_argument("output_zip")
    build.add_argument("--source-commit",required=True)
    build.add_argument("--manifest-output")
    build.add_argument("--overwrite",action="store_true")
    verify=sub.add_parser("verify")
    verify.add_argument("archive")
    verify.add_argument("--expected-source-commit")
    verify.add_argument("--output")
    args=parser.parse_args(argv)

    if args.cmd=="build":
        result=build_public_release(
            args.dist_dir,args.output_zip,
            source_commit=args.source_commit,
            overwrite=args.overwrite,
        )
        text=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
        if args.manifest_output:
            Path(args.manifest_output).write_text(text,encoding="utf-8")
        else:
            print(text,end="")
        return 0

    result=verify_public_release(
        args.archive,expected_source_commit=args.expected_source_commit
    )
    text=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        Path(args.output).write_text(text,encoding="utf-8")
    else:
        print(text,end="")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
