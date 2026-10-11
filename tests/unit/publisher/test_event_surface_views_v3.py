"""Reader surfaces consume the same sealed event and evidence state."""

from dataclasses import replace

from investo._internal.event_asset_impact import match_event_assets
from investo.briefing.event_story import attach_story_follow_ups
from investo.publisher.public_document import finalize_public_bundle
from investo.publisher.quality_consistency import parse_segment_status_block
from investo.publisher.site_index.hero import _render_hero_block
from investo.publisher.watchlist_pages import update_watchlist_pages, watchlist_publish_paths_for
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import TARGET, native_case, native_context


def test_home_asset_history_and_quality_use_terminal_id_without_price_matching(tmp_path):
    item, draft = native_case()
    draft = attach_story_follow_ups(draft, (), observed_at=NOW)
    draft = draft.model_copy(update={"asset_impacts": match_event_assets(draft, ("Acme",))})
    ctx = replace(
        native_context((item, draft)), event_asset_terms_by_segment={draft.segment: ("Acme",)}
    )
    sealed = finalize_public_bundle({draft.segment: draft}, context=ctx).documents[0]
    view = sealed.edition_view
    assert view is not None
    hero = _render_hero_block(TARGET, {draft.segment: view})
    assert view.edition.events[0].headline in hero
    status = parse_segment_status_block(sealed.rendered_markdown, draft.segment)
    assert status.status == "normal" and status.body_used_count == 1
    paths = watchlist_publish_paths_for((), event_editions=(view,), pages_root=tmp_path)
    written = update_watchlist_pages(TARGET, (), event_editions=(view,), pages_root=tmp_path)
    assert set(written) <= set(paths)
    page = tmp_path / "Acme.md"
    content = page.read_text()
    assert view.edition.events[0].event_id in content
    assert "1200" in content and "FY2026" in content and "당시 상태" in content
    assert "https://example.com/one" in content
    update_watchlist_pages(TARGET, (), event_editions=(view,), pages_root=tmp_path)
    assert page.read_text() == content
    no_impacts = view.model_copy(
        update={"edition": view.edition.model_copy(update={"asset_impacts": ()})}
    )
    update_watchlist_pages(TARGET, (), event_editions=(no_impacts,), pages_root=tmp_path)
    assert "investo:asset-event" not in page.read_text()
