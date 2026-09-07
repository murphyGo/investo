# Session Log: 2026-09-08 — u153 main integration

## Approval and isolation

The user requested `커밋·푸시·메인 통합` after the u153 cross-check. A subsequent
question, `운영 반영은 뭘 해야함?`, requested an explanation, not authorization to
regenerate archives or send public notifications.

- Source commit: `65a1246ca7ebaf0d79bba726365083422be6f1ba` on
  `codex/briefing-review-20260906`; 40 scoped files include reviewed u151–u154
  planning, u153 implementation/tests and construction/cross-check evidence.
- Integration base: fetched `origin/main`
  `6b76fabe6fcade673af001b875548957eb5ffd63`, which already includes u150's
  completed implementation and production qualification.
- Integration workspace: `/private/tmp/investo-u153-main-integration.mko8wQ`,
  branch `codex/u153-main-integration-20260907`.
- The original root remains on `985b7e4063a8037bf46f7e6f87426a816cf715f7` with
  its existing `.claude/settings.local.json`, `.claude/worktrees/` and
  `archive/_meta/fact_snapshots.jsonl` changes untouched. No root merge/reset/clean.

The isolated-main integration procedure preserved the dirty root, used current
remote main, retained both append-only audit histories and requires validation
of the combined implementation before push. Original historical cross-check
results remain tied to their recorded pre-u150 baseline.

## Integration decisions and regression repair

1. Preserve u150's shaped link scanner, inline-code/escape/table protections,
   owned-region disposition and residual-code handling. Layer u153's explicit
   continuation ownership onto that scanner; retain simultaneous strict summary
   residue and link findings without reviving legacy link false positives.
2. Preserve u150's link-first summary repair guard. Reuse u153 sentence bounding
   after canonical summary repair and before notification DTO construction.
   The u150 post-target-repair wrapper delegates to the same owned traversal;
   caution's existing link guard and default behavior remain unchanged.
3. Update u153's pre-u150 finalizer expectations to the actual integrated policy:
   recoverable href ellipses are `repaired` and then sentence-bounded; residual
   unmatched syntax is `replaced` in its owned region. Both keep usable siblings.
   Tests retain original inputs and verify typed outcomes plus exact summary text.
4. Combined repeat-finalization tests exposed normal blank separators being
   removed by cosmetic repair after navigation insertion, changing sealed bytes
   and SHA on the second pass. Preserve pre-existing blank/whitespace lines and
   their LF/CRLF endings; still remove nonempty trace lines emptied by repair.
   Two explicit newline regressions and all existing repeated-finalizer
   assertions cover the fix. No new text budget, disposition, scanner or layout order.

## Validation

- Focused combined u150/u153 gate: **709 passed in 19.08s**, seed `15320260907`.
- Ruff check/format: **577 Python files** pass; source mypy: **254 files** pass.
- Lock check, no-Anthropic-SDK, no-paid-API, curated-assets, image-store,
  strict MkDocs and Material theme/rendered-pair guards pass.
- Full repository gate: **4,950 passed in 494.85s (8m14s)**, with no failures,
  skips or xfails; this run started after the final production/test correction.
- Source/scoped unit mypy and all quality guards pass on the combined code.
  Exact remote merge SHA and its post-push quality-run result are verified in
  the final integration handoff, not inferred from the earlier source branch.
- Initial integration gate failures were addressed, not waived: 25 repeat-byte
  failures and two obsolete pre-u150 TL;DR expectations. Subsequent literal
  assertions distinguish repaired targets from required-region replacements.

No archive, site source, workflow, dependency lock or TECH-DEBT change is part
of this integration. Local documentation build outputs and test reports are
validation artifacts only, not staged publication data.

## Operational follow-up, separate from integration

Pushing this source/docs/test change to `main` activates the updated code for
the next existing daily workflow execution; it does not regenerate old Markdown.
The `quality.yml` workflow runs on main pushes. `pages.yml` has rendered-content
path filters, so this source-only change does not itself require a Pages dispatch.

To close production verification, observe the next scheduled `daily-briefing`
(KST weekdays 07:00, Saturday 09:00), or obtain separate approval for a manual
`workflow_dispatch` with an appropriate `target_date`. Manual replay can update
public archives and send Telegram again; it is not a dry run.

For that run, verify the checked-out code includes this integration, then inspect
generation, finalization, public commit, Telegram result, pipeline exit and
chained Pages deployment separately. Check final domestic/US/crypto owned
summaries and notification text for the 90-character cap, complete continuation,
canonical fallback and absence of incident tails. Distinguish source shortages,
usable partial bundles and numeric degradation from presentation correctness.
The workflow dispatches Pages only when publication is committed, including
content-partial publications; a green generation step alone is not closeout.

No manual daily workflow, production backfill, Pages deployment or Telegram send
was requested or performed in this integration task. Production verification
remains a separate follow-up; u154 still needs its own Functional Design approval.
