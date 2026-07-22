"""Unit tests for ``investo.publisher.watchpoint_matrix`` (u72/u98).

Coverage map (per u72 plan Steps 1/3/4/6 + AC-72.1..72.5):

* Schema / degradation (Step 1): closed confidence label set, max visible
  rows, ``데이터부족`` fallback rules pinned.
* Renderer (Step 3): structured bullet → compact card; generic ``확인 / 점검``
  bullet → ``데이터부족`` row internally and collapsed/filtered at render time
  (delegates to the u64 source/trigger/implication contract); idempotent;
  disclaimer preserved.
* Evidence inputs (Step 4): verified numeric anchor → 높음; source-backed
  but no figure → 보통; carryover-only → 낮음; coverage-limited → 데이터부족.
* Compliance (AC-72.4): rendered matrix carries no buy/sell/target wording.
"""

from __future__ import annotations

import pytest

from investo._internal.public_quality_language import (
    PUBLIC_LOW_COVERAGE_INLINE_TEXT,
    PUBLIC_LOW_COVERAGE_LABEL,
    PUBLIC_WATCHPOINT_LIMITED_TEXT,
    PUBLIC_WATCHPOINT_SOURCE_TEXT,
    first_forbidden_public_evidence,
)
from investo.briefing.disclaimer import DISCLAIMER
from investo.publisher.compliance_language import scan_compliance
from investo.publisher.reader_format import check_watchpoint_actionability
from investo.publisher.watchpoint_matrix import (
    CONFIDENCE_LABELS,
    DATA_LIMITED_CONFIDENCE,
    DATA_LIMITED_NOTE,
    MATRIX_COLUMNS,
    MAX_VISIBLE_ROWS,
    WatchpointRenderResult,
    WatchpointRow,
    build_watchpoint_rows,
    render_matrix_table,
    render_watchpoint_matrix,
    render_watchpoint_matrix_result,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A source-backed, observational watchpoint with a verified numeric threshold.
_STRUCTURED_NUMERIC = (
    "확인 소스: FRED · 10Y 금리가 4.5% 를 상회하면 성장주 변동성 부담 압력 관찰; "
    "4.3% 를 이탈하면 방어적 해석. 관심 영향: 변동성 확대 여부를 점검."
)
# Source-backed but no numeric figure (uses 거래량 keyword trigger).
_STRUCTURED_NO_FIGURE = (
    "확인 소스: KRX · 외국인 순매수 흐름이 확대되면 수급 개선 확인, 축소되면 "
    "약화. 관심 영향: 대형주 수급 점검."
)
# Carryover-only prior context, source word present but no fresh figure.
_CARRYOVER_ONLY = (
    "확인 소스: 어제 예고한 FOMC 발언 톤 — 매파적이면 부담 압력 관찰, "
    "비둘기파적이면 완화. 관심 영향: 금리 민감주 변동성 점검."
)
# Generic monitor verb only — u64 would reject this.
_GENERIC = "FOMC 발언 톤 확인 필요"


def _section_six(bullets: list[str]) -> str:
    body = "\n".join(f"- {b}" for b in bullets)
    return f"## ① 요약\n본문\n\n## ⑥ 오늘의 관전 포인트\n\n{body}\n"


# ---------------------------------------------------------------------------
# Step 1 — schema / degradation pins
# ---------------------------------------------------------------------------


def test_confidence_label_closed_set() -> None:
    expected = frozenset({"높음", "보통", "낮음", PUBLIC_LOW_COVERAGE_LABEL})
    assert expected == CONFIDENCE_LABELS
    assert DATA_LIMITED_CONFIDENCE == PUBLIC_LOW_COVERAGE_LABEL


def test_matrix_columns_are_observational() -> None:
    assert MATRIX_COLUMNS == (
        "관찰 신호",
        "현재",
        "상방 확인 조건",
        "하방 확인 조건",
        "신뢰도",
        "섹션 내 관심 영향",
    )


def test_max_visible_rows_bounds_table() -> None:
    bullets = [_STRUCTURED_NUMERIC] * (MAX_VISIBLE_ROWS + 4)
    rows = build_watchpoint_rows(bullets)
    assert len(rows) == MAX_VISIBLE_ROWS


def test_data_limited_row_uses_card_defaults() -> None:
    row = WatchpointRow.data_limited("신호")
    assert row.confidence == DATA_LIMITED_CONFIDENCE
    assert row.source == PUBLIC_WATCHPOINT_SOURCE_TEXT
    assert row.current == PUBLIC_WATCHPOINT_LIMITED_TEXT
    assert row.bullish_trigger == PUBLIC_LOW_COVERAGE_INLINE_TEXT
    assert row.bearish_trigger == PUBLIC_LOW_COVERAGE_INLINE_TEXT
    assert row.implication == PUBLIC_WATCHPOINT_LIMITED_TEXT
    assert first_forbidden_public_evidence(render_matrix_table([row])) is None


# ---------------------------------------------------------------------------
# Step 4 — confidence classification from evidence type
# ---------------------------------------------------------------------------


def test_verified_numeric_threshold_is_high() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    assert rows[0].confidence == "높음"


def test_source_backed_without_figure_is_medium() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NO_FIGURE])
    assert rows[0].confidence == "보통"


