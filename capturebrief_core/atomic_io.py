"""Fail-closed local artifact publication and path-lock helpers."""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


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


def fsync_directory(path: str | Path) -> None:
    _fsync_directory(Path(path))


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
        try:
            if hasattr(os,"fchmod"):
                os.fchmod(fd,mode)
            _write_all(fd,raw)
            os.fsync(fd)
        finally:
            os.close(fd)

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


DEFAULT_PATH_LOCK_TIMEOUT_SECONDS=5.0
_PATH_LOCK_POLL_SECONDS=0.05


class ArtifactLockedError(TimeoutError):
    pass


@contextmanager
def exclusive_path_lock(
    path: str | Path,
    *,
    timeout_seconds: float = DEFAULT_PATH_LOCK_TIMEOUT_SECONDS,
    suffix: str = ".lock",
) -> Iterator[Path]:
    """Serialize operations that must keep one mutable path coherent.

    Lock files are never guessed stale. A timeout requires operator review.
    """
    if timeout_seconds < 0:
        raise ValueError("lock timeout must be non-negative")
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    lock=target.with_name(target.name+suffix)
    deadline=time.monotonic()+timeout_seconds
    while True:
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ArtifactLockedError(
                    f"artifact path is locked; verify no writer is active before removing: {lock}"
                ) from None
            time.sleep(_PATH_LOCK_POLL_SECONDS)
            continue
        try:
            payload=(
                f"pid={os.getpid()} created_at={datetime.now(timezone.utc).isoformat()}\n"
            ).encode("utf-8")
            _write_all(fd,payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        break
    try:
        yield lock
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def ensure_exact_file(
    source_path: str | Path,
    target_path: str | Path,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
    mode: int = 0o444,
) -> dict[str,object]:
    """Stream-copy a file into a content-addressed destination.

    Existing targets are accepted only when SHA-256 and byte length match.
    Concurrent publication of the same bytes is idempotent; different bytes
    fail closed. The source is re-hashed while copying, so a mutable source
    cannot silently change after an earlier pre-copy digest was computed.
    """
    source=Path(source_path)
    target=Path(target_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if expected_sha256 is not None and (
        not isinstance(expected_sha256,str)
        or len(expected_sha256)!=64
        or any(ch not in "0123456789abcdef" for ch in expected_sha256)
    ):
        raise ValueError("expected_sha256 must be lowercase 64-character hex")
    if expected_size is not None and (type(expected_size) is not int or expected_size < 0):
        raise ValueError("expected_size must be a non-negative integer")

    source_sha,source_size=_sha256_file(source)
    if expected_sha256 is not None and source_sha!=expected_sha256:
        raise ValueError("source file SHA-256 changed before retention copy")
    if expected_size is not None and source_size!=expected_size:
        raise ValueError("source file size changed before retention copy")
    expected_sha256=source_sha
    expected_size=source_size

    target.parent.mkdir(parents=True,exist_ok=True)

    def existing_result() -> dict[str,object]:
        if target.is_symlink():
            raise ValueError(f"refusing to trust symlink artifact path: {target}")
        actual_sha,actual_size=_sha256_file(target)
        if (actual_sha,actual_size)!=(expected_sha256,expected_size):
            raise ValueError(f"existing artifact content conflicts with source file: {target}")
        return {
            "path":str(target),
            "sha256":actual_sha,
            "bytes":actual_size,
            "created":False,
        }

    if target.exists():
        return existing_result()

    fd,temp_name=tempfile.mkstemp(prefix=f".{target.name}.",suffix=".tmp",dir=str(target.parent))
    temp=Path(temp_name)
    copied_hash=hashlib.sha256()
    copied_size=0
    try:
        try:
            if hasattr(os,"fchmod"):
                os.fchmod(fd,mode)
            with source.open("rb") as inp, os.fdopen(fd,"wb",closefd=False) as out:
                while True:
                    chunk=inp.read(1024*1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    copied_hash.update(chunk)
                    copied_size += len(chunk)
                out.flush()
                os.fsync(out.fileno())
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

        if (copied_hash.hexdigest(),copied_size)!=(expected_sha256,expected_size):
            raise ValueError("retained snapshot copy failed source hash verification")

        try:
            os.link(temp,target)
        except FileExistsError:
            return existing_result()
        else:
            temp.unlink()
            _fsync_directory(target.parent)
            return {
                "path":str(target),
                "sha256":expected_sha256,
                "bytes":expected_size,
                "created":True,
            }
    finally:
        if temp.exists():
            temp.unlink()
