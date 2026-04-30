"""Orchestrator-internal exception types.

* :class:`ConfigError` — raised by :func:`investo.orchestrator.main`
  when environment-variable validation fails. Caught by ``main()``;
  the entrypoint then attempts a single best-effort operator alert
  (per u5 NFR Requirements AC-007-3) when ``TELEGRAM_BOT_TOKEN`` and
  ``TELEGRAM_OPERATOR_CHAT_ID`` happen to be present despite the
  failure, then logs to stderr and exits 1.

  Two failure modes are encoded:

  - **Missing required env var(s)** — ``missing_vars`` is the tuple of
    variable names absent from ``os.environ`` (per AC-007-1, the five
    required vars are ``CLAUDE_CODE_OAUTH_TOKEN``,
    ``TELEGRAM_BOT_TOKEN``, ``TELEGRAM_BRIEFING_CHANNEL_ID``,
    ``TELEGRAM_OPERATOR_CHAT_ID``, ``SITE_URL_BASE``).
  - **Chat-ID disjointness violation** (CLAUDE.md #5, AC-007-2) —
    ``missing_vars`` is an empty tuple; the message states the
    invariant. The orchestrator MUST reject equal IDs *before*
    constructing either dispatcher class so the two channels are
    never wired together by accident.

  Both factory classmethods produce a human-readable message suitable
  for direct interpolation into the operator-alert text and stderr
  log line — no further formatting in the caller is required.

* :class:`EmptyCollectError` — internal sentinel raised by
  :func:`investo.orchestrator.pipeline._stage_collect` when the
  source aggregator returned zero items (per AC-003-2). Routed by
  ``run_pipeline`` to ``OperatorAlerter.alert`` with ``stage="collect"``
  and surfaces ``status=FAILED``. Not exposed as a public symbol —
  it's an internal control-flow signal between ``_stage_collect`` and
  ``run_pipeline``.

Both classes inherit from :class:`RuntimeError`, not :class:`Exception`,
because they signal **runtime preconditions** (env wiring, source
availability) rather than programmer logic errors. ``main()``'s
top-level handler catches ``Exception`` separately to route truly
unexpected programmer errors (``KeyError``, ``AttributeError``, etc.)
to the same best-effort alert path with ``stage="orchestrator"`` per
AC-003-7.
"""

from __future__ import annotations


class ConfigError(RuntimeError):
    """Environment-variable validation failure (AC-007-1, AC-007-2)."""

    def __init__(self, message: str, *, missing_vars: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        # Stored as a tuple (immutable) so callers can safely log or
        # forward without worrying about later mutation. Empty tuple
        # signals the chat-ID-equality variant.
        self.missing_vars: tuple[str, ...] = missing_vars

    @classmethod
    def for_missing(cls, missing_vars: tuple[str, ...]) -> ConfigError:
        """Construct from one or more absent env var names.

        ``missing_vars`` MUST be non-empty — the chat-ID equality case
        has its own factory (:meth:`for_equal_chat_ids`) so the two
        failure modes are never conflated by accident.
        """
        if not missing_vars:
            raise ValueError(
                "ConfigError.for_missing requires at least one var name; "
                "use ConfigError.for_equal_chat_ids() for the chat-ID-"
                "equality case"
            )
        joined = ", ".join(missing_vars)
        message = f"missing required environment variable(s): {joined}"
        return cls(message, missing_vars=missing_vars)

    @classmethod
    def for_equal_chat_ids(cls) -> ConfigError:
        """Construct from CLAUDE.md #5 disjointness violation."""
        message = (
            "TELEGRAM_BRIEFING_CHANNEL_ID and TELEGRAM_OPERATOR_CHAT_ID "
            "must be disjoint (CLAUDE.md project rule #5): the public "
            "briefing channel and the operator 1:1 chat MUST NOT share "
            "the same chat_id"
        )
        return cls(message, missing_vars=())


class EmptyCollectError(RuntimeError):
    """Internal sentinel — every source returned zero items (AC-003-2).

    Raised by ``_stage_collect``; caught by ``run_pipeline`` and
    converted into a ``FailureContext(stage="collect", ...)`` for the
    operator alert. NOT part of the orchestrator's public surface.
    """
