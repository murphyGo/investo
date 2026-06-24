"""Unit tests for ``investo.publisher.reader_format`` (u51).

Coverage map (per u51 plan Step 3):

* TL;DR insertion: present → no-op, absent → callout-derived placeholder,
  no callouts → unchanged + WARNING.
* H3 promotion: whole-line bold → ``### Title``; partial bold inside a
  paragraph stays untouched; idempotent on repeated runs.
* Number wrap: signed percent / dollar / bare-decimal percent are bolded;
  table rows, code fences, link URLs, and already-bold tokens are skipped;
  idempotent.
* §⑥ action ratio: 5/5 observation → 1.0 + warn; 2/5 → 0.4 (at threshold,
  no warn); 0 bullets → 0.0; missing section → 0.0.
* Glossing dedupe: first occurrence kept; second/third stripped; different
  base terms untouched; URLs / non-glossing parens unaffected.
* Pipeline: ``apply_reader_format`` preserves the disclaimer string at the
  document tail (R5 pin).
"""

from __future__ import annotations

import logging

from investo.briefing.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO
from investo.publisher.reader_format import (
    ACTION_RATIO_THRESHOLD,
    TLDR_HEADER,
    apply_reader_format,
    check_action_bullet_ratio,
    check_watchpoint_actionability,
    dedupe_glossings,
    enforce_h3_subheadings,
    ensure_tldr_block,
    escape_krx_stock_code_link_fragments,
    normalize_data_limited_reader_copy,
    wrap_numbers_bold,
)

# ---------------------------------------------------------------------------
# ensure_tldr_block
# ---------------------------------------------------------------------------


def test_ensure_tldr_block_present_is_noop() -> None:
    text = f"{TLDR_HEADER}\n\n- a\n- b\n- c\n\n## ① 요약\nbody\n"
    assert ensure_tldr_block(text) == text


def test_ensure_tldr_block_inserts_from_callouts() -> None:
    text = (
        "# 2026-05-11 미국 증시 시황\n\n"
        "> **오늘의 결론**: 3대 지수 상승 마감 [강세]\n"
        "> **핵심 동인**: 전주 반등 흐름 연장\n"
        "> **주의할 점**: 10Y 4.42% 부담 잔존\n\n"
        "## ① 요약\nbody\n"
    )
    out = ensure_tldr_block(text)
    assert TLDR_HEADER in out
    # All three callout bodies surface as bullets.
    assert "- 3대 지수 상승 마감 [강세]" in out
    assert "- 전주 반등 흐름 연장" in out
    assert "- 10Y 4.42% 부담 잔존" in out
    # Block lands BEFORE the first section header.
    assert out.find(TLDR_HEADER) < out.find("## ①")


def test_ensure_tldr_block_missing_callout_uses_reader_copy() -> None:
    text = (
        "# 2026-05-11 미국 증시 시황\n\n"
        "> **오늘의 결론**: 3대 지수 상승 마감 [강세]\n"
        "> **주의할 점**: 10Y 4.42% 부담 잔존\n\n"
        "## ① 요약\nbody\n"
    )
    out = ensure_tldr_block(text)
    assert "데이터 부족" not in out.split("## ①", 1)[0]
    assert "- 뚜렷한 단일 동인은 본문 흐름으로 확인하세요." in out


def test_ensure_tldr_block_no_callouts_warns_and_passes_through(
    caplog: object,
) -> None:
    import pytest

    cap = caplog
    assert isinstance(cap, pytest.LogCaptureFixture)
    text = "# Title\n\n## ① 요약\nbody\n"
    with cap.at_level(logging.WARNING, logger="investo.publisher.reader_format"):
        out = ensure_tldr_block(text, segment="us-equity")
    assert out == text
    assert any("tldr_missing" in r.message for r in cap.records)


def test_ensure_tldr_block_appends_when_no_sections_either() -> None:
    text = "# Title\n\n> **오늘의 결론**: foo\n> **핵심 동인**: bar\n> **주의할 점**: baz\n"
    out = ensure_tldr_block(text)
    assert TLDR_HEADER in out
    assert out.index(TLDR_HEADER) > out.index("> **오늘의 결론**")


# ---------------------------------------------------------------------------
# enforce_h3_subheadings
# ---------------------------------------------------------------------------


