"""Regression tests for u25 — summary fidelity and content trust.

The 2026-05-06 segmented archive (us-equity / crypto / domestic-equity)
shipped with three first-viewport summary lines truncated to "1." or
``"**입법 가속화 vs."``. The persona evaluation flagged this as a P0
trust regression. This file pins the producer-side
(:func:`investo.briefing.pipeline._summary_sentence`) and gate-side
(:func:`investo.briefing.summary_quality.validate_first_viewport_summary`)
behavior against the patterns that produced those failures.

Coverage:

* Producer-side ``_summary_sentence`` rejects marker-only and
  conjunction-tail candidates and falls through to the next sentence
  or the explicit fallback string.
* Producer-side ``_summary_sentence`` correctly extracts a full
  sentence from each of the three real archive section bodies that
  previously truncated.
* Gate-side ``validate_first_viewport_summary`` rejects marker-only,
  conjunction-tail (English + Korean), unbalanced-bold, and
  unbalanced-link inputs.
* Watermark renderer emits the deterministic reader-facing
  ``**기준 시각**: YYYY-MM-DD <TZ> · 수집창 start_utc ~ end_utc (종료 미포함)`` line
  and is included in the segmented brief header.
"""

from __future__ import annotations

from datetime import date

import pytest

from investo._internal.public_quality_language import project_public_quality_language
from investo.briefing.pipeline import (
    _build_summary_header,
    _enhance_reader_experience,
    _is_unsafe_summary_candidate,
    _render_timestamp_watermark,
    _summary_sentence,
    parse_six_sections,
)
from investo.briefing.summary_quality import (
    SummaryQualityError,
    is_unsafe_summary_value,
    validate_first_viewport_summary,
)

# ---------------------------------------------------------------------------
# Producer-side rejects (`_summary_sentence`)
# ---------------------------------------------------------------------------


# Persona-cited 2026-05-06 archive section ⑥ bodies. Long Korean
# sentences trigger ``E501`` if inlined; assemble at module scope so the
# parametrize block stays readable.
_ARCHIVE_SECTION6_BODIES: tuple[str, ...] = (
    # domestic-equity ⑥ — data-limited fallback list.
    (
        "1. 데이터 수집 로그에서 실패한 소스와 0건 소스를 구분합니다.\n"
        "2. 해당 시장의 대표 가격 지표가 회복됐는지 확인합니다."
    ),
    # us-equity ⑥ — bold-then-prose list.
    (
        "1. **ARM 가이던스** — AI 로열티 매출 전망치가 더 중요하다."
        " 상향 시 반도체 섹터에 매수 심리가 확산될 수 있다.\n"
        "2. **APP vs. UBER** — 동시 확인 시 성장주 리레이팅 신호다."
    ),
    # crypto ⑥ — colon-style bullets.
    (
        "1. **입법 협상 진행 상황**: Gillibrand의 윤리 조항 요구가"
        " 7월 4일 목표 달성의 최대 장애물이다.\n"
        "2. **Hyperliquid 고래 포지션 지속 여부**: 2026년 최고치"
        " BTC 순롱이 유지되는지 확인할 필요가 있다."
    ),
)


@pytest.mark.parametrize("section_body", _ARCHIVE_SECTION6_BODIES)
def test_summary_sentence_returns_full_clause_for_archive_section6(
    section_body: str,
) -> None:
    """The previously-truncated archive section ⑥ bodies now resolve to
    a full clause, not the bare ``"1."`` marker.
    """
    result = _summary_sentence(section_body, fallback="FALLBACK")
    assert result != "1."
    assert result != "FALLBACK"
    # Result must be a meaningful Korean sentence — at least 10 chars
    # and contains hangul.
    assert len(result) >= 10
    assert any("가" <= ch <= "힣" for ch in result)