def test_carryover_only_is_low() -> None:
    rows = build_watchpoint_rows([_CARRYOVER_ONLY])
    assert rows[0].confidence == "낮음"


def test_coverage_limited_is_data_limited() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC], coverage_limited=True)
    assert len(rows) == 1
    assert rows[0].confidence == DATA_LIMITED_CONFIDENCE


# ---------------------------------------------------------------------------
# Step 3 — generic watchpoint degradation (delegates to u64 contract)
# ---------------------------------------------------------------------------


def test_generic_bullet_becomes_data_limited_row() -> None:
    # u64 would flag this generic bullet.
    assert check_watchpoint_actionability(_section_six([_GENERIC])) == (_GENERIC,)
    rows = build_watchpoint_rows([_GENERIC])
    assert rows[0].confidence == DATA_LIMITED_CONFIDENCE
    assert rows[0].bullish_trigger == PUBLIC_LOW_COVERAGE_INLINE_TEXT


def test_structured_bullet_populates_all_columns() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    row = rows[0]
    assert row.signal
    assert row.source == "FRED"
    assert "상회" in row.bullish_trigger
    assert "이탈" in row.bearish_trigger
    assert row.implication != "관심 영향 데이터 부족"


# ---------------------------------------------------------------------------
# Renderer / document-level
# ---------------------------------------------------------------------------


def test_render_matrix_table_compat_helper_outputs_cards() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    cards = render_matrix_table(rows)
    assert "| " + " | ".join(MATRIX_COLUMNS) + " |" not in cards
    assert cards.startswith("#### 관찰 신호:")
    assert "\n- 출처: FRED\n" in cards
    assert "\n- 확인 조건: 상방 " in cards
    assert "\n- 관심 영향: " in cards


def test_render_replaces_section_six_with_cards() -> None:
    text = _section_six([_STRUCTURED_NUMERIC, _GENERIC])
    out = render_watchpoint_matrix(text, segment="us-equity")
    assert "| " + " | ".join(MATRIX_COLUMNS) + " |" not in out
    assert "#### 관찰 신호:" in out
    assert "- 출처: FRED" in out
    # § ① untouched.
    assert "## ① 요약\n본문" in out
    # Generic bullet is filtered instead of producing a low-value card.
    assert "FOMC 발언 톤 확인 필요" not in out


def test_render_is_idempotent() -> None:
    text = _section_six([_STRUCTURED_NUMERIC])
    once = render_watchpoint_matrix(text)
    twice = render_watchpoint_matrix(once)
    assert once == twice


def test_render_preserves_disclaimer_footer() -> None:
    text = _section_six([_STRUCTURED_NUMERIC]) + f"\n## ⑦ 면책조항\n\n{DISCLAIMER}\n"
    out = render_watchpoint_matrix(text)
    assert DISCLAIMER in out
    assert out.endswith(f"{DISCLAIMER}\n")


