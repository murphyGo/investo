"""Unit tests for ``investo.publisher.watchpoint_matrix`` (u72).

Coverage map (per u72 plan Steps 1/3/4/6 + AC-72.1..72.5):

* Schema / degradation (Step 1): closed confidence label set, max visible
  rows, ``데이터부족`` fallback rules pinned.
* Renderer (Step 3): structured bullet → 6-column matrix; generic
  ``확인 / 점검`` bullet → explicit ``데이터부족`` row (delegates to the u64
  source/trigger/implication contract); idempotent; disclaimer preserved.
* Evidence inputs (Step 4): verified numeric anchor → 높음; source-backed
  but no figure → 보통; carryover-only → 낮음; coverage-limited → 데이터부족.
* Compliance (AC-72.4): rendered matrix carries no buy/sell/target wording.
"""

from __future__ import annotations

from investo.briefing.disclaimer import DISCLAIMER
from investo.publisher.compliance_language import scan_compliance
from investo.publisher.reader_format import check_watchpoint_actionability
from investo.publisher.watchpoint_matrix import (
    CONFIDENCE_LABELS,
    DATA_LIMITED_CONFIDENCE,
    DATA_LIMITED_NOTE,
    MATRIX_COLUMNS,
    MAX_VISIBLE_ROWS,
    WatchpointRow,
    build_watchpoint_rows,
    render_matrix_table,
    render_watchpoint_matrix,
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
    assert CONFIDENCE_LABELS == frozenset({"높음", "보통", "낮음", "데이터부족"})  # noqa: SIM300
    assert DATA_LIMITED_CONFIDENCE == "데이터부족"


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


def test_data_limited_row_omits_triggers() -> None:
    row = WatchpointRow.data_limited("신호")
    assert row.confidence == DATA_LIMITED_CONFIDENCE
    assert row.bullish_trigger == "데이터부족"
    assert row.bearish_trigger == "데이터부족"


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
    assert rows[0].bullish_trigger == "데이터부족"


def test_structured_bullet_populates_all_columns() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    row = rows[0]
    assert row.signal
    assert "상회" in row.bullish_trigger
    assert "이탈" in row.bearish_trigger
    assert row.implication != "—"


# ---------------------------------------------------------------------------
# Renderer / document-level
# ---------------------------------------------------------------------------


def test_render_matrix_table_has_header_and_alignment() -> None:
    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    table = render_matrix_table(rows)
    lines = table.splitlines()
    assert lines[0] == "| " + " | ".join(MATRIX_COLUMNS) + " |"
    assert lines[1] == "| " + " | ".join(["---"] * len(MATRIX_COLUMNS)) + " |"
    assert len(lines) == 3


def test_render_replaces_section_six_with_matrix() -> None:
    text = _section_six([_STRUCTURED_NUMERIC, _GENERIC])
    out = render_watchpoint_matrix(text, segment="us-equity")
    assert "| " + " | ".join(MATRIX_COLUMNS) + " |" in out
    # § ① untouched.
    assert "## ① 요약\n본문" in out
    # Generic bullet degraded to a 데이터부족 row in the table.
    assert "데이터부족" in out


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
    table = render_matrix_table(build_watchpoint_rows([bullet]))
    # No raw bullet pipe should appear inside a data cell beyond the grid pipes.
    for line in table.splitlines()[2:]:
        assert line.count("|") == len(MATRIX_COLUMNS) + 1


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
    # No multi-row 데이터부족 table — the note replaces the body entirely.
    assert out.count("데이터부족") == 0


def test_structured_bullet_produces_populated_row_ac87_5() -> None:
    """AC-87.5 — a fully-structured source+trigger+implication bullet yields
    a populated row: 현재 non-dash, ≥1 trigger non-데이터부족, confidence ∈
    {높음,보통,낮음}. (Proves the matrix populates — closes DEBT-074.)
    """
    text = _section_six([_STRUCTURED_NUMERIC])
    out = render_watchpoint_matrix(text, segment="us-equity")
    assert _HEADER_LINE in out
    assert DATA_LIMITED_NOTE not in out

    rows = build_watchpoint_rows([_STRUCTURED_NUMERIC])
    row = rows[0]
    assert row.current != "—"
    assert (
        row.bullish_trigger != DATA_LIMITED_CONFIDENCE
        or row.bearish_trigger != DATA_LIMITED_CONFIDENCE
    )
    assert row.confidence in {"높음", "보통", "낮음"}


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
