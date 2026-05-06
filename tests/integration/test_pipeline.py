"""End-to-end integration test for u5 orchestrator.

Wires all four existing mock patterns simultaneously so ``run_pipeline``
runs the entire u1 → u2 → u3 → u4 sequence under a single test
without any real network / subprocess / git activity:

* **u1 sources**: a fake ``fetch`` callable returns a pre-built
  ``list[NormalizedItem]`` (we don't drive the FomcRssAdapter against
  ``MockTransport`` here — that path is exercised by
  ``test_briefing_pipeline_poc.py``; for u5 we only care that the
  orchestrator's ``_stage_collect`` plumbing surfaces the items).
* **u2 briefing**: monkeypatches ``investo.briefing.pipeline.call_claude_code``
  with a stub that returns canned Stage 1 + Stage 2 stdouts, mirroring
  the pattern in ``test_briefing_pipeline_poc.py``. Drives the real
  ``generate_briefing`` (which is what u5's ``_default_generate_briefing``
  adapter calls), so the round-trip exercises u2's prompt-generation +
  parsing + disclaimer-append + leak-guard layers.
* **u3 publisher**: redirects ``ARCHIVE_ROOT`` to ``tmp_path`` and
  injects a fake ``GitRunner`` so ``git add/commit/push`` are
  recorded but never executed.
* **u4 notifier**: a single shared ``httpx.AsyncClient`` backed by
  ``MockTransport`` handles the public-channel ``sendMessage`` call.

Pins AC-006-1 (4 mocks wired simultaneously) + AC-006-3 (DI seams; no
internal monkeypatching beyond the well-defined boundaries above) +
the public-surface importability check.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.briefing import pipeline as briefing_pipeline
from investo.briefing.errors import SubprocessOutcome
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import NormalizedItem, PipelineResult, PipelineStatus
from investo.notifier import BriefingPublisher, OperatorAlerter
from investo.orchestrator import (
    resolve_target_date,
    run_pipeline,
)
from investo.publisher.paths import archive_path

_TARGET = date(2026, 4, 27)  # Monday
_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_PUBLIC_CHANNEL = "@example_public_channel"
_OPERATOR_CHAT = "12345678"
_SITE_BASE: HttpUrl = TypeAdapter(HttpUrl).validate_python("https://example.github.io/investo")


# ---------------------------------------------------------------------------
# Mock builders — one per work unit
# ---------------------------------------------------------------------------


def _fake_items(n: int = 2) -> list[NormalizedItem]:
    return [
        NormalizedItem(
            source_name="fomc-rss",
            category="calendar",
            title=f"FOMC item {i}",
            published_at=datetime(2026, 4, 25, 14, 0, tzinfo=UTC),
        )
        for i in range(1, n + 1)
    ]


async def _fake_fetch_returning(
    items: list[NormalizedItem],
) -> list[NormalizedItem]:
    """Stand-in for u1's ``fetch_all`` — yields the given items."""

    return items


def _make_fetch_callable(items: list[NormalizedItem]) -> object:
    async def _fetch(target_date: date) -> list[NormalizedItem]:
        return items

    return _fetch


def _stage1_classification_json(item_count: int) -> str:
    """Stage 1 stdout — every item assigned to section 4 (calendar)."""
    return json.dumps(
        {
            "assignments": {str(i): 4 for i in range(1, item_count + 1)},
            "unassigned": [],
        }
    )


def _stage2_markdown() -> str:
    """Stage 2 stdout exceeding the 200-char floor with FOMC prose."""
    parts = [
        "## ① 요약\n오늘은 FOMC 일정이 시장 관심사입니다. 금리 결정과 SEP 발표를 주목하세요.",
        "## ② 전일 핵심 이슈\n전일에는 FOMC 관련 이슈가 핵심이었습니다. 발표 대기 중입니다.",
        "## ③ 섹터/수급 동향\n금융 섹터와 채권 시장에 자금 흐름이 집중되었습니다.",
        "## ④ 지표·이벤트\nFOMC Statement 와 Press Conference 가 예정되어 있습니다.",
        "## ⑤ 주요 종목\n금리 민감 종목 흐름 — JPM, BAC, GS 등에 주목합니다.",
        "## ⑥ 오늘의 관전 포인트\nFed 의 점도표 변화와 의장의 발언 톤을 확인하세요.",
    ]
    return "\n\n".join(parts) + "\n"


