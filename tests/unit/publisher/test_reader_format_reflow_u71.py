"""u71 — reader-first viewport reflow.

These tests pin the *ordering / compactness / collapse* contract only.
u71 does not re-validate summary text (u61) or recompute status (u54/u62);
it reflows already-rendered values. The fixtures therefore start from a
fully-assembled briefing header (title, watermark, nav, coverage badge,
summary callouts) shaped exactly like
``investo.briefing.pipeline._enhance_reader_experience`` output.
"""

from __future__ import annotations

import re

from investo.publisher.reader_format import (
    DIAGNOSTICS_SUMMARY_LABEL,
    SNIPPET_MAX_CHARS,
    bound_summary_snippet,
    reflow_first_viewport,
)

_BADGE = (
    "> **데이터 상태**: 부분 — 일부 카테고리 미수집, 본문 일부 결론 보강 필요 · "
    "수집 12건 / 소스 5개 / 누락: 뉴스\n"
    "> **소스 카운트**: 수집 대상 6 / 성공 4 / 0건 1 / 실패 1 / 본문 사용 3\n"
    "> **소스 등급 분포**: S=1 / A=2 / B=1\n"
    "> **상세 사유**: 핵심 소스 실패\n"
    "> **소스별 상태**: cnbc-top-news 실패 (접근 제한), stooq-price 0건, 정상 4개\n"
)

_SUMMARY = (
    "> **오늘의 결론**: [관망] 3대 지수 혼조 마감.\n"
    "> **핵심 동인**: 금리 우려와 실적 기대가 충돌.\n"
    "> **주의할 점**: CPI 발표를 앞두고 변동성 확대 가능성에 유의.\n\n"
)


def _header(*, badge: str = _BADGE, summary: str = _SUMMARY) -> str:
    return (
        "# 2026-05-24 미국 증시 시황\n\n"
        "**기준 시각**: 2026-05-24 NY · [2026-05-23T20:00Z, 2026-05-24T20:00Z)\n\n"
        "**세그먼트**: [국내 증시](x) | [미국 증시](y) | [크립토](z)\n\n"
        "## 한눈에 보기\n\n"
        "- 결론 한 줄\n- 동인 한 줄\n- 주의 한 줄\n\n"
        f"{badge}"
        f"{summary}"
        "## ① 요약\n\n본문...\n\n"
        "## ⑦ 면책조항\n\n정보 제공용 자동 시황이며 매매 권유가 아닙니다.\n"
    )


def _index(text: str, needle: str) -> int:
    pos = text.find(needle)
    assert pos != -1, f"missing: {needle!r}"
    return pos


# ---------------------------------------------------------------------------
# AC-71.1 / AC-71.2 — ordering: main note before diagnostics
# ---------------------------------------------------------------------------


