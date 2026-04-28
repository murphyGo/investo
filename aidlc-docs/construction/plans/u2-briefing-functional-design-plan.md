# Functional Design Plan: `u2 briefing`

**Date**: 2026-04-28
**Unit**: u2 briefing — Briefing Generator (Claude Code CLI subprocess + 7-section Korean briefing + disclaimer auto-insert)
**Stage**: Functional Design
**Source artifacts**:
- `aidlc-docs/inception/application-design/components.md` — briefing component description
- `aidlc-docs/inception/application-design/component-methods.md` — `generate_briefing`, `call_claude_code`, `append_disclaimer` signatures
- `aidlc-docs/inception/application-design/component-dependency.md` — depends on `models` + `subprocess` (stdlib) only; **no** httpx, **no** Anthropic SDK
- `aidlc-docs/inception/application-design/unit-of-work.md` — Definition of Done
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md` — US-002, US-009
- `docs/requirements.md` — FR-002 acceptance criteria + NFR-002/003/004
- `aidlc-docs/construction/u1-sources/code/summary.md` — u1's stable surface (`fetch_all`, `NormalizedItem`, `Category`) — u2's input contract

---

## Unit Context

### Stories
- **US-002 AI가 한국어 데일리 시황을 작성한다** — Claude Code CLI로 7섹션 시황 생성, 면책조항 자동 삽입, 한국어 + 영문 종목명/티커 원문 유지
- **US-009 운영비를 월 $0으로 유지한다 (LLM slice)** — Claude Code CLI(setup token)만 사용, Anthropic API key 직접 호출 금지

### Cross-cutting NFRs
- **NFR-002** Cost — Claude Code CLI subprocess only (no Anthropic SDK in deps)
- **NFR-003** Reliability — LLM call retry with exponential backoff; final failure → no publish, alert only
- **NFR-004** Compliance — disclaimer auto-insert with idempotent guard; verifier in u3 Publisher (defense in depth)
- **NFR-006** Testing — record/replay LLM fixtures for deterministic CI

### What Functional Design covers
This stage defines **business logic, domain rules, and contracts** for u2. Concrete library choices already locked from inception (Claude Code CLI subprocess, no Anthropic SDK, `subprocess.run`) are inputs, not decisions.

What it does NOT cover (deferred):
- NFR Requirements (next stage) — measurable acceptance criteria
- Code Generation — actual implementation
- Specific Korean prompt wording — only the **structure** is decided here; exact prompt strings land in Code Generation

### Input contract from u1 (already locked)

```python
async def fetch_all(target_date: date) -> list[NormalizedItem]
```

`NormalizedItem` fields: `source_name: str`, `category: Literal["news","price","macro","calendar","earnings"]`, `title: str`, `summary: str | None`, `url: HttpUrl | None`, `published_at: datetime` (tz-aware), `raw_metadata: dict[str, str | int | float]`.

### Output contract to u3 (deferred to Briefing model in `models/`)

`Briefing` pydantic model already exists in `models/`. u2 produces a populated `Briefing` instance; u3 publishes the markdown.

---

## Execution Checklist

### Part 1 — Planning ✅
- [x] Q1~Q9 모두 [Answer]: 채움 (2026-04-28, every answer endorses option A — the (권장) default)
- [x] Ambiguity 분석: 없음 (every answer is "Yes, [the recommended option]..." — explicit endorsement, no "depends" / "maybe" / "not sure" patterns)
- [x] Plan 명시적 승인 (answers landed)

### Part 2 — Generation ✅
- [x] `aidlc-docs/construction/u2-briefing/functional-design/domain-entities.md` (E1 SectionId, E2 ClassificationResult, E3 SectionPlan, E4 BriefingGenerationError, E5 SubprocessOutcome + Briefing output mapping)
- [x] `aidlc-docs/construction/u2-briefing/functional-design/business-rules.md` (R1-R12 covering two-stage pipeline, Claude Code subprocess, retry/budget, failure isolation, disclaimer idempotence, PII leak guard, JSON serialization, Korean rule, fixture mechanism, LLM-decided section mapping, no-temperature determinism, atomic generate_briefing)
- [x] `aidlc-docs/construction/u2-briefing/functional-design/business-logic-model.md` (L1 end-to-end flow, L2 Stage 1 algorithm + prompt skeleton, L3 Stage 2 algorithm + prompt skeleton, L4 RetryBudget, L5 failure classification, L6 logging, L7 sequence diagram, L8 out-of-scope, L9 PoC against u1's FOMC fixture)
- [x] aidlc-state.md / audit.md 업데이트
- [x] Functional Design 명시적 승인 (2026-04-28, "approve")

---

## Embedded Questions

### Q1: Two-stage prompt structure

The unit-of-work.md mentions a "two-stage prompt flow" implemented via `build_classification_prompt` + `build_briefing_prompt`. What do the two stages produce?

A) **Stage 1 = item-level classification → Stage 2 = section-level synthesis (권장)**
   Stage 1 takes `list[NormalizedItem]` and returns a JSON map `{item_id → assigned_section_id}` (where section_id ∈ 1..6 per the 7-section template; section 7 is the auto-inserted disclaimer). Stage 2 takes the items grouped by section and produces the Korean prose for each. Splits a hard problem into two checkable pieces; cheap to record/replay.
B) **Stage 1 = filter/score (importance ranking) → Stage 2 = full synthesis** — Stage 1 ranks items by importance, drops low-signal ones, returns a filtered list. Stage 2 writes the briefing. Risks the LLM dropping things the operator wanted to see; harder to debug.
C) **Single stage** — One big prompt: items in, full markdown out. Simpler but harder to record/replay (one giant fixture); failure mode is opaque (no intermediate state to inspect).
D) **Stage 1 = section ordering + counts → Stage 2 = per-section content** — Stage 1 decides "section ④ has 3 events, section ⑤ has 5 stocks", Stage 2 fills each. Variant of A; less natural than item-classification.

[Answer]: Yes, the two-stage approach with item-level classification in Stage 1 and section-level synthesis in Stage 2 is the most modular and testable. It allows us to verify that the LLM is correctly categorizing items before we ask it to write the full briefing, which should lead to better results and easier debugging.

---

### Q2: 7-section mapping — how do `NormalizedItem.category` values map to the 7 sections?

The 7 sections per FR-002:
①요약 ②전일 핵심 이슈 ③섹터/수급 동향 ④지표·이벤트 ⑤주요 종목 ⑥오늘의 관전 포인트 ⑦면책조항

`NormalizedItem.category` ∈ {`news`, `price`, `macro`, `calendar`, `earnings`}.

A) **Stage 1 LLM does the mapping (권장)**
   The prompt tells the LLM: "given these items and their categories, place each into one of sections 1-6". Categories are *hints* not hard rules. ①요약 and ⑥관전 포인트 are LLM-synthesized from all items (no direct mapping). ②핵심 이슈 / ③섹터/수급 / ④지표·이벤트 / ⑤주요 종목 receive items based on the LLM's judgment. Allows cross-cutting items (e.g. a Fed event that's also a macro indicator).
B) **Hard mapping table** — Static dict: `news → ②`, `price → ③`, `macro → ④`, `calendar → ④`, `earnings → ⑤`. Stage 1 does no LLM work; Stage 2 just writes prose for each pre-bucketed list. Cheaper but loses cross-cutting flexibility.
C) **Hybrid** — Hard mapping for unambiguous categories (`earnings → ⑤`, `calendar → ④`); LLM-assigned for `news` (could land in ②, ③, or ⑤).
D) **All-LLM, no category hints** — Don't pass `category` to the LLM at all; let it figure it out from `title` + `summary`. Loses signal we already have.

[Answer]: Yes, letting the LLM do the mapping with category hints is more flexible and leverages the LLM's understanding to create a more coherent briefing. The categories guide the LLM but don't box it in, allowing for a richer synthesis.

---

### Q3: Claude Code CLI invocation pattern

The repo's CLAUDE.md says `subprocess.run(["claude", "-p", ...])`. What's the exact shape of the call?

A) **`subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=...)` (권장)**
   Prompt as positional arg after `-p`; output captured from stdout; timeout via subprocess kwarg. Auth via `CLAUDE_CODE_OAUTH_TOKEN` env var (already in GitHub Secrets per FR-002 / US-009). UTF-8 text mode. Long prompts (>~10K chars) may exceed argv limit on some shells — defer the streaming-via-stdin variant unless we hit that.
B) **`claude --print "..."` with stdin piping** — Similar but pipe prompt via stdin (`input=prompt`). Avoids argv length limits but slightly more setup.
C) **JSON mode** — `claude -p prompt --output-format json` if/when supported, gives structured output for easier parsing. Pin to text/markdown for v1; revisit if a JSON mode lands.
D) **Async subprocess (asyncio.create_subprocess_exec)** — Non-blocking. Overkill — u2 makes 1-2 LLM calls per pipeline run, not concurrent.

[Answer]: Yes, the `subprocess.run` with `capture_output=True` and `text=True` is the most straightforward approach. It keeps the implementation simple and fits our needs for v1. We can revisit if we encounter issues with prompt length or want to optimize for streaming responses in the future.

---

### Q4: LLM retry policy

NFR-003 says retry on failure with exponential backoff. What are the exact knobs?

A) **3 attempts, backoff 0/2/8 s, per-call timeout 120 s, total budget 5 min (권장)**
   Stage 1 + Stage 2 share the same policy. Retry on: subprocess exit code != 0, output empty / empty markdown, output length < N bytes (sanity floor), `subprocess.TimeoutExpired`. Don't retry on: clear "auth failed" stderr (re-issuing won't help). Total budget protects the orchestrator's 10-min ceiling (NFR-001).
B) **Tighter — 2 attempts, backoff 0/3 s, timeout 60 s, budget 2 min** — Faster fail; but Claude Code CLI cold start can be slow on first invocation in CI.
C) **Looser — 5 attempts, backoff 0/1/2/4/8 s, timeout 180 s, budget 10 min** — Eats the orchestrator's budget; only worth it if the LLM is flaky.
D) **No retry** — Single attempt, fail fast, alert. Minimum complexity but US-002 explicitly requires retry.

[Answer]: Yes, the 3-attempt policy with exponential backoff is a good balance. It gives the LLM a couple of chances to recover from transient issues without risking an endless loop or blowing the orchestrator's budget.

---

### Q5: Failure surface — how does u2 signal "I gave up" to u5 orchestrator?

When all retries are exhausted, what does u2 return / raise?

A) **Custom `BriefingGenerationError` exception (권장)**
   Subclass of `Exception` (mirrors `SourceFetchError` pattern from u1). Attributes: `stage` ("classification" / "synthesis"), `attempt_count`, `last_stderr`, `cause: BaseException | None`. u5 catches it in its stage guard, builds a `FailureContext`, and routes to `OperatorAlerter` (FR-007). u3 Publisher never sees it (publication is skipped).
B) **Return `Briefing | None`** — u2 returns `None` on failure; u5 checks for `None`. Cleaner-looking but loses the structured error info (no stage/attempt-count for the alert).
C) **Return `Briefing` with placeholder content + `status="FAILED"`** — Always returns a Briefing. u5 inspects `status`. But US-002 says "최종 실패 시 빈/저품질 시황 게시 금지" — a status field invites a future bug where someone publishes a FAILED briefing. Prefer the exception path that makes "publish a failed briefing" syntactically impossible.
D) **Tuple return `(Briefing | None, error_info | None)`** — Verbose; mypy union-handling at every call site.

[Answer]: Yes, the custom exception approach is more expressive and less error-prone. It gives us rich context for alerts and makes it impossible to accidentally publish a failed briefing.

---

### Q6: NormalizedItem → prompt serialization

How are items rendered into the prompt string?

A) **JSON array, one object per item, minimal fields (권장)**
   `[{"id": <int>, "category": "...", "source": "...", "title": "...", "summary": "...", "url": "...", "ts": "ISO8601"}]`. Stage 1 returns `{item_id → section_id}`. Stage 2 receives the same JSON re-grouped by section. JSON keeps the LLM honest about field boundaries; ids let Stage 1's response refer back unambiguously.
B) **Numbered markdown list** — `1. [news/reuters] Title — summary (2026-04-27 12:00 UTC)`. Reads like the briefing itself; risk: LLM may lose track of which section gets which item.
C) **YAML** — More readable than JSON for the LLM but harder to parse on the way back. Skip unless we hit JSON-parsing issues.
D) **Compact CSV** — Tightest token budget. Hard to read; LLM may miss field boundaries on summaries with commas.

**Token budget concern**: 30-day worth of FOMC + future news adapters could push past 50K tokens. Out of scope for v1 (FOMC ships ~5 items/day) but worth flagging for a future "items > N → summarize first" pre-pass.

[Answer]: Yes, the JSON approach is more robust for structured data. The LLM can still read it fine, and it gives us a clear contract for parsing the response.

---

### Q7: Disclaimer text — exact Korean wording + position

NFR-004 says auto-insert disclaimer with "투자 자문이 아닌 정보 제공" + 손실 책임 면책. What's the exact text + where in the markdown?

A) **Static constant, appended as section ⑦ at the end (권장)**
   ```
   ## ⑦ 면책조항
   본 시황은 일반 정보 제공을 목적으로 자동 생성된 자료이며,
   특정 종목·자산에 대한 매매 권유나 투자 자문이 아닙니다.
   투자 결정과 그 결과에 대한 책임은 전적으로 본인에게 있으며,
   본 시황의 내용에 따라 발생한 손실에 대해 작성자는 일체의 책임을 지지 않습니다.
   ```
   Defined as a module-level `DISCLAIMER` constant in `disclaimer.py`. `append_disclaimer(markdown)` appends only if not already present (idempotent — substring match on the section header). u3 Publisher's `verify_disclaimer` checks the same constant is present before allowing the commit.
B) **LLM writes its own disclaimer per call** — Reject. NFR-004 + the project rule "Do not rely on LLM output alone for disclaimer presence" already disallow this.
C) **Disclaimer at the top instead of the bottom** — Some compliance docs prefer top placement. Counter: section template explicitly numbers disclaimer as ⑦; readers see briefing first, disclaimer at end is the convention.
D) **Disclaimer as a separate file, transcluded via mkdocs** — Clean separation but the briefing must still carry it for git history + Telegram (publisher checks it on the markdown text, not on a build-time include).

[Answer]: Yes, the static constant + append approach is simple, reliable, and easy to verify. The idempotent guard prevents duplicates if the function is accidentally called multiple times.

---

### Q8: PII / secret leak guard on LLM output

US-002 AC: "시황 본문에 시크릿/PII가 포함되지 않도록 출력 검증". What does this check look like?

A) **Regex-based pattern blocklist + raise on hit (권장)**
   Patterns: GitHub PAT (`gh[pousr]_[A-Za-z0-9]{36,}`), AWS key (`AKIA[0-9A-Z]{16}`), generic OAuth-looking long base64 strings, email addresses, Korean phone numbers (`010-?\d{4}-?\d{4}`), JWT (three dots in base64). Any match → raise `BriefingGenerationError(stage="post_validation", ...)`. Lives in `briefing/leak_guard.py` (or appended to `disclaimer.py`).
B) **Trust the LLM, scan only at u4 notifier (Telegram boundary)** — Defense-only-at-egress. But u3 Publisher commits the markdown to the public repo *before* notifier runs — the leak surface is wider than just Telegram.
C) **Both — u2 scans output, u4 scans Telegram message body** — Defense in depth. Slightly redundant; same regex set in two places.
D) **AI-side check** — Add "do not include any PII or secrets" to the prompt and trust the LLM. Reject — same reason as Q7-B (LLM output not authoritative).

[Answer]: Yes, the regex-based guard is a simple but effective way to catch obvious leaks. It's not perfect (a clever secret could slip through), but it's a strong signal to the LLM that secrets are off-limits, and it provides a clear failure mode if something does get through.

---

### Q9: record/replay fixture mechanism

How are LLM calls recorded for tests?

A) **Hash-of-prompt → fixture filename (권장)**
   First test run records `tests/fixtures/llm/<sha256(prompt)[:16]>.json` with `{prompt, stdout, stderr, returncode}`. Subsequent runs check fixture, replay if found, error if missing (no live network). New prompt = new fixture must be checked in (caught at PR review). `_LIVE=1` env var enables real recording mode for a developer regenerating fixtures.
B) **Named fixtures, manually curated** — Tests reference `fixtures/llm/stage1_basic.json` by name. Simpler but every prompt change requires a manual rename + re-record. Heavier maintenance.
C) **VCR.py-style cassette** — Library does it. New dependency for what's essentially a 50-line wrapper.
D) **No recording — use a stub that returns canned strings inline in tests** — Loses fidelity to real LLM output shape. Tests pass without ever hitting a real `claude` invocation.

[Answer]: Yes, the fixture mechanism is a bit of plumbing but it's crucial for reliable CI and catching regressions in prompt formatting or output parsing. The hash-based approach strikes a good balance between automation and traceability.

---

## How to Approve

Reply with answers to Q1–Q9 (e.g. `Q1=A Q2=A Q3=A ...` or "all recommended" if you accept every (권장) option). I'll then generate the three FD artifacts (`business-logic-model.md`, `business-rules.md`, `domain-entities.md`) and update aidlc-state.md / audit.md.

If any answer is "not sure" or "depends" — I'll bounce back with a follow-up before generating, per the AIDLC rule's mandatory ambiguity check.