@pytest.fixture
def stub_u2_claude(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Replace u2's ``call_claude_code`` with canned segmented stubs.

    Yields the list of prompts u2 receives — assertions can check that
    the orchestrator triggered exactly the expected number of LLM calls.
    """
    captured_prompts: list[str] = []
    # Production run_pipeline now generates three market segments in fixed
    # order. The default fake FOMC items route only to us-equity, so
    # domestic-equity and crypto receive empty item sets.
    stdouts = [
        _stage1_classification_json(0),
        _stage2_markdown(),
        _stage1_classification_json(2),
        _stage2_markdown(),
        _stage1_classification_json(0),
        _stage2_markdown(),
    ]
    call_index = 0

    async def _fake_call(
        prompt: str,
        *,
        timeout_s: float = 120.0,
        runner: object | None = None,
    ) -> SubprocessOutcome:
        nonlocal call_index
        captured_prompts.append(prompt)
        outcome = SubprocessOutcome(
            stdout=stdouts[call_index],
            stderr="",
            returncode=0,
            elapsed_s=1.0,
        )
        call_index += 1
        return outcome

    monkeypatch.setattr(briefing_pipeline, "call_claude_code", _fake_call)
    # Disable u2's retry backoff so the integration test runs in milliseconds.
    monkeypatch.setattr(briefing_pipeline, "_BACKOFF_SCHEDULE", (0.0, 0.0, 0.0))
    yield captured_prompts


class _SuccessfulGitRunner:
    """Fake ``GitRunner`` Protocol — every git step succeeds (rc=0)."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def _telegram_send_handler(*, captured: list[dict[str, object]] | None = None) -> object:
    """``httpx.MockTransport`` handler for Telegram ``sendMessage``."""

    def _handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    return _handler


@pytest.fixture
def isolated_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect u3's ARCHIVE_ROOT and disable git backoff."""
    root = tmp_path / "archive"
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", root)
    monkeypatch.setattr("investo.publisher.git_ops.time.sleep", lambda _s: None)
    return root


# ---------------------------------------------------------------------------
# AC-006-1 — happy path with all 4 mocks wired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_end_to_end_success(
    isolated_archive: Path,
    stub_u2_claude: list[str],
) -> None:
    """All 4 stages succeed → SUCCESS, file on disk, telegram dispatched,
    no operator alert. Exercises the real u2 ``generate_briefing`` against
    a canned LLM stub + real u3 ``write_briefing`` to disk + fake git
    runner + httpx.MockTransport for u4 telegram.
    """
    items = _fake_items(2)
    git = _SuccessfulGitRunner()
    public_sends: list[dict[str, object]] = []
    operator_alerts: list[dict[str, object]] = []

    def _telegram_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        chat_id = body.get("chat_id")
        if chat_id == _PUBLIC_CHANNEL:
            public_sends.append(body)
        elif chat_id == _OPERATOR_CHAT:
            operator_alerts.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    transport = httpx.MockTransport(_telegram_handler)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as http_client:
        publisher = BriefingPublisher(
            bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=http_client
        )
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN,
            operator_chat_id=_OPERATOR_CHAT,
            http=http_client,
        )
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_make_fetch_callable(items),
            git_runner=git,
        )

    # Pipeline status.
    assert isinstance(result, PipelineResult)
    assert result.status == PipelineStatus.SUCCESS
    assert result.target_date == _TARGET
    assert result.briefing_url is not None
    assert "archive/domestic-equity/2026/04/2026-04-27" in str(result.briefing_url)
    # All 4 stages recorded as ok.
    assert result.stages == {
        "collect": "ok",
        "generate": "ok",
        "publish": "ok",
        "notify_briefing": "ok",
    }
    # All 4 stage timings present and non-negative.
    assert set(result.stage_timings) == {
        "collect",
        "generate",
        "publish",
        "notify_briefing",
    }
    # u2 was called exactly six times: three segments x Stage 1 + Stage 2, no retries.
    assert len(stub_u2_claude) == 6

    # u3: all three segment files land under the segmented archive paths.
    expected_path = archive_path(_TARGET, segment=DOMESTIC_EQUITY)
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        assert archive_path(_TARGET, segment=segment).exists()
    rendered = expected_path.read_text(encoding="utf-8")
    # Disclaimer landed in the rendered markdown (NFR-004).
    assert "투자 자문" in rendered or "면책" in rendered

    # u3: git lifecycle (add, commit, push) ran exactly once.
    git_steps = [c[1] for c in git.calls]
    assert git_steps == ["add", "commit", "push"]

    # u4 public channel: dispatched once with the per-day URL footer.
    assert len(public_sends) == 1
    assert "2026-04-27" in str(public_sends[0]["text"])
    assert str(result.briefing_url) in str(public_sends[0]["text"])
    # NO operator alert on the happy path (CLAUDE.md #5 isolation pin).
    assert operator_alerts == []


