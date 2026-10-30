"""Discover source HTML to verify on shared GitHub Pages, never build outputs.

This is intentionally separate from Cloudflare's allowlisted CaptureBrief release.
It only selects existing source documents for the legacy shared Pages check.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

# The shared gh-pages branch contains several sibling sites. Do not remove them
# from the existing publication check; exclude only non-source workspaces.
NON_SOURCE_ROOTS = frozenset({".git", ".github", "dist", "qa-output"})


def discover_source_html(root: Path, already_expected: Iterable[str] = ()) -> list[str]:
    """Return deterministic source-relative HTML paths, excluding generated files.

    Only existing, regular, non-symlink source files can become expectations.
    A generated `dist/*.html` is never a GitHub Pages source path: those files
    belong to the isolated Cloudflare build and do not exist at /dist/ on Pages.
    """
    root = Path(root)
    known = set(already_expected)
    paths: set[str] = set()
    for path in root.rglob("*.html"):
        relative = path.relative_to(root)
        if relative.parts[0] in NON_SOURCE_ROOTS:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        name = relative.as_posix()
        if name not in known:
            paths.add(name)
    return sorted(paths)
