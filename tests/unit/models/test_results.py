"""Unit tests for ``investo.models.results``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from investo.models.results import (
    FailureContext,
    FailureStage,
    PipelineResult,
    PipelineStatus,
    SendResult,
)

_FAILURE_STAGES: tuple[FailureStage, ...] = (
    "collect",
    "generate",
    "publish",
    "notify_briefing",
)

_DURATION_CEILING = 24 * 60 * 60


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _failure_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "stage": "collect",
        "error_type": "ConnectionError",
        "error_message": "API timeout after 30s",
        "occurred_at": _now_utc(),
    }
    base.update(overrides)
    return base


def _pipeline_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "target_date": date(2026, 4, 27),
        "status": PipelineStatus.SUCCESS,
        "duration_seconds": 1.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# PipelineStatus — StrEnum
# ---------------------------------------------------------------------------


def test_pipeline_status_values() -> None:
    assert PipelineStatus.SUCCESS == "success"
    assert PipelineStatus.PARTIAL == "partial"
    assert PipelineStatus.FAILED == "failed"


def test_pipeline_status_string_coercion() -> None:
    pr = PipelineResult(**_pipeline_kwargs(status="partial"))
    assert pr.status == PipelineStatus.PARTIAL
    assert isinstance(pr.status, PipelineStatus)


def test_pipeline_status_invalid_value_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineResult(**_pipeline_kwargs(status="weird"))


# ---------------------------------------------------------------------------
# SendResult — cross-field invariants (M1 fix from review)
# ---------------------------------------------------------------------------


def test_send_result_ok_bare() -> None:
    r = SendResult(ok=True)
    assert r.ok is True
    assert r.error is None
    assert r.message_id is None


def test_send_result_ok_with_message_id() -> None:
    r = SendResult(ok=True, message_id=42)
    assert r.message_id == 42


def test_send_result_ok_with_error_rejected() -> None:
    with pytest.raises(ValidationError, match="error must be None when ok is True"):
        SendResult(ok=True, error="something")


def test_send_result_failure_with_error() -> None:
    r = SendResult(ok=False, error="connection reset")
    assert r.ok is False
    assert r.error == "connection reset"


def test_send_result_failure_with_message_id_rejected() -> None:
    with pytest.raises(ValidationError, match="message_id must be None when ok is False"):
        SendResult(ok=False, message_id=42)


def test_send_result_empty_error_normalized_to_none() -> None:
    # Empty/whitespace error normalized to None *before* the cross-field
    # validator runs — so this is not an "ok=True with error" violation.
    r = SendResult(ok=True, error="")
    assert r.error is None
    r = SendResult(ok=True, error="   ")
    assert r.error is None


def test_send_result_frozen() -> None:
    r = SendResult(ok=True)
    with pytest.raises(ValidationError):
        r.ok = False  # type: ignore[misc]


def test_send_result_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SendResult(ok=True, extra="x")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# FailureContext
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", _FAILURE_STAGES)
def test_failure_context_each_stage_accepted(stage: str) -> None:
    fc = FailureContext(**_failure_kwargs(stage=stage))
    assert fc.stage == stage


def test_failure_context_invalid_stage_rejected() -> None:
    with pytest.raises(ValidationError):
        FailureContext(**_failure_kwargs(stage="bogus"))


def test_failure_context_blank_error_type_rejected() -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        FailureContext(**_failure_kwargs(error_type="   "))


def test_failure_context_blank_error_message_rejected() -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        FailureContext(**_failure_kwargs(error_message="\t\n"))


def test_failure_context_error_type_stripped() -> None:
    fc = FailureContext(**_failure_kwargs(error_type="  TimeoutError  "))
    assert fc.error_type == "TimeoutError"


def test_failure_context_error_message_preserves_whitespace() -> None:
    # Multi-line stack-trace-like message — preserve the formatting.
    fc = FailureContext(**_failure_kwargs(error_message="line1\n  line2\n"))
    assert fc.error_message == "line1\n  line2\n"


def test_failure_context_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        FailureContext(**_failure_kwargs(occurred_at=datetime(2026, 4, 27, 9)))


def test_failure_context_traceback_at_limit_accepted() -> None:
    fc = FailureContext(**_failure_kwargs(traceback_excerpt="x" * 2000))
    assert fc.traceback_excerpt is not None
    assert len(fc.traceback_excerpt) == 2000


def test_failure_context_traceback_over_limit_rejected() -> None:
    with pytest.raises(ValidationError):
        FailureContext(**_failure_kwargs(traceback_excerpt="x" * 2001))


def test_failure_context_traceback_empty_normalized() -> None:
    fc = FailureContext(**_failure_kwargs(traceback_excerpt=""))
    assert fc.traceback_excerpt is None
    fc = FailureContext(**_failure_kwargs(traceback_excerpt="   "))
    assert fc.traceback_excerpt is None


def test_failure_context_frozen() -> None:
    fc = FailureContext(**_failure_kwargs())
    with pytest.raises(ValidationError):
        fc.error_message = "different"  # type: ignore[misc]


def test_failure_context_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        FailureContext(**_failure_kwargs(extra="x"))


# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------


def test_pipeline_result_minimal() -> None:
    pr = PipelineResult(**_pipeline_kwargs())
    assert pr.status == PipelineStatus.SUCCESS
    assert pr.stages == {}
    assert pr.briefing_url is None


def test_pipeline_result_full() -> None:
    pr = PipelineResult(
        **_pipeline_kwargs(
            status=PipelineStatus.PARTIAL,
            stages={
                "collect": "ok",
                "generate": "ok",
                "publish": "ok",
                "notify_briefing": "failed: timeout",
            },
            duration_seconds=42.5,
            briefing_url="https://example.com/2026-04-27",
        )
    )
    assert pr.status == PipelineStatus.PARTIAL
    assert pr.stages["notify_briefing"] == "failed: timeout"
    assert str(pr.briefing_url) == "https://example.com/2026-04-27"


def test_pipeline_result_negative_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineResult(**_pipeline_kwargs(duration_seconds=-1.0))


def test_pipeline_result_duration_at_ceiling_accepted() -> None:
    PipelineResult(**_pipeline_kwargs(duration_seconds=_DURATION_CEILING))


def test_pipeline_result_duration_over_ceiling_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineResult(**_pipeline_kwargs(duration_seconds=_DURATION_CEILING + 1))


def test_pipeline_result_extreme_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineResult(**_pipeline_kwargs(duration_seconds=1e18))


def test_pipeline_result_frozen() -> None:
    pr = PipelineResult(**_pipeline_kwargs())
    with pytest.raises(ValidationError):
        pr.status = PipelineStatus.FAILED  # type: ignore[misc]


def test_pipeline_result_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineResult(**_pipeline_kwargs(extra="x"))
