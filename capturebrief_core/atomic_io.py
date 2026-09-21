"""Fail-closed local artifact publication helpers."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync for crash durability on supported filesystems."""
    try:
        fd=os.open(path,os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    view=memoryview(data)
    written=0
    while written < len(view):
        n=os.write(fd,view[written:])
        if n <= 0:
            raise OSError("artifact write made no forward progress")
        written += n


def _sha256_file(path: Path) -> tuple[str,int]:
    h=hashlib.sha256()
    size=0
    with path.open("rb") as stream:
        while True:
            chunk=stream.read(1024*1024)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    return h.hexdigest(),size


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
    *,
    overwrite: bool = True,
    mode: int = 0o600,
) -> Path:
    """Publish complete bytes atomically.

    overwrite=False fails if the destination already exists. The completed
    temporary file is fsynced before publication and removed on all failures.
    """
    if not isinstance(data,(bytes,bytearray,memoryview)):
        raise TypeError("data must be bytes-like")
    raw=bytes(data)
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing artifact: {target}")

    fd,temp_name=tempfile.mkstemp(prefix=f".{target.name}.",suffix=".tmp",dir=str(target.parent))
    temp=Path(temp_name)
    try:
        if hasattr(os,"fchmod"):
            os.fchmod(fd,mode)
        _write_all(fd,raw)
        os.fsync(fd)
    finally:
        os.close(fd)

    try:
        if overwrite:
            os.replace(temp,target)
        else:
            try:
                os.link(temp,target)
            except FileExistsError:
                raise FileExistsError(f"refusing to overwrite existing artifact: {target}") from None
            temp.unlink()
        _fsync_directory(target.parent)
    finally:
        if temp.exists():
            temp.unlink()
    return target


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    overwrite: bool = True,
    mode: int = 0o600,
) -> Path:
    if not isinstance(text,str):
        raise TypeError("text must be str")
    return atomic_write_bytes(path,text.encode(encoding),overwrite=overwrite,mode=mode)


def ensure_exact_bytes(
    path: str | Path,
    data: bytes,
    *,
    mode: int = 0o600,
) -> dict[str,object]:
    """Persist content-addressed bytes without silently replacing different data.

    An existing regular file is accepted only when byte length and SHA-256 match.
    A concurrent writer that publishes the exact same bytes is accepted; different
    bytes fail closed.
    """
    raw=bytes(data)
    target=Path(path)
    expected_sha=hashlib.sha256(raw).hexdigest()
    expected_size=len(raw)

    def existing_result() -> dict[str,object]:
        if target.is_symlink():
            raise ValueError(f"refusing to trust symlink artifact path: {target}")
        actual_sha,actual_size=_sha256_file(target)
        if (actual_sha,actual_size)!=(expected_sha,expected_size):
            raise ValueError(f"existing artifact content conflicts with captured bytes: {target}")
        return {
            "path":str(target),
            "sha256":actual_sha,
            "bytes":actual_size,
            "created":False,
        }

    if target.exists():
        return existing_result()

    try:
        atomic_write_bytes(target,raw,overwrite=False,mode=mode)
    except FileExistsError:
        return existing_result()

    return {
        "path":str(target),
        "sha256":expected_sha,
        "bytes":expected_size,
        "created":True,
    }
