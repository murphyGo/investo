# Business-Logic Model — `u2 briefing`

**Date**: 2026-04-28
**Source**: u2-briefing-functional-design-plan.md (Q1=A through Q9=A)

This document is the technology-neutral description of how the unit
behaves. Concrete library calls (`subprocess.run` shape, exact retry
helper API, fixture file format) are inputs; the algorithms below are
what code generation must implement.

---

## L1. End-to-end flow

```
orchestrator
    │
    │ target_date: date,
    │ items: list[NormalizedItem]   (from u1.fetch_all)
    ▼
generate_briefing(target_date, items)
    │
    │ 1. Serialize items to JSON (R7)
    │    — assign synthetic id=1..N at this step
    │
    │ 2. Build Stage 1 prompt:
    │    "Classify each item into section ∈ {2,3,4,5} or 'unassigned'.
    │     Categories are hints; use your judgment."
    │
    │ 3. call_claude_code(stage1_prompt) with R3 retry
    │    └── exhausted retries → BriefingGenerationError(stage="classification")
    │
    │ 4. Parse Stage 1 output as ClassificationResult (E2)
    │    └── invalid JSON / out-of-range / unknown id
    │        → retry per R3, then BriefingGenerationError(stage="classification")
    │
    │ 5. Build SectionPlan from items + classification (E3)
    │    — pure function, no LLM
    │
    │ 6. Build Stage 2 prompt:
    │    "Write Korean prose for sections ①-⑥, given these grouped items.
    │     Output exactly 6 markdown sections with the prescribed headers."
    │
    │ 7. call_claude_code(stage2_prompt) with R3 retry
    │    └── exhausted retries → BriefingGenerationError(stage="synthesis")
    │
    │ 8. Parse Stage 2 output:
    │    — split on section headers
    │    — verify all 6 sections present + non-empty
    │    └── parse failure → retry per R3, then BriefingGenerationError(stage="synthesis")
    │
    │ 9. append_disclaimer(markdown)  → markdown with section ⑦ (R5)
    │
    │ 10. leak_guard.scan(markdown_with_disclaimer)
    │     └── pattern matched → BriefingGenerationError(stage="post_validation")
    │
    │ 11. Build Briefing model (models.briefing.Briefing)
    │     — pydantic frozen, extra="forbid"
    │     └── ValidationError → propagate (programmer error, not BriefingGenerationError)
    │
    ▼
return Briefing
```

Notes:

- The two stages are **sequential**, not concurrent. Stage 2's prompt
  depends on Stage 1's output.
- The total wall-clock is bounded by R3 (5 min). Per-call timeouts
  are 120 s; with two stages × 3 attempts each = 6 calls × 120 s
  worst-case = 12 min, but the **total budget** check fires earlier.
