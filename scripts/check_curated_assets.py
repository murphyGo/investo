#!/usr/bin/env python3
"""CI license-clearance gate for the u86 curated context-asset library.

Mirrors ``scripts/check_no_paid_apis.py``: a stdlib-only blocking gate,
wired into the lint job, that fails the build on any non-compliant
curated library entry (AC-1.2 / TS-3). It re-uses the in-tree
``investo.visuals.curated.load_library`` + ``assert_registry_integrity``
so the load-time and CI clearance logic is single-sourced.

The gate fails (non-zero exit, clear message) on:
  * a binary with no sibling manifest (R1);
  * a binary-absent registered key with no explicit deferral marker —
    a silent empty (R8 / I14);
  * a manifest carrying a disallowed / unrecognized license (R2);
  * a byte / dimension / format budget violation on a filed asset (AC-1.1);
  * a registry id that resolves to no library entry (I8);
  * a secret-shaped value in any manifest field (R7 / AC-1.6).

An explicitly *deferred* key (deferral marker present, no binary)
**passes** (exit 0). An orphan filed asset (in the library, never
referenced by the registry) is a warning, not a failure.

Usage::

    python scripts/check_curated_assets.py

Exit codes:
    0 — the curated library is fully compliant (deferred keys allowed)
    1 — at least one violation; details printed to stderr
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from investo.visuals.curated import (  # noqa: E402
    LIBRARY_ROOT,
    CuratedLibraryError,
    assert_registry_integrity,
    default_registry,
    load_library,
)


def check(root: Path | None = None) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` for the curated library at ``root``.

    When ``root`` is ``None`` (the default — CI invocation), the
    committed seed registry's referential integrity is checked against
    the committed library (I8). When a custom ``root`` is supplied (test
    fixtures), only the load-time clearance is checked, because the
    committed registry does not describe an arbitrary fixture tree.
    """
    check_registry = root is None
    library_root = root if root is not None else (_REPO_ROOT / LIBRARY_ROOT)
    messages: list[str] = []
    try:
        library = load_library(library_root)
    except CuratedLibraryError as exc:
        return 1, [f"curated library clearance failed: {exc}"]
    orphans: list[str] = []
    if check_registry:
        try:
            orphans = assert_registry_integrity(default_registry(), library)
        except CuratedLibraryError as exc:
            return 1, [f"curated registry integrity failed: {exc}"]

    filed = sorted(a.asset_id for a in library.values() if a.state == "filed")
    deferred = sorted(a.asset_id for a in library.values() if a.state == "deferred")
    messages.append(f"curated library OK — {len(filed)} filed, {len(deferred)} deferred")
    if filed:
        messages.append(f"  filed: {', '.join(filed)}")
    if deferred:
        messages.append(f"  deferred: {', '.join(deferred)}")
    for orphan in orphans:
        messages.append(f"  warning: orphan filed asset (never referenced): {orphan}")
    return 0, messages


def main() -> int:
    exit_code, messages = check()
    stream = sys.stderr if exit_code != 0 else sys.stdout
    if exit_code != 0:
        print("Curated asset clearance gate failed (u86 AC-1.2):", file=stream)
    for message in messages:
        print(message, file=stream)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
