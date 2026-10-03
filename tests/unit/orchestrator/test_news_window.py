"""Pure window planning, recipient consumption and fixed-tree E11 metadata."""

import json
import subprocess
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest

from investo.models.coverage import SourceWindowCoverage
from investo.models.items import NormalizedItem
from investo.models.news_window import (
    NewsCursor,
    NewsCursorBaseline,
    NewsCursorLedger,
    NewsObservationWindow,
    NewsSeenRevision,
    NewsWindowConfig,
    NewsWindowConsumption,
    NewsWindowPlan,
)
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.orchestrator.news_window import (
    NEWS_CURSOR_PATH,
    deduplicate_news_items,
    filter_news_items_for_segment,
    load_committed_news_cursors,
    load_news_replay_windows,
    make_news_window_consumptions,
    make_news_window_plan,
    news_document_revision,
    news_manifest_path,
    prepare_news_window_publication,
    union_news_windows,
)
from investo.publisher.errors import PublisherGitError

END = datetime(2026, 9, 27, 22, tzinfo=UTC)  # Monday 07:00 KST, Friday price date.
PRICE_DATE = date(2026, 9, 25)
RUN = "window-run"


def _baseline(
    *cursors: NewsCursor,
    seen: tuple[NewsSeenRevision, ...] = (),
    event_paths: tuple[Path, ...] = (),
) -> NewsCursorBaseline:
    return NewsCursorBaseline(
        "a" * 40,
        "b" * 64,
        NewsCursorLedger(cursors=tuple(cursors), seen_revisions=seen),
        "c" * 64,
        (NEWS_CURSOR_PATH, news_manifest_path(RUN), *event_paths),
        RUN,
    )


def _plan(baseline: NewsCursorBaseline | None = None, **kwargs: object) -> NewsWindowPlan:
    return make_news_window_plan(
        NewsWindowConfig("active"),
        run_id=RUN,
        target_date=PRICE_DATE,
        observed_at=END,
        source_recipients={"rss": (US_EQUITY,)},
        baseline=baseline,
        **kwargs,
    )


def _item(
    *,
    at: datetime = END - timedelta(hours=12),
    source: str = "rss",
    summary: str = "Company launched its new service.",
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category="news",
        title="Service launch",
        summary=summary,
        url="https://example.com/news/launch",
        published_at=at,
    )


def _coverage(
    plan: NewsWindowPlan,
    completeness: Literal["full", "partial", "unknown"] = "full",
    **kwargs: object,
) -> SourceWindowCoverage:
    window = plan.windows[("rss", US_EQUITY)]
    return SourceWindowCoverage(
        "rss",
        window.requested_start,
        window.end_utc,
        pages=1,
        completeness=completeness,
        basis="provider_pagination" if completeness == "full" else "none",
        **kwargs,
    )


def _sealed(plan: NewsWindowPlan, items: tuple[NormalizedItem, ...] = ()) -> NewsWindowConsumption:
    (generated,) = make_news_window_consumptions(plan, segment=US_EQUITY, items=items)
    return replace(generated, phase="sealed", sealed_markdown_sha256="d" * 64)


def test_bootstrap_includes_weekend_without_changing_price_date() -> None:
    plan = _plan()
    window = plan.windows[("rss", US_EQUITY)]
    assert window.logical_start == window.requested_start == END - timedelta(hours=72)
    weekend = (
        _item(at=END - timedelta(hours=48), summary="Saturday service announcement."),
        _item(),
    )
    assert filter_news_items_for_segment(plan, US_EQUITY, weekend) == weekend
    assert plan.target_date == PRICE_DATE


@pytest.mark.parametrize(
    ("age_hours", "requested_hours", "gap_hours", "fetch"),
    [
        (72, 96, 0, True),
        (24 * 10, 24 * 7, 24 * 3, True),
        (0, 0, 0, False),
        (-2, 0, 0, False),
    ],
)
def test_cursor_overlap_maximum_gap_and_clock_hold(
    age_hours: int,
    requested_hours: int,
    gap_hours: int,
    fetch: bool,
) -> None:
    baseline = _baseline(
        NewsCursor(source_name="rss", segment=US_EQUITY, end_utc=END - timedelta(hours=age_hours))
    )
    plan = _plan(baseline)
    window = plan.windows[("rss", US_EQUITY)]
    assert window.requested_start == END - timedelta(hours=requested_hours)
    assert window.gap_seconds == gap_hours * 3600
    assert window.fetch_required is fetch
    assert bool(union_news_windows(plan)) is fetch


