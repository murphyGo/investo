# Cross-Check Report: u3 publisher

**Scope**: Unit `u3 publisher` (static archive writer + git commit/push)
**Date**: 2026-05-03
**Checked by**: Codex
**Triggered by**: `dev-investo` health check after all construction stages completed

---

## Inputs

| Document | Role |
|----------|------|
| `docs/requirements.md` | Single-source-of-truth FR/NFR list |
| `aidlc-docs/inception/user-stories/stories.md` | US-003 / US-006 acceptance criteria |
| `aidlc-docs/inception/application-design/unit-of-work-story-map.md` | Story-to-unit ownership |
| `aidlc-docs/construction/plans/u3-publisher-code-generation-plan.md` | u3 implementation plan |
| `aidlc-docs/construction/u3-publisher/code/summary.md` | Code-generation closeout and traceability |
| Implementation: `src/investo/publisher/`, `tests/unit/publisher/`, `tests/integration/test_publisher_smoke.py` | Artifacts verified |

---

## Scope Filter

Per `unit-of-work-story-map.md`, **u3 publisher** is responsible for:

- **Primary stories**: US-003 (GitHub Pages에 시황을 정적 게시한다), US-006 (모든 시황을 영구 보관한다)
- **Touched by**: NFR-004 (publish boundary disclaimer verification)
- **FRs**: FR-003 u3 slice, FR-006
- **NFRs covered whole or share**: NFR-003 git retry / publish failure surfacing, NFR-004 disclaimer hard block, NFR-007 subprocess hygiene / bounded stderr excerpt

Out of scope: MkDocs build, GitHub Pages deployment, latest-home/index/search navigation, and mobile rendering. Those are u6 infra/CI responsibilities.

---

## Summary

| Status | Count | Percentage |
|--------|------:|-----------:|
| ✅ Complete | 8 | 89% |
| ⚠️ Partial | 1 | 11% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **9** | **100%** |

**Overall compliance for u3 publisher**: u3's unit contract is complete. The Partial is FR-003/US-003 at the full-product level because Pages build and index/navigation are owned by u6, not u3.

---

## Functional Requirements

| ID | Description | Status | Evidence | Notes |
|----|-------------|--------|----------|-------|
| FR-003 | 정적 웹 게시 | ⚠️ Partial | `write_briefing`, `archive_path`, `commit_and_push`, integration smoke | u3 writes and commits markdown to the Git repo. Static site build, Pages deployment, latest/index/search are u6 scope. |
| FR-006 | 영구 이력 보관 | ✅ Complete | `archive_path`, `write_briefing`, `commit_and_push`, writer/git tests | Archive path and git commit/push lifecycle are implemented and tested. |

### FR-003 Acceptance-Criterion Detail

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 시황은 markdown 파일로 git repo에 저장 | ✅ | `writer.py::write_briefing`; `test_writer.py`; integration smoke |
| 정적 사이트 생성기로 빌드 → GitHub Pages 배포 | ⚠️ | Out of u3 scope; u6 owns MkDocs/Pages workflows |
| 날짜별 인덱스, 최신 시황 홈 노출 | ⚠️ | Out of u3 scope; u6 owns site navigation/index |
| 검색 또는 날짜/연도별 탐색 | ⚠️ | Out of u3 scope; u6 owns site navigation/search |

### FR-006 Acceptance-Criterion Detail

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 시황은 git commit으로 영구 저장 | ✅ | `git_ops.py::commit_and_push`; `test_git_ops.py`; integration smoke |
| 폴더 구조 `archive/YYYY/MM/YYYY-MM-DD.md` | ✅ | `paths.py::archive_path`; `test_paths.py` |
| 저장 용량 문제는 Out of Scope | ✅ | No contrary implementation; git-backed archive matches v1 scope |

---

## User Stories