# ---------------------------------------------------------------------------
# AC-003-2 — empty collect routes through the full alert path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_end_to_end_empty_collect_alerts_operator(
    isolated_archive: Path,
    stub_u2_claude: list[str],
) -> None:
    """Aggregator returns 0 items → FAILED + 1 operator alert lands at
    operator chat (NEVER at public channel — CLAUDE.md #5 dispatch
    isolation invariant).
    """
    git = _SuccessfulGitRunner()
    public_sends: list[dict[str, object]] = []
    operator_alerts: list[dict[str, object]] = []

    def _telegram_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        chat_id = body.get("chat_id")
        if chat_id == _PUBLIC_CHANNEL:
            public_sends.append(body)
        elif chat_id == _OPERATOR_CHAT:
            operator_alerts.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    transport = httpx.MockTransport(_telegram_handler)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as http_client:
        publisher = BriefingPublisher(
            bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=http_client
        )
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN,
            operator_chat_id=_OPERATOR_CHAT,
            http=http_client,
        )
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_make_fetch_callable([]),  # empty
            git_runner=git,
        )

    assert result.status == PipelineStatus.FAILED
    assert result.briefing_url is None
    assert result.stages["collect"] == "failed: empty"
    # Operator chat got the alert; public channel did NOT.
    assert len(operator_alerts) == 1
    assert public_sends == []
    # u2 + u3 + u4 publish-channel never invoked.
    assert stub_u2_claude == []
    assert git.calls == []


# ---------------------------------------------------------------------------
# AC-003-6 + AC-003-8 — notify failure → PARTIAL with no alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_end_to_end_notify_failure_yields_partial(
    isolated_archive: Path,
    stub_u2_claude: list[str],
) -> None:
    """Telegram public-channel ``sendMessage`` returns ``ok: false`` →
    PARTIAL with NO operator alert (PARTIAL is the visibility signal).
    File still written + committed (publish succeeded).
    """
    items = _fake_items(2)
    git = _SuccessfulGitRunner()
    public_sends: list[dict[str, object]] = []
    operator_alerts: list[dict[str, object]] = []

    def _telegram_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        chat_id = body.get("chat_id")
        if chat_id == _PUBLIC_CHANNEL:
            public_sends.append(body)
            return httpx.Response(200, json={"ok": False, "description": "rate limited"})
        if chat_id == _OPERATOR_CHAT:
            operator_alerts.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    transport = httpx.MockTransport(_telegram_handler)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as http_client:
        publisher = BriefingPublisher(
            bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=http_client
        )
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN,
            operator_chat_id=_OPERATOR_CHAT,
            http=http_client,
        )
        result = await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_make_fetch_callable(items),
            git_runner=git,
        )

    assert result.status == PipelineStatus.PARTIAL
    assert result.briefing_url is not None
    # NO operator alert.
    assert operator_alerts == []
    # Public-channel attempt was made (and failed).
    assert len(public_sends) == 1
    # u3 committed the segmented briefings.
    assert archive_path(_TARGET, segment=DOMESTIC_EQUITY).exists()
    assert archive_path(_TARGET, segment=US_EQUITY).exists()
    assert archive_path(_TARGET, segment=CRYPTO).exists()
    assert "push" in [c[1] for c in git.calls]


