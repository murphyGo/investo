"""Integration PoC — u1 sources → u2 briefing pipeline (FD L9).

End-to-end test that exercises the real flow:

1. u1's public ``aggregator.fetch_all`` entry point runs two
   controlled adapters: one wraps ``FomcRssAdapter`` against the
   recorded FOMC RSS fixture, while the other raises
   ``SourceFetchError``. This pins registry-driven fan-out and
   failure isolation without network access.
2. ``pipeline.generate_briefing(target_date, items)`` runs with a
   stubbed ``call_claude_code`` that returns canned valid Stage 1 +
   Stage 2 outputs. The stub bypasses the ``FakeClaudeRunner`` SHA-256
   fixture path (which is exercised in ``test_fake_claude_runner.py``);
   here we focus on the cross-unit wiring + final ``Briefing``
   assembly + AC-4.4 / AC-7.5 contract.
3. Assertions cover the Briefing model surface and the leak/script
   guards.

Pins NFR ACs:
- **AC-4.4** — ``DISCLAIMER`` substring appears in
  ``briefing.rendered_markdown``.
- **AC-7.5** — ``"<script>"`` (case-insensitive) does NOT appear in
  the rendered markdown.

The plan's "INVESTO_LIVE_LLM=1 fixture bootstrap" path is documented
under "Future fixture-based replay" below; CI uses the pure-stub mode
implemented here.

## Future fixture-based replay (FakeClaudeRunner SHA-256 path)

A future iteration may replace the ``call_claude_code`` stub with a
``FakeClaudeRunner`` reading from ``tests/fixtures/llm/<sha256>.json``.
That replay path is more faithful to production (exercises the
subprocess-list-form invocation + stdout parsing) but requires
recording the fixtures via ``INVESTO_LIVE_LLM=1`` against a real
``claude`` CLI. Documented in ``aidlc-docs/construction/u2-briefing/code/summary.md``
when it lands; current CI does not need it.

The test patches ``aggregator.list_sources`` instead of touching the
global registry so it stays isolated from unit-level registry tests.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

from investo.briefing import pipeline
from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.errors import SubprocessOutcome
from investo.models import Briefing, Category, NormalizedItem
from investo.sources import aggregator
from investo.sources._window import FetchWindow
from investo.sources.fomc_rss import FomcRssAdapter
from investo.sources.protocol import SourceFetchError
from tests._helpers.briefing_pipeline import valid_classification_stdout, valid_stage2_markdown

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FOMC_FIXTURE = (
    Path(__file__).parent.parent / "unit" / "sources" / "fixtures" / "api" / "fomc-rss" / "feed.xml"
)
_TARGET_DATE = date(2026, 4, 25)


class _FomcFixtureAdapter:
    name: ClassVar[str] = "fomc-rss-fixture"
    category: ClassVar[Category] = "calendar"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        body = _FOMC_FIXTURE.read_bytes()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/xml"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as fixture_client:
            return await FomcRssAdapter().fetch(fixture_client, window)


class _FailingFixtureAdapter:
    name: ClassVar[str] = "synthetic-failing-source"
    category: ClassVar[Category] = "news"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        raise SourceFetchError(
            self.name,
            "synthetic integration failure",
            transient=False,
        )


# ---------------------------------------------------------------------------
# Integration PoC — full pipeline AC-4.4 + AC-7.5
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_poc_against_recorded_fomc_fixture(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FD L9 PoC — u1's FOMC fixture flows through u2 to a valid
    ``Briefing``. Pins AC-4.4 (DISCLAIMER in rendered markdown) and
    AC-7.5 (no ``<script>``).
    """
    monkeypatch.setattr(pipeline, "_BACKOFF_SCHEDULE", (0.0, 0.0, 0.0))
    monkeypatch.setattr(
        aggregator,
        "list_sources",
        lambda: [_FomcFixtureAdapter(), _FailingFixtureAdapter()],
    )

    # Step 1: drive u1's public aggregator entry point. One adapter
    # yields the recorded FOMC fixture; one fails and must be isolated.
    with caplog.at_level(logging.WARNING, logger="investo.sources.aggregator"):
        items = await aggregator.fetch_all(_TARGET_DATE)

    assert len(items) == 2, "FOMC fixture should yield 2 items in window"
    assert all(item.source_name == "fomc-rss" for item in items)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].source_name == "synthetic-failing-source"
    assert warnings[0].category == "news"
    assert warnings[0].transient is False

    # Step 2: stub Claude calls with canned valid Stage 1 + Stage 2 outputs.
    stdouts = [
        valid_classification_stdout(item_count=len(items)),
        valid_stage2_markdown(),
    ]
    call_index = 0

    async def fake_call(
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
            elapsed_s=10.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(pipeline, "call_claude_code", fake_call)

    # Step 3: run the full pipeline.
    briefing = await pipeline.generate_briefing(_TARGET_DATE, items)

    # Step 4: assertions.
    assert isinstance(briefing, Briefing), "result must be a Briefing"
    assert briefing.target_date == _TARGET_DATE
    assert briefing.disclaimer == DISCLAIMER

    # AC-4.4: DISCLAIMER substring in rendered markdown.
    assert DISCLAIMER in briefing.rendered_markdown, (
        "AC-4.4: rendered_markdown must contain the canonical DISCLAIMER block"
    )

    # AC-7.5: case-insensitive ``<script>`` substring forbidden.
    assert "<script>" not in briefing.rendered_markdown.lower(), (
        "AC-7.5: rendered_markdown must not contain a <script> tag"
    )

    # Diagnostic: every Briefing section is non-blank (model-validated,
    # but pinned here for explicit failure messages).
    assert briefing.market_summary.strip()
    assert briefing.key_issues.strip()
    assert briefing.sector_flow.strip()
    assert briefing.indicators_events.strip()
    assert briefing.notable_tickers.strip()
    assert briefing.today_watch.strip()

    # Pipeline made exactly one Stage 1 + one Stage 2 call (no retries
    # on the happy path).
    assert call_index == 2
