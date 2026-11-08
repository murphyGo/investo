"""News datelines and reporting days preserve a closed statement frame."""

import pytest

from investo._internal.event_text_proof import assertion_span_hints, prove_text_assertion

PREFIX = "(서울=예시통신) 가나리 기자 = "
VALUE = "플랫폼 승인을 받았다고"


def prove(text, *, subject="가람증권", predicate="statement", action="밝혔다", proof=None):
    return prove_text_assertion(
        predicate=predicate,
        status="actual",
        subject=subject,
        action=action,
        object_label="",
        value=VALUE,
        assertion=text,
        status_proofs=(proof if proof is not None else text,),
    )


@pytest.mark.parametrize("prefix", ["", PREFIX])
@pytest.mark.parametrize("day", ["", "1일 ", "6일 ", "31일 "])
def test_only_reporting_frame_accepts_a_fixed_dateline_and_day(prefix, day):
    body = f"가람증권은 {VALUE} {day}밝혔다."
    text = prefix + body
    frame = prove(text, proof=body)
    assert frame is not None and frame.assertion == text and frame.value == VALUE
    hint = next(h for h in assertion_span_hints(text) if h["predicate"] == "statement")
    assert text[slice(*hint["subject"])] == "가람증권"
    assert text[slice(*hint["value"])] == VALUE
    assert text[slice(*hint["assertion"])] == text


@pytest.mark.parametrize(
    "text",
    [
        f"소문에 따르면 가람증권은 {VALUE} 6일 밝혔다.",
        f"다른회사는 가람증권은 {VALUE} 6일 밝혔다.",
        PREFIX + f"가람증권은 {VALUE} 0일 밝혔다.",
        PREFIX + f"가람증권은 {VALUE} 32일 밝혔다.",
        PREFIX + f"가람증권은 {VALUE} 6일 밝히지 않았다.",
        PREFIX + f"가람증권은 {VALUE} 6일 밝힐 예정이다.",
        PREFIX + f"가람증권은 {VALUE} 경우 6일 밝혔다.",
        PREFIX + f"가람증권은 {VALUE} 6일 밝혔다?",
    ],
)
def test_arbitrary_prefixes_invalid_dates_and_modality_remain_unsupported(text):
    assert prove(text) is None


def test_outer_speech_does_not_prove_the_inner_approval_action():
    text = PREFIX + f"가람증권은 {VALUE} 6일 밝혔다."
    assert prove(text, predicate="decision", action="승인했다") is None
    assert prove(text, subject="다른회사") is None
    assert prove(text, proof=f"가람증권은 {VALUE} 밝혔다.") is None


@pytest.mark.parametrize(
    "text",
    [
        PREFIX + "가람증권은 플랫폼 승인을 받지 않았다고 6일 밝혔다.",
        PREFIX + "가람증권은 플랫폼 승인을 받을 계획이라고 6일 밝혔다.",
        PREFIX + "가람증권은 플랫폼 승인을 받는 경우라고 6일 밝혔다.",
    ],
)
def test_unsupported_inner_negation_plan_or_condition_never_proves_actual_approval(text):
    assert not any(h["predicate"] == "decision" for h in assertion_span_hints(text))