def test_summary_sentence_does_not_truncate_at_conjunction() -> None:
    """A section body whose first line is ``**입법 가속화 vs. 정치적 마찰**``
    must not be returned truncated at ``vs.`` — either the full
    sentence (terminator-anchored) or a safe later candidate.
    The persona-cited 2026-05-06 crypto archive shipped
    ``> **핵심 동인**: **입법 가속화 vs.``; this regression test pins
    that the fix never produces that truncation again.
    """
    body = (
        "**입법 가속화 vs. 정치적 마찰**\n"
        "[White House가 7월 4일 목표를 잡았다고 밝혔다.](https://example.com)"
    )
    result = _summary_sentence(body, fallback="FALLBACK")
    assert not result.endswith("vs.")
    assert not result.endswith("vs")
    # Result must be a complete clause (ends in 다. / 니다. / 요. / ? / !).
    assert any(result.endswith(t) for t in ("다.", "니다.", "요.", "?", "!"))


def test_summary_sentence_skips_conjunction_tail_when_safe_next_clause_exists() -> None:
    """If the only complete sentence ends with a conjunction, the
    picker must continue scanning rather than returning the bad
    candidate.
    """
    # Two complete sentences — first ends in `vs.`, second is clean.
    body = "정책은 입법 가속화 vs. 그러나 다음 단계는 명확하다."
    result = _summary_sentence(body, fallback="FALLBACK")
    assert not result.rstrip().endswith("vs.")


def test_summary_sentence_returns_fallback_when_only_unsafe_candidates_exist() -> None:
    """Marker-only line + conjunction-tail bold heading + nothing else
    → the explicit fallback string is returned (not the empty string,
    not the marker, not the truncation).
    """
    body = "1.\n**입법 가속화 vs.\n"
    result = _summary_sentence(body, fallback="관전 포인트는 데이터 회복 후 보강합니다.")
    assert result == "관전 포인트는 데이터 회복 후 보강합니다."


def test_summary_sentence_marker_only_candidate_rejected() -> None:
    """A bare ``"1."`` (no following text on the same line) does not
    survive cleaning — fallback is returned.
    """
    assert _summary_sentence("1.", fallback="FB") == "FB"
    assert _summary_sentence("- ", fallback="FB") == "FB"
    assert _summary_sentence("①", fallback="FB") == "FB"


def test_summary_sentence_strips_plain_heading_before_candidate_scan() -> None:
    body = "### KOSPI 가격 흐름\n삼성전자 강보합과 외국인 수급이 지수 하단을 지지했다."

    result = _summary_sentence(body, fallback="FB")

    assert not result.startswith("###")
    assert result == "KOSPI 가격 흐름 삼성전자 강보합과 외국인 수급이 지수 하단을 지지했다."


def test_is_unsafe_summary_candidate_covers_persona_patterns() -> None:
    # Marker-only.
    assert _is_unsafe_summary_candidate("1.")
    assert _is_unsafe_summary_candidate("-")
    # English conjunction tail.
    assert _is_unsafe_summary_candidate("입법 가속화 vs.")
    assert _is_unsafe_summary_candidate("policy and.")
    # Unbalanced bold.
    assert _is_unsafe_summary_candidate("**입법 가속화")
    # Unbalanced bracket.
    assert _is_unsafe_summary_candidate("[미국 증시")
    assert _is_unsafe_summary_candidate("### KOSPI 가격 흐름")
    assert _is_unsafe_summary_candidate("금리 **-**0.10%**p** 변동")
    assert _is_unsafe_summary_candidate("미국 증시 변동성 ROS")
    # Korean particle tail.
    assert _is_unsafe_summary_candidate("정책과.")
    # Safe sentence — must NOT trip the gate.
    assert not _is_unsafe_summary_candidate("2026년 5월 6일 미국 증시는 대형주 어닝 집중일이다.")


@pytest.mark.parametrize(
    "candidate",
    [
        "1.",
        "1)",
        "①",
        "**입법 가속화 vs.",
        "입법 가속화 vs.",
        "policy and.",
        "정책과.",
        "[미국 증시",
        "(미확인",
        "### KOSPI 가격 흐름",
        "금리 **-**0.10%**p** 변동",
        "미국 증시 변동성 ROS",
    ],
)
def test_producer_uses_canonical_summary_reject_predicate(candidate: str) -> None:
    assert _is_unsafe_summary_candidate(candidate) is is_unsafe_summary_value(candidate)


