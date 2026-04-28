# Domain Entities — `u2 briefing`

**Date**: 2026-04-28
**Source**: u2-briefing-functional-design-plan.md (Q1=A through Q9=A)

This unit's domain is the **synthesis layer**: it consumes a list of
`NormalizedItem` from u1 sources, performs a two-stage Claude Code CLI
prompt, appends the disclaimer, validates the output, and produces a
`Briefing`. The `Briefing` and `NormalizedItem` pydantic models are
defined in `models/` and are *consumed* — this document focuses on
entities that originate inside `briefing`.

---

## E1. SectionId (closed enumeration)

**Kind**: Closed enumeration of the seven fixed sections (FR-002).

| ID | Korean label | English code-side name |
|----|--------------|------------------------|
| `1` | ① 요약 | `market_summary` |
| `2` | ② 전일 핵심 이슈 | `key_issues` |
| `3` | ③ 섹터/수급 동향 | `sector_flow` |
| `4` | ④ 지표·이벤트 | `indicators_events` |
| `5` | ⑤ 주요 종목 | `notable_tickers` |
| `6` | ⑥ 오늘의 관전 포인트 | `today_watch` |
| `7` | ⑦ 면책조항 | `disclaimer` |

**Why an enumeration**: Stage 1 of the prompt asks the LLM to assign each
input item to one of `{1, 2, 3, 4, 5}` (sections that receive items
directly). Sections `1`, `6`, and `7` are *not* targets for direct
mapping:

- Section `1` (요약) is synthesized by Stage 2 from the union of all items.
- Section `6` (관전 포인트) is forward-looking and synthesized by Stage 2.
- Section `7` (disclaimer) is appended programmatically (R5), never via the LLM.

The enumeration is defined as integer literals for prompt-stable
mapping; the code-side mirror uses the English snake_case names listed
above to match the `Briefing` model fields.

---

## E2. ClassificationResult (Stage 1 output)

**Kind**: Pydantic model (or frozen dataclass) parsed from Stage 1's
JSON response.

**Attributes**:

| Field | Type | Constraint |
|-------|------|-----------|
| `assignments` | `dict[int, int]` | keys = `NormalizedItem.id` (synthetic id assigned at serialization, see L1 step 2); values ∈ `{2, 3, 4, 5}` |
| `unassigned` | `list[int]` | item ids the LLM judged not worth including in any section (allowed to be empty) |

**Behaviour**:

- Construction: parsed from Stage 1 stdout, which the prompt instructs
  the LLM to emit as a JSON object literal.
- Validation: every `assignments` value must be in `{2, 3, 4, 5}`;
  every key + every `unassigned` element must correspond to an id
  that was passed in. Mismatches → `BriefingGenerationError(stage="classification")`.
- Trustability: structurally invalid JSON, value out-of-range, or id
  not from the original input → terminal failure (no retry helps; the
  prompt itself is broken). One-attempt JSON-parse failure → retry per R3
  (transient — LLM may have just hiccuped).

**Why a dedicated entity**: `dict[int, int]` would do mechanically,
but the wrapper makes the contract testable in isolation (parser tests
in `tests/unit/briefing/test_classification.py`) and gives a clear
type for u5's stage guard to inspect on alert.

---

## E3. SectionPlan (intermediate, Stage 1 → Stage 2)

**Kind**: Frozen dataclass (or simple TypedDict).

**Attributes**:

| Field | Type | Constraint |
|-------|------|-----------|
| `target_date` | `date` | the KST trading date the briefing is for |
| `items_by_section` | `dict[int, list[NormalizedItem]]` | keys ∈ `{2, 3, 4, 5}`; values are subsets of the original input (preserves ordering by `published_at` desc within each section) |
| `unassigned` | `list[NormalizedItem]` | items the LLM judged not section-worthy; included in Stage 2's prompt as context for sections ① and ⑥ but not directly slotted |

**Construction**: `build_section_plan(items, classification)` —
deterministic function (no LLM). Maps `ClassificationResult` back onto
the original `NormalizedItem` list.

**Why an intermediate entity**: Stage 2's prompt builder needs items
*grouped by section*, not the raw `id → section_id` map. Putting the
grouping in a pure function (and a pure value object) makes Stage 2's
prompt builder testable without re-invoking the LLM.

---

## E4. BriefingGenerationError (exception)

**Kind**: Custom exception class.

