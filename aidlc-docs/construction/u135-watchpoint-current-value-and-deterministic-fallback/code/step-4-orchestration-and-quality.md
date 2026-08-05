# u135 Step 4 — Pre-seal orchestration and quality diagnostics

## Outcome

- Built one immutable `WatchpointValuePayload` per segment from the reconciled
  anchors and already-routed items owned by u144 phase-1 assembly.
- Resolved LLM rows first and invoked the deterministic fallback only when no
  usable card survived.
- Scanned every synthesized card independently; a rejected card is omitted and
  cannot block publication. The existing second full-document compliance scan
  remains the terminal rendered-shape verifier.
- Propagated `synthesized_card_count` through the typed draft lifecycle and
  seal, then summed sealed documents into private quality-history metadata as
  `watchpoint_synthesized`.

## Rerun contract

No origin marker is embedded in public Markdown. A rerun recognizes only an
exact canonical, order-preserving subset of deterministic rows derivable from
the same frozen payload. It re-applies the row compliance filter and either
preserves the survivor count, replaces a changed survivor subset, or collapses
to the bounded note. Raw LLM bullets are not classified through this path.

## u144 ownership

The count is observed once from the phase-1 `WatchpointRenderResult`, carried
on `PublicDocumentDraft`, copied across every lifecycle transition, and sealed
on `FinalizedPublicDocument`. The orchestrator reads only sealed typed data;
it never rediscovers the count from final public Markdown and performs no
post-seal mutation.

## Review and validation

- Fresh-eyes review found three Medium gaps: sealed-writer fixture coverage,
  typed count restoration on rerun, and forced compliance-drop tests. Those
  were fixed.
- Re-review found one combined partial-drop rerun gap (`[1, 0]`); canonical
  subset recognition and a two-pass integration regression closed it as
  `[1, 1]` with byte-identical public output.
- Changed-impact suite: 274 passed.
- Publisher + orchestrator unit suites: 1,453 passed before the final isolated
  subset refinement; the final affected gate passed 22 tests.
- Scoped Ruff, format, mypy, and `git diff --check`: passed.
- Final fresh-eyes re-review: approved with no remaining finding.
