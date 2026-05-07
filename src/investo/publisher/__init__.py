"""Publisher (u3) — static-site archive writer + git commit/push (US-003, US-006).

Public surface for u5 orchestrator and u3-internal callers:

* :func:`write_briefing` — verify disclaimer (NFR-004), then write
  ``rendered_markdown`` atomically to ``archive/YYYY/MM/YYYY-MM-DD.md``
  or, for u7 segmented runs, ``archive/{segment}/YYYY/MM/YYYY-MM-DD.md``
  (FR-006). Returns the written path.
* :func:`commit_and_push` — ``git add → git commit → git push origin
  HEAD`` with whole-pipeline retry. Default ``retries=2`` allows up
  to 3 attempts.
* :func:`verify_disclaimer` — pure boolean predicate (the runtime
  safety net for NFR-004). Exposed for callers that need the
  predicate without the write side effect.
* :func:`archive_path`, :data:`ARCHIVE_ROOT` — FR-006 path arithmetic.
* :class:`PublisherError` and three subclasses — failure-mode taxonomy
  for the orchestrator's stage guard.

Failure-mode contract (used by u5 orchestrator's stage guard):

* ``PublisherDisclaimerError`` raised by ``write_briefing`` → block
  publish, alert operator with NFR-004 context.
* ``PublisherIOError`` raised by ``write_briefing`` → block publish,
  alert with disk-level diagnostic from ``cause``.
* ``PublisherGitError`` raised by ``commit_and_push`` → publish
  succeeded locally but the push failed; alert with last-stderr
  context. The orchestrator may retry the push manually or roll the
  commit forward in the next run (uncommitted file is harmless).

The orchestrator's typical flow::

    path = write_briefing(briefing, target_date)
    commit_and_push(
        message=f"publish {target_date.isoformat()}",
        files=[path],
    )

Module boundary recap:

* u3 imports from :mod:`investo.models` (Briefing) and
  :mod:`investo.briefing.disclaimer` (DISCLAIMER constant + the
  ``append_disclaimer`` helper available defensively).
* u3 does NOT import any other u2 symbol — ``pipeline``,
  ``claude_code``, ``prompts``, ``errors`` (briefing-side),
  ``leak_guard``, ``RetryBudget``, ``BriefingGenerationError`` —
  those are u5 orchestrator concerns.

Reference:
    aidlc-docs/construction/u2-briefing/code/summary.md "Pre-flight
        notes for u3 publisher"
    aidlc-docs/construction/plans/u3-publisher-code-generation-plan.md
"""

from investo.publisher.errors import (
    PublisherDisclaimerError,
    PublisherError,
    PublisherGitError,
    PublisherIOError,
)
from investo.publisher.git_ops import GitRunner, commit_and_push
from investo.publisher.paths import ARCHIVE_ROOT, archive_path
from investo.publisher.verifier import verify_disclaimer
from investo.publisher.weekly_digest import (
    WEEKLY_ARCHIVE_ROOT,
    WEEKLY_INDEX_PATH,
    publish_weekly_digest,
    update_weekly_index,
    weekly_digest_opt_in,
    weekly_path,
)
from investo.publisher.writer import write_briefing

__all__ = [
    "ARCHIVE_ROOT",
    "WEEKLY_ARCHIVE_ROOT",
    "WEEKLY_INDEX_PATH",
    "GitRunner",
    "PublisherDisclaimerError",
    "PublisherError",
    "PublisherGitError",
    "PublisherIOError",
    "archive_path",
    "commit_and_push",
    "publish_weekly_digest",
    "update_weekly_index",
    "verify_disclaimer",
    "weekly_digest_opt_in",
    "weekly_path",
    "write_briefing",
]
