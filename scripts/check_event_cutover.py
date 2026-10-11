#!/usr/bin/env python
"""Read-only v3 acceptance audit; never activate, dispatch, publish or retire."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from investo.models.event_config import EVENT_V3_ACTIVE_READY
from investo.models.event_quality import EventCutoverAcceptance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--reviewed-code-sha", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        with args.evidence.open("rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        with args.policy.open("rb") as stream:
            policy = stream.read(64 * 1024 + 1)
        if len(data) > 1024 * 1024 or len(policy) > 64 * 1024:
            raise ValueError("cutover.budget_exhausted")
        evidence = EventCutoverAcceptance.model_validate_json(data)
        if (
            evidence.reviewed_code_sha != args.reviewed_code_sha
            or evidence.policy_sha256 != sha256(policy).hexdigest()
        ):
            raise ValueError("cutover.identity_invalid")
    except (OSError, ValueError):
        print(json.dumps({"codes": ["cutover.evidence_invalid"]}))
        return 1
    print(
        json.dumps(
            dict(
                status=evidence.status,
                code_ready=evidence.code_ready,
                human_ready={
                    s: evidence.human_market_ready(s)
                    for s in ("domestic-equity", "us-equity", "crypto")
                },
                source_ready=evidence.source_gate_ready,
                cursor_ready=evidence.cursor_gate_ready,
                release_ready=evidence.capability_ready
                and EVENT_V3_ACTIVE_READY
                and bool(evidence.release_instruction_ref),
                accepted_scheduled_runs=len(
                    {o.run_id for o in evidence.scheduled_observations if o.accepted}
                ),
                cleanup_ready=evidence.status == "cleanup_complete",
                codes=[],
            ),
            sort_keys=True,
        )
    )
    return int(
        args.require_ready
        and evidence.status not in {"ready", "active_observing", "accepted", "cleanup_complete"}
    )


if __name__ == "__main__":
    raise SystemExit(main())
