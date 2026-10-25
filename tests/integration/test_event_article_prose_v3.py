"""Article-first presentation retains every checked claim and its public semantics."""

import pytest
from pydantic import ValidationError

from investo._internal.event_v3_contract import validate_event_edition
from investo.briefing.editorial_plan import build_editorial_plan
from investo.briefing.event_context import (
    event_context_refs,
    prepare_context_documents,
    support_vector,
)
from investo.briefing.event_document import render_event_document_prompt
from investo.briefing.event_identity import canonical_event_binding
from investo.models.event_context import MeaningContext
from investo.models.event_document import (
    ArticleDisplayBlock,
    EditionAvailability,
    EventArticle,
    EventReferencePanel,
)
from investo.models.event_evidence import make_evidence_document
from investo.publisher.compliance_language import ComplianceLanguageError, scan_compliance
from investo.publisher.event_edition import render_article_body, render_event_edition
from investo.publisher.public_document import (
    PublicDocumentFinalizationError,
    finalize_public_bundle,
)
from tests._helpers.event_context_v3 import FACT, NOW, TITLE, draft, ref
from tests._helpers.event_document_v3 import native_case, native_context


def rich_case(*, fact_subject="Acme", unit="USD"):
    item, edition = native_case()
    evidence = make_evidence_document(
        source_name="official",
        title=TITLE,
        summary=FACT.replace("Acme", fact_subject, 1).replace("USD", unit),
        detail_excerpt="Earlier access was restricted. Demand may improve if access expands.",
        url=str(item.url),
        published_at=NOW,
        received_at=NOW,
        source_tier="official",
    )
    item = item.model_copy(update={"event_evidence": evidence})
    docs = prepare_context_documents((item,), received_at=NOW)
    background = ref(docs[0], "Earlier access was restricted.")
    meaning = ref(docs[0], "Demand may improve if access expands.")
    source = draft(docs[0]).model_copy(
        update={"background_refs": (background,), "meaning_refs": (meaning,)}
    )
    source = source.model_copy(
        update={
            "facts": (
                source.facts[0].model_copy(
                    update={
                        "subject_refs": (ref(docs[0], fact_subject),),
                        "unit_refs": (ref(docs[0], unit),),
                    }
                ),
            )
        }
    )
    binding = canonical_event_binding(source, docs, (), observed_at=NOW, baseline_available=True)
    plan, bindings, _ = build_editorial_plan((source,), (binding,), docs, observed_at=NOW)
    article = edition.articles[0].model_copy(
        update={
            "event_id": binding.identity.event_id,
            "fact_ids": tuple(f.fact_id for f in binding.facts),
            "source_refs": event_context_refs(source, optional=False),
            "background": "Earlier access was restricted.",
            "background_refs": (background,),
            "meaning": MeaningContext(
                mode="source_reported",
                text="Demand may improve if access expands.",
                refs=(meaning,),
            ),
        }
    )
    if fact_subject != "Acme":
        article = article.model_copy(update={"what_changed": "Acme가 Widget을 발표했습니다."})
    edition = edition.model_copy(
        update={
            "documents": docs,
            "bindings": bindings,
            "editorial_plan": plan,
            "articles": (article,),
            "support": (support_vector(source, docs, baseline_available=True),),
        }
    )
    return item, edition


def seal(item, edition):
    return finalize_public_bundle(
        {edition.segment: edition}, context=native_context((item, edition))
    ).documents[0]


def test_default_is_integrated_prose_without_empty_role_rows():
    item, edition = rich_case()
    article = edition.articles[0]
    body = render_article_body(article).markdown
    assert body == " ".join((article.what_changed, article.background, article.meaning.text))
    assert not any(label in body for label in ("배경:", "의미:", "반응:", "확인하지 못"))
    document = seal(item, edition)
    assert document.surviving_event_ids == (article.event_id,)
    assert document.rendered_markdown.count("## " + article.headline) == 1
    assert "<summary>출처·시점·확인 범위</summary>" in document.rendered_markdown
    assert "1200" in document.rendered_markdown and "FY2026" in document.rendered_markdown
    assert "시장 반응은 확인하지 못했습니다." not in document.rendered_markdown


def test_topic_can_mix_paragraphs_and_lists_without_new_or_lost_claims():
    item, edition = rich_case()
    article = edition.articles[0].model_copy(
        update={
            "display_blocks": (
                ArticleDisplayBlock(parts=("background", "what_changed")),
                ArticleDisplayBlock(kind="labeled_list", parts=("meaning",)),
            ),
            "show_facts": True,
        }
    )
    alternate = edition.model_copy(update={"articles": (article,)})
    body = render_article_body(article).markdown
    assert body.startswith(article.background)
    assert "- 해석: " + article.meaning.text in body
    first, second = seal(item, edition), seal(item, alternate)
    assert first.edition_view.edition.events == second.edition_view.edition.events
    assert first.markdown_sha256 != second.markdown_sha256
    assert "| 주체 | 항목 | 값 | 단위 | 기간 | 구분 |" in second.rendered_markdown
    assert "| Acme | revenue | 1200 | USD | FY2026 | 실제 |" in second.rendered_markdown
    assert "display_blocks" not in second.edition_view.edition.model_dump_json()