| ID | Title | Status | Evidence | Notes |
|----|-------|--------|----------|-------|
| US-003 | GitHub Pages에 시황을 정적 게시한다 | ⚠️ Partial | u3 writes/commits markdown; u6 owns Pages build/deploy/index | u3 slice is complete, full story closes only with u6. |
| US-006 | 모든 시황을 영구 보관한다 | ✅ Complete | `archive_path`, `write_briefing`, `commit_and_push` | Same-day overwrite policy is pinned: overwrite file, prior versions remain in git history. |

---

## Non-Functional Requirements

| ID | Description | Status | Evidence | Notes |
|----|-------------|--------|----------|-------|
| NFR-003 (u3 share) | Git operation retry / failure surfacing | ✅ Complete | `commit_and_push`, `PublisherGitError`, retry and partial-success tests | Add/commit/push retried end-to-end; idempotent commit no-op handled after push failure. |
| NFR-004 | Disclaimer enforcement at publish boundary | ✅ Complete | `verify_disclaimer`, `write_briefing`, `PublisherDisclaimerError`, verifier/writer tests | Verification runs before mkdir/write; missing disclaimer writes nothing. |
| NFR-007 (u3 share) | Subprocess list form and bounded stderr | ✅ Complete | `git_ops.py`, `test_git_ops.py`, `PublisherGitError` stderr truncation tests | Only git subprocess path is list-form; no `shell=True`; stderr bounded to 1024 UTF-8 bytes. |
| Maintainability / module boundary | u3 imports only allowed cross-unit dependencies | ✅ Complete | `src/investo/publisher/*`; `code/summary.md` boundary audit | u3 imports `models.Briefing` and `briefing.disclaimer.DISCLAIMER`; no sources/notifier/orchestrator imports. |

---

## Verification Run

| Command | Result |
|---------|--------|
| `uv run pytest tests/unit/publisher tests/integration/test_publisher_smoke.py -q` | ✅ 70 passed |
| `uv run mypy --strict src/investo/publisher src/investo/models/briefing.py` | ✅ no issues in 7 source files |
| `uv run ruff check src/investo/publisher tests/unit/publisher tests/integration/test_publisher_smoke.py` | ✅ all checks passed |
| `rg -n "subprocess\\.(run\\|Popen)\\(|shell\\s*=\\s*True|eval\\(|exec\\(|pickle\\.loads|from investo\\.(sources|notifier|orchestrator)|import investo\\.(sources|notifier|orchestrator)" src/investo/publisher tests/unit/publisher tests/integration/test_publisher_smoke.py` | ✅ only expected list-form `subprocess.run` and test doc/self-check matches |

---

## Gaps Analysis

### GAP-001: FR-003 / US-003 full static-site publication is split with u6

**Requirement**: FR-003 includes markdown storage, static-site build, GitHub Pages deployment, latest/index navigation, and search/date exploration.

**Status**: ⚠️ Partial at full-product level. u3 implements the markdown archive and git commit/push lifecycle. MkDocs build, Pages deployment, home/latest/index/search are owned by u6 infra/CI.

**Impact**: Low for u3 stage gate. This is an intentional unit boundary, not an implementation miss inside u3.

**Proposed Action**: Verify the remaining FR-003 acceptance criteria in the u6 infra/CI cross-check. Do not add a u3 TECH-DEBT item.

---

## Open TECH-DEBT in u3 Scope

| ID | Priority | Description | Cross-check status |
|----|----------|-------------|--------------------|
| DEBT-012 | Medium | `_truncate_stderr` helper duplicated across u2 + u3 errors modules | Accepted; not blocking u3 correctness |
| DEBT-013 | Low | u3 publisher test `_build_briefing` fixture duplicated | Accepted maintainability item |

No new TECH-DEBT items were added by this cross-check.

---

## Sign-Off

✅ **u3 publisher cross-check PASSED with one expected cross-unit Partial for FR-003 / US-003.**

The unit is complete for its contract: archive markdown write, disclaimer hard block, atomic write, git commit/push retry, and public publisher surface. Recommended next health-check target is the next completed unit without a cross-check report: `u4 notifier`.
