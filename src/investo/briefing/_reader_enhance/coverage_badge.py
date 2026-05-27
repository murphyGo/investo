"""Reader-facing coverage badge + failure-reason classification.

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). ``_render_coverage_badge`` /
``_classify_failure_reason`` keep their import path via re-export from
``briefing/pipeline.py``.
"""

from __future__ import annotations

import re
from typing import Final

from investo.briefing.segments import SEVERITY_READER_EXPLANATIONS, SegmentCoverage


def _render_coverage_badge(coverage: SegmentCoverage) -> str:
    """Render the reader-facing coverage badge.

    The badge is one or four blockquote lines:

    * line 1 — severity label + one-line reader explanation, item /
      source counts, missing categories. u54 — explanation is sourced
      from :data:`investo.briefing.segments.SEVERITY_READER_EXPLANATIONS`
      so the reader sees both the tier and "what it means".
    * line 2 (only when source outcomes are wired) — 5-tuple count
      split ``수집 대상 / 성공 / 0건 / 실패 / 본문 사용``.
    * line 3 (only when reason codes are present) — Korean labels for
      every reason code in deterministic order.
    * line 4 (only when source outcomes are present) — sanitized
      per-source breakdown (failed first, then zero) so readers can
      see *which* source caused the partial / limited / failed verdict.
      Failure reasons go through
      :func:`investo.models.sanitize_source_error_message` upstream and
      are guaranteed not to leak secret-shaped tokens.
    """
    explanation = SEVERITY_READER_EXPLANATIONS.get(coverage.status, "")
    head = (
        f"> **데이터 상태**: {coverage.status_label} — "
        f"수집 {coverage.item_count}건 / 소스 {coverage.source_count}개 / "
        f"누락: {coverage.missing_category_label}"
    )
    lines = [head]
    if explanation:
        # Surface short explanation on the same line so the reader does
        # not have to scan two lines for severity context.
        lines[0] = head + f" · {explanation}"
    if coverage.targeted_count > 0:
        body_used = (
            str(coverage.body_used_count)
            if coverage.body_used_count > 0 or coverage.succeeded_count == 0
            else "미집계"
        )
        lines.append(
            "> **소스 카운트**: "
            f"수집 대상 {coverage.targeted_count} / 성공 {coverage.succeeded_count} / "
            f"0건 {coverage.zero_count} / 실패 {coverage.failed_count} / "
            f"본문 사용 {body_used}"
        )
    tier_label = coverage.tier_mix_label
    if tier_label:
        lines.append(f"> **소스 등급 분포**: {tier_label}")
    if coverage.reason_codes:
        lines.append(f"> **상세 사유**: {', '.join(coverage.reason_labels)}")
    source_line = _render_source_outcome_line(coverage)
    if source_line:
        lines.append(f"> **소스별 상태**: {source_line}")
    return "\n".join(lines) + "\n"


# P1-3 — reader-facing failure classification.
#
# ``failure_reason`` on a ``SourceOutcome`` is the *sanitized* adapter
# error message (R13-scrubbed via ``sanitize_source_error_message``), but
# its surface form is raw English plumbing text such as
# ``source 'cnbc-top-news' failed: status 403 (terminal)`` or
# ``CONGRESS_API_KEY not set; ... adapter will not run``. Exposing that to
# readers is the bug. We classify the sanitized reason into a small set of
# Korean labels for the reader surface; the original sanitized reason is
# preserved upstream (it still lives on ``outcome.failure_reason`` and any
# trace/diagnostics consumer that reads the field directly).
_FAILURE_LABEL_ACCESS_DENIED: Final = "접근 제한"
_FAILURE_LABEL_TRANSIENT: Final = "일시적 수집 오류"
_FAILURE_LABEL_UNCONFIGURED: Final = "설정 미완료(미수집)"
_FAILURE_LABEL_FALLBACK: Final = "수집 불가"

# 4xx that read as access/permission denials (403/401/451/429-as-terminal,
# 404, 4xx-terminal). 5xx and network/timeout phrases read as transient.
_RE_HTTP_STATUS: Final = re.compile(r"status\s+(\d{3})")
_RE_NOT_SET: Final = re.compile(r"\bnot set\b", re.IGNORECASE)
_RE_TRANSIENT: Final = re.compile(
    r"\b(timeout|timed out|budget|network error|connection|connect|temporarily)\b",
    re.IGNORECASE,
)


def _classify_failure_reason(reason: str | None) -> str:
    """Map a sanitized adapter failure reason to a reader-facing label.

    Deterministic pure function. Order matters: an unconfigured-secret
    message (``... not set``) is classified before HTTP-status parsing so
    a stray ``status`` substring cannot mislabel a config gap.
    """
    if not reason:
        return _FAILURE_LABEL_FALLBACK
    if _RE_NOT_SET.search(reason):
        return _FAILURE_LABEL_UNCONFIGURED
    status_match = _RE_HTTP_STATUS.search(reason)
    if status_match is not None:
        status = int(status_match.group(1))
        if 400 <= status < 500:
            return _FAILURE_LABEL_ACCESS_DENIED
        if 500 <= status < 600:
            return _FAILURE_LABEL_TRANSIENT
    if _RE_TRANSIENT.search(reason):
        return _FAILURE_LABEL_TRANSIENT
    return _FAILURE_LABEL_FALLBACK


def _render_source_outcome_line(coverage: SegmentCoverage) -> str:
    """Compose the per-source status line for the reader surface.

    The composition is deterministic: failed sources first (with a
    Korean failure *category* label, never the raw plumbing string),
    then zero-item sources, then a concise count of healthy sources. We
    omit individual healthy source names to keep the line short — the
    reader-relevant signal is *what went wrong*, not the full healthy
    adapter list. The raw sanitized reason is preserved on the outcome
    for any trace/diagnostics consumer; only the reader line is
    re-labelled (P1-3).
    """
    failed = coverage.failed_source_outcomes
    zero = coverage.zero_source_outcomes
    ok = coverage.ok_source_outcomes
    if not failed and not zero and not ok:
        return ""
    parts: list[str] = []
    for outcome in failed:
        label = _classify_failure_reason(outcome.failure_reason)
        parts.append(f"{outcome.source_name} 실패 ({label})")
    for outcome in zero:
        parts.append(f"{outcome.source_name} 0건")
    if ok:
        parts.append(f"정상 {len(ok)}개")
    return ", ".join(parts)


__all__ = [
    "_classify_failure_reason",
    "_render_coverage_badge",
    "_render_source_outcome_line",
]
