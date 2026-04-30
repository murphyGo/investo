"""Property-based round-trip tests for the public ``investo.models``.

NFR-006 (Property-Based Testing extension, partial scope): every public
model must round-trip losslessly through ``model_dump_json()`` ↔
``model_validate_json()``.

We use :func:`hypothesis.strategies.builds` (or a ``@composite`` strategy
where cross-field validators apply) to generate valid model instances,
then assert that the JSON round-trip produces an equal instance.

Strategy choices favour predictability over coverage breadth:

* ASCII printable text for free-form fields, so length checks behave the
  same as in production with mixed-content input.
* Stripped ASCII text for fields whose validators strip the value — this
  way the constructed model already holds the canonical form and the
  round-trip equality is unambiguous.
* ``zoneinfo``-backed timezones (via ``hypothesis.strategies.timezones``)
  for tz-aware datetimes, exercising the validator's UTC-offset check
  against real-world tz objects.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from investo.models import (
    TELEGRAM_MESSAGE_LIMIT,
    Briefing,
    BriefingNotification,
    FailureContext,
    NormalizedItem,
    PipelineResult,
    PipelineStatus,
    SendResult,
)

PBT_SETTINGS = settings(max_examples=100, deadline=None)

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

# ASCII printable, non-blank after strip. Used wherever the contract is
# "non-whitespace string up to N chars".
_PRINTABLE_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    min_size=1,
    max_size=80,
).filter(lambda s: bool(s.strip()))

# Stripped variant — already canonical, so models that strip on validation
# don't transform the value and equality holds without normalization.
_STRIPPED_TEXT = _PRINTABLE_TEXT.map(str.strip).filter(lambda s: bool(s))

_TZ_DATETIMES = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.timezones(),
).filter(lambda d: d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None)

_DATES = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31),
)

_HTTP_URLS = st.integers(min_value=0, max_value=10**6).map(lambda n: f"https://example.com/r/{n}")

_CATEGORIES = st.sampled_from(("news", "price", "macro", "calendar", "earnings"))
_FAILURE_STAGES = st.sampled_from(
    ("collect", "generate", "publish", "notify_briefing", "orchestrator")
)
_PIPELINE_STATUSES = st.sampled_from(list(PipelineStatus))

# raw_metadata values: strict union rejects bool. ``st.integers()`` does
# not generate bool instances (hypothesis differentiates them), so this
# is safe. Bound floats to a JSON-safe range.
_METADATA_VALUE = st.one_of(
    st.text(max_size=30),
    st.integers(min_value=-(10**9), max_value=10**9),
    st.floats(
        allow_nan=False,
        allow_infinity=False,
        min_value=-1e9,
        max_value=1e9,
    ),
)
_METADATA_DICT = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=_METADATA_VALUE,
    max_size=5,
)

# UTF-16-safe summary text: ASCII => 1 char = 1 UTF-16 unit, so
# max_size=4096 keeps every example below the Telegram cap.
_TELEGRAM_SAFE_SUMMARY = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    min_size=1,
    max_size=TELEGRAM_MESSAGE_LIMIT,
).filter(lambda s: bool(s.strip()))

# Traceback excerpt is optional and capped at 2000.
_TRACEBACK_EXCERPT = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
        min_size=1,
        max_size=2000,
    ).filter(lambda s: bool(s.strip())),
)


# ---------------------------------------------------------------------------
# Round-trip property
# ---------------------------------------------------------------------------


def _assert_roundtrip(model: Any) -> None:
    json_str = model.model_dump_json()
    restored = type(model).model_validate_json(json_str)
    assert restored == model


# ---------------------------------------------------------------------------
# NormalizedItem
# ---------------------------------------------------------------------------


@given(
    st.builds(
        NormalizedItem,
        source_name=_STRIPPED_TEXT.filter(lambda s: 1 <= len(s) <= 100),
        category=_CATEGORIES,
        title=_STRIPPED_TEXT,
        summary=st.one_of(st.none(), _STRIPPED_TEXT),
        url=st.one_of(st.none(), _HTTP_URLS),
        published_at=_TZ_DATETIMES,
        raw_metadata=_METADATA_DICT,
    )
)
@PBT_SETTINGS
def test_normalized_item_roundtrip(item: NormalizedItem) -> None:
    _assert_roundtrip(item)


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------


@given(
    st.builds(
        Briefing,
        target_date=_DATES,
        market_summary=_PRINTABLE_TEXT,
        key_issues=_PRINTABLE_TEXT,
        sector_flow=_PRINTABLE_TEXT,
        indicators_events=_PRINTABLE_TEXT,
        notable_tickers=_PRINTABLE_TEXT,
        today_watch=_PRINTABLE_TEXT,
        disclaimer=_PRINTABLE_TEXT,
        rendered_markdown=_PRINTABLE_TEXT,
    )
)
@PBT_SETTINGS
def test_briefing_roundtrip(briefing: Briefing) -> None:
    _assert_roundtrip(briefing)


@given(
    st.builds(
        BriefingNotification,
        target_date=_DATES,
        summary_text=_TELEGRAM_SAFE_SUMMARY,
        site_url=_HTTP_URLS,
    )
)
@PBT_SETTINGS
def test_briefing_notification_roundtrip(notif: BriefingNotification) -> None:
    _assert_roundtrip(notif)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@st.composite
def _send_result_strategy(draw: st.DrawFn) -> SendResult:
    # Cross-field invariant requires a composite strategy:
    #  - ok=True ⇒ error must be None; message_id may be None or int
    #  - ok=False ⇒ message_id must be None; error may be None or str
    ok = draw(st.booleans())
    if ok:
        error: str | None = None
        message_id: int | None = draw(
            st.one_of(st.none(), st.integers(min_value=1, max_value=10**9))
        )
    else:
        error = draw(st.one_of(st.none(), _STRIPPED_TEXT))
        message_id = None
    return SendResult(ok=ok, error=error, message_id=message_id)


@given(_send_result_strategy())
@PBT_SETTINGS
def test_send_result_roundtrip(result: SendResult) -> None:
    _assert_roundtrip(result)


@given(
    st.builds(
        FailureContext,
        stage=_FAILURE_STAGES,
        error_type=_STRIPPED_TEXT,
        error_message=_PRINTABLE_TEXT,
        traceback_excerpt=_TRACEBACK_EXCERPT,
        occurred_at=_TZ_DATETIMES,
    )
)
@PBT_SETTINGS
def test_failure_context_roundtrip(ctx: FailureContext) -> None:
    _assert_roundtrip(ctx)


_STAGES_DICT = st.dictionaries(
    keys=_STRIPPED_TEXT,
    values=_STRIPPED_TEXT,
    max_size=5,
)


@given(
    st.builds(
        PipelineResult,
        target_date=_DATES,
        status=_PIPELINE_STATUSES,
        stages=_STAGES_DICT,
        duration_seconds=st.floats(
            min_value=0,
            max_value=24 * 60 * 60,
            allow_nan=False,
            allow_infinity=False,
        ),
        briefing_url=st.one_of(st.none(), _HTTP_URLS),
    )
)
@PBT_SETTINGS
def test_pipeline_result_roundtrip(result: PipelineResult) -> None:
    _assert_roundtrip(result)
