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
