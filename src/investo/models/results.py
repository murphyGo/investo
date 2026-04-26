"""Pipeline + notifier result types.

* :class:`PipelineStatus` — terminal status of one pipeline run.
* :class:`SendResult` — outcome of a single Telegram dispatch
  (``BriefingPublisher.send`` / ``OperatorAlerter.alert``). The notifier
  classes are non-raising for HTTP failures: they encode the outcome
  here so callers (orchestrator) can decide whether to mark the
  pipeline ``PARTIAL`` or ``FAILED``.
* :class:`FailureContext` — payload sent to the operator's 1:1 chat
  (FR-007, US-007). Never sent to the public channel.
* :class:`PipelineResult` — what ``orchestrator.run_pipeline`` returns.
  The entrypoint uses ``status`` to choose the exit code and whether to
  trigger an alert.

Reference: aidlc-docs/inception/application-design/component-methods.md

Note on JSON serialization: ``HttpUrl`` fields (e.g.
``PipelineResult.briefing_url``) round-trip through
``model_dump()`` as ``Url`` objects, which ``json.dumps`` cannot encode.
Callers that need a plain dict must use ``model_dump(mode="json")``.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from investo.models._validators import (
    ensure_tz_aware,
    reject_blank_preserve,
    reject_blank_strict,
)

FailureStage = Literal["collect", "generate", "publish", "notify_briefing"]

# Sanity ceiling for ``PipelineResult.duration_seconds`` — 24 hours.
# NFR-001 caps a real run at 10 minutes; anything above this is a bug
# (e.g. wall-clock arithmetic gone wrong) rather than a slow run.
_DURATION_CEILING_SECONDS = 24 * 60 * 60

# Cap for ``FailureContext.traceback_excerpt`` so a megabyte-sized stack
# doesn't blow past Telegram's 4096-unit limit when forwarded to the
# operator chat. Callers should excerpt before constructing the context.
_TRACEBACK_EXCERPT_MAX = 2000


class PipelineStatus(StrEnum):
    """Outcome of a single pipeline run."""

    SUCCESS = "success"
    """All stages completed; briefing is published and the public channel
    notification succeeded."""

    PARTIAL = "partial"
    """Briefing was published, but the public-channel notification
    failed. Operator alert is optional in this state."""

    FAILED = "failed"
    """The pipeline could not publish a briefing for ``target_date``.
    Operator must be alerted."""


class SendResult(BaseModel):
    """Outcome of a single Telegram dispatch.

    Frozen so callers can safely log or pass the result around without
    worrying about later mutation. The cross-field invariant enforces a
    consistent contract: ``ok=True`` implies ``error is None`` (and may
    or may not include a Telegram-assigned ``message_id``); ``ok=False``
    implies ``message_id is None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    error: str | None = None
    message_id: int | None = None

    @field_validator("error")
    @classmethod
    def _normalize_optional_error(cls, value: str | None) -> str | None:
        # Empty/whitespace ``error`` is meaningless next to ``ok=False``;
        # collapse to ``None`` so consumers only handle one absence form.
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _check_consistency(self) -> SendResult:
        if self.ok and self.error is not None:
            raise ValueError("error must be None when ok is True")
        if not self.ok and self.message_id is not None:
            raise ValueError("message_id must be None when ok is False")
        return self


class FailureContext(BaseModel):
    """Operator alert payload (FR-007, US-007)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: FailureStage
    error_type: str = Field(min_length=1)
    error_message: str = Field(min_length=1)
    traceback_excerpt: str | None = Field(default=None, max_length=_TRACEBACK_EXCERPT_MAX)
    occurred_at: datetime

    @field_validator("error_type")
    @classmethod
    def _strip_error_type(cls, value: str) -> str:
        # Error class name — surrounding whitespace is meaningless.
        return reject_blank_strict(value)

    @field_validator("error_message")
    @classmethod
    def _validate_error_message(cls, value: str) -> str:
        # Human-readable; may be multi-line. Preserve formatting but
        # reject whitespace-only.
        return reject_blank_preserve(value)

    @field_validator("traceback_excerpt")
    @classmethod
    def _normalize_optional_traceback(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("occurred_at")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        # Same reasoning as ``NormalizedItem.published_at``: cron-driven
        # date math is unforgiving of naive datetimes.
        return ensure_tz_aware(value)


class PipelineResult(BaseModel):
    """Top-level outcome of one ``orchestrator.run_pipeline`` call.

    Constructed once when the pipeline returns. Frozen so the entrypoint
    and any logger can safely share it.

    ``stages`` is intentionally a ``dict[str, str]`` rather than typed
    against :data:`FailureStage` because it is a **free-form diagnostic
    surface** — operators may want to record extra synthetic stages
    (``"overall"``, ``"date_resolution"``, etc.) without changing this
    type. Standard values are ``"ok"``, ``"skipped"``, or
    ``"failed: <reason>"``. Orchestrator is responsible for using
    consistent stage names; tests should pin them explicitly.

    ``briefing_url`` is :class:`HttpUrl` and serializes as a ``Url``
    object via ``model_dump()`` — use ``model_dump(mode="json")`` for
    JSON-safe output.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_date: date
    status: PipelineStatus
    stages: dict[str, str] = Field(default_factory=dict)
    duration_seconds: float = Field(ge=0, le=_DURATION_CEILING_SECONDS)
    briefing_url: HttpUrl | None = None
