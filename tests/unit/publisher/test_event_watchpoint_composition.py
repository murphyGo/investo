"""u162 composition preserves the frozen numeric branch and current fragments."""

from dataclasses import replace

import pytest

from investo.models.events import EventWatchpoint, NumericWatchpoint
from investo.publisher.event_watchpoints import (
    EventWatchpointBuildResult,
    build_event_watchpoints,
    event_watchpoint_ids,
)
from investo.publisher.reader_format.emphasis import wrap_numbers_bold
from investo.publisher.watchpoint_matrix import (
    DATA_LIMITED_NOTE,
    NumericWatchpointBaseline,
    WatchpointRenderResult,
    WatchpointRow,
    capture_numeric_watchpoint_baseline,
    compose_event_watchpoints,
    is_canonical_numeric_watchpoint_content,
    render_watchpoint_rows_result,
    replace_watchpoint_content,
    watchpoint_content_span,
)
from tests.unit.briefing.test_event_narrative import payload_for

_HEAD = "## ① 요약\n본문 근거를 유지합니다.\n\n## ⑥ 오늘의 관전 포인트"
_TAIL = "## ⑦ 면책조항\n합성 fixture 면책문구\n"
_VISUAL = "<!-- owned visual -->\n![그림](source.svg)\n<!-- /owned visual -->\n"
_CHART = "<!-- owned chart -->\n<div>차트 원문</div>\n<!-- /owned chart -->"


def _numeric_result(
    count: int = 6, *, synthesized: bool = False, fragment: str = ""
) -> WatchpointRenderResult:
    rows = tuple(
        WatchpointRow(
            signal=f"종목 {index} 가격",
            source="검증된 시장 앵커",
            current=f"{100 + index}.00 (+1%)",
            bullish_trigger="110 상회 시 회복 흐름 관찰",
            bearish_trigger="90 이탈 시 약화 흐름 관찰",
            confidence="높음",
            implication="본문 가격 변화와 연계해 확인합니다.",
        )
        for index in range(count)
    )
    result = render_watchpoint_rows_result(
        f"{_HEAD}\n\n{fragment}\n{DATA_LIMITED_NOTE}\n{_TAIL}",
        rows,
        preserved_fragments=(fragment,) if fragment else (),
    )
    return result if synthesized else replace(result, synthesized_card_count=0)


def _events(count: int) -> tuple[EventWatchpoint, ...]:
    cards = []
    for actor in ("Alpha", "Beta", "Gamma")[:count]:
        payload = payload_for(actor_override=actor, object_override=f"{actor} Product")
        built = build_event_watchpoints(
            payload, surviving_event_ids=(payload.plan.selected[0].event_id,)
        )
        assert len(built.watchpoints) == 1
        cards.append(built.watchpoints[0])
    return tuple(cards)


def _built(count: int = 0) -> EventWatchpointBuildResult:
    return EventWatchpointBuildResult(_events(count), count, ())


@pytest.mark.parametrize(("count", "synthesized"), [(0, False), (2, True), (6, False)])
def test_no_event_preserves_exact_legacy_bytes_and_all_counts(
    count: int, synthesized: bool
) -> None:
    legacy = _numeric_result(count, synthesized=synthesized, fragment=_VISUAL)
    baseline = capture_numeric_watchpoint_baseline(legacy, preserved_fragments=(_VISUAL,))
    composed = compose_event_watchpoints(
        legacy.markdown, baseline, _built(), preserved_fragments=(_VISUAL,)
    )

    assert composed.result == legacy
    assert composed.event_watchpoints == ()
    assert composed.companion.numeric_attempted == count
    assert composed.companion.numeric_rendered == count
    assert composed.companion.event_attempted == 0
    assert composed.companion.event_rendered == 0
    assert _VISUAL not in baseline.content
    assert len(baseline.rows) == count
    assert all(
        isinstance(card, NumericWatchpoint) and card.kind == "numeric" for card in baseline.rows
    )