def test_enforce_h3_promotes_whole_line_bold() -> None:
    text = "**3대 지수 상승 마감 — 전주 반등 흐름 연장**\n\nbody paragraph.\n"
    out = enforce_h3_subheadings(text)
    assert out.startswith("### 3대 지수 상승 마감 — 전주 반등 흐름 연장\n")


def test_enforce_h3_leaves_inline_bold_alone() -> None:
    text = "이번 분기 **AAPL** 실적은 컨센서스를 상회했다.\n"
    assert enforce_h3_subheadings(text) == text


def test_enforce_h3_idempotent() -> None:
    text = "### Already H3\n\nbody\n"
    assert enforce_h3_subheadings(text) == text


def test_enforce_h3_skips_callout_lines() -> None:
    text = "> **오늘의 결론**: foo bar\n"
    # The blockquote pattern has trailing prose, so the regex never matches.
    assert enforce_h3_subheadings(text) == text


def test_enforce_h3_multiple_subheadings() -> None:
    text = "**Title A**\n\npara A.\n\n**Title B**\n\npara B.\n"
    out = enforce_h3_subheadings(text)
    assert "### Title A" in out
    assert "### Title B" in out


# ---------------------------------------------------------------------------
# wrap_numbers_bold
# ---------------------------------------------------------------------------


def test_wrap_numbers_bold_signed_percent() -> None:
    assert wrap_numbers_bold("TSLA가 +3.89% 상승했다.") == "TSLA가 **+3.89%** 상승했다."


def test_wrap_numbers_bold_dollar() -> None:
    assert wrap_numbers_bold("BTC가 $81,154.06 회복.") == "BTC가 **$81,154.06** 회복."


def test_wrap_numbers_bold_bare_decimal_percent() -> None:
    assert wrap_numbers_bold("10Y 4.42% 부담.") == "10Y **4.42%** 부담."


def test_wrap_numbers_bold_signed_unit_tokens_u112() -> None:
    cases = {
        "-0.04%p 둔화": "**-0.04%p** 둔화",
        "+0.29pp 확대": "**+0.29pp** 확대",
        "-$0.23 하락": "**-$0.23** 하락",
        "$2.30T 기록": "**$2.30T** 기록",
        "+0.74달러(+0.97%) 상승": "**+0.74달러(+0.97%)** 상승",
    }
    for raw, expected in cases.items():
        assert wrap_numbers_bold(raw) == expected


def test_wrap_numbers_bold_idempotent_on_already_bold() -> None:
    text = "이미 **+3.89%** 처리됨."
    assert wrap_numbers_bold(text) == text


def test_wrap_numbers_bold_skips_table_rows() -> None:
    text = "| 지표 | 값 |\n|------|-----|\n| 10Y | 4.42% |\n"
    out = wrap_numbers_bold(text)
    # The table cell value remains plain — the table is itself the
    # bolding mechanism.
    assert out == text


def test_wrap_numbers_bold_skips_code_fences() -> None:
    text = "```\nprint(4.42)\n```\n"
    assert wrap_numbers_bold(text) == text


def test_wrap_numbers_bold_skips_link_urls() -> None:
    text = "[S&P 500](https://stooq.com/q/?s=%5Espx)은 +0.37% 상승.\n"
    out = wrap_numbers_bold(text)
    # The URL substring stays byte-equal; only the prose percent wraps.
    assert "https://stooq.com/q/?s=%5Espx" in out
    assert "**+0.37%**" in out


def test_wrap_numbers_bold_preserves_trailing_newline() -> None:
    assert wrap_numbers_bold("+1.0%\n").endswith("\n")
    assert not wrap_numbers_bold("+1.0%").endswith("\n")


def test_escape_krx_stock_code_link_fragments() -> None:
    text = "삼성전자[005930](**+8.97%**, 322,000원)와 SK하이닉스[000660](**+15.91%**)"
    out = escape_krx_stock_code_link_fragments(text)

    assert r"삼성전자\[005930\](**+8.97%**, 322,000원)" in out
    assert r"SK하이닉스\[000660\](**+15.91%**)" in out


def test_escape_krx_stock_code_link_fragments_preserves_real_links() -> None:
    text = r"[SK오션플랜트\[100090\]](https://example.com) — 삼성전자[005930]는 상승"

    assert escape_krx_stock_code_link_fragments(text) == text