def test_main_sections_precede_collapsed_diagnostics() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    tldr = _index(out, "## 한눈에 보기")
    conclusion = _index(out, "**오늘의 결론**")
    section = _index(out, "## ①")
    chip = _index(out, "이번 문서는 수집 근거가 제한적입니다.")
    details = _index(out, f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>")
    disclaimer = _index(out, "## ⑦ 면책조항")
    assert tldr < conclusion < section < chip < details < disclaimer


def test_raw_diagnostics_moved_below_main_sections() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    # The raw per-source / count / tier lines now live inside <details>,
    # i.e. after the main market sections, not in the lead.
    section = _index(out, "## ①")
    source_status = _index(out, "소스별 상태")
    count_line = _index(out, "소스 카운트")
    tier_line = _index(out, "소스 등급 분포")
    assert section < source_status
    assert section < count_line
    assert section < tier_line
    # And all sit inside the details block.
    open_idx = _index(out, f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>")
    close_idx = _index(out, "</details>")
    for needle in ("소스 카운트", "소스 등급 분포", "상세 사유", "소스별 상태"):
        idx = _index(out, needle)
        assert open_idx < idx < close_idx


def test_compact_chip_kept_outside_details() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    chip = _index(out, "이번 문서는 수집 근거가 제한적입니다.")
    open_idx = _index(out, f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>")
    assert chip < open_idx


def test_chip_format_fixed_fields() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    assert (
        "> **데이터 상태**: 부분 · 이번 문서는 수집 근거가 제한적입니다. "
        "· 수집 상세는 진단 섹션에서 확인할 수 있습니다."
    ) in out


def test_chip_omits_untracked_body_usage_wording() -> None:
    badge = _BADGE.replace("본문 사용 3", "본문 사용 미집계")
    out = reflow_first_viewport(_header(badge=badge), segment="us-equity")
    assert "> **데이터 상태**: 부분 · 이번 문서는 수집 근거가 제한적입니다." in out
    chip = out.split(f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>", 1)[0]
    assert "본문 사용 미집계" not in chip
    assert "실패 1" not in chip
    assert "0건 1" not in chip


def test_details_collapsed_by_default_for_non_failed() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    assert "<details><summary>" in out
    assert "<details open>" not in out


def test_details_expanded_when_failed() -> None:
    failed_badge = _BADGE.replace(
        "**데이터 상태**: 부분 — 일부 카테고리 미수집, 본문 일부 결론 보강 필요",
        "**데이터 상태**: 실패 — 핵심 소스 전부 실패",
    )
    out = reflow_first_viewport(_header(badge=failed_badge), segment="us-equity")
    assert "<details open><summary>" in out


# ---------------------------------------------------------------------------
# AC-71.3 — caution/watchpoint snippet bounding
# ---------------------------------------------------------------------------


def test_long_caution_truncated_at_word_boundary() -> None:
    long_caution = (
        "> **주의할 점**: "
        + "변동성 확대 가능성과 금리 인상 우려 및 실적 둔화 신호가 " * 4
        + "동시에 작용할 수 있다.\n\n"
    )
    out = reflow_first_viewport(_header(summary=_SUMMARY[:0] + long_caution), segment="us-equity")
    m = re.search(r">\s*\*\*주의할 점\*\*\s*:\s*(.+)", out)
    assert m is not None
    body = m.group(1).strip()
    assert body.endswith("...")
    # Bounded to the limit (the "..." may push 3 past the visible window).
    assert len(body) <= SNIPPET_MAX_CHARS + 3
    # No mid-token break: the char before "..." is not a partial syllable
    # join — boundary truncation means the text before "..." is a clean run.
    assert "  " not in body


def test_bound_summary_snippet_short_unchanged() -> None:
    short = "CPI 발표를 앞두고 변동성 확대에 유의."
    assert bound_summary_snippet(short) == short


def test_bound_summary_snippet_unbreakable_token_omitted() -> None:
    # A single 100-char token with no boundary before the limit → omit.
    token = "가" * 100
    assert bound_summary_snippet(token) == ""


def test_unbreakable_caution_falls_back_not_blank() -> None:
    bad = "> **주의할 점**: " + "가" * 120 + "\n\n"
    out = reflow_first_viewport(_header(summary=bad), segment="us-equity")
    m = re.search(r">\s*\*\*주의할 점\*\*\s*:\s*(\S.+)", out)
    assert m is not None
    assert m.group(1).strip() == "주요 주의 사항은 본문을 참고하세요."


# ---------------------------------------------------------------------------
# AC-71.5 / regression — idempotent, disclaimer + tldr preserved
# ---------------------------------------------------------------------------


def test_reflow_idempotent() -> None:
    once = reflow_first_viewport(_header(), segment="us-equity")
    twice = reflow_first_viewport(once, segment="us-equity")
    assert once == twice


def test_disclaimer_preserved() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    assert "## ⑦ 면책조항" in out
    assert "정보 제공용 자동 시황이며 매매 권유가 아닙니다." in out


def test_tldr_block_preserved_and_first() -> None:
    out = reflow_first_viewport(_header(), segment="us-equity")
    assert "## 한눈에 보기" in out
    assert _index(out, "## 한눈에 보기") < _index(out, "## ①")


def test_no_badge_is_noop_for_diagnostics() -> None:
    # Data-limited legacy run with no coverage badge: reflow only bounds
    # the caution line; no chip / details are injected.
    out = reflow_first_viewport(_header(badge=""), segment="us-equity")
    assert "<details>" not in out
    assert "데이터 상태" not in out
    # Summary + tldr still intact and ordered.
    assert _index(out, "## 한눈에 보기") < _index(out, "**오늘의 결론**") < _index(out, "## ①")


def test_reflow_without_summary_callouts_uses_section_anchor() -> None:
    # No summary callouts (rare) — chip + details still land at the end.
    out = reflow_first_viewport(_header(summary=""), segment="us-equity")
    chip = _index(out, "> **데이터 상태**: 부분")
    details = _index(out, f"<summary>{DIAGNOSTICS_SUMMARY_LABEL}</summary>")
    section = _index(out, "## ①")
    disclaimer = _index(out, "## ⑦ 면책조항")
    assert section < chip < details < disclaimer