def test_render_no_section_six_is_noop() -> None:
    text = "## ① 요약\n본문\n"
    assert render_watchpoint_matrix(text) == text


def test_render_escapes_pipe_in_cell() -> None:
    bullet = "확인 소스: FRED · A | B 가 4.5% 상회하면 압력 관찰. 관심 영향: 점검."
    cards = render_matrix_table(build_watchpoint_rows([bullet]))
    assert "A | B" not in cards
    assert "A / B" in cards


# ---------------------------------------------------------------------------
# AC-72.4 — compliance: matrix carries no advice wording
# ---------------------------------------------------------------------------


def test_rendered_matrix_passes_compliance_scan() -> None:
    text = _section_six([_STRUCTURED_NUMERIC, _STRUCTURED_NO_FIGURE, _CARRYOVER_ONLY])
    out = render_watchpoint_matrix(text, segment="us-equity")
    # Should not raise ComplianceLanguageError; the P0 scanner is the
    # authoritative compliance gate (AC-72.4). Standalone advice verbs
    # (``매수 검토`` etc.) must not appear — substring tokens inside
    # legitimate observation words (``순매수``) are scanner-allowed.
    report = scan_compliance(out, "us-equity")
    assert report.p0_hits == ()
    for banned in ("매수 검토", "매도 검토", "목표가", "손절", "비중 확대", "비중 축소"):
        assert banned not in out


# ===========================================================================
# u87 — watchpoint-matrix-rehabilitation (AC-87.1..87.7)
# u98 — card-list renderer contract
#
# Fixtures derived from the real 2026-05-26 §⑥ defect shapes (crypto /
# us-equity / domestic-equity briefings): diagnostic-hash leak, markdown-link
# fragments, dangling particles, and the universal all-데이터부족 wall.
# ===========================================================================

_HEADER_LINE = "| " + " | ".join(MATRIX_COLUMNS) + " |"


def test_diagnostic_hash_line_is_filtered_before_rows_ac87_1() -> None:
    """AC-87.1 — a trace-footer ``input_hash`` bullet never becomes a row.

    The crypto §⑥ matrix carried ``- `input_hash`: `1ee42e89b281` ``. The
    pre-filter must drop it (and ``stage1_hash`` / ``stage2_hash``) before
    row building so no signal cell contains the diagnostic key or a backtick.
    """
    text = _section_six(
        [
            "`input_hash`: `1ee42e89b281`",
            "stage1_hash: abc123",
            "stage2_hash: def456",
            _STRUCTURED_NUMERIC,
        ]
    )
    out = render_watchpoint_matrix(text, segment="crypto")
    assert "input_hash" not in out
    assert "stage1_hash" not in out
    assert "stage2_hash" not in out
    assert "1ee42e89b281" not in out
    # No backtick survives into the rendered matrix body.
    assert "`" not in out


def test_markdown_link_bullet_never_yields_url_fragment_ac87_2() -> None:
    """AC-87.2 — a markdown-link bullet's signal uses the link text, never
    a truncated ``](http`` URL fragment.
    """
    bullet = (
        "확인 소스: Nasdaq · [AAPL](https://www.nasdaq.com/articles/aapl-news) "
        "주가가 신고점을 상회하면 모멘텀 관찰, 직전 지지선을 이탈하면 약화. "
        "관심 영향: 대형 기술주 점검."
    )
    out = render_watchpoint_matrix(_section_six([bullet]), segment="us-equity")
    assert "](http" not in out
    assert "https://" not in out
    # The link text (AAPL) survives as part of the signal label.
    assert "AAPL" in out