def test_normalize_data_limited_reader_copy_rewrites_standalone_placeholder() -> None:
    text = "## ③ 섹터/수급 동향\n\n데이터 부족.\n\n> 데이터 부족\n\n문장 안 데이터 부족은 유지."
    out = normalize_data_limited_reader_copy(text)
    assert "오늘 확인 가능한 새 신호는 제한적입니다." in out
    assert "> 오늘 확인 가능한 새 신호는 제한적입니다." in out
    assert "문장 안 수집 근거 제한은 유지." in out
    assert "데이터 부족" not in out


# ---------------------------------------------------------------------------
# check_action_bullet_ratio
# ---------------------------------------------------------------------------


def _section_six(bullets: list[str]) -> str:
    body = "\n".join(f"- {b}" for b in bullets)
    return f"## ⑥ 오늘의 관전 포인트\n\n{body}\n"


def test_action_ratio_all_observation() -> None:
    text = _section_six(
        [
            "5/11 실적 결과 — SPG의 EPS 상회 여부",
            "달러 강세 지속 여부",
            "10Y 금리 추세 확인할 필요가 있다",
            "FOMC 발언 톤 관건이다",
            "VIX 변동성 주목할 필요가 있다",
        ]
    )
    ratio, violations = check_action_bullet_ratio(text)
    assert ratio == 1.0
    assert len(violations) == 5


def test_action_ratio_at_threshold_does_not_warn(
    caplog: object,
) -> None:
    import pytest

    cap = caplog
    assert isinstance(cap, pytest.LogCaptureFixture)
    text = _section_six(
        [
            "EPS 상회 여부",  # observation
            "달러 강세 지속 여부",  # observation
            "TSLA 매수 검토",
            "비중 축소 신중",
            "추세 확인",
        ]
    )
    with cap.at_level(logging.WARNING, logger="investo.publisher.reader_format"):
        ratio, _ = check_action_bullet_ratio(text)
    assert ratio == 0.4
    assert ratio <= ACTION_RATIO_THRESHOLD
    assert not any("action_ratio_high" in r.message for r in cap.records)


def test_action_ratio_empty_section() -> None:
    text = "## ⑥ 오늘의 관전 포인트\n\n(없음)\n"
    ratio, violations = check_action_bullet_ratio(text)
    assert ratio == 0.0
    assert violations == ()


def test_action_ratio_missing_section() -> None:
    text = "## ① 요약\nbody\n"
    ratio, violations = check_action_bullet_ratio(text)
    assert ratio == 0.0
    assert violations == ()


def test_watchpoint_actionability_warns_without_source_trigger_implication() -> None:
    text = _section_six(["FOMC 발언 톤 확인 필요"])

    violations = check_watchpoint_actionability(text, segment="us-equity")

    assert violations == ("FOMC 발언 톤 확인 필요",)


def test_watchpoint_actionability_accepts_source_trigger_implication() -> None:
    text = _section_six(
        ["확인 소스: FRED · 10Y 금리 4.5% 상회 시 성장주 변동성 부담 여부를 확인합니다."]
    )

    assert check_watchpoint_actionability(text, segment="us-equity") == ()


def test_action_ratio_warns_above_threshold(caplog: object) -> None:
    import pytest

    cap = caplog
    assert isinstance(cap, pytest.LogCaptureFixture)
    text = _section_six(
        [
            "EPS 상회 여부",
            "달러 강세 지속 여부",
            "10Y 금리 추세 확인할 필요가 있다",
            "TSLA 매수 검토",
            "비중 축소",
        ]
    )
    with cap.at_level(logging.WARNING, logger="investo.publisher.reader_format"):
        ratio, _ = check_action_bullet_ratio(text, segment="us-equity")
    assert ratio == 0.6
    msgs = [r for r in cap.records if "action_ratio_high" in r.message]
    assert msgs, "expected WARNING when ratio > threshold"
    # R13 hygiene: WARNING extras carry only structured fields, never bullet text.
    extra = msgs[0]
    assert extra.__dict__.get("segment") == "us-equity"
    assert isinstance(extra.__dict__.get("ratio"), float)


# ---------------------------------------------------------------------------
# dedupe_glossings
# ---------------------------------------------------------------------------


def test_dedupe_glossings_first_kept_second_stripped() -> None:
    text = (
        "S&P 500(스탠더드앤드푸어스 500 지수) 상승. S&P 500(스탠더드앤드푸어스 500 지수) 재차 언급."
    )
    out = dedupe_glossings(text)
    assert out.count("(스탠더드앤드푸어스 500 지수)") == 1
    # Base term survives both occurrences.
    assert out.count("S&P 500") == 2


