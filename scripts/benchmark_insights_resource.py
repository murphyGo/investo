"""Measure u180's actual phase against synthetic near-cap local Git snapshots.

Run from the checkout: PYTHONPATH=src:. .venv/bin/python
scripts/benchmark_insights_resource.py. Fixtures and pushes stay in a temporary
local bare repository; this is not provider permission or production evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from tests._helpers.insights import HREF, NOW, capture, metric, qualification

from investo.models.insights import (
    HistoryDefinition,
    InsightDefinitionQualification,
    InsightHistory,
    InsightHistoryRow,
    InsightSourceQualification,
    InsightTime,
    SourceInsightEnvelope,
    SourceInsightEvent,
    canonical_bytes,
    digest,
)
from investo.orchestrator.insights import InsightCapture, InsightsConfig
from investo.orchestrator.insights_projection import project_module, update_history
from investo.orchestrator.insights_publication import _phase
from investo.publisher.insights.store import prepare_bundle


def inputs():
    crypto = tuple(
        metric(metric_id=f"m{i}", definition_id=f"d{i}", field_scope=f"v{i}") for i in range(32)
    )
    macro = tuple(
        metric(
            module="macro",
            metric_id=f"macro-m{i}",
            definition_id=f"macro-d{i}",
            field_scope=f"macro-v{i}",
            cadence="daily",
            calendar_policy="treasury",
            time=InsightTime(
                basis="effective_date",
                precision="date",
                local_date=NOW.date(),
                source_timezone="America/New_York",
            ),
        )
        for i in range(32)
    )
    events = tuple(
        SourceInsightEvent(
            event_id=f"fixture:{i}",
            definition_id="calendar-fixture",
            source_name=crypto[0].source_name,
            label=f"합성 일정 {i}",
            time=InsightTime(
                basis="schedule",
                precision="date",
                local_date=NOW.date(),
                source_timezone="America/New_York",
            ),
            endpoint=HREF,
            field_scope="events",
            source_href=HREF,
        )
        for i in range(128)
    )
    event_rights = InsightSourceQualification(
        source_name=crypto[0].source_name,
        endpoint=HREF,
        field_scope="events",
        definition_ids=("calendar-fixture",),
        definitions=(
            InsightDefinitionQualification(
                definition_id="calendar-fixture",
                module="calendar",
                public_id="calendar-fixture",
            ),
        ),
        display_allowed=True,
        public_git_history_allowed=True,
        retention_allowed=False,
        evidence_hrefs=("https://example.invalid/terms",),
        checked_on=NOW.date(),
        attribution="Synthetic permission fixture " + "x" * 900,
        allowed_hrefs=(HREF,),
        runtime_probe_state="ok",
    )
    rights = (*tuple(qualification(m) for m in (*crypto, *macro)), event_rights)
    metric_envelopes = tuple(
        SourceInsightEnvelope(
            source_name=crypto[0].source_name,
            origin_adapter_name=crypto[0].source_name,
            metrics=group[i : i + 16],
        )
        for group in (crypto, macro)
        for i in (0, 16)
    )
    envelopes = (
        *metric_envelopes,
        SourceInsightEnvelope(
            source_name=crypto[0].source_name,
            origin_adapter_name=crypto[0].source_name,
            events=events,
        ),
    )
    return InsightCapture(envelopes, capture().outcomes), rights


def history_rows(definitions: tuple[HistoryDefinition, ...], *, daily: bool, days: int):
    rows = []
    for definition in definitions:
        for offset in range(days):
            at = NOW - timedelta(days=offset)
            clock = (
                InsightTime(
                    basis="effective_date",
                    precision="date",
                    local_date=at.date(),
                    source_timezone="America/New_York",
                )
                if daily
                else InsightTime(basis="source_response", precision="exact", exact_at=at)
            )
            value = Decimal(offset)
            rows.append(
                InsightHistoryRow(
                    definition_key=definition.key,
                    observation_key=at.date().isoformat(),
                    value=value,
                    time=clock,
                    record_hash=digest(
                        canonical_bytes(
                            {"value": str(value), "time": clock.model_dump(mode="json")}
                        )
                    ),
                )
            )
    return tuple(rows)


def git(root: Path, *args: str):
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)


def setup(root: Path) -> int:
    captured, qualified = inputs()
    modules = tuple(
        project_module(
            name,
            captured,
            qualified,
            run_started_at=NOW,
            collection_completed_at=NOW,
            evaluated_at=NOW,
        )
        for name in ("crypto", "macro", "calendar")
    )
    histories = {}
    for current, days in zip(modules[:2], (275, 250), strict=True):
        initial = update_history(current, None, qualified)
        history = InsightHistory(
            module=current.module,
            definitions=initial.definitions,
            rows=history_rows(initial.definitions, daily=current.module == "macro", days=days),
        )
        histories[current.module] = update_history(current, history, qualified)
    prepared = prepare_bundle(modules, histories)
    work, remote = root / "work", root / "remote.git"
    git(root, "init", "--bare", str(remote))
    git(root, "init", "-b", "main", str(work))
    git(work, "config", "user.name", "Resource Fixture")
    git(work, "config", "user.email", "fixture@example.invalid")
    for relative, data in prepared.files:
        target = work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    permissions = work / "ops/insights_source_qualification.json"
    permissions.parent.mkdir()
    permissions.write_bytes(
        canonical_bytes(
            {"schema_version": 1, "qualifications": [q.model_dump(mode="json") for q in qualified]}
        )
    )
    git(work, "add", "site_docs", "ops")
    git(work, "commit", "-m", "Synthetic resource baseline")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-u", "origin", "main")
    return sum(len(canonical_bytes(history)) for history in histories.values())


def measure(root: Path, history_bytes: int):
    captured, _ = inputs()
    os.chdir(root / "work")
    baseline_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    phase_at = NOW + timedelta(seconds=1)
    rss_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    cpu_start, wall_start = time.process_time(), time.monotonic()
    outcome = _phase(
        InsightsConfig("active", ("crypto", "macro", "calendar")),
        captured,
        run_started_at=phase_at,
        collection_completed_at=phase_at,
        evaluated_at=phase_at,
        write_allowed=True,
        runner=None,
    )
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - rss_start
    remote_sha = subprocess.check_output(
        ["git", "-C", str(root / "remote.git"), "rev-parse", "main"], text=True
    ).strip()
    record = {
        "kind": "actual foundation phase with synthetic three-module "
        "local bare-Git baseline and push",
        "metrics": 64,
        "events": 128,
        "history_bytes": history_bytes,
        "status": outcome.status,
        "new_commit_remote_confirmed": outcome.receipt is not None
        and outcome.receipt.local_sha == remote_sha
        and remote_sha != baseline_sha,
        "additional_rss_bytes": rss * (1 if sys.platform == "darwin" else 1024),
        "cpu_seconds": time.process_time() - cpu_start,
        "wall_seconds": time.monotonic() - wall_start,
        "source_http_calls": 0,
        "llm_calls": 0,
        "telegram_calls": 0,
    }
    print(json.dumps(record))
    return not (
        outcome.status == "remote_confirmed"
        and record["new_commit_remote_confirmed"]
        and record["additional_rss_bytes"] <= 96 * 1024 * 1024
        and record["cpu_seconds"] <= 5
        and record["wall_seconds"] <= 60
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--history-bytes", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return measure(args.worker, args.history_bytes)
    with tempfile.TemporaryDirectory(prefix="investo-insights-resource-") as directory:
        root = Path(directory)
        history_bytes = setup(root)
        # A fresh process excludes fixture construction from incremental phase RSS.
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--worker",
                str(root),
                "--history-bytes",
                str(history_bytes),
            ],
            check=False,
        )
        return child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