def test_invalid_events_leave_numeric_six_unchanged_and_reasons_private() -> None:
    legacy = _numeric_result()
    built = EventWatchpointBuildResult(
        (), 2, (("a" * 24, "source_unavailable"), ("b" * 24, "unsupported_timing"))
    )
    composed = compose_event_watchpoints(
        legacy.markdown, capture_numeric_watchpoint_baseline(legacy), built
    )

    assert composed.result == legacy
    assert composed.result.limitation_reasons == ()
    assert composed.companion.event_attempted == 2
    assert composed.companion.event_limitation_reasons == (
        "source_unavailable",
        "unsupported_timing",
    )
    assert "source_unavailable" not in composed.result.markdown


def test_mixed_selects_first_event_and_numeric_only_with_private_cap_reasons() -> None:
    legacy = _numeric_result()
    built = _built(3)
    baseline = capture_numeric_watchpoint_baseline(legacy)
    composed = compose_event_watchpoints(legacy.markdown, baseline, built)

    assert event_watchpoint_ids(composed.result.markdown) == (built.watchpoints[0].event_id,)
    assert composed.event_watchpoints == built.watchpoints[:1]
    assert composed.result.usable_card_count == 2
    assert composed.result.synthesized_card_count == 0
    assert composed.result.limitation_reasons == ()
    assert "#### 관찰 신호: Alpha 제품 출시" in composed.result.markdown
    assert "- 현재: 100.00 (+1%)" in composed.result.markdown
    assert "#### 관찰 신호: 종목 1 가격" not in composed.result.markdown
    assert composed.result.markdown.index("Alpha 제품 출시") < composed.result.markdown.index(
        "종목 0 가격"
    )
    assert composed.companion.numeric_attempted == 6
    assert composed.companion.numeric_rendered == 1
    assert composed.companion.event_attempted == 3
    assert composed.companion.event_rendered == 1
    assert composed.companion.numeric_limitation_reasons == ("watchpoint_limit",)
    assert composed.companion.event_limitation_reasons == ("watchpoint_limit",)
    assert compose_event_watchpoints(composed.result.markdown, baseline, built) == composed


@pytest.mark.parametrize("event_count", [1, 2, 3])
def test_event_only_limit_is_two_and_aggregate_never_mixes_in_limitation(event_count: int) -> None:
    legacy = _numeric_result(0)
    built = _built(event_count)
    composed = compose_event_watchpoints(
        legacy.markdown, capture_numeric_watchpoint_baseline(legacy), built
    )

    assert event_watchpoint_ids(composed.result.markdown) == tuple(
        card.event_id for card in built.watchpoints[:2]
    )
    assert composed.result.state == "rendered"
    assert composed.result.usable_card_count == min(event_count, 2)
    assert composed.result.limitation_reasons == ()
    assert composed.companion.numeric_attempted == 0
    assert composed.companion.numeric_limitation_reasons == ("watchpoint_unavailable",)
    assert DATA_LIMITED_NOTE not in composed.result.markdown
    assert "- 현재:" not in composed.result.markdown
    assert "상방" not in composed.result.markdown


def test_mixed_fallback_counts_only_its_one_visible_synthesized_card() -> None:
    legacy = _numeric_result(2, synthesized=True)
    composed = compose_event_watchpoints(
        legacy.markdown, capture_numeric_watchpoint_baseline(legacy), _built(1)
    )
    assert composed.result.usable_card_count == 2
    assert composed.result.synthesized_card_count == 1


@pytest.mark.parametrize(("count", "synthesized"), [(0, False), (2, True), (6, False)])
def test_removing_all_events_restores_complete_numeric_baseline(
    count: int, synthesized: bool
) -> None:
    legacy = _numeric_result(count, synthesized=synthesized)
    baseline = capture_numeric_watchpoint_baseline(legacy)
    built = _built(2)
    mixed = compose_event_watchpoints(legacy.markdown, baseline, built)
    removed = EventWatchpointBuildResult(
        (), 2, tuple((card.event_id, "finalization_removed") for card in built.watchpoints)
    )
    restored = compose_event_watchpoints(mixed.result.markdown, baseline, removed)

    assert restored.result == legacy
    assert restored.event_watchpoints == ()
    assert restored.companion.event_limitation_reasons == ("finalization_removed",)
    assert compose_event_watchpoints(restored.result.markdown, baseline, removed) == restored


