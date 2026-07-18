#!/usr/bin/env python3
"""CI license-compliance gate for the u137 image-candidate store.

Mirrors ``scripts/check_curated_assets.py``: a stdlib-only blocking gate
(TS-3 — no third-party dependency; in-tree investo modules are reused so
the validation logic stays single-sourced) that fails the build on any
non-compliant store state (Contract #6, AC-1.1 / AC-1.2 / AC-1.3).

The gate fails (non-zero exit, one distinct message per violation) on:
  * a store binary with no ``{cid}{ext}.provenance.json`` sidecar (I12);
  * an orphan sidecar with no binary (I12);
  * a store binary with no ``clearances/{cid}.manifest.json`` (R7);
  * a sidecar whose ``content_sha256`` does not match the binary bytes,
    or whose ``candidate_id`` does not match the filename stem (I12);
  * an invalid / unparseable / hash-mismatched (I9) clearance manifest —
    RED even when no binary was stored for it (I8, fail-closed);
  * an unrecognized extension or non-hex filename in the store tree;
  * a per-file > 2,000,000 B or store-total > 50,000,000 B budget breach
    (AC-1.1 — the per-file cap is the existing u19 fetch cap, reused);
  * a per-file < 100 B floor breach on a store binary (AC-1.1 — the
    floor is the existing u19 fetch minimum, reused);
  * an R13 secret-pattern hit in any sidecar / ledger / index /
    clearance manifest (AC-1.3 — reuses the u27 ``scan_for_leak``
    catalogue). The ratified u137 digest exemption is applied
    KEY-SCOPED (DEBT-086), mirroring ``visuals/provenance.py``: only
    sidecar ``additional_metadata.candidate_id`` /
    ``content_sha256`` values, ``index.json`` top-level map keys, and
    ledger-row ``candidate_id`` values are exempt (64-hex shape
    required). A 64-hex-shaped string anywhere else — including any
    clearance-manifest field — triggers the RED. Content that does not
    parse as JSON is scanned raw with NO masking (fail-closed).

Green states (binding, AC-1.2): an empty store passes; a
metadata-only-everything state (ledgers + index present, zero binaries,
zero clearances) passes; a ``.blocked`` marker with no binary passes.
The gate polices the STORE, not the operator's clearance backlog.

Usage::

    python scripts/check_image_store.py

Exit codes:
    0 — the image store is fully compliant (empty store allowed)
    1 — at least one violation; details printed to stderr
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from pydantic import ValidationError  # noqa: E402

from investo._internal.redaction import scan_for_leak  # noqa: E402
from investo.visuals.external_image import (  # noqa: E402
    _MAX_IMAGE_BYTES,
    _MIN_IMAGE_BYTES,
)
from investo.visuals.image_library import candidate_id_for_url  # noqa: E402
from investo.visuals.policy import ExternalAssetManifest  # noqa: E402
from investo.visuals.provenance import VisualProvenanceManifest  # noqa: E402

_DEFAULT_STORE_ROOT = _REPO_ROOT / "assets" / "images"
_DEFAULT_LEDGER_ROOT = _REPO_ROOT / "archive" / "_meta" / "image_candidates"

# AC-1.1 — store-total budget across everything under assets/images/
# (binaries AND sidecar JSON). The per-file cap is _MAX_IMAGE_BYTES
# (2,000,000 B), imported — not re-declared — from the u19 fetch gate.
_STORE_TOTAL_BUDGET_BYTES = 50_000_000

_BINARY_EXTENSIONS = (".png", ".jpg")
_SIDECAR_SUFFIX = ".provenance.json"
_HEX_CID = r"[0-9a-f]{64}"

# The ratified u137 digest exemption (see visuals/provenance.py) is
# KEY-SCOPED (DEBT-086): only these positions may carry a bare 64-hex
# value without triggering the R13 long-base64 pattern. Everything
# else — clearance-manifest fields included — is scanned in full.
_SIDECAR_DIGEST_PATHS = (
    ("additional_metadata", "candidate_id"),
    ("additional_metadata", "content_sha256"),
)
_LEDGER_DIGEST_PATH = ("candidate_id",)
# The sidecar's asset_path embeds the cid in a slash-joined store
# address ("/" is inside the long-base64 character class, so the whole
# address would false-positive). Exempt ONLY when the value is exactly
# the Contract #4 store-address shape — anything else under that key
# is scanned.
_STORE_ADDRESS_SHAPE = rf"assets/images/[0-9a-f]{{2}}/{_HEX_CID}\.(?:png|jpg)"


def check(
    store_root: Path | None = None,
    ledger_root: Path | None = None,
) -> tuple[int, list[str]]:
    """Return ``(exit_code, messages)`` for the store + candidate registry."""
    store = store_root if store_root is not None else _DEFAULT_STORE_ROOT
    registry = ledger_root if ledger_root is not None else _DEFAULT_LEDGER_ROOT
    clearances = registry / "clearances"

    failures: list[str] = []
    binaries: list[Path] = []
    sidecars: list[Path] = []
    total_bytes = 0

    store_entries = sorted(store.rglob("*")) if store.exists() else []
    for path in store_entries:
        if not path.is_file():
            continue
        total_bytes += path.stat().st_size
        if path.name.endswith(_SIDECAR_SUFFIX):
            sidecars.append(path)
        elif path.suffix in _BINARY_EXTENSIONS and re.fullmatch(_HEX_CID, path.stem):
            binaries.append(path)
        else:
            failures.append(
                f"unrecognized store entry (only {{cid}}.png/.jpg + "
                f"*{_SIDECAR_SUFFIX} allowed): {path}"
            )

    for binary in binaries:
        cid = binary.stem
        content = binary.read_bytes()
        if len(content) > _MAX_IMAGE_BYTES:
            failures.append(
                f"per-file budget breach ({len(content)} B > {_MAX_IMAGE_BYTES} B, "
                f"AC-1.1): {binary}"
            )
        if len(content) < _MIN_IMAGE_BYTES:
            failures.append(
                f"per-file floor breach ({len(content)} B < {_MIN_IMAGE_BYTES} B, AC-1.1): {binary}"
            )
        sidecar = binary.with_name(binary.name + _SIDECAR_SUFFIX)
        if not sidecar.exists():
            failures.append(f"store binary has no provenance sidecar (I12): {binary}")
        else:
            failures.extend(_check_sidecar_pairing(sidecar, cid, content))
        clearance = clearances / f"{cid}.manifest.json"
        if not clearance.exists():
            failures.append(f"store binary has no clearance manifest (R7/AC-1.2): {binary}")

    binary_names = {binary.name for binary in binaries}
    for sidecar in sidecars:
        expected_binary = sidecar.name.removesuffix(_SIDECAR_SUFFIX)
        if expected_binary not in binary_names:
            failures.append(f"orphan sidecar with no store binary (I12): {sidecar}")

    if total_bytes > _STORE_TOTAL_BUDGET_BYTES:
        failures.append(
            f"store total budget breach ({total_bytes} B > "
            f"{_STORE_TOTAL_BUDGET_BYTES} B, AC-1.1): {store}"
        )

    failures.extend(_check_clearances(clearances))
    failures.extend(_scan_r13(registry, sidecars))

    if failures:
        return 1, failures
    summary = (
        f"image store OK — {len(binaries)} binaries, {len(sidecars)} sidecars, "
        f"{total_bytes} B total"
    )
    return 0, [summary]


def _check_sidecar_pairing(sidecar: Path, cid: str, content: bytes) -> list[str]:
    """Validate one sidecar against its binary (I12 pairing + hashes)."""
    try:
        manifest = VisualProvenanceManifest.model_validate(
            json.loads(sidecar.read_text(encoding="utf-8"))
        )
    except (ValidationError, ValueError, OSError) as exc:
        return [f"provenance sidecar unparseable (I12): {sidecar} ({type(exc).__name__})"]
    failures: list[str] = []
    recorded_sha = manifest.additional_metadata.get("content_sha256", "")
    actual_sha = hashlib.sha256(content).hexdigest()
    if recorded_sha != actual_sha:
        failures.append(
            f"sidecar content_sha256 does not match binary bytes (I12): {sidecar} "
            f"(recorded={recorded_sha[:12] or '<missing>'}…, actual={actual_sha[:12]}…)"
        )
    recorded_cid = manifest.additional_metadata.get("candidate_id", "")
    if recorded_cid != cid:
        failures.append(
            f"sidecar candidate_id does not match filename stem (I12): {sidecar} "
            f"(recorded={recorded_cid[:12] or '<missing>'}…, stem={cid[:12]}…)"
        )
    return failures


def _check_clearances(clearances: Path) -> list[str]:
    """Fail-closed clearance validation — RED even without a binary (I8/I9)."""
    if not clearances.exists():
        return []
    failures: list[str] = []
    for manifest_path in sorted(clearances.glob("*.manifest.json")):
        cid = manifest_path.name.removesuffix(".manifest.json")
        if not re.fullmatch(_HEX_CID, cid):
            failures.append(f"clearance filename is not a candidate id: {manifest_path}")
            continue
        try:
            manifest = ExternalAssetManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        except (ValidationError, OSError, UnicodeDecodeError) as exc:
            failures.append(
                f"clearance manifest unparseable (I8, fail-closed): {manifest_path} "
                f"({type(exc).__name__})"
            )
            continue
        if manifest.kind != "explicit-license":
            failures.append(
                f"clearance manifest kind must be 'explicit-license' (E3): "
                f"{manifest_path} (got {manifest.kind!r})"
            )
        if candidate_id_for_url(str(manifest.source_url)) != cid:
            failures.append(
                f"clearance source_url does not hash to the candidate id (I9): {manifest_path}"
            )
    return failures


def _scan_r13(registry: Path, sidecars: list[Path]) -> list[str]:
    """AC-1.3 — u27 secret-pattern scan over the persisted artifacts.

    Scanned: every store sidecar, every date ledger, the recurrence
    index, and every other JSON under the registry (clearance manifests
    included — with NO masking; the digest exemption never applies to
    operator-authored content). On a hit the message names the PATTERN
    and the file — never the matched secret text (R13).
    """
    index_path = registry / "index.json"
    targets: list[tuple[Path, str]] = [(sidecar, "sidecar") for sidecar in sidecars]
    if registry.exists():
        targets.extend((path, "ledger") for path in sorted(registry.rglob("*.jsonl")))
        for path in sorted(registry.rglob("*.json")):
            kind = "index" if path == index_path else "raw"
            targets.append((path, kind))
    failures: list[str] = []
    for target, kind in targets:
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(f"R13 scan could not read (AC-1.3): {target} ({type(exc).__name__})")
            continue
        pattern_name = _leak_pattern_in_artifact(text, kind)
        if pattern_name is not None:
            failures.append(
                f"R13 secret-pattern hit (AC-1.3): {target} matched pattern "
                f"'{pattern_name}' — value withheld"
            )
    return failures


def _leak_pattern_in_artifact(text: str, kind: str) -> str | None:
    """Return the first leak pattern name in one artifact, or ``None``.

    ``kind`` selects the key-scoped digest exemption (DEBT-086):
    ``sidecar`` / ``index`` / ``ledger`` parse as JSON and skip only
    the ratified digest positions; ``raw`` (clearance manifests, stray
    files) scans everything. Unparseable-as-JSON content falls back to
    a raw full-text scan with no masking — fail-closed.
    """
    if kind == "raw":
        hit = scan_for_leak(text)
        return hit.pattern_name if hit is not None else None
    chunks = text.splitlines() if kind == "ledger" else [text]
    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            parsed = json.loads(chunk)
        except ValueError:
            hit = scan_for_leak(chunk)  # fail-closed: unmasked raw scan
            if hit is not None:
                return hit.pattern_name
            continue
        for path, value, is_key in _iter_json_strings(parsed):
            if not is_key and _is_exempt_digest(kind, path, value):
                continue
            if is_key and kind == "index" and path == () and re.fullmatch(_HEX_CID, value):
                continue  # index top-level map keys ARE candidate ids
            hit = scan_for_leak(value)
            if hit is not None:
                return hit.pattern_name
    return None


def _is_exempt_digest(kind: str, path: tuple[str, ...], value: str) -> bool:
    """Shape-locked, key-scoped digest exemption (TS-2 / DEBT-086)."""
    if kind == "sidecar" and path == ("asset_path",):
        return re.fullmatch(_STORE_ADDRESS_SHAPE, value) is not None
    if not re.fullmatch(_HEX_CID, value):
        return False
    if kind == "sidecar":
        return path in _SIDECAR_DIGEST_PATHS
    if kind == "ledger":
        return path == _LEDGER_DIGEST_PATH
    return False


def _iter_json_strings(
    node: object, path: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], str, bool]]:
    """Yield every string in a parsed JSON tree as ``(path, text, is_key)``.

    A value's ``path`` includes its own key; a key's ``path`` is its
    parent's. Lists do not extend the path.
    """
    found: list[tuple[tuple[str, ...], str, bool]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                found.append((path, key, True))
                found.extend(_iter_json_strings(value, (*path, key)))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_json_strings(item, path))
    elif isinstance(node, str):
        found.append((path, node, False))
    return found


def main() -> int:
    exit_code, messages = check()
    stream = sys.stderr if exit_code != 0 else sys.stdout
    if exit_code != 0:
        print("Image store license-compliance gate failed (u137 AC-1.2):", file=stream)
    for message in messages:
        print(message, file=stream)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
