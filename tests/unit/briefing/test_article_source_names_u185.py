"""Literal punctuation and grammatical concepts cannot invent source entities."""

import pytest

from investo._internal.event_article import validate_composition
from investo._internal.event_v3_contract import validate_claim
from investo._internal.korean_subjects import is_source_role_subject
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


@pytest.mark.parametrize(
    ("detail", "text"),
    [
        (
            "Acme described an application to become a bank holding company.",
            "Acme에 따르면 은행지주회사가 되기 위한 신청이다.",
        ),
        (
            "Acme explained that billions of dollars left the wallets.",
            "원문에는 Acme 지갑에서 달러가 빠져나갔다고 명시돼 있다.",
        ),
    ],
)
def test_generic_type_and_currency_translation_needs_assigned_source(detail, text):
    check_context(detail, text)


@pytest.mark.parametrize("label", ["은행지주회사", "달러"])
def test_generic_translation_is_not_allowed_without_its_source_type(label):
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context("Acme explained the proposal.", f"Acme는 {label}가 대상이라고 설명했다.")


@pytest.mark.parametrize("label", ["은행지주회사테크", "달러은행"])
def test_source_type_translation_does_not_license_a_named_company(label):
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context(
            "Acme described a bank holding company and USD.",
            f"Acme는 {label}가 대상이라고 설명했다.",
        )


def test_bank_type_words_cannot_be_stitched_from_separate_proof_windows():
    assert not is_source_role_subject(
        "은행지주회사", {"bank", "holding", "company"}, proof_windows=("bank", "holding company")
    )
    assert not is_source_role_subject(
        "은행지주회사",
        {"bank", "holding", "company"},
        proof_windows=("bank policy; holding company",),
    )
    assert is_source_role_subject(
        "은행지주회사", {"bank", "holding", "company"}, proof_windows=("a bank holding company",)
    )


@pytest.mark.parametrize("tag", ["$TOKEN", "$1INCH", "$1000PEPE", "$0G", "$1.79TOKEN", "$1_ABC"])
def test_cash_tag_is_not_a_dollar_currency_reference(tag):
    assert not is_source_role_subject("달러", {"token"}, proof_windows=(f"{tag} launched",))
    with pytest.raises(ValueError, match="entity_unsupported"):
        check_context(
            f"Acme explained that {tag} is a token.",
            "원문에는 Acme의 달러가 대상이라고 명시돼 있다.",
        )
    assert is_source_role_subject("달러", set(), proof_windows=("$1.79 billion was frozen",))