def test_signal_never_ends_on_bare_particle_ac87_3() -> None:
    """AC-87.3 — a signal label never dangles on a bare Korean 조사.

    Real defect shapes: ``원/달러 환율 1,499.83원이 …``, ``기관 순매수
    +8,168억원 독주 구도가 …``, ``BTC-USD가 …``.
    """
    from investo.publisher.watchpoint_matrix import _short_signal

    for bullet, forbidden in (
        ("원/달러 환율 1,499.83원이 상단 저항을 시험하는 흐름", "원이"),
        ("기관 순매수 +8,168억원 독주 구도가 이어지는 양상", "구도가"),
        ("BTC-USD가 단기 변동성 확대 국면", "BTC-USD가"),
    ):
        signal = _short_signal(bullet)
        assert not signal.rstrip("…").endswith(forbidden), signal
        for particle in ("이", "가", "은", "는", "을", "를"):
            assert not signal.rstrip("…").endswith(particle), signal


def test_all_unstructured_collapses_to_single_note_ac87_4() -> None:
    """AC-87.4 — when no bullet is structured, §⑥ renders the single pinned
    note and NO matrix header (never a ≥2-row 데이터부족 wall).
    """
    text = _section_six([_GENERIC, "BTC-USD 흐름 점검", "환율 추세 확인 필요"])
    out = render_watchpoint_matrix(text, segment="crypto")
    assert DATA_LIMITED_NOTE in out
    assert _HEADER_LINE not in out
    assert "#### 관찰 신호:" not in out
    # No multi-row/card 데이터부족 wall — the note replaces the body entirely.
    assert out.count("데이터부족") == 0


def test_structured_bullet_produces_populated_card_ac87_5_u98() -> None:
    """AC-87.5/u98 — a fully-structured source+trigger+implication bullet
    yields a populated card: source/current/triggers/implication present,
    confidence ∈ {높음,보통,낮음}. (Proves the card populates.)
    """
    text = _section_six([_STRUCTURED_NUMERIC])
    out = render_watchpoint_matrix(text, segment="us-equity")
    assert _HEADER_LINE not in out
    assert "#### 관찰 신호:" in out
    assert "- 출처: FRED" in out
    assert "- 현재: FRED" in out
    assert "- 확인 조건: 상방 " in out
    assert "- 신뢰도: 높음" in out
    assert "- 관심 영향: 변동성 확대 여부를 점검" in out
    assert "관심 영향: 관심 영향" not in out
    assert DATA_LIMITED_NOTE not in out

    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    row = rows[0]
    assert row.current != "현재 신호 부족"
    assert (
        row.bullish_trigger != DATA_LIMITED_CONFIDENCE
        or row.bearish_trigger != DATA_LIMITED_CONFIDENCE
    )
    assert row.confidence in {"높음", "보통", "낮음"}


def test_mixed_valid_and_unusable_rows_render_only_valid_cards_u98() -> None:
    text = _section_six([_GENERIC, _STRUCTURED_NO_FIGURE, "환율 추세 확인 필요"])
    out = render_watchpoint_matrix(text, segment="domestic-equity")
    assert DATA_LIMITED_NOTE not in out
    assert out.count("#### 관찰 신호:") == 1
    assert "- 출처: KRX" in out
    assert _GENERIC not in out
    assert "환율 추세 확인 필요" not in out


def test_card_defaults_for_partially_populated_structured_row_u98() -> None:
    bullet = (
        "10Y 금리가 4.5% 를 상회하면 성장주 변동성 부담 압력 관찰; "
        "4.3% 를 이탈하면 방어적 해석. 관심 영향: 변동성 확대 여부를 점검."
    )
    row = WatchpointRow(
        signal="10Y 금리",
        source="",
        current="",
        bullish_trigger="",
        bearish_trigger="",
        confidence="보통",
        implication="",
    )
    cards = render_matrix_table([row])
    assert f"- 출처: {PUBLIC_WATCHPOINT_SOURCE_TEXT}" in cards
    assert "- 현재: 현재 신호 부족" in cards
    assert (
        f"- 확인 조건: 상방 {PUBLIC_LOW_COVERAGE_INLINE_TEXT}; "
        f"하방 {PUBLIC_LOW_COVERAGE_INLINE_TEXT}" in cards
    )
    assert f"- 관심 영향: {PUBLIC_WATCHPOINT_LIMITED_TEXT}" in cards
    assert first_forbidden_public_evidence(cards) is None
    # A structured row without explicit source is still rejected by the u64
    # parser contract and collapses at document-render time.
    out = render_watchpoint_matrix(_section_six([bullet]), segment="us-equity")
    assert DATA_LIMITED_NOTE in out


