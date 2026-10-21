"""Fail-closed PRIVATE disk-space budget for one unapproved SAM archive.

This checks only a conservative single-stream original->gzip working budget,
NOT aggregate archive/index/backup capacity, disk encryption, human source
catalog review or customer release. No network access or writes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))

from scripts.fy2027_archive_compression_probe import frozen_unapproved_sizes

# Preserve enough unallocated space for basic OS/operator operation. This
# conservative floor is NOT an estimate of the independent SQLite, source-
# index, active extract, temp retention, encrypted off-device-backup budget.
UNALLOCATED_RESERVE_BYTES=4*1024**3
MAX_ANNUAL_ORIGINAL_BYTES=1_500_000_000
MIN_GZIP_OVERHEAD_BYTES=256*1024
# ensure_exact_file streams the completed gzip temp to a second temporary
# copy before hard-link publication; both compressed copies coexist briefly.
MAX_SIMULTANEOUS_GZIP_COPIES=2
PUBLICATION_METADATA_ALLOWANCE_BYTES=1024*1024



def worst_case_gzip_bytes(declared_original_bytes: int) -> int:
    """Conservative input-size-bound gzip ceiling, shared with publisher retainer."""
    if (type(declared_original_bytes) is not int
            or not 0 < declared_original_bytes <= MAX_ANNUAL_ORIGINAL_BYTES):
        raise ValueError("Unsupported bounded source-original byte count")
    return (
        declared_original_bytes
        + max(MIN_GZIP_OVERHEAD_BYTES, (declared_original_bytes + 99) // 100)
    )


def inspect_source_capacity(
    private_root: str | Path, declared_original_bytes: int, *,
    disk_usage=None,
) -> dict[str, Any]:
    """Read local free bytes; never infer source review or disk encryption."""
    worst_case_compressed_bytes=worst_case_gzip_bytes(declared_original_bytes)
    root=Path(private_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Source capacity requires an existing private directory")
    # No uncompressed source temp exists, but ensure_exact_file creates a
    # SECOND full-size gzip copy during atomic publication. Budget both
    # concurrent copies plus bounded receipt/lock/FS metadata overhead.
    # Never substitute sampled ratios or infer 34-year storage feasibility.
    publication_bytes = (MAX_SIMULTANEOUS_GZIP_COPIES * worst_case_compressed_bytes
                         + PUBLICATION_METADATA_ALLOWANCE_BYTES)
    required_free=publication_bytes+UNALLOCATED_RESERVE_BYTES
    if disk_usage is None:
        disk_usage=shutil.disk_usage
    usage=disk_usage(root)
    free=getattr(usage,"free",None)
    if type(free) is not int or free < 0:
        raise ValueError("Storage provider did not establish available disk bytes")
    return {
        "schema": "capturebrief-fy2027-single-source-private-capacity-check-v1",
        "declared_original_bytes": declared_original_bytes,
        "worst_case_gzip_temp_bytes": worst_case_compressed_bytes,
        "simultaneous_gzip_publication_copies": MAX_SIMULTANEOUS_GZIP_COPIES,
        "publication_metadata_allowance_bytes": PUBLICATION_METADATA_ALLOWANCE_BYTES,
        "peak_publication_working_bytes": publication_bytes,
        "unallocated_safety_reserve_bytes": UNALLOCATED_RESERVE_BYTES,
        "required_free_bytes": required_free,
        "available_free_bytes": free,
        "single_source_disk_capacity_pass": free >= required_free,
        "all_34_year_archive_fits": False,
        "active_extract_index_and_working_space_built": False,
        "disk_encryption_verified": False,
        "encrypted_offdevice_backup_and_independent_key_verified": False,
        "human_publisher_catalog_approval": False,
        "source_index_updated": False,
        "customer_release_authorized": False,
    }


def require_source_capacity(private_root: str | Path, declared_original_bytes: int) -> dict[str, Any]:
    """Block before network/original fetch if free space cannot be verified."""
    result=inspect_source_capacity(private_root,declared_original_bytes)
    if result["single_source_disk_capacity_pass"] is not True:
        raise ValueError("Insufficient private disk reserve for bounded source compression")
    return result


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root",required=True)
    p.add_argument("--year",type=int,required=True)
    args=p.parse_args(argv)
    try:
        years=frozen_unapproved_sizes()
        if args.year not in years:
            raise ValueError("Source year outside unapproved frozen FY2027 archive inventory")
        result=inspect_source_capacity(args.private_root,years[args.year])
        result["fiscal_year"]=args.year
    except (OSError,ValueError,TypeError,RuntimeError) as exc:
        print(json.dumps({
            "status": "SOURCE_CAPACITY_UNVERIFIED",
            "error_type": type(exc).__name__,
            "single_source_disk_capacity_pass": False,
            "customer_release_authorized": False,
        },sort_keys=True))
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    # A no-capacity reading is a controlled nonzero result.
    return 0 if result["single_source_disk_capacity_pass"] else 3


if __name__=="__main__":
    raise SystemExit(main())