@pytest.mark.parametrize(("day", "hours"), [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)])
def test_replay_uses_recipient_calendar_day_across_dst(day: date, hours: int) -> None:
    plan = make_news_window_plan(
        NewsWindowConfig("active"),
        run_id=RUN,
        target_date=day,
        observed_at=END,
        source_recipients={"rss": (US_EQUITY,)},
        replay=True,
    )
    window = plan.windows[("rss", US_EQUITY)]
    assert window.end_utc - window.requested_start == timedelta(hours=hours)
    assert plan.observed_at == window.end_utc


def test_replay_frozen_manifest_ignores_live_cursor_and_today_clock() -> None:
    saved = NewsObservationWindow(
        END - timedelta(days=3), END - timedelta(days=4), END, "scheduled", "old-run", "f" * 40
    )
    baseline = replace(_baseline(), run_id="unrelated-live-run")
    plan = _plan(baseline, replay=True, replay_windows={("rss", US_EQUITY): saved})
    restored = plan.windows[("rss", US_EQUITY)]
    assert (restored.logical_start, restored.requested_start, restored.end_utc) == (
        saved.logical_start,
        saved.requested_start,
        saved.end_utc,
    )
    assert restored.mode == "replay" and plan.baseline_ref == "f" * 40
    assert plan.baseline_cursor_hash is None
    assert _plan(baseline, dry_run=True).baseline_ref is None


def test_union_once_then_recipient_filter_respects_different_cursors() -> None:
    baseline = _baseline(
        NewsCursor(source_name="rss", segment=US_EQUITY, end_utc=END - timedelta(hours=12)),
        NewsCursor(source_name="rss", segment=CRYPTO, end_utc=END - timedelta(hours=72)),
    )
    plan = make_news_window_plan(
        NewsWindowConfig("active"),
        run_id=RUN,
        target_date=PRICE_DATE,
        observed_at=END,
        source_recipients={"rss": (US_EQUITY, CRYPTO)},
        baseline=baseline,
    )
    union = union_news_windows(plan)
    assert len(union) == 1 and union["rss"].requested_start == END - timedelta(hours=96)
    old = _item(at=END - timedelta(hours=48))
    assert filter_news_items_for_segment(plan, US_EQUITY, (old,), baseline) == ()
    assert filter_news_items_for_segment(plan, CRYPTO, (old,), baseline) == (old,)
    with pytest.raises(TypeError):
        union["other"] = union["rss"]  # type: ignore[index]


def test_filter_keeps_nonoptin_price_lookahead_and_new_revision_only() -> None:
    current = _item()
    revision = news_document_revision(current)
    seen = NewsSeenRevision(
        source_name="rss",
        segment=US_EQUITY,
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        observed_at=END - timedelta(hours=1),
    )
    baseline = _baseline(seen=(seen,))
    plan = _plan(baseline)
    changed = _item(summary="Company launched its service in another 12 countries.")
    price = current.model_copy(
        update={"category": "price", "published_at": END - timedelta(days=9)}
    )
    future = current.model_copy(update={"scheduled_at": END + timedelta(days=1)})
    legacy = _item(at=END - timedelta(days=10), source="legacy")
    rows = (current, current, changed, price, future, legacy)
    assert filter_news_items_for_segment(plan, US_EQUITY, rows, baseline) == (
        changed,
        price,
        future,
        legacy,
    )
    assert deduplicate_news_items((current, current, changed)) == (current, changed)
    assert filter_news_items_for_segment(replace(plan, mode="off"), US_EQUITY, rows) == rows
    assert filter_news_items_for_segment(replace(plan, mode="shadow"), US_EQUITY, rows) == rows
    with pytest.raises(ValueError, match="differs from plan"):
        filter_news_items_for_segment(
            plan, US_EQUITY, rows, replace(baseline, cursor_hash="e" * 64)
        )