def test_u110_promotes_source_from_current_and_strips_duplicate_labels() -> None:
    bullet = (
        "현재: 확인 소스: FRED · 10Y 금리가 상방 압력 구간에 머물며, "
        "상방: 상방 - 4.5%를 상회하면 성장주 변동성 부담 압력 관찰, "
        "하방: 하방 - 4.3%를 이탈하면 방어적 해석. "
        "관심 영향: 관심 영향: 대형 기술주 수급 점검."
    )
    out = render_watchpoint_matrix(_section_six([bullet]), segment="us-equity")
    assert "- 출처: FRED" in out
    assert "출처: 확인 소스 미상" not in out
    assert "관심 영향: 관심 영향" not in out
    assert "상방 상방" not in out
    assert "하방 하방" not in out
    # Prefix stripping must not erase semantic direction text in the current field.
    assert "상방 압력 구간" in out


def test_u110_identical_up_down_triggers_are_omitted() -> None:
    bullet = (
        "확인 소스: FRED · 10Y 금리가 4.5% 부근에서 정체; "
        "상방: 4.5% 확인 필요; 하방: 4.5% 확인 필요. "
        "관심 영향: 성장주 변동성 점검."
    )
    out = render_watchpoint_matrix(_section_six([bullet]), segment="us-equity")
    assert DATA_LIMITED_NOTE in out
    assert "#### 관찰 신호:" not in out


def test_u110_mixed_section_omits_invalid_rows_but_keeps_valid_card() -> None:
    invalid = (
        "확인 소스: FRED · 10Y 금리 점검; 상방: 4.5% 확인 필요; "
        "하방: 4.5% 확인 필요. 관심 영향: 성장주 변동성 점검."
    )
    valid = (
        "현재: 확인 소스: KRX · 외국인 순매수가 확대되면 수급 개선 관찰, "
        "축소되면 약화. 관심 영향: 대형주 수급 점검."
    )
    out = render_watchpoint_matrix(_section_six([invalid, valid]), segment="domestic-equity")
    assert DATA_LIMITED_NOTE not in out
    assert out.count("#### 관찰 신호:") == 1
    assert "- 출처: KRX" in out
    assert "4.5% 확인 필요; 하방 4.5% 확인 필요" not in out


def test_u110_one_soft_invalid_renders_two_soft_invalids_omit() -> None:
    from investo.publisher.watchpoint_matrix import _renderable_row

    one_soft = WatchpointRow(
        signal="10Y 금리",
        source="FRED",
        current="금리 추세",
        bullish_trigger="4.5%를 상회하면 압력 관찰",
        bearish_trigger="4.3%를 이탈하면 방어적 해석",
        confidence="보통",
        implication="금리 민감주 점검",
    )
    two_soft = WatchpointRow(
        signal="원/달러 환율",
        source="KRX",
        current="환율 추세",
        bullish_trigger="1,400원을 상회하면 부담 관찰",
        bearish_trigger="1,350원을 이탈하면 완화",
        confidence="보통",
        implication="관심 영향 데이터 부족",
    )
    assert _renderable_row(one_soft)
    assert not _renderable_row(two_soft)


def test_card_renderer_removes_urls_broken_markdown_and_trace_tokens_u98() -> None:
    row = WatchpointRow(
        signal="[AAPL](https://example.com/aapl) input_hash: abcdef123456",
        source="Nasdaq https://example.com/source",
        current="[AAPL](https://example.com/aapl) 주가가 신고점을 상회하면 모멘텀 관찰",
        bullish_trigger="상방 https://example.com/bull",
        bearish_trigger="하방 ](https://broken.example",
        confidence="보통",
        implication="stage1_hash: abcdef123456 관심 영향: 기술주 점검",
    )
    cards = render_matrix_table([row])
    assert "https://" not in cards
    assert "](http" not in cards
    assert "input_hash" not in cards
    assert "stage1_hash" not in cards


