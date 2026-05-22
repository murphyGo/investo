#!/usr/bin/env python
"""Run offline generated-briefing quality replay for one target date."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from investo.publisher.briefing_replay import replay_generated_briefing_quality


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_date", help="YYYY-MM-DD")
    parser.add_argument("--archive-root", default="archive")
    args = parser.parse_args()
    findings = replay_generated_briefing_quality(
        date.fromisoformat(args.target_date),
        archive_root=Path(args.archive_root),
    )
    for finding in findings:
        segment = finding.segment or "bundle"
        print(f"{finding.severity}\t{segment}\t{finding.code}\t{finding.message}")
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