def test_consumption_includes_successful_zero_input_and_only_actual_source_revisions() -> None:
    plan = _plan(_baseline())
    (empty,) = make_news_window_consumptions(plan, segment=US_EQUITY, items=())
    assert empty.documents == () and empty.phase == "generated"
    (receipt,) = make_news_window_consumptions(
        plan, segment=US_EQUITY, items=(_item(), _item(), _item(source="foreign"))
    )
    assert receipt.documents == (news_document_revision(_item()),)
    assert make_news_window_consumptions(plan, segment=DOMESTIC_EQUITY, items=()) == ()
    assert (
        make_news_window_consumptions(replace(plan, mode="shadow"), segment=US_EQUITY, items=())
        == ()
    )


@pytest.mark.parametrize("completeness", ["full", "partial", "unknown"])
@pytest.mark.parametrize("sealed", [True, False])
def test_cursor_only_advances_full_coverage_with_exact_sealed_consumption(
    completeness: Literal["full", "partial", "unknown"],
    sealed: bool,
) -> None:
    baseline = _baseline()
    plan = _plan(baseline)
    receipt = (
        _sealed(plan, (_item(),))
        if sealed
        else make_news_window_consumptions(plan, segment=US_EQUITY, items=(_item(),))[0]
    )
    prepared = prepare_news_window_publication(
        plan, baseline, coverage=(_coverage(plan, completeness),), consumed=(receipt,)
    )
    assert prepared is not None
    request, metadata = prepared
    ledger = NewsCursorLedger.model_validate_json(metadata[NEWS_CURSOR_PATH])
    assert bool(ledger.cursors) is (completeness == "full" and sealed)
    assert bool(ledger.seen_revisions) is (completeness == "full" and sealed)
    assert request.baseline_metadata_hash == baseline.metadata_hash
    assert set(request.metadata_paths) == set(metadata)
    manifest = json.loads(metadata[news_manifest_path(RUN)])
    assert manifest["baseline_cursor_hash"] == baseline.cursor_hash
    assert "own_commit_sha" not in manifest
    assert b"Service launch" not in b"".join(metadata.values())


def test_unknown_geometry_failure_and_unpublished_sibling_hold_cursors() -> None:
    prior = NewsCursor(source_name="rss", segment=US_EQUITY, end_utc=END - timedelta(days=1))
    baseline = _baseline(prior)
    plan = _plan(baseline)
    coverage = replace(_coverage(plan), requested_start=END - timedelta(hours=1))
    prepared = prepare_news_window_publication(
        plan, baseline, coverage=(coverage,), consumed=(_sealed(plan),)
    )
    assert prepared is not None
    assert NewsCursorLedger.model_validate_json(prepared[1][NEWS_CURSOR_PATH]).cursors == (prior,)
    # A wider, stale provider response is not the receipt for this run's exact union request.
    wider = replace(_coverage(plan), requested_start=END - timedelta(days=6))
    prepared = prepare_news_window_publication(
        plan, baseline, coverage=(wider,), consumed=(_sealed(plan),)
    )
    assert prepared is not None
    assert NewsCursorLedger.model_validate_json(prepared[1][NEWS_CURSOR_PATH]).cursors == (prior,)
    prepared = prepare_news_window_publication(
        plan, baseline, coverage=(_coverage(plan),), consumed=()
    )
    assert prepared is not None
    assert NewsCursorLedger.model_validate_json(prepared[1][NEWS_CURSOR_PATH]).cursors == (prior,)


def test_publication_requires_exact_receipt_and_combines_all_metadata_cas_paths() -> None:
    event_path = Path("archive/_meta/event_receipts.json")
    baseline = _baseline(event_paths=(event_path,))
    plan = _plan(baseline)
    receipt = _sealed(plan)
    with pytest.raises(ValueError, match="CAS fields"):
        prepare_news_window_publication(plan, baseline, coverage=(), consumed=())
    with pytest.raises(ValueError, match="differs from plan"):
        prepare_news_window_publication(
            plan,
            baseline,
            coverage=(_coverage(plan),),
            consumed=(replace(receipt, baseline_ref="e" * 40),),
            event_metadata={event_path: b"{}"},
        )
    result = prepare_news_window_publication(
        plan,
        baseline,
        coverage=(_coverage(plan),),
        consumed=(receipt,),
        event_metadata={event_path: b"{}"},
    )
    assert result is not None
    assert result[1][event_path] == b"{}" and event_path in result[0].metadata_paths


@pytest.mark.parametrize("flag", ["off", "shadow", "replay", "dry_run"])
def test_nonproduction_paths_prepare_no_transaction_and_require_no_baseline(flag: str) -> None:
    plan = _plan()
    plan = replace(plan, **({"mode": flag} if flag in {"off", "shadow"} else {flag: True}))
    assert prepare_news_window_publication(plan, None, coverage=(), consumed=()) is None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()