def test_existing_watchpoint_tests_compliance_unchanged_ac87_6() -> None:
    """AC-87.6 — the rehabilitated renderer introduces no advice wording; a
    mixed structured+unstructured §⑥ still passes the P0 compliance scan.
    """
    text = _section_six([_STRUCTURED_NUMERIC, _GENERIC])
    out = render_watchpoint_matrix(text, segment="us-equity")
    report = scan_compliance(out, "us-equity")
    assert report.p0_hits == ()
    for banned in ("매수 검토", "매도 검토", "목표가", "손절"):
        assert banned not in out


def test_data_limited_note_render_is_idempotent_ac87_7() -> None:
    """AC-87.7 — re-running over output containing DATA_LIMITED_NOTE returns
    it unchanged (idempotent for the collapsed state too).
    """
    text = _section_six([_GENERIC, "환율 추세 확인 필요"])
    once = render_watchpoint_matrix(text, segment="crypto")
    twice = render_watchpoint_matrix(once, segment="crypto")
    assert DATA_LIMITED_NOTE in once
    assert once == twice


def test_render_byte_preserves_outside_section_six_ac87_7() -> None:
    """AC-87.7 — every section outside §⑥ plus the disclaimer footer is
    byte-preserved by the collapse transform.
    """
    head = "## ① 요약\n본문 그대로\n\n## ④ 지표·이벤트\n표 본문\n\n"
    six = "## ⑥ 오늘의 관전 포인트\n\n- FOMC 발언 톤 확인 필요\n\n"
    tail = f"## ⑦ 면책조항\n\n{DISCLAIMER}\n"
    out = render_watchpoint_matrix(head + six + tail, segment="us-equity")
    assert out.startswith(head)
    assert out.endswith(tail)
    assert DATA_LIMITED_NOTE in out


def test_typed_watchpoint_result_reports_rendered_cards_without_limitation() -> None:
    text = _section_six([_STRUCTURED_NUMERIC])

    result = render_watchpoint_matrix_result(text, segment="us-equity")

    assert result.state == "rendered"
    assert result.usable_card_count == 1
    assert result.limitation_reasons == ()
    assert "#### 관찰 신호:" in result.markdown
    assert render_watchpoint_matrix(text, segment="us-equity") == result.markdown


def test_typed_watchpoint_result_reports_exact_limited_reason() -> None:
    result = render_watchpoint_matrix_result(
        _section_six([_GENERIC]),
        segment="crypto",
        coverage_limited=True,
    )

    assert result.state == "limited"
    assert result.usable_card_count == 0
    assert result.limitation_reasons == ("watchpoint_unavailable",)
    assert DATA_LIMITED_NOTE in result.markdown


@pytest.mark.parametrize(
    ("bullet", "coverage_limited", "expected_state"),
    (
        (_STRUCTURED_NUMERIC, False, "rendered"),
        (_GENERIC, True, "limited"),
    ),
)
def test_typed_watchpoint_result_byte_preserves_opaque_owned_fragment(
    bullet: str,
    coverage_limited: bool,
    expected_state: str,
) -> None:
    fragment = (
        "<!-- investo:block visual:us-equity.visual.watchlist-relevance -->\n"
        "![관심 자산 관련성](watchlist-relevance.svg)\n"
        "<!-- /investo:block visual:us-equity.visual.watchlist-relevance -->\n"
    )
    text = _section_six([bullet]).replace(
        "## ⑥ 오늘의 관전 포인트\n\n",
        f"## ⑥ 오늘의 관전 포인트\n\n{fragment}\n",
    )

    result = render_watchpoint_matrix_result(
        text,
        segment="us-equity",
        coverage_limited=coverage_limited,
        preserved_fragments=(fragment,),
    )
    repeated = render_watchpoint_matrix_result(
        result.markdown,
        segment="us-equity",
        coverage_limited=coverage_limited,
        preserved_fragments=(fragment,),
    )

    assert result.state == expected_state
    assert result.markdown.count(fragment) == 1
    assert repeated.markdown == result.markdown


