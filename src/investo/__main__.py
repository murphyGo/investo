"""``python -m investo`` entrypoint (US-005, AC-007-1 ~ AC-007-5, AC-003-7).

Parses 5 environment variables, enforces the CLAUDE.md #5 chat-ID
disjointness invariant *before* constructing either dispatcher,
builds a shared ``httpx.AsyncClient`` for both Telegram dispatchers,
runs ``investo.orchestrator.run_pipeline``, maps the resulting public-content
completeness to an exit code, and (per AC-003-7) wraps
the whole thing so an unexpected programmer error still triggers a
best-effort operator alert + ``exit 1``.

Exit codes (u144 public-document finalization contract):

* complete public content (including notifier-only ``PARTIAL``) → ``0``
* zero public documents or ``FAILED`` → ``1``
* one/two-document content-partial publication → ``2``
* :class:`ConfigError` (env validation) → ``1``
* unexpected ``Exception`` → ``1``

Per Q9=A+ (env validation):

* If ``TELEGRAM_BOT_TOKEN`` AND ``TELEGRAM_OPERATOR_CHAT_ID`` are
  present, a single best-effort ``OperatorAlerter.alert`` is
  attempted on ``ConfigError`` even though one or more *other* env
  vars are missing — operator gets visibility into the boot failure
  via Telegram, not just the GHA email default.
* On unexpected ``Exception`` (per AC-003-7) the same best-effort
  alert path is used with ``stage="orchestrator"``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.models import FailureContext, PipelineResult, PipelineStatus
from investo.notifier import BriefingPublisher, OperatorAlerter
from investo.notifier._telegram import send_message as _telegram_send
from investo.orchestrator import boot_alert_dedup, weekly_ops_digest
from investo.orchestrator.date_resolution import validate_target_date_sanity
from investo.orchestrator.errors import ConfigError
from investo.orchestrator.pipeline import run_pipeline

# The 5 required env vars per AC-007-1 + ``component-methods.md`` C5.
# Order pinned: governs the order ``ConfigError.for_missing`` reports.
#
# u27 note: ``OPENAI_API_KEY`` is intentionally NOT in this tuple. It is
# tracked by :data:`investo._internal.redaction.SECRET_ENV_VARS` (so its
# value is redacted from any operator-facing surface when present), but
# it is *required* only when ``INVESTO_OPENAI_VISUALS=1`` opts in to
# the cost-bearing surface. See :func:`_validate_optional_env` for the
# opt-in branch.
_REQUIRED_ENV_VARS: Final[tuple[str, ...]] = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHANNEL_ID",
    "TELEGRAM_OPERATOR_CHAT_ID",
    "SITE_URL_BASE",
)

# u27: when this env var is ``"1"`` the OpenAI visual surface is enabled
# and ``OPENAI_API_KEY`` becomes required. Default (any other value or
# absent) keeps the surface disabled so the project's "free APIs only"
# rule (CLAUDE.md #4) holds at the code level — a missing key with the
# flag enabled is a hard ``ConfigError``, not a silent fallback.
_OPENAI_VISUALS_FLAG_VAR: Final[str] = "INVESTO_OPENAI_VISUALS"
_OPENAI_API_KEY_VAR: Final[str] = "OPENAI_API_KEY"

# Best-effort alert on ConfigError can only run when these two vars
# specifically are present (regardless of which others are missing).
# The token authenticates the bot; the chat_id is where the alert lands.
_ALERT_PREREQ_VARS: Final[tuple[str, ...]] = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OPERATOR_CHAT_ID",
)

_logger = logging.getLogger("investo")

# Optional override from the GHA ``workflow_dispatch`` input (u6
# ``daily-briefing.yml``). When present and non-empty, parsed via
# ``date.fromisoformat`` (ISO-8601 ``YYYY-MM-DD``) and passed to
# ``run_pipeline(target_date=...)`` — overrides
# ``resolve_target_date(now_utc)``. Used for backfills + US-public-
# holiday recoveries (per Q3=A: holiday days surface as empty-collect
# → operator alert; the operator re-triggers manually with
# ``target_date=last-trading-day``). Empty string or absent ⇒ default
# cron behavior (orchestrator resolves from ``now_utc``).
_TARGET_DATE_OVERRIDE_VAR: Final[str] = "INVESTO_TARGET_DATE"

# One-shot timeout for the boot-failure best-effort alert. Must be
# short — the pipeline has already failed and we're keeping the
# operator informed; if Telegram is also down, GHA's email default
# is the fallback.
_BOOT_ALERT_TIMEOUT_S: Final[float] = 5.0
_BOOT_ALERT_ATTEMPTS: Final[int] = 2
_GITHUB_STEP_SUMMARY_VAR: Final[str] = "GITHUB_STEP_SUMMARY"
_GITHUB_OUTPUT_VAR: Final[str] = "GITHUB_OUTPUT"


def _missing_env_vars() -> tuple[str, ...]:
    """Return the names of required env vars absent from the
    environment, in the order declared by ``_REQUIRED_ENV_VARS``.

    Treats ``""`` (empty string) as missing — GitHub Secrets cannot
    surface an unset secret as anything other than empty, so empty
    is functionally the same as absent for env-validation purposes.
    """
    return tuple(name for name in _REQUIRED_ENV_VARS if not os.environ.get(name))


def _validate_env() -> tuple[str, str, str, str, HttpUrl]:
    """Validate the 5 required env vars and return their parsed values.

    Returns a 5-tuple in the order
    ``(claude_oauth_token, bot_token, briefing_channel_id,
    operator_chat_id, site_url_base)``.

    Raises
    ------
    ConfigError
        Per AC-007-1 (one or more required vars missing) or
        AC-007-2 (briefing channel and operator chat IDs identical).
        ``ConfigError.missing_vars`` discriminates: empty tuple ⇒
        equality violation; non-empty ⇒ missing-var case.
    """
    missing = _missing_env_vars()
    if missing:
        raise ConfigError.for_missing(missing)

    # ``.strip()`` defangs a sneaky misconfiguration where the operator
    # pastes ``"@invest_brief"`` into one secret and ``" @invest_brief"``
    # (leading whitespace) into the other. The raw strings are unequal
    # but Telegram's API resolves both to the same chat — without the
    # strip the disjointness check would pass and the public channel
    # would receive operator alerts. We carry the stripped values
    # forward so downstream callers see the canonical form too.
    claude_oauth = os.environ["CLAUDE_CODE_OAUTH_TOKEN"].strip()
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    channel_id = os.environ["TELEGRAM_BRIEFING_CHANNEL_ID"].strip()
    operator_id = os.environ["TELEGRAM_OPERATOR_CHAT_ID"].strip()
    site_url_raw = os.environ["SITE_URL_BASE"].strip()

    # CLAUDE.md project rule #5 — disjointness enforced BEFORE either
    # dispatcher is constructed. Whitespace differences (one secret has
    # a leading/trailing space, the other doesn't) MUST NOT bypass
    # this — strip both sides above + compare here.
    if channel_id == operator_id:
        raise ConfigError.for_equal_chat_ids()

    try:
        site_url_base = TypeAdapter(HttpUrl).validate_python(site_url_raw)
    except ValidationError as exc:
        # Surfaces as ``ConfigError`` with ``SITE_URL_BASE`` named so
        # the operator alert text is actionable.
        raise ConfigError.for_bad_value(
            "SITE_URL_BASE",
            f"SITE_URL_BASE is not a valid HTTP URL: {site_url_raw!r}",
        ) from exc

    # u27 cost guard: if the OpenAI visual surface is opted-in via
    # ``INVESTO_OPENAI_VISUALS=1`` we MUST have an API key. Failing
    # closed here means an operator who flips the flag without
    # configuring the key gets a hard ``ConfigError`` at boot, not a
    # silent fallback to deterministic SVG cards (which would mask the
    # misconfiguration). When the flag is absent / any value other
    # than ``"1"``, the key is treated as optional (and OpenAI is
    # never called by the visual layer per ``visuals.openai_image``).
    if (
        os.environ.get(_OPENAI_VISUALS_FLAG_VAR, "").strip() == "1"
        and not os.environ.get(_OPENAI_API_KEY_VAR, "").strip()
    ):
        raise ConfigError.for_missing((_OPENAI_API_KEY_VAR,))

    return claude_oauth, bot_token, channel_id, operator_id, site_url_base


async def _attempt_boot_alert(exc: BaseException) -> None:
    """Best-effort operator alert during boot/top-level failure.

    Only fires when ``TELEGRAM_BOT_TOKEN`` AND ``TELEGRAM_OPERATOR_CHAT_ID``
    are both present (per AC-007-3). Construction errors and dispatch
    failures are silently swallowed — the underlying failure is
    already on its way to ``exit 1``; alert is the cherry on top, not
    a hard requirement.

    Note: we intentionally do NOT validate the chat-ID disjointness
    invariant here. The OperatorAlerter only knows the operator
    chat_id, never the public channel_id, so there's no risk of
    misroute even if the operator misconfigured them to be equal —
    the alert lands at the operator chat, full stop.
    """
    if any(not os.environ.get(name) for name in _ALERT_PREREQ_VARS):
        return

    # Truncate the exception text to fit ``FailureContext`` limits.
    # Use the same simple string fallback as the orchestrator's
    # ``_build_failure_context`` to keep the boot path independent
    # of the orchestrator's helpers (which import the four stage
    # runners and pull in u1-u4 even on a config-only failure path).
    error_message = redact_text(
        str(exc) or type(exc).__name__,
        policy=RedactionPolicy.STRICT,
    )
    error_type = type(exc).__name__

    # u31 Step 2 — bounded dedup. A stuck misconfiguration would
    # otherwise page the operator on every cron firing. The ledger is
    # off-by-default until the operator wires GHA caching for
    # ``archive/_meta/operator_state/`` (see runbook).
    now_utc = datetime.now(UTC)
    if not boot_alert_dedup.should_alert(
        error_type=error_type,
        error_message=error_message,
        now_utc=now_utc,
    ):
        _logger.info(
            "[boot_alert] suppressed duplicate (within dedup window): %s",
            error_type,
        )
        return

    try:
        ctx = FailureContext(
            stage="orchestrator",
            error_type=error_type,
            error_message=error_message,
            occurred_at=now_utc,
        )
    except (ValidationError, ValueError):
        return  # Construction failure ⇒ skip alert silently.

    delivered = False
    try:
        async with httpx.AsyncClient(timeout=_BOOT_ALERT_TIMEOUT_S) as client:
            alerter = OperatorAlerter(
                bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
                operator_chat_id=os.environ["TELEGRAM_OPERATOR_CHAT_ID"],
                http=client,
            )
            for _ in range(_BOOT_ALERT_ATTEMPTS):
                result = await alerter.alert(ctx)
                if result.ok:
                    delivered = True
                    break
    except Exception:
        # Best-effort — never let alerter exceptions mask the
        # underlying failure exit code.
        _logger.warning("[boot_alert] dispatch failed", exc_info=True)
    if delivered:
        boot_alert_dedup.record_alert(
            error_type=error_type,
            error_message=error_message,
            now_utc=now_utc,
        )


def _resolve_target_date_override() -> date | None:
    """Parse the optional ``INVESTO_TARGET_DATE`` env-var override.

    Returns
    -------
    date | None
        ``None`` if the var is absent or empty (default cron path —
        orchestrator resolves from ``now_utc``). A parsed
        :class:`datetime.date` if it's set to a valid ISO-8601
        ``YYYY-MM-DD`` string.

    Raises
    ------
    ConfigError
        If the var is set to a non-empty value that isn't a valid
        ISO-8601 date — fail loudly at the boundary so the operator's
        manual workflow_dispatch input doesn't silently roll back to
        the cron default.
    """
    raw = os.environ.get(_TARGET_DATE_OVERRIDE_VAR, "").strip()
    if not raw:
        return None
    try:
        return validate_target_date_sanity(date.fromisoformat(raw))
    except ValueError as exc:
        raise ConfigError.for_bad_value(
            _TARGET_DATE_OVERRIDE_VAR,
            f"{_TARGET_DATE_OVERRIDE_VAR} is not a valid supported ISO-8601 date "
            f"(YYYY-MM-DD): {raw!r}",
        ) from exc


def _redact_diagnostic_text(text: str) -> str:
    """Redact token/chat-id-like values before operator-visible diagnostics.

    Thin shim over :func:`investo._internal.redaction.redact_text` (u27
    chokepoint). The full secret env-var list lives in
    :data:`investo._internal.redaction.SECRET_ENV_VARS` so this site
    cannot drift behind a newly-added secret (resolves DEBT-036). The
    bot-token / chat-id regexes live there too (resolves DEBT-035).
    """
    return redact_text(text, policy=RedactionPolicy.STRICT)


def _pipeline_exit_code(result: PipelineResult) -> int:
    """Map typed public-content disposition to the process contract."""
    if result.content_completeness == "partial":
        return 2
    if result.status == PipelineStatus.FAILED or result.content_completeness == "none":
        return 1
    return 0


def _write_github_outputs(result: PipelineResult) -> None:
    """Append bounded machine outputs for the daily workflow controller."""
    output_path = os.environ.get(_GITHUB_OUTPUT_VAR, "").strip()
    if not output_path:
        return
    finalized_segments = sum(
        1 for outcome in result.segment_outcomes if outcome.state == "finalized"
    )
    published_segments = finalized_segments if result.publication_committed else 0
    lines = (
        f"pipeline_status={result.status}",
        f"content_completeness={result.content_completeness}",
        f"publication_committed={str(result.publication_committed).lower()}",
        "expected_segments=3",
        f"finalized_segments={finalized_segments}",
        f"published_segments={published_segments}",
    )
    try:
        with Path(output_path).open("a", encoding="utf-8") as output_file:
            output_file.write("\n".join(lines) + "\n")
    except OSError:
        _logger.warning("could not write GitHub outputs", exc_info=True)


def _write_github_step_summary(result: PipelineResult) -> None:
    """Write a concise GitHub Actions run summary when available.

    The file path is provided by GitHub Actions via ``GITHUB_STEP_SUMMARY``.
    Local runs simply skip this surface. Any write failure is swallowed so
    diagnostics never change the pipeline's exit-code contract.
    """
    summary_path = os.environ.get(_GITHUB_STEP_SUMMARY_VAR, "").strip()
    if not summary_path:
        return

    lines = [
        "## Investo Daily Briefing",
        "",
        f"- Status: `{result.status}`",
        f"- Target date: `{result.target_date.isoformat()}`",
        f"- Briefing URL: {result.briefing_url if result.briefing_url is not None else 'n/a'}",
        f"- Duration: `{result.duration_seconds:.2f}s`",
        "",
        "### Stages",
        "",
        "| Stage | Status | Seconds |",
        "|-------|--------|---------|",
    ]
    stage_names = list(result.stages)
    stage_names.extend(stage for stage in result.stage_timings if stage not in result.stages)
    for stage in stage_names:
        status = result.stages.get(stage, "timing")
        seconds = result.stage_timings.get(stage)
        seconds_text = "" if seconds is None else f"{seconds:.2f}"
        lines.append(
            "| "
            + " | ".join(
                (
                    _redact_diagnostic_text(stage),
                    _redact_diagnostic_text(status),
                    seconds_text,
                )
            )
            + " |"
        )
    lines.append("")

    timed_source_outcomes = [
        outcome for outcome in result.source_outcomes if outcome.elapsed_s is not None
    ]
    if timed_source_outcomes:
        lines.extend(
            [
                "### Slowest Sources",
                "",
                "| Source | Status | Seconds | Items |",
                "|--------|--------|---------|-------|",
            ]
        )
        for outcome in sorted(
            timed_source_outcomes,
            key=lambda source_outcome: source_outcome.elapsed_s or 0.0,
            reverse=True,
        )[:10]:
            assert outcome.elapsed_s is not None
            lines.append(
                "| "
                + " | ".join(
                    (
                        _redact_diagnostic_text(outcome.source_name),
                        outcome.status,
                        f"{outcome.elapsed_s:.2f}",
                        str(outcome.item_count),
                    )
                )
                + " |"
            )
        lines.append("")

    # u31 Step 1 — per-source outcome table so a failed adapter is
    # visible at a glance during morning triage. Sorted: failed first,
    # then zero-item, then ok (counts of healthy adapters can be skimmed
    # last). Failure reasons are already sanitized at construction time
    # via ``SourceOutcome.from_failure``; we re-route through the
    # diagnostic redactor as a defensive belt-and-braces step.
    if result.source_outcomes:
        ranked = sorted(
            result.source_outcomes,
            key=lambda outcome: (
                {"failed": 0, "zero": 1, "ok": 2}.get(outcome.status, 3),
                outcome.source_name,
            ),
        )
        lines.extend(
            [
                "### Sources",
                "",
                "| Source | Tier | Category | Status | Items | Reason |",
                "|--------|------|----------|--------|-------|--------|",
            ]
        )
        for outcome in ranked:
            reason = outcome.failure_reason or ""
            lines.append(
                "| "
                + " | ".join(
                    (
                        _redact_diagnostic_text(outcome.source_name),
                        outcome.tier,
                        _redact_diagnostic_text(outcome.category),
                        outcome.status,
                        str(outcome.item_count),
                        _redact_diagnostic_text(reason),
                    )
                )
                + " |"
            )
        lines.append("")

    try:
        Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(summary_path).open("a", encoding="utf-8") as fp:
            fp.write("\n".join(lines))
    except OSError:
        _logger.warning("failed to write GitHub step summary", exc_info=True)


async def _async_main() -> int:
    """Async core of :func:`main` — separated so ``main`` can synchronously
    drive ``asyncio.run`` and translate the final integer to the
    process exit code.
    """
    try:
        (
            _claude_oauth,  # consumed by the ``claude`` CLI itself, not by Python.
            bot_token,
            channel_id,
            operator_id,
            site_url_base,
        ) = _validate_env()
        # Optional override from u6's workflow_dispatch input. Parsed
        # alongside the required vars so a malformed value rejects
        # before any httpx client is constructed (matches the
        # ConfigError fail-fast pattern).
        target_date_override = _resolve_target_date_override()
    except ConfigError as exc:
        _logger.error("config error: %s", exc)
        await _attempt_boot_alert(exc)
        return 1

    try:
        # Single shared httpx.AsyncClient → one TLS handshake covers
        # both BriefingPublisher.send and any OperatorAlerter.alert
        # the pipeline issues internally. Production tip from u4
        # docstring (Step 7 L4 doc).
        # u31 Step 2 — operator-rehearsal mode reads the env once at boot
        # and threads the flag into both Telegram dispatchers. The
        # orchestrator's publish stage reads the same env per call so a
        # caller flipping the flag mid-run is honoured at every layer.
        dry_run = os.environ.get("INVESTO_DRY_RUN", "").strip() == "1"
        if dry_run:
            _logger.warning(
                "[boot] INVESTO_DRY_RUN=1 — git push and Telegram dispatch will be skipped"
            )
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            publisher = BriefingPublisher(
                bot_token=bot_token,
                channel_id=channel_id,
                http=http_client,
                dry_run=dry_run,
            )
            alerter = OperatorAlerter(
                bot_token=bot_token,
                operator_chat_id=operator_id,
                http=http_client,
                dry_run=dry_run,
            )

            result = await run_pipeline(
                target_date_override,
                publisher=publisher,
                alerter=alerter,
                site_url_base=site_url_base,
            )

            # u33 Step 4 — multi-channel watchlist webhook fan-out.
            # Best-effort: failure here never changes the run's exit
            # code. Skip on FAILED runs so a malformed publish doesn't
            # ping every webhook with a half-finished briefing.
            from investo.notifier.webhooks import (
                dispatch_watchlist_alert,
                load_webhook_endpoints,
            )

            endpoints = load_webhook_endpoints()
            if endpoints and result.status != PipelineStatus.FAILED and not dry_run:
                fan_text = f"Investo daily briefing — {result.target_date.isoformat()} published"
                if result.briefing_url is not None:
                    fan_text += f"\n{result.briefing_url}"
                try:
                    await dispatch_watchlist_alert(fan_text, http=http_client, endpoints=endpoints)
                except Exception:
                    _logger.warning("[webhooks] watchlist dispatch failed", exc_info=True)

            # u31 Step 4 — operator weekly digest. Opt-in via
            # ``INVESTO_WEEKLY_OPS_DIGEST=1`` (the workflow sets it on
            # the Saturday cron). Best-effort: a digest dispatch
            # failure must not change the run's exit code or mask the
            # primary briefing's status. Dry-run mode still skips the
            # network dispatch — operator rehearsals should not page
            # the operator with a synthetic digest.
            if weekly_ops_digest.is_opt_in():
                try:
                    digest_text = weekly_ops_digest.build_weekly_digest_text(result.target_date)
                    if dry_run:
                        _logger.info(
                            "[weekly_ops_digest] dry-run — would have sent: %s",
                            digest_text.splitlines()[0],
                        )
                    else:
                        await _telegram_send(
                            http_client,
                            bot_token=bot_token,
                            chat_id=operator_id,
                            text=digest_text,
                            parse_mode=None,
                        )
                except Exception:
                    _logger.warning("[weekly_ops_digest] dispatch failed", exc_info=True)

        _write_github_step_summary(result)
        _write_github_outputs(result)
        return _pipeline_exit_code(result)
    except Exception as exc:
        # Programmer errors (KeyError, AttributeError, ValidationError
        # constructing models, etc.) reach here. Log + best-effort
        # alert + exit 1.
        _logger.exception("unexpected pipeline error: %s", exc)
        await _attempt_boot_alert(exc)
        return 1


def main() -> int:
    """Synchronous module entrypoint.

    Configures stdlib logging, dispatches to :func:`_async_main`,
    returns the exit code. Idempotent w.r.t. the running event loop —
    ``asyncio.run`` creates a fresh loop on each invocation.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(_async_main())


if __name__ == "__main__":
    sys.exit(main())