def test_plain_bullets_do_not_force_evidence_role_labels():
    item, edition = rich_case()
    article = edition.articles[0].model_copy(
        update={
            "display_blocks": (
                ArticleDisplayBlock(parts=("what_changed",)),
                ArticleDisplayBlock(kind="bullets", parts=("background", "meaning")),
            )
        }
    )
    body = render_article_body(article).markdown
    assert "- Earlier access was restricted." in body
    assert "배경:" not in body and "해석:" not in body
    assert seal(item, edition.model_copy(update={"articles": (article,)})).surviving_event_ids


def test_fact_subject_can_differ_from_event_actors():
    item, edition = rich_case(fact_subject="Beta")
    fact = edition.bindings[0].facts[0]
    assert fact.canonical.subject_id not in {
        e.entity.entity_id for e in edition.bindings[0].entities
    }
    article = edition.articles[0].model_copy(update={"show_facts": True})
    document = seal(item, edition.model_copy(update={"articles": (article,)}))
    assert "| Beta | revenue | 1200 | USD | FY2026 | 실제 |" in document.rendered_markdown


def test_reference_fact_subject_uses_its_own_source_label():
    item, edition = rich_case(fact_subject="Beta")
    source = edition.editorial_plan.events[0].source_event
    binding = edition.bindings[0]
    plan, bindings, _ = build_editorial_plan(
        (source,), (binding,), edition.documents, observed_at=NOW, reference_item_ids=frozenset({1})
    )
    reference = EventReferencePanel(
        event_id=binding.identity.event_id,
        fact_ids=tuple(f.fact_id for f in binding.facts),
        source_refs=event_context_refs(source, optional=False),
    )
    edition = edition.model_copy(
        update={
            "articles": (),
            "editorial_plan": plan,
            "bindings": bindings,
            "reference_panels": (reference,),
            "availability": EditionAvailability(status="quiet"),
        }
    )
    document = seal(item, edition)
    assert "Beta · revenue · 1200 · USD · FY2026 · 실제" in document.rendered_markdown


@pytest.mark.parametrize("show_facts", [False, True])
def test_fact_presentation_cannot_hide_original_compliance_findings(show_facts):
    item, edition = rich_case(unit="USD 매수 검토")
    article = edition.articles[0].model_copy(
        update={"what_changed": TITLE + ".", "show_facts": show_facts}
    )
    edition = edition.model_copy(update={"articles": (article,)})
    validate_event_edition(edition, observed_at=NOW)
    validation_markdown = render_event_edition(edition, for_validation=True)
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(validation_markdown, edition.segment)
    with pytest.raises(PublicDocumentFinalizationError, match=r"compliance\.language"):
        seal(item, edition)


@pytest.mark.parametrize(
    "blocks",
    [
        [{"parts": ["what_changed"]}],
        [{"parts": ["what_changed", "background", "meaning", "what_changed"]}],
        [{"parts": ["what_changed", "background", "meaning", "reaction"]}],
        [{"parts": ["what_changed", "background", "invented"]}],
        [{"kind": "html", "parts": ["what_changed", "background", "meaning"]}],
        [{"parts": []}],
    ],
)
def test_display_plan_cannot_hide_duplicate_or_invent_content(blocks):
    _, edition = rich_case()
    payload = edition.articles[0].model_dump()
    with pytest.raises(ValidationError):
        EventArticle.model_validate({**payload, "display_blocks": blocks})


def test_finalizer_rejects_layout_omission_even_after_model_copy():
    item, edition = rich_case()
    article = edition.articles[0].model_copy(
        update={
            "display_blocks": (ArticleDisplayBlock(parts=("what_changed",)),),
        }
    )
    with pytest.raises(PublicDocumentFinalizationError, match=r"edition\.schema_invalid"):
        seal(item, edition.model_copy(update={"articles": (article,)}))


def test_layout_does_not_weaken_entity_or_source_proof():
    item, edition = rich_case()
    article = edition.articles[0].model_copy(update={"background": "Beta changed access."})
    with pytest.raises(PublicDocumentFinalizationError, match=r"event\.entity_unsupported"):
        seal(item, edition.model_copy(update={"articles": (article,)}))


def test_policy_treats_evidence_roles_as_metadata_and_prose_as_default():
    prompt = render_event_document_prompt("synthetic protected evidence")
    assert "integrated, coherent news narrative as the default" in prompt
    assert "not a mandatory reader outline" in prompt
    assert "Do not write a repetitive questionnaire" in prompt
    assert "every populated role exactly once" in prompt
