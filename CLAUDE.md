# Investo

매일 미국 주식·크립토(보조: 코스피)의 데일리 시황을 자동 생성·게시하는 1인용 자동화 도구. 무료 공개 데이터를 수집해 Claude Code CLI로 한국어 7섹션 시황을 만들고, GitHub Pages 정적 사이트에 영구 보관 + 공개 텔레그램 채널로 푸시한다.

---

## Important: Before Development

Run `/dev-investo` to:
1. See current construction stage and unit progress (from `aidlc-docs/aidlc-state.md`)
2. Get the next task to work on (from AIDLC per-stage plan files)
3. Follow the AIDLC Construction workflow

---

## Quick Commands

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `/dev-investo` | Main development driver | Start here for any development work |
| `/code-review git` | Review code changes | Before committing |
| `/tech-debt` | Manage technical debt | Track and prioritize issues |
| `/cross-check` | Verify requirements | After completing a unit |

---

## Agent Team

The project ships with a **5-agent specialist team** at `.claude/agents/` for routed development work. Use the team for non-trivial requests; the lead decomposes and dispatches.

| Agent | Korean role | Responsibility | Owns (write authority) |
|-------|-------------|----------------|-------------------------|
| **`investo-lead`** | 팀장 | Orchestrator. Reads aidlc-state, decomposes requests, dispatches specialists, integrates outputs, reports. Does NOT write code/docs itself. | Nothing (routes only) |
| **`investo-planner`** | 기획 | AIDLC plans, FD/NFR/business-rules edits, audit.md entries, TECH-DEBT triage, aidlc-state.md updates, session logs | `aidlc-docs/`, `docs/requirements.md`, `docs/TECH-DEBT.md`, `docs/DESIGN.md`, `docs/sessions/` |
| **`investo-developer`** | 개발 | Python implementation per existing patterns (mypy strict, ruff, asyncio, pydantic v2, plugin pattern), test writing, fixture recording, quality gate | `src/investo/`, `tests/`, fixtures |
| **`investo-qa`** | QA | Code review (post-impl), project-rule audit, NFR AC coverage check, cross-cutting consistency, tech-debt candidate identification. Read-only. | Nothing (review only) |
| **`investo-ops`** | 운영 | GitHub Actions workflows, GHA secrets injection, mkdocs config, operator runbook | `.github/workflows/`, `mkdocs.yml`, `site_docs/`, CONTRIBUTING runbook section, README operations sections |

### How to invoke

**User pattern**: address the lead in plain language — `"투자 데이터 봇 진행해줘"`, `"DEBT-028 처리해줘"`, `"add a news adapter"`. The main session dispatches `investo-lead` which routes to specialists.

**Specialist pattern**: if you know exactly what you want, address a specialist directly — `"investo-developer: implement Step 2 of u1-sources-extension-plan.md"`.

**Autonomous pattern**: pair with `/loop` or `/schedule` for unattended progress —
```
/schedule every Monday at 9am: investo-lead, find work and progress the project
```
The lead's "Mode B: autonomous" prompt picks the highest-ROI next step (pending cross-checks / aged TECH-DEBT / FR-001 gap / etc.).

### Critical guarantees the team enforces

Every specialist's prompt re-states the project's hard rules so violations are caught at the team level, not at code-review time:

1. **No Anthropic SDK** — LLM calls only via Claude Code CLI subprocess
2. **Module boundary** — only `orchestrator` imports `sources/briefing/publisher/notifier`
3. **No paid APIs** — every external call free-tier reachable
4. **Disclaimer enforcement** — `publisher.verify_disclaimer` is the gate
5. **Telegram channel separation** — public channel ID ≠ operator chat ID
6. **No raw stdlib XML** — `defusedxml` only
7. **Secret hygiene (R13)** — no secret value in logs/errors/raw_metadata/fixtures