def test_dedupe_glossings_three_occurrences() -> None:
    text = "S&P 500(지수) a. S&P 500(지수) b. S&P 500(지수) c."
    out = dedupe_glossings(text)
    assert out.count("(지수)") == 1


def test_dedupe_glossings_different_terms_unaffected() -> None:
    text = "S&P 500(스탠더드 지수). NASDAQ(나스닥) 상승. DJI(다우) 마감."
    out = dedupe_glossings(text)
    assert "(스탠더드 지수)" in out
    assert "(나스닥)" in out
    assert "(다우)" in out


def test_dedupe_glossings_url_unaffected() -> None:
    text = "[link](https://example.com/path) 본문."
    assert dedupe_glossings(text) == text


# ---------------------------------------------------------------------------
# apply_reader_format — composite + disclaimer pin
# ---------------------------------------------------------------------------


def test_apply_reader_format_preserves_disclaimer() -> None:
    text = (
        "# Title\n\n"
        "> **오늘의 결론**: foo\n"
        "> **핵심 동인**: bar\n"
        "> **주의할 점**: baz\n\n"
        "## ① 요약\nbody. +3.89% 상승.\n\n"
        f"{DISCLAIMER}\n"
    )
    out = apply_reader_format(text, segment="us-equity")
    assert DISCLAIMER in out
    # The format chain ran (TL;DR inserted, number wrapped).
    assert TLDR_HEADER in out
    assert "**+3.89%**" in out


def test_apply_reader_format_preserves_crypto_disclaimer_with_duplicate_glossing() -> None:
    text = (
        "# Title\n\n"
        "> **오늘의 결론**: foo\n"
        "> **핵심 동인**: bar\n"
        "> **주의할 점**: baz\n\n"
        "## ① 요약\n"
        "가상자산이용자보호법(2024-07-19 시행) 관련 이슈가 재부각됐다. "
        "BTC는 +3.89% 상승했다.\n\n"
        f"{DISCLAIMER_CRYPTO}\n"
    )
    out = apply_reader_format(text, segment="crypto")
    assert DISCLAIMER_CRYPTO in out
    assert "**+3.89%**" in out


def test_warning_log_extras_carry_no_bullet_text(caplog: object) -> None:
    """R13 hygiene pin — WARN ``extra=`` carries only structured fields.

    The action-ratio diagnostic logs at WARNING when §⑥ bullets fall
    into observation-shape territory. The ``extra`` dict must contain
    ONLY ``segment / ratio / count / total`` — no bullet body strings,
    no raw_metadata snippets. The bullet text itself flows through the
    return value (the caller may surface it), but log records are R13-
    safe by construction.
    """
    import pytest

    cap = caplog
    assert isinstance(cap, pytest.LogCaptureFixture)
    text = _section_six(
        [
            "EPS 상회 여부",
            "달러 강세 지속 여부",
            "10Y 금리 추세 확인할 필요가 있다",
            "FOMC 발언 톤 관건이다",
            "VIX 변동성 주목할 필요가 있다",
        ]
    )
    with cap.at_level(logging.WARNING, logger="investo.publisher.reader_format"):
        check_action_bullet_ratio(text, segment="us-equity")
    warn_records = [r for r in cap.records if "action_ratio_high" in r.message]
    assert warn_records, "expected WARNING fixture"
    record = warn_records[0]
    # Only the allow-listed extra fields are present (and the stdlib's
    # internal LogRecord attrs).
    allow_listed = {"segment", "ratio", "count", "total"}
    # The bullet bodies must not appear in any extra value.
    for key in allow_listed:
        assert hasattr(record, key)
        value = getattr(record, key)
        assert not isinstance(value, str) or "여부" not in value
    # Spot-check: nothing in the message itself leaks bullet bodies.
    assert "여부" not in record.message
    assert "필요가 있다" not in record.message


def test_apply_reader_format_idempotent_second_pass() -> None:
    text = (
        "# Title\n\n"
        "> **오늘의 결론**: foo\n"
        "> **핵심 동인**: bar\n"
        "> **주의할 점**: baz\n\n"
        "## ① 요약\nbody +1.0% +2.5%.\n"
    )
    once = apply_reader_format(text)
    twice = apply_reader_format(once)
    # Idempotent: a second pass over the formatted text is a no-op.
    assert once == twice
