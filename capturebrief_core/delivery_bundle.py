"""Build a buyer-safe, hash-manifested CaptureBrief delivery bundle."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import audit_case
from .decision_trace import canonical, digest, evaluate_decision_trace
from .render import render_markdown
from .trace_render import render_trace_html, render_trace_markdown
from .watch_baseline import build_watch_baseline

BUNDLE_SCHEMA = "1.0"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _aware(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _public_source_manifest(case: dict[str, Any]) -> dict[str, Any]:
    trace = case.get("decision_trace") or {}
    snapshots = []
    for row in trace.get("snapshots") or []:
        if not isinstance(row, dict):
            continue
        snapshots.append({
            key: row.get(key)
            for key in (
                "snapshot_id", "source_id", "source_key", "kind", "title", "url",
                "version_label", "document_sha256", "text_sha256", "observed_at",
                "published_at", "capture_method",
            )
        })
    rules = []
    for row in trace.get("rule_versions") or []:
        if not isinstance(row, dict):
            continue
        rules.append({
            key: row.get(key)
            for key in (
                "rule_version_id", "rule_key", "namespace", "citation", "edition",
                "agency", "effective_from", "effective_until", "revision_ref",
            )
        })
    snapshots.sort(key=lambda x: (str(x.get("source_key") or ""), str(x.get("version_label") or ""), str(x.get("snapshot_id") or "")))
    rules.sort(key=lambda x: (str(x.get("rule_key") or ""), str(x.get("edition") or ""), str(x.get("rule_version_id") or "")))
    return {
        "schema_version": BUNDLE_SCHEMA,
        "case_id": case.get("case_id"),
        "family_id": case.get("family_id"),
        "snapshots": snapshots,
        "rule_versions": rules,
    }


def build_delivery_files(case: dict[str, Any], *, now: datetime | None = None) -> dict[str, bytes]:
    """Return buyer-safe delivery files. Refuses any case that is not release-ready."""
    now = _aware(now or datetime.now(timezone.utc))
    if case.get("decision_trace_required") is not True:
        raise ValueError("delivery bundle requires decision_trace_required=true")

    audit = audit_case(case, now=now)
    if audit.release_state != "READY_FOR_HUMAN_RELEASE":
        codes = sorted({f.code for f in audit.findings if f.severity == "BLOCK"})
        raise ValueError("case is not release-ready: " + ",".join(codes))

    trace = evaluate_decision_trace(case, now=now)
    if trace.get("trace_state") != "TRACE_COMPLETE" or trace.get("synthetic") is True:
        raise ValueError("delivery bundle requires a complete non-synthetic decision trace")

    brief = render_markdown(case, audit)
    trace_md = render_trace_markdown(case)
    trace_html = render_trace_html(case)
    source_manifest = _public_source_manifest(case)
    summary = {
        "schema_version": BUNDLE_SCHEMA,
        "case_id": case.get("case_id"),
        "family_id": case.get("family_id"),
        "current_posture": case.get("current_posture"),
        "release_state": audit.release_state,
        "currentness_verdict": audit.currentness_verdict,
        "current_action_id": audit.current_action_id,
        "trace_state": trace.get("trace_state"),
        "decision_at": trace.get("decision_at"),
        "case_sha256": trace.get("case_sha256"),
        "assumptions": trace.get("assumptions") or [],
        "limitations": trace.get("limitations") or [],
    }
    return {
        "brief.md": brief.encode("utf-8"),
        "decision-evidence.md": trace_md.encode("utf-8"),
        "decision-evidence.html": trace_html.encode("utf-8"),
        "decision-summary.json": _json_bytes(summary),
        "source-version-manifest.json": _json_bytes(source_manifest),
        "watch-baseline.json": _json_bytes(build_watch_baseline(case, now=now)),
    }


def build_delivery_bundle(
    case: dict[str, Any],
    output_zip: str | Path,
    *,
    now: datetime | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a deterministic ZIP and return its manifest + ZIP SHA-256."""
    now = _aware(now or datetime.now(timezone.utc))
    target = Path(output_zip)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing bundle: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    files = build_delivery_files(case, now=now)
    file_rows = [
        {"path": name, "sha256": digest(data), "bytes": len(data)}
        for name, data in sorted(files.items())
    ]
    manifest = {
        "schema_version": BUNDLE_SCHEMA,
        "case_id": case.get("case_id"),
        "family_id": case.get("family_id"),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "case_sha256": digest(canonical(case)),
        "release_state": "READY_FOR_HUMAN_RELEASE",
        "trace_state": "TRACE_COMPLETE",
        "files": file_rows,
        "contains_raw_case": False,
        "contains_restricted_source_bytes": False,
    }
    files["delivery-manifest.json"] = _json_bytes(manifest)

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, files[name])

    result = dict(manifest)
    result["bundle_path"] = str(target)
    result["bundle_sha256"] = digest(target.read_bytes())
    result["bundle_bytes"] = target.stat().st_size
    return result
