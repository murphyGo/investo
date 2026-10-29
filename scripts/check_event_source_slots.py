#!/usr/bin/env python
"""Validate source slot evidence offline. Never fetch, generate or publish."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

from investo.models.enrichment import (
    SLOT_REQUIRED_FIELDS,
    SourceSlotParserCapture,
    SourceSlotQualificationSet,
)
from investo.sources.event_evidence import (
    load_source_slot_qualification,
    replay_source_slot_capture,
)


def check_private_capture(
    path: Path,
    manifest: Path,
    *,
    matrix: SourceSlotQualificationSet | None = None,
) -> tuple[tuple[str, str, int], ...]:
    """Read only an ignored private file; diagnostics never contain its payload."""
    root = Path(__file__).resolve().parents[1]
    path = path.absolute()
    if (
        not path.is_relative_to(root)
        or any(part.is_symlink() for part in (path, *path.parents))
        or not path.resolve().is_relative_to(root)
        or not path.is_file()
        or subprocess.run(
            ["git", "check-ignore", "-q", "--", str(path)],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=5,
        ).returncode
        != 0
    ):
        raise ValueError("slot.private_capture_invalid")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("slot.private_capture_invalid")
        data = handle.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("slot.private_capture_invalid")
    capture = SourceSlotParserCapture.model_validate_json(data)
    matrix = matrix if matrix is not None else load_source_slot_qualification(manifest)
    return replay_source_slot_capture(
        capture,
        matrix,
        qualification_sha256=hashlib.sha256(matrix.model_dump_json().encode()).hexdigest(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("ops/event_source_slot_qualification.json")
    )
    parser.add_argument("--private-capture", type=Path)
    args = parser.parse_args()
    try:
        matrix = load_source_slot_qualification(args.manifest)
        if {row.slot_id for row in matrix.records} != set(SLOT_REQUIRED_FIELDS):
            raise ValueError("slot.matrix_incomplete")
        replay = (
            check_private_capture(args.private_capture, args.manifest, matrix=matrix)
            if args.private_capture
            else ()
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print(json.dumps({"codes": ["slot.manifest_invalid"]}))
        return 1
    for row in matrix.records:
        print(
            json.dumps(
                {
                    "source": row.source_name or row.proposed_source_name,
                    "slot": row.slot_id,
                    "status": row.status,
                    "codes": row.reason_codes,
                },
                sort_keys=True,
            )
        )
    print(
        json.dumps(
            {
                "rows": len(matrix.records),
                "verified": sum(row.status == "verified" for row in matrix.records),
                "blocked": sum(row.status == "blocked" for row in matrix.records),
                "activation_ready": False,
                **(
                    {"parser_samples": len(replay), "field_bindings": sum(r[2] for r in replay)}
                    if args.private_capture
                    else {}
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