def test_typed_watchpoint_result_rejects_forged_or_mixed_idempotent_shapes() -> None:
    malformed = _section_six([]).replace(
        "## ⑥ 오늘의 관전 포인트\n\n",
        "## ⑥ 오늘의 관전 포인트\n\n#### 관찰 신호: 제목만\n",
    )
    malformed_result = render_watchpoint_matrix_result(malformed)
    assert malformed_result.state == "limited"
    assert malformed_result.usable_card_count == 0

    embedded_note = _section_six([_STRUCTURED_NUMERIC]).replace(
        "## ⑥ 오늘의 관전 포인트\n\n",
        f"## ⑥ 오늘의 관전 포인트\n\n{DATA_LIMITED_NOTE}\n\n",
    )
    embedded_result = render_watchpoint_matrix_result(embedded_note)
    assert embedded_result.state == "rendered"
    assert DATA_LIMITED_NOTE not in embedded_result.markdown

    rendered = render_watchpoint_matrix_result(_section_six([_STRUCTURED_NUMERIC])).markdown
    mixed = f"{rendered.rstrip()}\n\n{DATA_LIMITED_NOTE}\n"
    mixed_result = render_watchpoint_matrix_result(mixed)
    assert mixed_result.state == "limited"
    assert mixed_result.markdown != mixed
    assert mixed_result.markdown.count(DATA_LIMITED_NOTE) == 1
    assert "#### 관찰 신호:" not in mixed_result.markdown

    unusable = rendered.replace("- 출처: FRED", "- 출처: 확인 소스 미상").replace(
        "- 신뢰도: 높음", "- 신뢰도: 데이터부족"
    )
    unusable_result = render_watchpoint_matrix_result(unusable)
    assert unusable_result.state == "limited"
    assert unusable_result.usable_card_count == 0
    assert "#### 관찰 신호:" not in unusable_result.markdown

    card = rendered.split("## ⑥ 오늘의 관전 포인트\n\n", maxsplit=1)[1].strip()
    overbound = (
        "## ① 요약\n본문\n\n## ⑥ 오늘의 관전 포인트\n\n"
        + "\n\n".join([card] * (MAX_VISIBLE_ROWS + 1))
        + "\n"
    )
    overbound_result = render_watchpoint_matrix_result(overbound)
    assert overbound_result.state == "limited"
    assert overbound_result.usable_card_count == 0

    for forged in (
        rendered.replace("#### 관찰 신호: 10Y 금리", "#### 관찰 신호: https://secret.test/raw"),
        rendered.replace("- 현재: ", "- 현재: input_hash: deadbeef ", 1),
    ):
        forged_result = render_watchpoint_matrix_result(forged)
        assert forged_result.state == "limited"
        assert forged_result.usable_card_count == 0
        assert "https://secret.test/raw" not in forged_result.markdown
        assert "deadbeef" not in forged_result.markdown


def test_legacy_watchpoint_renderer_preserves_empty_input_compatibility() -> None:
    assert render_watchpoint_matrix("") == ""
    with pytest.raises(ValueError, match="input markdown must not be empty"):
        render_watchpoint_matrix_result("")


@pytest.mark.parametrize(
    "result",
    (
        lambda: WatchpointRenderResult("body", "rendered", 0),
        lambda: WatchpointRenderResult(
            "body",
            "rendered",
            1,
            ("watchpoint_unavailable",),
        ),
        lambda: WatchpointRenderResult("body", "limited", 1, ("watchpoint_unavailable",)),
        lambda: WatchpointRenderResult("body", "limited", 0),
    ),
)
def test_typed_watchpoint_result_rejects_state_count_reason_drift(result: object) -> None:
    with pytest.raises(ValueError):
        result()  # type: ignore[operator]