# ---------------------------------------------------------------------------
# Gate-side rejects (`validate_first_viewport_summary`)
# ---------------------------------------------------------------------------


def _wrap_first_viewport(*, conclusion: str, driver: str, caution: str) -> str:
    return (
        "# 2026-05-06 미국 증시 시황\n\n"
        f"> **오늘의 결론**: {conclusion}\n"
        f"> **핵심 동인**: {driver}\n"
        f"> **주의할 점**: {caution}\n\n"
        "## ① 요약\n본문\n"
    )


@pytest.mark.parametrize(
    "caution",
    [
        # Persona-cited regression patterns.
        "1.",
        "1)",
        "①",
        "**입법 가속화 vs.",
        "입법 가속화 vs.",
        "policy and.",
        "정책과.",
        "[미국 증시",
        "(미확인",
    ],
)
def test_gate_rejects_archive_2026_05_06_truncation_patterns(caution: str) -> None:
    """Each persona-cited pattern from the 2026-05-06 archive segments
    is rejected by the publish-time gate.
    """
    markdown = _wrap_first_viewport(
        conclusion="미국 증시는 실적 일정을 앞두고 방향성 확인이 필요합니다.",
        driver="입법 가속화는 7월 4일 통과 가능성이 가장 큰 변수입니다.",
        caution=caution,
    )
    with pytest.raises(SummaryQualityError):
        validate_first_viewport_summary(markdown)


def test_gate_accepts_well_formed_segmented_brief() -> None:
    markdown = _wrap_first_viewport(
        conclusion="미국 증시는 실적 일정을 앞두고 방향성 확인이 필요합니다.",
        driver="입법 가속화는 7월 4일 통과 가능성이 가장 큰 변수입니다.",
        caution="ARM 가이던스가 반도체 섹터 심리를 좌우할 전망이다.",
    )
    validate_first_viewport_summary(markdown)


# ---------------------------------------------------------------------------
# Watermark — Step 3
# ---------------------------------------------------------------------------


def test_watermark_us_equity_uses_ny_clock() -> None:
    line = _render_timestamp_watermark(date(2026, 5, 6), "us-equity")
    # NY EDT in May → UTC-4. So 2026-05-06 00:00 NY = 2026-05-06 04:00Z.
    assert line == (
        "**기준 시각**: 2026-05-06 NY · 수집창 2026-05-06T04:00Z ~ 2026-05-07T04:00Z (종료 미포함)"
    )


def test_watermark_domestic_equity_uses_kst_clock() -> None:
    line = _render_timestamp_watermark(date(2026, 5, 6), "domestic-equity")
    # KST = UTC+9. So 2026-05-06 00:00 KST = 2026-05-05 15:00Z.
    assert line == (
        "**기준 시각**: 2026-05-06 KST · 수집창 2026-05-05T15:00Z ~ 2026-05-06T15:00Z (종료 미포함)"
    )


def test_watermark_crypto_uses_utc_clock() -> None:
    line = _render_timestamp_watermark(date(2026, 5, 6), "crypto")
    assert line == (
        "**기준 시각**: 2026-05-06 UTC · 수집창 2026-05-06T00:00Z ~ 2026-05-07T00:00Z (종료 미포함)"
    )


