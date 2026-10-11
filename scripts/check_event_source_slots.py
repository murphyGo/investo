#!/usr/bin/env python
"""Validate source slot evidence offline. Never fetch, generate or publish."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from investo.models.enrichment import SLOT_REQUIRED_FIELDS
from investo.sources.event_evidence import load_source_slot_qualification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("ops/event_source_slot_qualification.json")
    )
    args = parser.parse_args()
    try:
        matrix = load_source_slot_qualification(args.manifest)
        if {row.slot_id for row in matrix.records} != set(SLOT_REQUIRED_FIELDS):
            raise ValueError("slot.matrix_incomplete")
    except ValueError:
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
