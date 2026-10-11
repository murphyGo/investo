"""Native HTML and optional E1 visuals retain source ownership through sealing."""

from dataclasses import replace

import markdown
import pytest

from investo.publisher.public_document import (
    PublicDocumentFinalizationError,
    finalize_public_bundle,
)
from investo.visuals.assets import prepare_event_visual_assets
from tests._helpers.event_document_v3 import native_case, native_context


def test_plaintext_braces_cannot_become_mkdocs_attributes():
    item, draft = native_case()
    article = draft.articles[0].model_copy(
        update={"headline": 'Acme Widget 실적 발표 {onclick="alert()"}'}
    )
    with pytest.raises(PublicDocumentFinalizationError, match="narrative_invalid"):
        finalize_public_bundle(
            {draft.segment: draft.model_copy(update={"articles": (article,)})},
            context=native_context((item, draft)),
        )


def test_e1_body_visual_and_provenance_are_used_only_by_surviving_event(tmp_path):
    item, draft = native_case()
    visual_inputs, artifacts = prepare_event_visual_assets(draft, staging_root=tmp_path)
    assert len(visual_inputs) == 1 and len(artifacts) == 3
    draft = draft.model_copy(update={"visual_inputs": visual_inputs})
    ctx = replace(
        native_context((item, draft)),
        event_visual_inputs_by_segment={draft.segment: visual_inputs},
        staged_artifacts_by_segment={draft.segment: artifacts},
    )
    bundle = finalize_public_bundle({draft.segment: draft}, context=ctx)
    sealed = bundle.documents[0]
    assert sealed.staged_artifact_ids == tuple(a.artifact_id for a in artifacts)
    assert bundle.promotion_manifest == artifacts
    html = markdown.markdown(sealed.rendered_markdown, extensions=["attr_list", "tables"])
    assert "1200" in html and "FY2026" in html
    assert html.index("Acme Widget 실적 발표") < html.index("gh-light-mode-only")
    assert "<!-- investo:block event:" in sealed.rendered_markdown
    assert all(a.staged_path.is_file() for a in artifacts)
    with pytest.raises(PublicDocumentFinalizationError, match="asset_unbound"):
        finalize_public_bundle({draft.segment: draft}, context=native_context((item, draft)))


def test_independent_meaning_and_context_keep_their_own_public_locator():
    from investo.briefing.editorial_plan import build_editorial_plan
    from investo.briefing.event_context import prepare_context_documents, support_vector
    from investo.briefing.event_identity import canonical_event_binding
    from investo.models.event_context import MeaningContext
    from investo.models.event_document import ContextPanel
    from investo.models.items import NormalizedItem
    from tests._helpers.event_context_v3 import NOW, ref

    item, draft = native_case()
    detail = "The service expands access."
    second = NormalizedItem(
        source_name="official",
        category="news",
        title="Acme announced Widget",
        summary=detail,
        url="https://example.com/second",
        published_at=NOW,
    )
    docs = prepare_context_documents((item, second), received_at=NOW)
    meaning_refs = (ref(docs[1], detail),)
    source = draft.editorial_plan.events[0].source_event.model_copy(
        update={
            "item_ids": (1, 2),
            "meaning_refs": meaning_refs,
        }
    )
    binding = canonical_event_binding(source, docs, (), observed_at=NOW, baseline_available=True)
    plan, bindings, _ = build_editorial_plan((source,), (binding,), docs, observed_at=NOW)
    article = draft.articles[0].model_copy(
        update={
            "event_id": binding.identity.event_id,
            "meaning": MeaningContext(mode="source_reported", text=detail, refs=meaning_refs),
        }
    )
    draft = draft.model_copy(
        update={
            "editorial_plan": plan,
            "bindings": bindings,
            "documents": docs,
            "articles": (article,),
            "support": (support_vector(source, docs, baseline_available=True),),
            "context_panels": (
                ContextPanel(
                    kind="background",
                    event_id=article.event_id,
                    text=detail,
                    source_refs=meaning_refs,
                ),
            ),
        }
    )
    ctx = replace(native_context((item, draft)), items_by_segment={draft.segment: (item, second)})
    sealed = finalize_public_bundle({draft.segment: draft}, context=ctx).documents[0]
    text = sealed.rendered_markdown
    event_block = text.split(f"<!-- /investo:block event:{article.event_id} -->", 1)[0]
    assert event_block.count("https://example.com/one") == 1
    assert "https://example.com/second" in event_block
    assert "https://example.com/second" in text.split("### 관련 background", 1)[1]
