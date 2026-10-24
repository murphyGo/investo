# Korean component-label false-positive repair

Private US run `40122882991`, source `8ee57c710e34e30ca2076801160da87be289c6b1`,
passed classification on its first call, then failed both synthesis attempts with
`event.entity_unsupported`. Complete encrypted recordings enabled a local reconstruction
of the exact context, bindings, editorial plan and 13,345-byte protected evidence.

Both attempts contained four articles. All headlines passed claim checks, and every required
actor/object label was present. No unsupported English identifier was found. The first
failure in all eight `what_changed` checks was the Korean-subject heuristic treating the
generic component nouns `관측값` and `단위` as unsupported named entities. These describe
the source-bound observation and unit fields; they are not new issuers or institutions.

## Bounded acceptance criteria

- [x] Treat only these two component nouns like the existing generic nouns `수치` and
  `내용`; preserve every numeric, field-role, required identity, ownership and source gate.
- [x] Regress source-bound Korean component prose through native validation/finalization.
  Reject unsupported names, incorrect units/values, swapped actual/forecast roles and
  omitted required identity labels, including when generic nouns occur in the same claim.
- [x] Replay both complete actual synthesis outputs through the unchanged remaining
  gates; distinguish local replay from fresh model or human acceptance.
- [x] Obtain independent read-only QA, exact-source CI and fresh nonpublishing US preview.

After correcting only the generic-noun false positive, local replay exposes a second
independent failure: each article omits one fact subject reference, even though it includes
the event actor reference. The existing fact-source completeness gate rejects this as
`event.evidence_invalid`. The existing protected `context.events` rows already contain all
fact-component span IDs, aligned in the same order as the parent events. The prompt now
directs copying every fact-component ref from that row through `context.spans[id].ref`,
including a separate fact subject. The evidence payload and its 16KiB outer limit are
unchanged. Returned refs are never automatically filled in, and omission still fails the
same gate. No duplicate fact-to-ref mapping is added to the evidence budget.

No output schema, source/provider calls, time budgets, shared auth, production pin,
publication or notification change is required for this correction. Corpus/human/slot/
viewport/performance/scheduled acceptance and legacy retirement remain separate.

Local focused **94 PASS (3.41s)** includes native57, the component prose/negative mutations,
distinct fact-subject ref completeness, existing claim/finalization and context-budget gates.
Ruff/format 777 files and mypy 328 source files passed. The complete recorded synthesis
outputs both pass `validate_event_edition` after the two generic-noun corrections and a
local counterfactual copying only omitted subject refs from existing protected facts.
The protected payload remains exactly 13,345 bytes. This is not fresh model output or
human semantic acceptance; the original run remains failed.

Independent read-only QA: **113 PASS (7.92s)**, Ruff/format/diff passed, no open P1/P2.
The final source delta is two generic nouns and the complete-fact-ref instruction; the
editorial-plan payload builder is byte-for-byte unchanged. Native57/multi-document across
all markets, reader/claim/finalization and context bounds passed. Unsupported name, value,
unit, status, period and omitted required actor/object probes remain rejected.

Exact source `d44a5df3b7ff75f7cff5132a07768c975157269a` passed
[quality 40123857168](https://github.com/murphyGo/investo/actions/runs/40123857168):
7,117 passed, one skipped (761.90s), Node29 and all required guards. Actual US
[40123873052](https://github.com/murphyGo/automation-runtime/actions/runs/40123873052)
sealed one schema-three document containing four terminal events with complete two-call
recording and matching Markdown hash. Availability remains source-limited, human review
pending, publication/notification/cursor/receipt writes false. This proves actual generation,
not corpus acceptance or production readiness.