# ---------------------------------------------------------------------------
# CLAUDE.md #5 — channel isolation invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_chat_id_separation_on_failure_path(
    isolated_archive: Path,
    stub_u2_claude: list[str],
) -> None:
    """When the pipeline routes a failure through the operator alerter,
    the alert MUST land at ``operator_chat_id`` and NEVER at the
    public ``channel_id``. This is the cross-class isolation invariant
    (CLAUDE.md #5) at the integration boundary.
    """
    git = _SuccessfulGitRunner()
    chat_ids_seen: list[str] = []

    def _telegram_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        chat_ids_seen.append(str(body["chat_id"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    transport = httpx.MockTransport(_telegram_handler)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as http_client:
        publisher = BriefingPublisher(
            bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=http_client
        )
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN,
            operator_chat_id=_OPERATOR_CHAT,
            http=http_client,
        )
        await run_pipeline(
            _TARGET,
            publisher=publisher,
            alerter=alerter,
            site_url_base=_SITE_BASE,
            fetch=_make_fetch_callable([]),  # forces empty-collect → alert
            git_runner=git,
        )

    # Exactly one Telegram call, and it landed at the operator chat —
    # NOT at the public channel.
    assert chat_ids_seen == [_OPERATOR_CHAT]
    assert _PUBLIC_CHANNEL not in chat_ids_seen


# ---------------------------------------------------------------------------
# Public-surface importability
# ---------------------------------------------------------------------------


def test_orchestrator_public_surface_is_importable() -> None:
    """All re-exported names resolve from ``investo.orchestrator``.

    Mirrors u3's Step 7.3 / u4's Step 6.3 consolidation precedent —
    public surface is pinned at the integration boundary.
    """
    from investo import orchestrator as orch_pkg

    assert hasattr(orch_pkg, "run_pipeline")
    assert hasattr(orch_pkg, "resolve_target_date")
    assert hasattr(orch_pkg, "ConfigError")
    assert hasattr(orch_pkg, "EmptyCollectError")
    # Internal stage runners NOT re-exported.
    assert not hasattr(orch_pkg, "_stage_collect")
    assert not hasattr(orch_pkg, "_stage_generate")
    assert not hasattr(orch_pkg, "_stage_publish")
    assert not hasattr(orch_pkg, "_stage_notify_briefing")
    # ``main`` lives in ``__main__`` — NOT re-exported here.
    assert not hasattr(orch_pkg, "main")
    # Sanity: each name is in __all__.
    assert set(orch_pkg.__all__) == {
        "ConfigError",
        "EmptyCollectError",
        "resolve_target_date",
        "run_pipeline",
    }


def test_orchestrator_imports_have_correct_types() -> None:
    """Imported re-exports have the expected types — guards against an
    accidental wildcard re-export pulling in something unintended.
    """
    from investo import orchestrator as orch_pkg

    assert callable(orch_pkg.run_pipeline)
    assert callable(orch_pkg.resolve_target_date)
    assert issubclass(orch_pkg.ConfigError, RuntimeError)
    assert issubclass(orch_pkg.EmptyCollectError, RuntimeError)


# ---------------------------------------------------------------------------
# Smoke: resolve_target_date round-trip via the public surface
# ---------------------------------------------------------------------------


def test_resolve_target_date_via_public_surface_returns_weekday() -> None:
    """Quick smoke test that the re-exported ``resolve_target_date``
    works the same as the module-level import from
    ``date_resolution``. Catches accidental shadowing in __init__.
    """
    target = resolve_target_date(datetime(2026, 4, 28, 22, 0, tzinfo=UTC))
    assert target == date(2026, 4, 28)  # KST 4-29 Wed → previous trading = Tue 4-28
    assert target.weekday() < 5