def test_watermark_appears_in_segmented_brief_header() -> None:
    """The watermark line is rendered between the H1 title and the
    segment-nav line of every segmented brief.
    """
    body = (
        "## ① 요약\n2026년 5월 6일 미국 증시는 실적 집중일이다.\n\n"
        "## ② 전일 핵심 이슈\n어닝 카탈리스트가 시장을 주도한다.\n\n"
        "## ③ 섹터/수급 동향\n반도체 섹터 자금 유입.\n\n"
        "## ④ 지표·이벤트\n어닝 발표가 단기 변동성 이벤트.\n\n"
        "## ⑤ 주요 종목\nARM 실적이 주요 관전 항목.\n\n"
        "## ⑥ 오늘의 관전 포인트\nARM 가이던스를 확인합니다.\n"
    )
    sections = parse_six_sections(body)
    enhanced = _enhance_reader_experience(
        body,
        target_date=date(2026, 5, 6),
        segment="us-equity",
        sections=sections,
    )
    assert "# 2026-05-06 미국 증시 시황\n\n" in enhanced
    assert (
        "**기준 시각**: 2026-05-06 NY · 수집창 2026-05-06T04:00Z ~ 2026-05-07T04:00Z (종료 미포함)"
    ) in enhanced
    # Watermark precedes the segment-nav line.
    watermark_idx = enhanced.find("**기준 시각**:")
    nav_idx = enhanced.find("**세그먼트**:")
    assert 0 < watermark_idx < nav_idx


# ---------------------------------------------------------------------------
# End-to-end producer → gate contract
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# u30 Step 3 — action tag contract integration
# ---------------------------------------------------------------------------


def test_summary_header_appends_default_action_tag_when_missing() -> None:
    sections = (
        "2026년 5월 6일 미국 증시는 대형주 어닝 집중일이다.",
        "어닝 카탈리스트가 시장을 주도한다.",
        "",
        "",
        "",
        "ARM 가이던스를 확인합니다.",
    )
    header = _build_summary_header(sections)
    # u56 — DEFAULT_ACTION_TAG migrated [관망] → [데이터부족]
    assert header.conclusion.endswith(" [데이터부족]")


def test_summary_header_preserves_in_set_action_tag() -> None:
    sections = (
        "오늘은 변동성이 커집니다. [변동성 확대]",
        "동인 본문.",
        "",
        "",
        "",
        "관전 포인트.",
    )
    header = _build_summary_header(sections)
    assert header.conclusion.endswith(" [변동성 확대]")
    # No double-tagging.
    assert header.conclusion.count("[변동성 확대]") == 1
    assert "[데이터부족]" not in header.conclusion


def test_summary_header_strips_off_set_tag_and_replaces_with_default() -> None:
    sections = (
        "Bullish day ahead. [BUY]",
        "Driver line.",
        "",
        "",
        "",
        "Caution line.",
    )
    header = _build_summary_header(sections)
    assert "[BUY]" not in header.conclusion
    # u56 — default migrated [관망] → [데이터부족]
    assert header.conclusion.endswith(" [데이터부족]")


def test_summary_header_forces_data_limited_tag_when_data_limited_true() -> None:
    sections = (
        "오늘은 데이터 부족합니다. [강세]",
        "Driver line.",
        "",
        "",
        "",
        "Caution line.",
    )
    header = _build_summary_header(sections, data_limited=True)
    assert header.conclusion.endswith(" [데이터부족]")
    assert "[강세]" not in header.conclusion


def test_summary_header_from_archive_section_bodies_passes_gate() -> None:
    """Build the header from realistic archive section bodies and
    verify it survives the publish-time gate. This pins the contract
    between the producer (which outputs the header) and the gate
    (which validates it on publish).
    """
    sections = (
        # ① 요약 — clean conclusion.
        "2026년 5월 6일 미국 증시는 대형주 어닝 집중일이다.",
        # ② 전일 핵심 이슈 — bold heading then prose.
        "**입법 가속화 vs. 정치적 마찰**\n"
        "[White House는 7월 4일 통과 목표를 유지한다고 밝혔다.](https://example.com)",
        "",  # ③
        "",  # ④
        "",  # ⑤
        # ⑥ 오늘의 관전 포인트 — numbered list with bold.
        "1. **ARM 가이던스** — AI 로열티 매출 전망치가 더 중요하다.\n"
        "2. **APP vs. UBER** — 동시 확인 시 성장주 리레이팅 신호다.",
    )
    header = _build_summary_header(sections)
    markdown = _wrap_first_viewport(
        conclusion=project_public_quality_language(header.conclusion),
        driver=header.driver,
        caution=header.caution,
    )
    validate_first_viewport_summary(markdown)
