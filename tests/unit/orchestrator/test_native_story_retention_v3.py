"""Ledger retention, active-record and serialized-byte bounds are independent."""

from datetime import timedelta

import pytest

from investo.models.event_story import StoryLedger
from investo.orchestrator.event_story import story_ledger_bytes
from tests._helpers.event_context_v3 import NOW
from tests.unit.models.test_event_story_contract_v3 import record


def test_active_limit_and_exact_retention_boundaries():
    base = record()
    records = tuple(base.model_copy(update={"story_id": f"{i:064x}"}) for i in range(200))
    assert (
        len(
            StoryLedger.model_validate_json(
                story_ledger_bytes(records, (), observed_at=NOW)
            ).records
        )
        == 200
    )
    with pytest.raises(ValueError, match="record_budget_exhausted"):
        story_ledger_bytes(
            (*records, base.model_copy(update={"story_id": "f" * 64})), (), observed_at=NOW
        )
    before = StoryLedger.model_validate_json(
        story_ledger_bytes(
            (base,), (), observed_at=NOW + timedelta(days=180) - timedelta(seconds=1)
        )
    ).records[0]
    after = StoryLedger.model_validate_json(
        story_ledger_bytes((base,), (), observed_at=NOW + timedelta(days=180))
    ).records[0]
    assert before.disposition == "active" and after.disposition == "archived_unknown"
    assert before.latest_state == after.latest_state == "announced"
    assert after.last_evidence_at == NOW
    closed = base.model_copy(
        update={
            "latest_state": "resolved",
            "disposition": "closed",
            "closed_at": NOW,
            "resolution_evidence": base.source_refs,
        }
    )
    assert StoryLedger.model_validate_json(
        story_ledger_bytes(
            (closed,), (), observed_at=NOW + timedelta(days=90) - timedelta(seconds=1)
        )
    ).records
    assert not StoryLedger.model_validate_json(
        story_ledger_bytes((closed,), (), observed_at=NOW + timedelta(days=90))
    ).records


def test_oversized_provenance_fails_before_any_write():
    base = record()
    refs = tuple(
        base.source_refs[0].model_copy(
            update={
                "context_ref": base.source_refs[0].context_ref.model_copy(
                    update={"document_id": f"{i:064x}"}
                )
            }
        )
        for i in range(64)
    )
    records = tuple(
        base.model_copy(update={"segment": market, "story_id": f"{i:064x}", "source_refs": refs})
        for market in ("domestic-equity", "us-equity", "crypto")
        for i in range(200)
    )
    with pytest.raises(ValueError, match="record_budget_exhausted"):
        story_ledger_bytes(records, (), observed_at=NOW)
