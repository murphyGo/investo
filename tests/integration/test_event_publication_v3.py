"""Real native archive, sidecar, ledgers and CAS over a local bare Git remote."""

from __future__ import annotations

import json

import pytest

from investo.briefing.event_story import attach_story_follow_ups
from investo.models.publication import PublishReceipt
from investo.orchestrator import pipeline
from investo.orchestrator.event_publication import (
    load_event_v3_baseline,
    prepare_event_v3_publication,
)
from investo.orchestrator.event_story import STORY_LEDGER_PATH
from investo.publisher.public_document import finalize_public_bundle
from investo.publisher.publication_receipts import PublicationReceiptError
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import TARGET, native_case, native_context
from tests.integration.test_event_publication_boundary import (
    FailingRunner,
    Repository,
    _git,
)
from tests.integration.test_event_publication_boundary import (
    repository as repository,
)


def prepared(repository: Repository):
    baseline = load_event_v3_baseline(
        target_date=TARGET, observed_at=NOW, baseline_sha=repository.baseline
    )
    item, draft = native_case()
    draft = attach_story_follow_ups(draft, (), observed_at=NOW)
    bundle = finalize_public_bundle({draft.segment: draft}, context=native_context((item, draft)))
    request, metadata = prepare_event_v3_publication(
        baseline, bundle, run_id="native-transaction", observed_at=NOW
    )
    return baseline, bundle, request, metadata


async def test_native_archive_projection_and_story_share_confirmed_commit(repository: Repository):
    _, bundle, request, metadata = prepared(repository)
    observed: list[PublishReceipt] = []
    paths = await pipeline._stage_publish_segments(
        {d.segment: d.payload for d in bundle.documents},
        TARGET,
        phase_one_complete=True,
        finalized_bundle=bundle,
        publication_request=request,
        transactional_metadata=metadata,
        publication_receipts=observed,
    )
    assert repository.head() == repository.remote_head() != repository.baseline
    assert observed[-1].status == "remote_confirmed"
    for path in (*paths.values(), *metadata):
        assert _git(repository.remote, "show", f"main:{path}").stdout.encode() == path.read_bytes()
    ledger = json.loads(STORY_LEDGER_PATH.read_bytes())
    assert (
        ledger["records"][0]["verified_delta"]["reader_text"]
        in bundle.documents[0].rendered_markdown
    )
    from_remote = load_event_v3_baseline(
        target_date=TARGET, observed_at=NOW, baseline_sha=repository.remote_head()
    )
    assert (
        from_remote.stories.records[0]
        == bundle.documents[0].story_publication_deltas[0].next_record
    )


@pytest.mark.parametrize("phase", ["pre_commit", "post_commit"])
async def test_native_failure_preserves_commit_boundary(repository: Repository, phase: str):
    _, bundle, request, metadata = prepared(repository)
    snapshots = {p: p.read_bytes() if p.exists() else None for p in metadata}
    with pytest.raises(PublicationReceiptError) as caught:
        await pipeline._stage_publish_segments(
            {d.segment: d.payload for d in bundle.documents},
            TARGET,
            phase_one_complete=True,
            finalized_bundle=bundle,
            publication_request=request,
            transactional_metadata=metadata,
            git_runner=FailingRunner(repository, phase, block=False),
        )
    assert caught.value.phase == phase
    assert repository.remote_head() == repository.baseline
    # Unconfirmed local files never become the next run's baseline.
    baseline = load_event_v3_baseline(
        target_date=TARGET, observed_at=NOW, baseline_sha=repository.baseline
    )
    assert baseline.stories.records == ()
    assert baseline.identity["us-equity"].segment_receipts == ()
    if phase == "pre_commit":
        assert repository.head() == repository.baseline
        assert (repository.work / ".git/index").read_bytes() == repository.original_index
        for path, content in snapshots.items():
            assert (path.read_bytes() if path.exists() else None) == content
    else:
        assert repository.head() != repository.baseline
        assert STORY_LEDGER_PATH.exists()
        assert caught.value.receipt.status == "outcome_unknown"


def test_native_fixed_baseline_ignores_dirty_local_ledger(repository: Repository):
    baseline, _, _, _ = prepared(repository)
    STORY_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORY_LEDGER_PATH.write_text("private uncommitted invalid text")
    second = load_event_v3_baseline(
        target_date=TARGET, observed_at=NOW, baseline_sha=repository.baseline
    )
    assert second == baseline
    assert second.stories.available and second.stories.records == ()
