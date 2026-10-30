"""Literal punctuation and grammatical concepts cannot invent source entities."""

import pytest

from investo._internal.event_article import validate_composition
from investo._internal.event_v3_contract import validate_claim
from tests._helpers.event_article_v2 import article_case
from tests._helpers.event_context_v3 import NOW, ref


def check_context(detail, text):
    _, draft, composition, _ = article_case(detail=detail)
    sentence = composition.narrative.sentences[1].model_copy(update={"text": text})
    changed = composition.model_copy(
        update={
            "narrative": composition.narrative.model_copy(
                update={
                    "blocks": (
                        composition.narrative.blocks[0],
                        composition.narrative.blocks[1].model_copy(
                            update={"sentences": (sentence,)}
                        ),
                    )
                }
            )
        }
    )
    validate_composition(changed, draft.article_readiness[0].packet, draft, observed_at=NOW)


@pytest.mark.parametrize("name", ["Avery J. Vale", "Riley K. Brook", "Market.example.com", "U.S."])
def test_source_initials_acronyms_and_domains_keep_internal_periods(name):
    check_context(
        f"Acme explained that {name} supports the proposal.",
        f"Acme는 {name}의 지지를 설명했습니다.",
    )


@pytest.mark.parametrize(
    "name", ["Avery X. Vale", "Morgan J. Vale", "Other.example.com", "U.K.", "Market. example.com"]
)
def test_normalized_periods_cannot_license_other_initials_names_or_domains(name):
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context(
            "Acme explained that Avery J. Vale and Market.example.com support the U.S. proposal.",
            f"Acme는 {name}의 지지를 설명했습니다.",
        )


@pytest.mark.parametrize(
    "name",
    [
        "Avery K. Vale",
        "Riley J. Brook",
        "K. Vale",
        "Avery K Vale",
        "riley J. Vale",
        "Avery J. brook",
        "Avery j. Brook",
        "avery k. vale",
        "riley\u200b J. Vale",
        "\uff52\uff49\uff4c\uff45\uff59 J. Vale",
    ],
)
def test_known_initials_cannot_be_borrowed_from_another_person(name):
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context(
            "Acme explained that Avery J. Vale and Riley K. Brook support the proposal.",
            f"Acme는 {name}의 지지를 설명했습니다.",
        )


def test_contiguous_shortened_name_is_bound_to_the_original_person():
    check_context(
        "Acme explained that Avery J. Vale supports the proposal.",
        "Acme는 J. Vale의 지지를 설명했습니다.",
    )


@pytest.mark.parametrize("name", ["avery j. vale", "Avery j. Vale", "Avery J. vale"])
def test_case_changes_preserve_a_complete_literal_source_name(name):
    check_context(
        "Acme explained that Avery J. Vale supports the proposal.",
        f"Acme는 {name}의 지지를 설명했습니다.",
    )


def test_name_crossing_adjacent_packet_spans_keeps_its_literal_binding():
    prefix = "Acme explained "
    detail = prefix + "x" * (235 - len(prefix)) + " Avery J. Vale supports the proposal."
    check_context(detail, "Acme는 Avery J. Vale의 지지를 설명했습니다.")


@pytest.mark.parametrize("initial", ["J.", "K."])
def test_name_components_need_contiguous_source_proof(initial):
    _, draft, _, _ = article_case(
        detail="Acme explained that Avery J. Vale and Riley K. Brook support the proposal."
    )
    refs = tuple(ref(draft.documents[0], part) for part in ("Avery", initial, "Vale"))
    if initial == "J.":
        validate_claim("Avery J. Vale", refs, draft)
    else:
        with pytest.raises(ValueError, match="entity_unsupported"):
            validate_claim("Avery K. Vale", refs, draft)


@pytest.mark.parametrize("concept", ["증가세", "축적", "표결"])
def test_plain_concepts_are_not_organization_aliases(concept):
    check_context(
        "Acme explained growth, information accumulation and voting on the proposal.",
        f"Acme는 {concept}이 정책에 도움이 된다고 설명했습니다.",
    )


@pytest.mark.parametrize(
    "name", ["증가세은행", "축적테크", "표결증권", "되돌리는테크", "만드는테크"]
)
def test_compound_organization_names_still_require_source_evidence(name):
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context(
            "Acme explained growth, information accumulation and voting on the proposal.",
            f"Acme는 {name}이 정책을 결정했다고 설명했습니다.",
        )


def test_inflected_return_modifier_is_not_a_named_actor():
    check_context(
        "Acme explained that additional information helps return inflation to the target.",
        "Acme는 물가상승률을 목표로 되돌리는 데 도움이 될 것이라고 설명했습니다.",
    )


@pytest.mark.parametrize("cue", ["원문에서는", "원문에는"])
@pytest.mark.parametrize("modifier", ["생성하는", "만드는"])
def test_document_description_does_not_require_invented_company_speech(cue, modifier):
    check_context(
        "Acme Widget creates a separate wallet for each position.",
        f"{cue} Acme의 Widget은 포지션마다 별도 지갑을 {modifier} 방식이라고 설명한다.",
    )


def test_possessive_owner_and_agentless_introduction_are_not_explicit_attribution():
    with pytest.raises(ValueError, match="attribution_missing"):
        check_context(
            "Acme Widget creates a separate wallet for each position.",
            "Acme의 Widget은 포지션마다 별도 지갑을 만드는 방식이라고 소개됐다.",
        )


def test_writer_cannot_invent_a_source_publisher():
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context(
            "Acme Widget creates a separate wallet for each position.",
            "FakeWire에 따르면 Acme의 Widget은 별도 지갑을 만든다고 설명했다.",
        )