def test_baseline_reads_only_fixed_commit_ignoring_dirty_worktree(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.invalid")
    target = tmp_path / NEWS_CURSOR_PATH
    target.parent.mkdir(parents=True)
    target.write_text(NewsCursorLedger().model_dump_json())
    _git(tmp_path, "add", str(NEWS_CURSOR_PATH))
    _git(tmp_path, "commit", "-m", "fixture baseline")
    sha = _git(tmp_path, "rev-parse", "HEAD")
    target.write_text("untrusted dirty prose")
    commands: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return subprocess.run(
            args, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=10
        )

    baseline = load_committed_news_cursors(sha, run_id=RUN, runner=runner)
    assert baseline.ledger == NewsCursorLedger()
    assert baseline.baseline_sha == sha
    assert target.read_text() == "untrusted dirty prose"
    assert all(not {"fetch", "push", "add", "commit"}.intersection(row) for row in commands)


def test_baseline_errors_do_not_retain_raw_diagnostics() -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, stdout="private article", stderr="token=secret")

    with pytest.raises(PublisherGitError) as error:
        load_committed_news_cursors("a" * 40, run_id=RUN, runner=runner)
    assert error.value.last_stderr == "news baseline unavailable"
    assert error.value.cause is None


@pytest.mark.parametrize("size", [str(1024 * 1024 + 1), "not-a-size", "-1"])
def test_oversized_or_invalid_committed_blob_size_never_reads_body(size: str) -> None:
    commands: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if "rev-parse" in args:
            stdout = "a" * 40 + "\n"
        elif "ls-tree" in args:
            stdout = f"100644 blob {'f' * 40}\t{NEWS_CURSOR_PATH}\0"
        elif args[1:3] == ["cat-file", "-s"]:
            assert args[-1] == f"{'a' * 40}:{NEWS_CURSOR_PATH}"
            stdout = size + "\n"
        else:
            pytest.fail("invalid committed size must not request a body")
        return subprocess.CompletedProcess(args, 0, stdout, "")

    with pytest.raises(PublisherGitError):
        load_committed_news_cursors("a" * 40, run_id=RUN, runner=runner)
    assert any(args[1:3] == ["cat-file", "-s"] for args in commands)
    assert not any("show" in args for args in commands)


@pytest.mark.parametrize(("mode", "kind"), [("120000", "blob"), ("040000", "tree")])
def test_cursor_metadata_must_be_a_regular_blob_before_size_or_body(mode: str, kind: str) -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "rev-parse" in args:
            stdout = "a" * 40 + "\n"
        elif "ls-tree" in args:
            stdout = f"{mode} {kind} {'f' * 40}\t{NEWS_CURSOR_PATH}\0"
        else:
            pytest.fail("nonregular cursor must not request blob size or body")
        return subprocess.CompletedProcess(args, 0, stdout, "")

    with pytest.raises(PublisherGitError):
        load_committed_news_cursors("a" * 40, run_id=RUN, runner=runner)


def test_clock_rollback_hold_retains_confirmed_seen_revision_for_recovery_dedup() -> None:
    current = _item()
    identity = news_document_revision(current)
    future = END + timedelta(hours=1)
    seen = NewsSeenRevision(
        source_name="rss",
        segment=US_EQUITY,
        document_id=identity.document_id,
        revision_id=identity.revision_id,
        observed_at=future,
    )
    baseline = _baseline(
        NewsCursor(source_name="rss", segment=US_EQUITY, end_utc=future), seen=(seen,)
    )
    held = _plan(baseline)
    assert not held.windows[("rss", US_EQUITY)].fetch_required
    prepared = prepare_news_window_publication(held, baseline, coverage=(), consumed=())
    assert prepared is not None
    ledger = NewsCursorLedger.model_validate_json(prepared[1][NEWS_CURSOR_PATH])
    assert ledger == baseline.ledger
    recovered_baseline = replace(baseline, ledger=ledger)
    recovered = make_news_window_plan(
        NewsWindowConfig("active"),
        run_id=RUN,
        target_date=PRICE_DATE,
        observed_at=future + timedelta(hours=1),
        source_recipients={"rss": (US_EQUITY,)},
        baseline=recovered_baseline,
    )
    updated = _item(summary="Company expanded its service to another country.")
    assert filter_news_items_for_segment(
        recovered, US_EQUITY, (current, updated), recovered_baseline
    ) == (updated,)