Any specialist returning work that violates a rule is rejected by the lead (or by you, the main session) before integration.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| `aidlc-docs/aidlc-state.md` | **Start here** — AIDLC state, construction progress |
| `aidlc-docs/inception/plans/execution-plan.md` | Which stages execute per unit |
| `aidlc-docs/inception/application-design/unit-of-work.md` | 5 units + delivery order |
| `docs/requirements.md` | FR/NFR + acceptance criteria (single source of truth) |
| `docs/DESIGN.md` | Architecture summary (developer-facing) |
| `docs/TECH-DEBT.md` | Technical debt registry |

`/dev-investo` keeps Functional Design and NFR Requirements selective. New code-generation plans must include a `Stage Decision` section explaining whether those stages are required or skipped, and why.

---

## Development Workflow

```
1. /dev-investo          → Get next task from AIDLC construction stage
2. Implement             → Write code following requirements + design
3. /code-review git      → Review before committing
4. Commit                → Save your work
5. /dev-investo          → Mark complete, get next task
```

---

## Project Structure

```
investo/                       # repo root
├── pyproject.toml
├── mkdocs.yml                 # static site config (FR-003)
├── archive/                   # generated briefings (run-time output)
│   └── YYYY/MM/YYYY-MM-DD.md
├── docs/                      # mkdocs source (site pages)
│   └── (index.md, etc.)
├── src/
│   └── investo/
│       ├── __main__.py        # python -m investo entry
│       ├── models/            # shared pydantic types (foundation)
│       ├── sources/           # u1: Source Adapters (plugin)
│       ├── briefing/          # u2: Briefing Generator (Claude Code CLI)
│       ├── publisher/         # u3: Publisher (markdown + git)
│       ├── notifier/          # u4: Notifier (BriefingPublisher + OperatorAlerter)
│       └── orchestrator/      # u5: Pipeline runner
├── tests/
│   ├── unit/                  # per-module tests
│   ├── integration/           # cross-module pipeline test
│   └── fixtures/              # LLM record/replay, sample API responses
└── .github/workflows/         # u6: cron + Pages deploy
```

(목표 구조 — Construction phase에서 실현됨)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| LLM Runtime | **Claude Code CLI** (`subprocess.run(["claude", "-p", ...])`) — Anthropic SDK 직접 호출 금지 |
| HTTP | httpx (async) |
| Validation | pydantic v2 |
| Static Site | MkDocs Material → GitHub Pages |
| Notification | Telegram Bot API (raw HTTP) |
| Scheduler | GitHub Actions cron (KST 평일 07:00 / 토요일 09:00) |
| Storage | Git repo (markdown files) |
| Lint/Format | ruff |
| Type Check | mypy (strict) |
| Test | pytest + hypothesis (PBT partial) |

---

## Critical Project Rules

이 규칙들은 모든 PR과 코드 리뷰에서 강제됨:

1. **Anthropic SDK import 금지** — LLM 호출은 오직 Claude Code CLI subprocess. 운영비 0원 목표(NFR-002).
2. **면책조항 자동 삽입 강제** — 모든 시황은 disclaimer 포함. Publisher가 게시 직전 검증.
3. **모듈 경계** — orchestrator만 다른 4 unit을 import. 4 unit은 서로 import 금지 (모두 models만 공유).
4. **무료 API only** — 유료 데이터 키 등록 금지.
5. **텔레그램 채널 분리** — 공개 시황 채널(BriefingPublisher) ↔ 운영자 1:1 chat(OperatorAlerter), chat ID 공유 금지.

---

## Reference: AIDLC Documentation Layout

- `aidlc-docs/aidlc-state.md` — 현재 단계/진행
- `aidlc-docs/audit.md` — 모든 결정 audit log
- `aidlc-docs/inception/`
  - `requirements/` — requirements bridge (단일 출처는 `docs/requirements.md`)
  - `user-stories/` — personas + stories (US-001~US-009)
  - `plans/` — workflow / story-generation / application-design / unit-of-work / execution plans
  - `application-design/` — 5 components + methods + services + dependency + units
- `aidlc-docs/construction/` — 향후 Construction phase 산출물 (per-stage plans)
- `aidlc-workflows/` — AIDLC 룰 정의 (수정 금지, 참조 전용)
