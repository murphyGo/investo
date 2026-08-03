#!/usr/bin/env python3
"""Prepare one offline Commons exact-file curated review packet (U-146).

This command never fetches, approves, files, or edits repository assets.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Literal, cast

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from investo.visuals.curated_supply import (  # noqa: E402
    CuratedSupplyError,
    prepare_commons_evidence,
    write_pending_review_packet,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--category", choices=("person", "topic", "asset"), required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--verified-on", required=True, type=date.fromisoformat)
    parser.add_argument("--variant-kind", choices=("original", "thumbnail"), default="thumbnail")
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evidence = prepare_commons_evidence(
            asset_id=args.asset_id,
            category=cast(Literal["person", "topic", "asset"], args.category),
            expected_title=args.expected_title,
            snapshot_path=args.snapshot,
            binary_path=args.binary,
            verified_on=args.verified_on,
            variant_kind=cast(Literal["original", "thumbnail"], args.variant_kind),
        )
        if evidence.assessment != "READY_FOR_REVIEW":
            print(
                "review blocked: " + ",".join(evidence.blocker_codes),
                file=sys.stderr,
            )
            return 1
        output = write_pending_review_packet(
            evidence=evidence,
            snapshot_path=args.snapshot,
            binary_path=args.binary,
            output_dir=args.output_dir,
            repo_root=_REPO_ROOT,
        )
    except CuratedSupplyError as exc:
        print(f"curated review preparation failed: {exc}", file=sys.stderr)
        return 1
    print(f"READY_FOR_REVIEW: {output}")
    print("No approval, manifest, registry entry, or U137 clearance was created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
