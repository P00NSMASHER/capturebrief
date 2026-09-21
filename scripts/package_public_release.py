"""Package only reviewed public site bytes from a clean, exact Git revision.

Creates a deployable ZIP plus an external hash receipt. It performs no deployment,
network request, email, form submission, or production configuration change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

PUBLIC_FILES = frozenset({
    "404.html", "_headers", "_redirects", "data-handling.html",
    "decision-evidence-sample.html", "favicon.svg", "index.html", "privacy.html",
    "robots.txt", "sample.html", "site.webmanifest", "sitemap.xml", "terms.html",
    "thanks.html", "assets/main.js", "assets/og-capturebrief.png",
    "assets/styles.css", "assets/v5.css",
})
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def package_release(root: Path, output_dir: Path, source_sha: str) -> dict:
    root, output_dir = Path(root).resolve(), Path(output_dir).resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("exact 40-character source commit required")
    if _git(root, "rev-parse", "HEAD").decode().strip() != source_sha:
        raise ValueError("checked-out revision does not match requested release")
    if _git(root, "diff", "--name-only", "HEAD", "--"):
        raise ValueError("tracked source has uncommitted changes")
    dist = root / "dist"
    if dist.is_symlink() or not dist.is_dir():
        raise ValueError("dist must be a real, prebuilt directory")
    paths = list(dist.rglob("*"))
    if any(p.is_symlink() or (not p.is_file() and not p.is_dir()) for p in paths):
        raise ValueError("links and non-regular deployment entries are forbidden")
    actual = {p.relative_to(dist).as_posix() for p in paths if p.is_file()}
    if actual != PUBLIC_FILES:
        raise ValueError("public file allowlist mismatch: missing=" + str(sorted(PUBLIC_FILES-actual))
                         + "; unexpected=" + str(sorted(actual-PUBLIC_FILES)))
    files: dict[str, bytes] = {}
    for name in sorted(PUBLIC_FILES):
        data = (dist / name).read_bytes()
        if not data:
            raise ValueError("empty public file: " + name)
        if data != _git(root, "show", f"{source_sha}:{name}"):
            raise ValueError("built file does not match pinned source: " + name)
        files[name] = data
    rows = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(files.items())]
    manifest = {
        "schema_version": "1.0", "source_commit": source_sha,
        "files": rows, "payload_sha256": hashlib.sha256(_json(rows)).hexdigest(),
        "publication_status": "BUILD_ARTIFACT_NOT_DEPLOYMENT_PROOF",
    }
    files["release-manifest.json"] = _json(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "CaptureBrief_Public_Release.zip"
    receipt_path = output_dir / "release-receipt.json"
    sums_path = output_dir / "SHA256SUMS"
    if any(p.exists() or p.is_symlink() for p in (target, receipt_path, sums_path)):
        raise FileExistsError("refusing to overwrite release output")
    with target.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=_FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compresslevel=9)
    receipt = {
        "schema_version": "1.0", "source_commit": source_sha,
        "archive": target.name, "archive_bytes": target.stat().st_size,
        "archive_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "file_count": len(files), "public_payload_sha256": manifest["payload_sha256"],
        "deployed": False, "contains_internal_product_files": False,
    }
    with receipt_path.open("xb") as stream:
        stream.write(_json(receipt))
    with sums_path.open("x", encoding="utf-8") as stream:
        stream.write(receipt["archive_sha256"] + "  " + target.name + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        result = package_release(args.root, args.output_dir, args.source_sha)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Public release stopped: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
