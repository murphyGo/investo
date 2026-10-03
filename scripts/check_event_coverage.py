#!/usr/bin/env python
"""Check frozen synthetic event replay; emit only bounded IDs, counts and codes."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path

from _event_coverage_replay import replay_event_manifest  # type: ignore[import-not-found]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests/fixtures/event_briefing/manifest.json",
    )
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        results = asyncio.run(replay_event_manifest(args.manifest))
    except Exception:
        print(json.dumps({"codes": ["replay.input_invalid"]}))
        return 1
    for result in results:
        print(json.dumps(asdict(result), ensure_ascii=True, sort_keys=True))
    passed = all(result.passed for result in results)
    print(
        json.dumps(
            {
                "scenario_groups": len({result.scenario_id for result in results}),
                "input_replay_variants": len(results),
                "passed_variants": sum(result.passed for result in results),
                "output_inventory_count": 18,
                "human_semantic_review": "pending",
                "codes": [] if passed else ["replay.failed"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
