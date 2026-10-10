"""Hash-only cumulative history, actual byte bounds and remote-only reads."""

import json
import subprocess
from datetime import timedelta

import pytest

from investo.models.event_identity import CanonicalEventLedger, FactSlotReceipt, OccurrenceAlias
from investo.orchestrator.event_receipts import (
    event_identity_v3_bytes,
    event_identity_v3_path,
    load_committed_event_identity_v3,
)
from tests._helpers.event_context_v3 import NOW
from tests.unit.briefing.test_event_identity_v3 import binding, receipt, source


def current():
    doc, proposed = source()
    return receipt(binding(doc, proposed))


def test_alias_only_history_keeps_id_facts_and_evidence_freshness() -> None:
    old = current()
    clock = NOW + timedelta(days=1)
    alias = OccurrenceAlias(key_hash="f" * 64, basis="official_key", stage="unknown")
    newer = old.model_copy(
        update={"occurrence_aliases": (*old.occurrence_aliases, alias), "last_evidence_at": clock}
    )
    data = event_identity_v3_bytes((old,), (newer,), segment="us-equity", published_at=clock)
    restored = CanonicalEventLedger.model_validate_json(data).records[0]
    assert restored.event_id == old.event_id and restored.last_evidence_at == NOW
    assert alias in restored.occurrence_aliases
    assert data == event_identity_v3_bytes(
        (old,), (newer,), segment="us-equity", published_at=clock
    )
    assert b"Acme" not in data and b"1200" not in data and b"example.com" not in data


def test_rolling_window_and_cumulative_facts_are_not_last_observation_only() -> None:
    old = current()
    clock = NOW + timedelta(days=1)
    update = old.model_copy(
        update={
            "cumulative_fact_hashes": ("e" * 64,),
            "fact_slots": (
                FactSlotReceipt(slot_key_hash="f" * 64, fact_hash="e" * 64, status="actual"),
            ),
            "last_evidence_at": clock,
        }
    )
    data = event_identity_v3_bytes((old,), (update,), segment="us-equity", published_at=clock)
    restored = CanonicalEventLedger.model_validate_json(data).records[0]
    assert set(restored.cumulative_fact_hashes) == {*old.cumulative_fact_hashes, "e" * 64}
    assert restored.last_evidence_at == clock
    empty = event_identity_v3_bytes(
        (restored,), (), segment="us-equity", published_at=clock + timedelta(days=31)
    )
    assert not CanonicalEventLedger.model_validate_json(empty).records


def test_utf8_overflow_is_explicit_and_does_not_truncate_history() -> None:
    row = current()
    records = tuple(row.model_copy(update={"event_id": f"{i:024x}"}) for i in range(2000))
    with pytest.raises(ValueError, match="ledger_budget_exhausted"):
        event_identity_v3_bytes((), records, segment="us-equity", published_at=NOW)


def test_fixed_remote_reader_never_reads_dirty_local_ledger(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = event_identity_v3_path("us-equity")
    path.parent.mkdir(parents=True)
    path.write_text("PRIVATE_DIRTY_LOCAL")
    calls = []
    sha = "a" * 40

    def runner(args, **kwargs):
        calls.append(args)
        if args[1] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, sha + "\n", "")
        if "ls-tree" in args:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)

    result = load_committed_event_identity_v3(
        sha, segment="us-equity", observed_at=NOW, runner=runner
    )
    assert result.availability == "available" and not result.segment_receipts
    assert all(args[1] != "fetch" for args in calls)
    assert path.read_text() == "PRIVATE_DIRTY_LOCAL"


@pytest.mark.parametrize("case", ["malformed", "wrong_segment", "oversized"])
def test_malformed_wrong_market_and_oversized_remote_history_is_unavailable(case) -> None:
    payload = (
        "{bad"
        if case == "malformed"
        else json.dumps({"schema_version": 3, "segment": "crypto", "records": []})
        if case == "wrong_segment"
        else "x" * (1024 * 1024 + 1)
    )
    sha = "a" * 40
    path = event_identity_v3_path("us-equity").as_posix()

    def runner(args, **kwargs):
        if args[1] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, sha + "\n", "")
        if "ls-tree" in args:
            # Tree hashing expects a full mode/type/object/path row; the explicit
            # --name-only presence read expects only the path.
            output = path + "\n" if "--name-only" in args else f"100644 blob {'b' * 40}\t{path}\0"
            return subprocess.CompletedProcess(args, 0, output, "")
        if args[1] == "show":
            return subprocess.CompletedProcess(args, 0, payload, "")
        raise AssertionError(args)

    result = load_committed_event_identity_v3(
        sha, segment="us-equity", observed_at=NOW, runner=runner
    )
    assert result.availability == "unavailable" and not result.segment_receipts


def test_initial_serialization_is_stable_under_hash_collection_permutations() -> None:
    row = current()
    aliases = (
        *row.occurrence_aliases,
        OccurrenceAlias(key_hash="f" * 64, basis="official_key", stage="unknown"),
    )
    forward = row.model_copy(
        update={
            "occurrence_aliases": aliases,
            "revision_hashes": ("d" * 64, "c" * 64),
            "document_aliases": ("b" * 64, "a" * 64),
        }
    )
    reverse = forward.model_copy(
        update={
            "occurrence_aliases": tuple(reversed(aliases)),
            "revision_hashes": tuple(reversed(forward.revision_hashes)),
            "document_aliases": tuple(reversed(forward.document_aliases)),
        }
    )
    assert event_identity_v3_bytes(
        (), (forward,), segment="us-equity", published_at=NOW
    ) == event_identity_v3_bytes((), (reverse,), segment="us-equity", published_at=NOW)


def test_legacy_replay_does_not_invent_canonical_facts_or_live_baseline() -> None:
    from investo.models.events import EventIdentityReceipt
    from investo.orchestrator.event_receipts import inspect_legacy_event_receipts

    old = EventIdentityReceipt(
        event_id="a" * 24,
        event_key_hash="b" * 64,
        semantic_key_hash="c" * 64,
        document_aliases=("d" * 64,),
        fact_hashes=("e" * 64,),
        published_at=NOW,
    )
    replay = inspect_legacy_event_receipts((old,))[0]
    assert replay.fact_hashes == old.fact_hashes and replay.event_id == old.event_id
    assert set(replay.model_dump()) == {
        "basis",
        "event_id",
        "document_aliases",
        "revision_hashes",
        "fact_hashes",
        "published_at",
    }
    assert not hasattr(replay, "canonical") and not hasattr(replay, "story_id")