- All side effects (file writes, git commits, Telegram pushes)
  happen *outside* this unit. u2 returns a `Briefing` value object
  and never touches the filesystem at runtime (test fixtures are
  the only file I/O, and they're read-only at test time).

---

## L2. Stage 1 algorithm — classification

```
async def classify(items: list[NormalizedItem]) -> ClassificationResult:
    serialized = json_serialize(items)        # R7
    prompt = build_classification_prompt(serialized)
    
    for attempt in range(MAX_ATTEMPTS):       # R3: 3
        check_total_budget()                  # raise BGE(stage="budget") if past
        outcome = await call_claude_code(prompt, timeout_s=120)
        
        if outcome.returncode != 0:
            register_failed_attempt(outcome)
            sleep(BACKOFF_SCHEDULE[attempt])   # R3: 0/2/8
            continue
        
        try:
            parsed = parse_classification_json(outcome.stdout)
        except (json.JSONDecodeError, ValidationError) as exc:
            register_failed_attempt(outcome, cause=exc)
            sleep(BACKOFF_SCHEDULE[attempt])
            continue
        
        if not validate_id_set(parsed, items):  # all keys / unassigned values must be valid item ids
            register_failed_attempt(outcome, cause=ValueError("id mismatch"))
            sleep(BACKOFF_SCHEDULE[attempt])
            continue
        
        return parsed
    
    raise BriefingGenerationError(
        stage="classification",
        attempt_count=MAX_ATTEMPTS,
        last_stderr=last_outcome.stderr[:1024],
        cause=last_cause,
    )
```

### Stage 1 prompt skeleton (technology-neutral; exact strings in CG)

```
[SYSTEM]
You are a Korean market-briefing classifier. Output ONLY a JSON object
matching this schema:
  {
    "assignments": {<item_id_int>: <section_id ∈ {2,3,4,5}>, ...},
    "unassigned": [<item_id_int>, ...]
  }
No prose, no markdown, no commentary.

Section ID legend:
  2 = 전일 핵심 이슈 (key market issues from yesterday)
  3 = 섹터/수급 동향 (sector / fund-flow trends)
  4 = 지표·이벤트 (macro indicators / scheduled events)
  5 = 주요 종목 (notable individual stocks / tickers)

Categories on each item are HINTS, not hard rules. Use your judgment
when an item could belong to multiple sections.

[USER]
Items:
<JSON array, one item per object, fields per R7>

Return only the JSON.
```

---

## L3. Stage 2 algorithm — synthesis

```
async def synthesize(plan: SectionPlan) -> str:
    grouped_json = json_serialize_section_plan(plan)
    prompt = build_synthesis_prompt(grouped_json)
    
    for attempt in range(MAX_ATTEMPTS):
        check_total_budget()
        outcome = await call_claude_code(prompt, timeout_s=120)
        
        if outcome.returncode != 0 or len(outcome.stdout) < SANITY_FLOOR:
            register_failed_attempt(outcome)
            sleep(BACKOFF_SCHEDULE[attempt])
            continue
        
        try:
            sections = parse_six_sections(outcome.stdout)  # split on ## headers
        except ValueError as exc:
            register_failed_attempt(outcome, cause=exc)
            sleep(BACKOFF_SCHEDULE[attempt])
            continue
        
        # All 6 sections must be present and non-blank.
        if not all_present_and_non_blank(sections):
            register_failed_attempt(outcome, cause=ValueError("missing section"))
            sleep(BACKOFF_SCHEDULE[attempt])
            continue
        
        return outcome.stdout
    
    raise BriefingGenerationError(
        stage="synthesis",
        attempt_count=MAX_ATTEMPTS,
        last_stderr=last_outcome.stderr[:1024],
        cause=last_cause,
    )
```

### Stage 2 prompt skeleton (technology-neutral; exact strings in CG)

```
[SYSTEM]
You are a Korean market-briefing writer. Produce markdown with
EXACTLY these six sections, in this order, with these exact headers:

  ## ① 요약
  ## ② 전일 핵심 이슈
  ## ③ 섹터/수급 동향
  ## ④ 지표·이벤트
  ## ⑤ 주요 종목
  ## ⑥ 오늘의 관전 포인트

Rules:
- Korean prose throughout EXCEPT for tickers, fund/index names,
  currency symbols, and number formats (R8).
- Each section non-blank, even if just "특이사항 없음" when the
  grouped items are empty.
- DO NOT include section ⑦ — the disclaimer is appended by the
  caller (R5).
- DO NOT include any private tokens, keys, email addresses, or
  phone numbers in your output.

[USER]
Pre-grouped items (Stage 1 output):

Section ②:
  <items assigned to 2>
Section ③:
  <items assigned to 3>
Section ④:
  <items assigned to 4>
Section ⑤:
  <items assigned to 5>

Unassigned (context for sections ① and ⑥):
  <unassigned items>

Target date: <YYYY-MM-DD>

Return only the markdown.
```

---

## L4. Retry helper algorithm

```
class RetryBudget:
    total_budget_s: float = 300.0
    elapsed_s: float = 0.0
    
    def check(self):
        if self.elapsed_s >= self.total_budget_s:
            raise BriefingGenerationError(stage="budget", ...)

# Shared between Stage 1 and Stage 2; passed by reference.
budget = RetryBudget()

# Each call_claude_code invocation:
#   - records its own elapsed_s
#   - adds it to budget.elapsed_s
#   - checks budget BEFORE issuing the next attempt
```

The retry budget is a single shared counter across both stages, so
that Stage 2's retries don't have a fresh 5-min budget if Stage 1
already consumed 4 min.

---

## L5. Failure classification

| Trigger | Stage | Surfaces as |
|---------|-------|-------------|
| `subprocess.TimeoutExpired` | classification or synthesis | retry per R3; on exhaust → `BriefingGenerationError(stage=<current>)` |
| `returncode != 0` | classification or synthesis | retry per R3; on exhaust → same |
| Empty / under-sanity-floor stdout | classification or synthesis | retry per R3; on exhaust → same |
| Stage 1 JSON parse failure | classification | retry per R3; on exhaust → same |
| Stage 1 invalid id / out-of-range section_id | classification | retry per R3 (LLM may correct on re-prompt); on exhaust → same |
| Stage 2 missing section header | synthesis | retry per R3; on exhaust → same |
| Stage 2 blank section body | synthesis | retry per R3; on exhaust → same |
| Total budget exceeded | budget | immediate `BriefingGenerationError(stage="budget")`, no further retry |
| `leak_guard.scan` matched | post_validation | immediate `BriefingGenerationError(stage="post_validation")`, no retry (re-running same prompt won't help; the prompt or item set needs human review) |
| `pydantic.ValidationError` building `Briefing` | (programmer error) | propagate as-is, NOT wrapped in BGE — it means u2's parser produced something the model rejects, which is a code bug |
| `KeyError`/`AttributeError`/`TypeError` from internal logic | (programmer error) | propagate as-is — u5's stage guard converts to "PROGRAMMER_ERROR" alert |

Rule of thumb: anything traceable to *the LLM's response* becomes a
`BriefingGenerationError`. Anything traceable to *our code being wrong*
propagates so we see it.

---

## L6. Logging contract (informational)

Per the same convention as u1: u2 logs nothing during success. The
orchestrator (u5) emits INFO-level lifecycle ("briefing generation
started" / "completed in N s"). u2 itself stays silent at INFO and
DEBUG.

On `BriefingGenerationError`, u5's stage guard logs WARNING with
structured fields:

| Field | Example |
|-------|---------|
| `stage` | `"classification"` |
| `attempt_count` | `3` |
| `last_stderr_excerpt` | first 200 chars of stderr |

The `OperatorAlerter` (u4) consumes the same fields when building the
Telegram message body (FR-007).

---

## L7. Sequence diagram (happy path)

```
orchestrator       generate_briefing      claude CLI         (no fs / net)
     │                    │                   │
     │  generate_briefing │                   │
     │   (target_date,    │                   │
     │    items)          │                   │
     │───────────────────▶│                   │
     │                    │ build Stage 1     │
     │                    │ prompt            │
     │                    │ subprocess.run    │
     │                    │──────────────────▶│
     │                    │                   │ (LLM thinks)
     │                    │  stdout (JSON)    │
     │                    │◀──────────────────│
     │                    │ parse → ClassificationResult
     │                    │ build SectionPlan │
     │                    │ build Stage 2     │
     │                    │ prompt            │
     │                    │ subprocess.run    │
     │                    │──────────────────▶│
     │                    │                   │ (LLM thinks)
     │                    │  stdout (markdown)│
     │                    │◀──────────────────│
     │                    │ parse 6 sections  │
     │                    │ append_disclaimer │
     │                    │ leak_guard.scan   │
     │                    │ Briefing(...)     │
     │     Briefing       │                   │
     │◀───────────────────│                   │
```

---

## L8. Out of scope for this stage

- Concrete Korean prompt strings — Code Generation owns these. FD pins
  the prompt *structure* (system message, user message shape, JSON
  schema), not the exact words.
- The `claude` CLI's internal behavior — u2 treats it as a black box
  with a defined exit-code / stdout / stderr contract.
- Caching across runs — no cache. Each pipeline run does Stage 1 +
  Stage 2 fresh. Cron is daily; cache TTL would be < cron interval, so
  no win.
- Multi-LLM fallback — out of scope for v1. If `claude` is down,
  alert operator and skip the publish.
- Streaming output parsing — the `claude` CLI returns full output;
  no incremental parsing needed at this scale.
- `--output-format json` — locked to text/markdown for v1 (Q3=A); a
  future ADR can revisit.

---

## L9. PoC reference flow — Stage 1 + Stage 2 against the FOMC fixture

To validate the design, the Code Generation step will exercise the
two-stage flow against u1's recorded FOMC RSS fixture
(`tests/unit/sources/fixtures/api/fomc-rss/feed.xml`):

1. Run `fetch_all(date(2026, 4, 25))` → returns 2 FOMC items.
2. Stage 1 prompt → expected output:
   `{"assignments": {1: 4, 2: 4}, "unassigned": []}`
   (both items are calendar entries → section ④).
3. Stage 2 prompt → expected output: 6 markdown sections, with
   section ④ mentioning the two FOMC orders.
4. `append_disclaimer` → adds section ⑦.
5. `leak_guard.scan` → no match.
6. `Briefing(...)` → constructed successfully.

The recorded LLM fixtures for steps 2 and 3 will be committed to
`tests/fixtures/llm/<sha256(prompt)[:16]>.json`. This becomes the
PoC guarantee: u2 + u1 working together against a real recorded
input, fully offline.