def test_partial_event_removal_keeps_only_supplied_survivors() -> None:
    legacy = _numeric_result(0)
    baseline = capture_numeric_watchpoint_baseline(legacy)
    built = _built(2)
    first = compose_event_watchpoints(legacy.markdown, baseline, built)
    surviving = EventWatchpointBuildResult(
        built.watchpoints[1:], 2, ((built.watchpoints[0].event_id, "finalization_removed"),)
    )
    repaired = compose_event_watchpoints(first.result.markdown, baseline, surviving)

    assert repaired.result.usable_card_count == 1
    assert event_watchpoint_ids(repaired.result.markdown) == (built.watchpoints[1].event_id,)
    assert "Alpha 제품 출시" not in repaired.result.markdown
    assert "Beta 제품 출시" in repaired.result.markdown


def test_recomposition_preserves_current_fragments_and_current_other_sections() -> None:
    legacy = _numeric_result(fragment=_VISUAL)
    baseline = capture_numeric_watchpoint_baseline(legacy, preserved_fragments=(_VISUAL,))
    current = legacy.markdown.replace(_VISUAL, _CHART).replace("본문 근거", "수정된 본문 근거")
    mixed = compose_event_watchpoints(
        current, baseline, _built(1), preserved_fragments=(_VISUAL, _CHART)
    )
    restored = compose_event_watchpoints(
        mixed.result.markdown, baseline, _built(), preserved_fragments=(_VISUAL, _CHART)
    )

    for result in (mixed.result, restored.result):
        assert result.markdown.count(_CHART) == 1
        assert _VISUAL not in result.markdown
        assert result.markdown.startswith(_HEAD.replace("본문 근거", "수정된 본문 근거"))
        assert result.markdown.endswith(_TAIL)
    assert restored.result.usable_card_count == 6


def test_baseline_recognizes_emphasized_canonical_cards_and_keeps_omission_suffix() -> None:
    legacy = _numeric_result()
    legacy = replace(
        legacy,
        markdown=wrap_numbers_bold(legacy.markdown).replace(
            _TAIL, "\n_관전 신호 3건 추가 — 본문 참조._\n" + _TAIL
        ),
    )
    baseline = capture_numeric_watchpoint_baseline(legacy)
    mixed = compose_event_watchpoints(legacy.markdown, baseline, _built(1))
    restored = compose_event_watchpoints(mixed.result.markdown, baseline, _built())

    assert len(baseline.rows) == 6
    assert baseline.rows[0].current == "100.00 (**+1%**)"
    assert "_관전 신호" not in mixed.result.markdown
    assert restored.result == legacy


def test_numeric_capture_rejects_event_or_unvalidated_content_claiming_rendered() -> None:
    forged = WatchpointRenderResult(
        markdown=f"{_HEAD}\n\n- 수치가 없는 사건\n{_TAIL}", state="rendered", usable_card_count=1
    )
    with pytest.raises(ValueError, match="numeric baseline rows"):
        capture_numeric_watchpoint_baseline(forged)


def test_unresolved_limited_content_is_not_reclassified_as_an_event() -> None:
    markdown = f"{_HEAD}\n\n관측값이 없는 미래 조건 문장\n{_TAIL}"
    limited = WatchpointRenderResult(
        markdown=markdown,
        state="limited",
        usable_card_count=0,
        limitation_reasons=("watchpoint_unavailable",),
    )
    composed = compose_event_watchpoints(
        markdown, capture_numeric_watchpoint_baseline(limited), _built()
    )
    assert composed.result == limited
    assert composed.event_watchpoints == ()
    assert composed.companion.numeric_attempted == composed.companion.event_attempted == 0