def test_only_actually_expired_seen_revision_is_pruned() -> None:
    identity = news_document_revision(_item())
    old = NewsSeenRevision(
        source_name="rss",
        segment=US_EQUITY,
        document_id=identity.document_id,
        revision_id=identity.revision_id,
        observed_at=END - timedelta(days=8),
    )
    baseline = _baseline(NewsCursor(source_name="rss", segment=US_EQUITY, end_utc=END), seen=(old,))
    prepared = prepare_news_window_publication(_plan(baseline), baseline, coverage=(), consumed=())
    assert prepared is not None
    assert NewsCursorLedger.model_validate_json(prepared[1][NEWS_CURSOR_PATH]).seen_revisions == ()


def _manifest_bytes() -> bytes:
    baseline = _baseline()
    plan = _plan(baseline)
    result = prepare_news_window_publication(
        plan, baseline, coverage=(_coverage(plan),), consumed=(_sealed(plan, (_item(),)),)
    )
    assert result is not None
    return result[1][news_manifest_path(RUN)]


def test_local_manifest_roundtrip_is_exact_and_never_calls_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "saved.json"
    path.write_bytes(_manifest_bytes())

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("manifest replay must not invoke Git or a subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    windows = load_news_replay_windows(path)
    assert dict(windows) == dict(_plan(_baseline()).windows)
    replay = _plan(replay=True, replay_windows=windows)
    restored = replay.windows[("rss", US_EQUITY)]
    assert restored.requested_start == windows[("rss", US_EQUITY)].requested_start
    assert restored.end_utc == END and restored.baseline_ref == "a" * 40
    assert replay.baseline_cursor_hash is None
    with pytest.raises(TypeError):
        windows[("other", US_EQUITY)] = restored  # type: ignore[index]


@pytest.mark.parametrize("level", ["root", "row", "window", "consumption", "document"])
def test_manifest_rejects_unknown_fields_without_echoing_prose(tmp_path: Path, level: str) -> None:
    raw = json.loads(_manifest_bytes())
    row = raw["windows"][0]
    objects = {
        "root": raw,
        "row": row,
        "window": row["window"],
        "consumption": row["consumption"],
        "document": row["consumption"]["documents"][0],
    }
    objects[level]["raw_article"] = "private article text"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=r"^invalid local news replay manifest$") as exc:
        load_news_replay_windows(path)
    assert "private article" not in str(exc.value)


@pytest.mark.parametrize("kind", ["version", "duplicate", "baseline", "hash", "range", "gap"])
def test_manifest_rejects_duplicate_or_inconsistent_closed_fields(
    tmp_path: Path, kind: str
) -> None:
    raw = json.loads(_manifest_bytes())
    row = raw["windows"][0]
    if kind == "version":
        raw["schema_version"] = True
    elif kind == "duplicate":
        raw["windows"].append(row.copy())
    elif kind == "baseline":
        other = json.loads(json.dumps(row))
        other["source_name"] = other["consumption"]["source_name"] = "another"
        other["window"]["baseline_ref"] = other["consumption"]["baseline_ref"] = "f" * 40
        raw["windows"].append(other)
    elif kind == "hash":
        row["consumption"]["baseline_cursor_hash"] = "f" * 64
    elif kind == "range":
        row["window"]["requested_start"] = "2026-01-01T00:00:00Z"
    else:
        row["gap_seconds"] = 99
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=r"^invalid local news replay manifest$"):
        load_news_replay_windows(path)


def test_manifest_limits_and_catalog_drift_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "large.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="invalid local news replay manifest"):
        load_news_replay_windows(path)
    windows = dict(_plan(_baseline()).windows)
    windows[("removed-source", US_EQUITY)] = windows[("rss", US_EQUITY)]
    with pytest.raises(ValueError, match="recipients differ"):
        _plan(replay=True, replay_windows=windows)
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_news_window_plan(
            NewsWindowConfig("active", END - timedelta(days=1), END),
            run_id=RUN,
            target_date=PRICE_DATE,
            observed_at=END,
            source_recipients={"rss": (US_EQUITY,)},
            replay=True,
            replay_windows=_plan(_baseline()).windows,
        )
