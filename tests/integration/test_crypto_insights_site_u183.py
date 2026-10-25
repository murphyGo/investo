"""Local scoped Git publication and full dashboard coexistence, no production activation."""

from pathlib import Path

from investo.orchestrator import insights_publication as publication
from investo.orchestrator.insights import InsightsConfig, load_qualifications
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.store import module_paths, prepare_bundle, validate_bundle
from tests._helpers.crypto_insights import NOW, capture, module, qualifications
from tests._helpers.macro_insights import module as macro_module
from tests._helpers.macro_insights import qualifications as macro_qualifications
from tests._helpers.upcoming_insights import module as calendar_module
from tests.integration.test_insights_publication_u180 import git
from tests.integration.test_insights_publication_u180 import repository as repository


async def test_crypto_local_remote_confirmation_and_history_preserve_unrelated_work(
    repository, monkeypatch
):
    work, remote, _ = repository
    monkeypatch.setattr(publication, "load_qualifications", qualifications)
    (work / "legacy.md").write_text("unrelated dirty")
    outcome = await publication.run_insights_phase(
        InsightsConfig("active", ("crypto",)),
        capture(),
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
        write_allowed=True,
    )
    assert outcome.status == "remote_confirmed" and outcome.receipt.local_sha == git(
        remote, "rev-parse", "main"
    )
    baseline = publication.load_remote_baseline()
    assert (
        len(baseline.modules["crypto"].metrics) == 7 and len(baseline.histories["crypto"].rows) == 7
    )
    assert (work / "legacy.md").read_text() == "unrelated dirty"
    assert b"funding" in (work / module_paths("crypto")[2]).read_bytes()


def test_all_three_modules_have_distinct_snapshots_and_history_owners():
    macro = macro_module()
    crypto = module()
    calendar = calendar_module()
    histories = {
        "macro": update_history(macro, None, macro_qualifications()),
        "crypto": update_history(crypto, None, qualifications()),
    }
    bundle = prepare_bundle((macro, calendar, crypto), histories)
    manifest, modules, loaded = validate_bundle(dict(bundle.files))
    assert len(manifest.modules) == 3 and set(modules) == {"macro", "calendar", "crypto"}
    assert loaded == histories and len({m.snapshot_id for m in modules.values()}) == 3


def test_final_navigation_default_off_and_provider_permission_matrix():
    nav = Path("mkdocs.yml").read_text()
    hub = Path("site_docs/insights/index.md").read_text()
    assert "미국 섹터: sectors/index.md" in nav
    for module_id in ("macro", "calendar", "crypto"):
        assert f"insights/{module_id}/index.md" in nav and f'href="{module_id}/"' in hub
    assert InsightsConfig.from_env({}).mode == "off"
    assert InsightsConfig.from_env({}).modules == ("macro",)
    rights = [q for q in load_qualifications() if any(d.module == "crypto" for d in q.definitions)]
    assert len(rights) == 9
    assert sum(q.display_allowed and q.public_git_history_allowed for q in rights) == 1
    assert [q.source_name for q in rights if q.retention_allowed] == ["alternative-fng"]