**Hierarchy**: subclass of `Exception` (mirrors `SourceFetchError` from
u1; not `RuntimeError`, so `pytest.raises(BriefingGenerationError)`
doesn't accidentally catch programmer-error `RuntimeError`s).

**Attributes**:

| Attr | Type | Required | Notes |
|------|------|----------|-------|
| `stage` | `Literal["classification", "synthesis", "post_validation", "budget"]` | yes | which step of the pipeline failed; routes to the operator-alert message format |
| `attempt_count` | `int` | yes | retries actually consumed (1 = single attempt; 3 = exhausted under default config) |
| `last_stderr` | `str \| None` | yes | last subprocess stderr (truncated to ~1 KB) — useful in the operator alert; `None` for `post_validation` and `budget` stages where no subprocess returned |
| `cause` | `BaseException \| None` | yes | original exception when wrapped (e.g. `subprocess.TimeoutExpired`, `json.JSONDecodeError`, `ValidationError`) |

**Construction examples**:

- Stage 1 output not parseable as JSON after 3 attempts:
  `BriefingGenerationError(stage="classification", attempt_count=3, last_stderr="...", cause=json.JSONDecodeError(...))`
- Stage 2 produced empty markdown:
  `BriefingGenerationError(stage="synthesis", attempt_count=2, last_stderr="", cause=None)`
- PII regex matched in synthesized output:
  `BriefingGenerationError(stage="post_validation", attempt_count=1, last_stderr=None, cause=None)`
- Total budget exceeded:
  `BriefingGenerationError(stage="budget", attempt_count=N, last_stderr=None, cause=TimeoutError(...))`

**Why "stage" matters**: u5's `OperatorAlerter` reads `stage` to decide
the message template. `"classification"` failure → "LLM is misbehaving
on item bucketing"; `"post_validation"` failure → "LLM emitted a
secret-looking pattern, manual inspection needed". The flag also lets
the audit log distinguish prompt-design issues from infra issues.

---

## E5. SubprocessOutcome (internal value object)

**Kind**: Frozen dataclass returned by the `claude_code.call_claude_code`
subprocess wrapper.

**Attributes**:

| Field | Type | Notes |
|-------|------|-------|
| `stdout` | `str` | UTF-8-decoded subprocess stdout |
| `stderr` | `str` | UTF-8-decoded subprocess stderr |
| `returncode` | `int` | subprocess exit code |
| `elapsed_s` | `float` | wall-clock duration (used by the retry helper to track the total budget) |

**Why expose `elapsed_s`**: the retry helper compares cumulative
`elapsed_s` against `total_budget_s` to fire `BriefingGenerationError(stage="budget")`
without waiting for one more round-trip when there's no time left.

**Why not just return a dict**: typed access in the retry helper +
fewer chances for typos in attribute names.

---

## Output: `Briefing` (defined in `models/`)

This unit produces a `Briefing` instance per `models/briefing.py`. The
contract is:

| Field | Source |
|-------|--------|
| `target_date` | `BriefingGenerationRequest.target_date` (input) |
| `market_summary` | Stage 2 output, parsed section ① |
| `key_issues` | Stage 2 output, parsed section ② |
| `sector_flow` | Stage 2 output, parsed section ③ |
| `indicators_events` | Stage 2 output, parsed section ④ |
| `notable_tickers` | Stage 2 output, parsed section ⑤ |
| `today_watch` | Stage 2 output, parsed section ⑥ |
| `disclaimer` | `DISCLAIMER` constant (R5) |
| `rendered_markdown` | full markdown string (sections 1-6 from Stage 2 + appended ⑦ disclaimer) |

The model's frozen `extra="forbid"` config means the briefing object
is immutable once built — any post-construction mutation attempt
raises `pydantic.ValidationError`, which propagates as a programmer
error (caught by u5's stage guard).

---

## Entity dependency graph

```
                        +-------------------+
                        |  models.items     |
                        | NormalizedItem    |
                        +---------+---------+
                                  |
                                  v
                        +-------------------+
                        |  Stage 1 prompt   |
                        |   (E2 output)     |
                        +---------+---------+
                                  |
                                  v
                        +-------------------+
                        |  SectionPlan (E3) |
                        +---------+---------+
                                  |
                                  v
                        +-------------------+
                        |  Stage 2 prompt   |
                        |  (markdown body)  |
                        +---------+---------+
                                  |
                                  v
                        +-------------------+
                        | append_disclaimer |
                        | + leak guard      |
                        +---------+---------+
                                  |
                                  v
                        +-------------------+
                        |  models.Briefing  |
                        |    (output)       |
                        +-------------------+

  Errors flow upward as BriefingGenerationError (E4),
  bubbled to u5 orchestrator's stage guard for alerting.
```

---

## What lives outside this unit

- `NormalizedItem`, `Briefing`, `BriefingNotification` types — `investo.models`
- The `claude` CLI binary — environment dependency; not built here
- `CLAUDE_CODE_OAUTH_TOKEN` env var — provided by GitHub Secrets at runtime; not validated here
- The actual operator-alert sending — u4 notifier (`OperatorAlerter`)
- `archive/` markdown write + git commit — u3 publisher
