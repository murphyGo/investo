"""Tests for the u22 reader-facing coverage badge in segmented briefings.

The badge ships in three forms:

* status only — when no reasons or outcomes are available (legacy
  unsegmented runs / coverage built without source outcomes).
* status + reasons — when reason codes are present.
* status + reasons + per-source line — when source outcomes flow in
  from :func:`investo.sources.collect_sources` via the orchestrator.

These tests pin the rendering shape and the sanitization guarantee
(no secret-shaped tokens leak through to the public markdown).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from investo.briefing import pipeline
from investo.briefing._core import orchestration  # u83: call_claude_code seam moved here
from investo.briefing.errors import SubprocessOutcome
from investo.briefing.segments import US_EQUITY, build_segment_coverage
from investo.models import NormalizedItem, SourceOutcome
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown

_TARGET = date(2026, 5, 7)


def _item(idx: int, *, source_name: str | None = None) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name or f"src-{idx}",
        category="news",
        title=f"item-{idx}",
        published_at=datetime(2026, 5, 7, 12, idx, tzinfo=UTC),
    )


def test_coverage_badge_renders_only_status_line_when_no_reasons() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item(1, source_name="yfinance-price"),
            _item(2, source_name="yahoo-finance-news"),
            _item(3, source_name="fomc-rss"),
        ],
    )
    # Force a normal-status sample by ensuring required categories are present.
    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="S&P 500",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="yahoo-finance-news",
            category="news",
            title="AAPL",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="fomc-rss",
            category="calendar",
            title="FOMC",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
    ]
    coverage = build_segment_coverage(US_EQUITY, items)
    badge = pipeline._render_coverage_badge(coverage)
    assert "> **데이터 상태**: 정상" in badge
    assert "상세 사유" not in badge
    assert "소스별 상태" not in badge


def test_coverage_badge_renders_reason_labels_when_partial() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            NormalizedItem(
                source_name="yfinance-price",
                category="price",
                title="S&P 500",
                published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
            ),
        ],
    )
    badge = pipeline._render_coverage_badge(coverage)
    assert "> **데이터 상태**: 부분" in badge
    assert "> **상세 사유**:" in badge
    assert "뉴스 카테고리 누락" in badge
    assert "최소 수집 기준 미달" in badge


def test_coverage_badge_renders_per_source_status_with_failed_first() -> None:
    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="S&P 500",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="yahoo-finance-news",
            category="news",
            title="AAPL",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="fomc-rss",
            category="calendar",
            title="FOMC",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
    ]
    outcomes = [
        SourceOutcome.from_failure(
            "fred-macro",
            "macro",
            message="connection reset",
            transient=True,
        ),
        SourceOutcome.zero("nasdaq-earnings-calendar", "earnings"),
        SourceOutcome.ok("yfinance-price", "price", item_count=1),
        SourceOutcome.ok("yahoo-finance-news", "news", item_count=1),
        SourceOutcome.ok("fomc-rss", "calendar", item_count=1),
    ]
    coverage = build_segment_coverage(US_EQUITY, items, source_outcomes=outcomes)

    badge = pipeline._render_coverage_badge(coverage)

    assert "> **소스별 상태**:" in badge
    # Failed entries lead.
    failed_idx = badge.index("fred-macro 실패")
    zero_idx = badge.index("nasdaq-earnings-calendar 0건")
    ok_idx = badge.index("정상 3개")
    assert failed_idx < zero_idx < ok_idx
    # P1-3 — the reader surface carries a Korean classification label, not
    # the raw English plumbing string. "connection reset" classifies to the
    # transient bucket.
    assert "fred-macro 실패 (일시적 수집 오류)" in badge
    assert "connection reset" not in badge


def test_coverage_badge_does_not_leak_secret_in_failure_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R13 — sanitization is the single chokepoint; bot tokens, env-var
    values and query strings never reach the rendered badge.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "supersecret-bot-token-xyz")
    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="S&P 500",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
    ]
    outcomes = [
        SourceOutcome.from_failure(
            "yfinance-price",
            "price",
            message=(
                "GET https://example.com?api_key=ABCDEFG&fmt=json failed; "
                "bot supersecret-bot-token-xyz; chat 1234567890"
            ),
            transient=True,
        ),
    ]
    coverage = build_segment_coverage(US_EQUITY, items, source_outcomes=outcomes)

    badge = pipeline._render_coverage_badge(coverage)

    assert "supersecret-bot-token-xyz" not in badge
    assert "api_key=ABCDEFG" not in badge
    assert "1234567890" not in badge
    # P1-3 — the reader line shows a classification label, not the
    # sanitized reason text (which still routes through the R13 chokepoint
    # at ``from_failure`` and is preserved on the outcome). This reason has
    # no status / not-set / transient keyword, so it falls back.
    assert "yfinance-price 실패 (수집 불가)" in badge


@pytest.mark.asyncio
async def test_generate_briefing_threads_source_outcomes_into_badge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end sanity check that ``generate_briefing`` honors the
    new ``source_outcomes=`` parameter and renders the per-source line.
    """
    stdouts = [
        valid_classification_stdout(item_count=2),
        valid_stage2_markdown(),
    ]
    call_index = 0

    async def fake_call_claude_code(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        nonlocal call_index
        outcome = SubprocessOutcome(
            stdout=stdouts[call_index],
            stderr="",
            returncode=0,
            elapsed_s=1.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(orchestration, "call_claude_code", fake_call_claude_code)

    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="S&P 500",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="yahoo-finance-news",
            category="news",
            title="AAPL",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
    ]
    outcomes = [
        SourceOutcome.from_failure(
            "fred-macro",
            "macro",
            message="schema mismatch",
            transient=False,
        ),
        # An outcome for a source not mapped to US_EQUITY — should be
        # filtered out in the rendered badge by ``segment_source_outcomes``.
        SourceOutcome.zero("coingecko-price", "price"),
    ]

    briefing = await pipeline.generate_briefing(
        _TARGET,
        items,
        segment=US_EQUITY,
        source_outcomes=outcomes,
    )

    assert "> **소스별 상태**: fred-macro 실패 (수집 불가)" in briefing.rendered_markdown
    # P1-3 — raw English plumbing string never reaches the reader.
    assert "schema mismatch" not in briefing.rendered_markdown
    assert "coingecko-price" not in briefing.rendered_markdown


@pytest.mark.asyncio
async def test_generate_briefing_passes_leak_guard_with_secret_shaped_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end safety check — a failure_reason that *originally*
    contained a secret-shaped token still flows through the pipeline
    without tripping ``leak_guard_scan`` (which would raise
    ``BriefingGenerationError(stage="post_validation")``). The
    sanitizer must remove the bot-token and chat-id shapes before
    they hit the rendered markdown.
    """
    stdouts = [
        valid_classification_stdout(item_count=2),
        valid_stage2_markdown(),
    ]
    call_index = 0

    async def fake_call_claude_code(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        nonlocal call_index
        outcome = SubprocessOutcome(
            stdout=stdouts[call_index],
            stderr="",
            returncode=0,
            elapsed_s=1.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(orchestration, "call_claude_code", fake_call_claude_code)

    items = [
        NormalizedItem(
            source_name="yfinance-price",
            category="price",
            title="S&P 500",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
        NormalizedItem(
            source_name="yahoo-finance-news",
            category="news",
            title="AAPL",
            published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        ),
    ]
    outcomes = [
        SourceOutcome.from_failure(
            "yfinance-price",
            "price",
            message=(
                "401 from https://example.com?api_key=secretkey&fmt=json "
                "with bot 1111111111:abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"
            ),
            transient=True,
        ),
    ]

    briefing = await pipeline.generate_briefing(
        _TARGET,
        items,
        segment=US_EQUITY,
        source_outcomes=outcomes,
    )

    assert "1111111111:" not in briefing.rendered_markdown
    assert "api_key=secretkey" not in briefing.rendered_markdown
    # P1-3 — the reader line carries a classification label (no status /
    # not-set / transient keyword survives the redaction → fallback). The
    # secret-shaped substrings are gone (sanitize at ``from_failure``), and
    # the leak guard passed (no exception raised above).
    assert "yfinance-price 실패 (수집 불가)" in briefing.rendered_markdown
