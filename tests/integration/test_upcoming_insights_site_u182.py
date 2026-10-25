"""Local Git/DTO/site evidence only; never production deployment or source activation."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from investo.models.insights_events import BEA_RECIPES, FRED_RECIPES
from investo.orchestrator import insights_publication as publication
from investo.orchestrator.insights import InsightCapture, InsightsConfig, load_qualifications
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.store import module_paths, prepare_bundle, validate_bundle
from tests._helpers.macro_insights import capture as macro_capture
from tests._helpers.macro_insights import module as macro_module
from tests._helpers.macro_insights import qualifications as macro_qualifications
from tests._helpers.upcoming_insights import NOW, capture, exact, local, module, qualifications
from tests.integration.test_insights_publication_u180 import git
from tests.integration.test_insights_publication_u180 import repository as repository


async def test_calendar_local_remote_confirmation_preserves_unrelated_dirty_work(
    repository, monkeypatch
):
    work, remote, _ = repository
    monkeypatch.setattr(publication, "load_qualifications", qualifications)
    (work / "legacy.md").write_text("unrelated dirty")
    outcome = await publication.run_insights_phase(
        InsightsConfig("active", ("calendar",)),
        capture(),
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
        write_allowed=True,
    )
    assert outcome.status == "remote_confirmed"
    assert outcome.receipt.local_sha == git(remote, "rev-parse", "main")
    assert (work / "legacy.md").read_text() == "unrelated dirty"
    baseline = publication.load_remote_baseline()
    assert len(baseline.modules["calendar"].events) == 8
    assert "calendar" not in baseline.histories
    assert not (work / module_paths("calendar")[2]).exists()


def test_macro_and_calendar_share_bundle_without_changing_numeric_history():
    macro = macro_module()
    history = update_history(macro, None, macro_qualifications())
    prepared = prepare_bundle((macro, module()), {"macro": history})
    _, modules, histories = validate_bundle(dict(prepared.files))
    assert modules["macro"] == macro and len(modules["calendar"].events) == 8
    assert histories == {"macro": history}


async def test_inactive_calendar_removes_revoked_reference_and_preserves_allowed_primary(
    repository, monkeypatch
):
    bea = BEA_RECIPES["gdp"].event(exact(datetime(2026, 10, 29, 12, 30, tzinfo=UTC)), "bea:gdp")
    fred = FRED_RECIPES["53"].event(local(date(2026, 10, 29)), "fred:53")
    all_rights = (*qualifications(), *macro_qualifications())
    monkeypatch.setattr(publication, "load_qualifications", lambda: all_rights)
    first = await publication.run_insights_phase(
        InsightsConfig("active", ("calendar",)),
        capture((bea, fred)),
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
        write_allowed=True,
    )
    assert first.status == "remote_confirmed"
    revoked = tuple(
        q.model_copy(update={"revoked": True}) if q.source_name == "fred-economic-calendar" else q
        for q in all_rights
    )
    monkeypatch.setattr(publication, "load_qualifications", lambda: revoked)
    macro = macro_capture()
    captured = InsightCapture(macro.envelopes, (*macro.outcomes, *capture().outcomes))
    now = NOW + timedelta(seconds=1)
    result = await publication.run_insights_phase(
        InsightsConfig("active", ("macro",)),
        captured,
        run_started_at=now,
        collection_completed_at=now,
        evaluated_at=now,
        write_allowed=True,
    )
    assert result.status == "remote_confirmed"
    calendar = publication.load_remote_baseline().modules["calendar"]
    assert len(calendar.events) == 1 and calendar.events[0].source_name == "us-economic-calendar"
    assert not calendar.events[0].references and calendar.events[0].last_good
    assert calendar.events[0].collection_completed_at == NOW


def test_only_implemented_navigation_links_and_production_calendar_rights():
    nav = Path("mkdocs.yml").read_text()
    assert "미국 섹터: sectors/index.md" in nav
    assert "주요 일정: insights/calendar/index.md" in nav
    hub = Path("site_docs/insights/index.md").read_text()
    assert 'href="calendar/"' in hub and 'href="macro/"' in hub
    assert ('href="crypto/"' in hub) == Path("site_docs/insights/crypto/index.md").is_file()
    assert Path("site_docs/insights/calendar/index.md").is_file()
    assert InsightsConfig.from_env({}).mode == "off"
    qs = [q for q in load_qualifications() if any(d.module == "calendar" for d in q.definitions)]
    assert len(qs) == 24
    assert sum(q.display_allowed and q.public_git_history_allowed for q in qs) == 14
    assert all(not q.retention_allowed for q in qs)
    assert not any(q.display_allowed for q in qs if q.source_name == "fred-economic-calendar")