def test_missing_section_does_not_invent_a_rendered_card_or_hide_structure_failure() -> None:
    markdown = "## ① 요약\n관전 포인트 섹션이 없습니다.\n" + _TAIL
    limited = WatchpointRenderResult(
        markdown=markdown,
        state="limited",
        usable_card_count=0,
        limitation_reasons=("watchpoint_unavailable",),
    )
    baseline = capture_numeric_watchpoint_baseline(limited)
    assert baseline.content == ""
    assert watchpoint_content_span(markdown) is None
    assert replace_watchpoint_content(markdown, "새 관전 내용") == markdown
    composed = compose_event_watchpoints(markdown, baseline, _built(1))
    assert composed.result == limited
    assert composed.companion.event_rendered == 0
    assert composed.companion.event_limitation_reasons == ("watchpoint_section_missing",)


def test_replacement_stops_before_protected_diagnostics() -> None:
    diagnostics = "<details><summary>수집/품질 진단</summary>\n원문 진단\n</details>\n\n"
    legacy = _numeric_result(1)
    markdown = legacy.markdown.replace(_TAIL, diagnostics + _TAIL)
    span = watchpoint_content_span(markdown)
    assert span is not None
    assert "- 현재: 100.00 (+1%)" in markdown[span[0] : span[1]]
    assert markdown[span[1] :] == diagnostics + _TAIL
    replaced = replace_watchpoint_content(markdown, DATA_LIMITED_NOTE)
    assert replaced.endswith(diagnostics + _TAIL)
    assert replaced.startswith(_HEAD)
    assert "종목 0 가격" not in replaced


def test_raw_baseline_boundary_whitespace_survives_mixed_then_restore() -> None:
    legacy = _numeric_result(1)
    unusual = replace(
        legacy,
        markdown=legacy.markdown.replace("\n\n####", "\n\n\n####").replace(_TAIL, "\n\n" + _TAIL),
    )
    baseline = capture_numeric_watchpoint_baseline(unusual)
    mixed = compose_event_watchpoints(unusual.markdown, baseline, _built(1))
    restored = compose_event_watchpoints(mixed.result.markdown, baseline, _built())
    assert restored.result == unusual


def test_baseline_cannot_replace_validated_row_identity_with_another_card() -> None:
    legacy = _numeric_result(1)
    baseline = capture_numeric_watchpoint_baseline(legacy)
    altered_row = NumericWatchpoint.model_validate(
        {**baseline.rows[0].model_dump(), "current": "999.00"}
    )
    with pytest.raises(ValueError, match="canonical numeric card content"):
        replace(baseline, rows=(altered_row,))
    assert "- 현재: 100.00 (+1%)" in baseline.content
    assert isinstance(baseline, NumericWatchpointBaseline)


@pytest.mark.parametrize("count", [0, 1, 2, 6])
def test_canonical_numeric_content_recognizes_only_complete_baseline_shapes(count: int) -> None:
    baseline = capture_numeric_watchpoint_baseline(_numeric_result(count))
    assert is_canonical_numeric_watchpoint_content(baseline.content)
    assert is_canonical_numeric_watchpoint_content(wrap_numbers_bold(baseline.content))
    if count:
        assert is_canonical_numeric_watchpoint_content(
            baseline.content + "\n_관전 신호 3건 추가 — 본문 참조._\n"
        )


def test_canonical_numeric_content_rejects_event_mixed_and_malformed_shapes() -> None:
    legacy = _numeric_result(1)
    baseline = capture_numeric_watchpoint_baseline(legacy)
    composed = compose_event_watchpoints(legacy.markdown, baseline, _built(1))
    span = watchpoint_content_span(composed.result.markdown)
    assert span is not None
    event_mixed = composed.result.markdown[span[0] : span[1]]
    for content in (
        "",
        "미래 조건을 자유 문장으로 작성했습니다.",
        "- 현재: 123.00",
        "#### 관찰 신호: 제목만 존재",
        legacy.markdown,
        event_mixed,
        baseline.content + DATA_LIMITED_NOTE,
        baseline.content.replace("- 신뢰도: 높음", "- 신뢰도: 임의 값"),
        baseline.content.replace("- 현재: 100.00 (+1%)", ""),
    ):
        assert not is_canonical_numeric_watchpoint_content(content)
