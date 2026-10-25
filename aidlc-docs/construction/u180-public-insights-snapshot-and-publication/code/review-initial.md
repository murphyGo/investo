# u180 independent code review — initial

작성일: 2026-10-12. 검토자: 별도 Codex reviewer. 상태: **High 1건 미해결 — 수정 후 좁은 재검토 필요**.

## 범위와 방법

dev-investo Step 5.1에 따라 code-review skill과 security-boundary, concurrency, data-integrity, resource-lifecycle, error-contract, memory, performance protocols를 읽고 적용했다. 실제 공통 C1–C7, u180 business-rules/NFR/infrastructure/code-generation plan을 기준으로 검토했다.

신규 공통 models/insights.py·insights_calendar.py, orchestrator/insights.py·insights_projection.py·insights_publication.py, publisher/insights/store.py를 읽었다. 기존 items/results/window/aggregator/stages/__main__/private-runtime workflow의 변경 diff와 pipeline의 collection·capture·실패 결과 보존 경로, 기존 publication_receipts의 commit/receipt/CAS 소유권 경로를 대조했다. 신규 u180 계약·capture·projection·store·publication·resource 테스트와 합성 helper를 읽었다. 후속 compact history 구현 전체를 새로 독립 재검증하거나 전체 suite를 반복 실행한 것은 아니다.

소스별 원 응답 매핑·제품 UI·새 source HTTP·LLM·Telegram 추가는 검토 범위에 없다. 실제 production activation·Pages·private pin·5회 scheduled observation을 수행하거나 수용했다고 주장하지 않는다.

## 미해결 findings

### H180-01 — no-receipt crash recovery가 owned Git index를 복구하지 않는다 (High)

위치: `src/investo/orchestrator/insights_publication.py:166`, `:231`; `src/investo/publisher/insights/store.py:294`, `:385` (이 초기 검토 시점 기준).

`InsightTransaction.stage()` 뒤 `git add`가 끝나고 `git commit` 전에 프로세스가 종료되면, journal에는 receipt가 없지만 owned paths의 새 내용이 index에 남는다. 다음 `_phase()`의 `recover()`는 작업 파일을 rollback하고 journal을 삭제한다. index는 그대로 남아 이후 pre-existing staging guard가 실패한다. 재시도도 같은 상태로 실패하여 C5/C6의 자동복구를 만족하지 않는다. 파일 rollback 뒤 journal을 없애므로 다음 실행에는 index 소유권을 판단할 복구 자료도 없다.

추가로 journal에 초기 HEAD가 없어 `git commit`은 완료됐으나 pending receipt 기록 전에 종료된 상태와 진짜 pre-commit 상태를 구별할 수 없다. 이 구간에서 작업 파일을 되돌리고 journal을 삭제해서는 안 된다.

**실행 재현:** 설치된 `.venv/bin/python`으로 임시 bare remote와 main checkout을 만들고 synthetic qualified crypto bundle을 stage한 뒤 네 owned paths를 `git add`했다. no-receipt journal을 남긴 상태에서 실제 `run_insights_phase()`를 두 번 호출했다. 원격은 임시 로컬 bare Git만 사용했다.

```text
retry 1 status failed journal False manifest_worktree False
retry 2 status failed journal False manifest_worktree False
remaining_owned_index ['site_docs/insights/_data/crypto/current.json',
 'site_docs/insights/_data/crypto/history.json',
 'site_docs/insights/_data/manifest.json',
 'site_docs/insights/crypto/index.md']
```

**수정 제안:** stage journal에 초기 HEAD와 owned paths/hash를 먼저 durable하게 저장한다. 복구 시 HEAD가 초기 값과 같고 owned index blob이 journal의 new hash 또는 baseline 상태와 일치함을 확인한 뒤 해당 paths만 scoped reset한다. 다른 staged paths를 보존한다. HEAD가 달라졌거나 index identity가 불명확하면 rollback/cleanup 없이 reconciliation이 필요한 상태를 유지한다. 작업 파일·index·journal cleanup 순서를 함께 복구 가능하도록 설계한다.

**필요한 회귀 테스트:** git add 이후/pre-commit crash 후 다음 phase 정상 재개, unrelated staged path 보존, commit 이후/receipt 이전 crash의 rollback 차단, owned index mismatch의 fail-closed 및 journal 보존.

## 초기 발견 후 반영된 수정

| 항목 | 최신 코드 확인 상태 |
| --- | --- |
| backup/journal의 fsync 및 rename 후 parent directory fsync 누락 | `_atomic_write`, directory 생성·cleanup에서 flush/fsync를 추가한 코드 확인. 실제 power-loss 시험은 수행하지 않음. |
| rollback이 뒤쪽 파일 충돌 발견 전 앞쪽 파일을 복구할 수 있음 | 전체 경로/hash preflight 후 restoration 수행을 확인. old_hash 검증도 확인. |
| 새 future/unknown/stale numeric가 last_good=false로 공개됨 | 최신 projection에서 신규 unknown/stale 값을 억제하고 기존 qualified previous만 복원하는 분기를 확인. |
| numeric semantic qualification | public id/unit/provider/scope/methodology/sample/cadence/calendar policy exact-match와 dynamic event definition binding 코드를 확인. |
| 비활성 모듈 rights/retention 철회 | 최신 `_phase`의 inactive baseline sanitation 및 해당 통합 테스트 존재를 확인. |
| 다른 모듈 source failure가 현재 모듈 reason에 영향을 줌 | `rows`가 빈 envelope를 즉시 continue하는 코드 확인. |
| unknown receipt/live writer/cleanup | lease 획득, retained receipt reconciliation, confirmed cleanup 실패 시 성공 결과 보존을 확인. |
| memory/resource | lead가 compact history·streaming canonical·binary Git reads 및 실제 phase resource gate 통과를 보고. reviewer가 리소스 시험을 별도로 실행한 것은 아님. |

현재 확인한 **Critical 0 / High 1 / Medium 0**. H180-01 수정 전에는 all-clear로 판정하지 않는다. 이 수치는 실행·코드 경로로 확정한 findings이며 잠재적인 일반 개선 제안을 포함하지 않는다.

## 검증 출처

- **reviewer 직접 실행:** 위 no-receipt/staged-index crash 재현 1건, 두 재시도의 영구 실패 확인. 파일·소스·테스트는 수정하지 않았다.
- **reviewer read-only 확인:** 범위 내 diff·코드·테스트·계약 및 matched protocols. SOFR/EFFR 2026-07-03 예외는 [NY Fed 공식 발표](https://www.newyorkfed.org/markets/opolicy/operating_policy_260618a)와 대조하여 SOFR의 7월 6일 관찰일 7월 2일 및 EFFR의 7월 3일 발표 유지가 서로 다름을 확인했다.
- **lead 제공 결과:** full suite 6987 passed / 1 existing skip; 최종 집중107 passed; Ruff/format/mypy319/actionlint PASS; 실제 새 커밋의 로컬 bare remote 확인 resource 시험 추가 RSS75.1MiB / CPU1.90s / wall4.08s PASS. 이 결과들은 reviewer가 재실행했다고 표현하지 않는다.
- 최초 `uv run` 재현 요청은 cache sandbox 접근 오류 뒤 승인 대기 중 중단되었다. 이후 설치된 venv로 위 재현을 완료했다. 중단된 명령을 성공한 검증으로 계산하지 않았다.

## 프로젝트 경계 판정

기존 approved LLM CLI/disclaimer/Telegram 경계를 변경한 신규 호출은 diff에서 확인되지 않았다. shared DTO는 models, source collection은 sources, 연결은 orchestrator, 저장은 publisher의 기존 방향을 유지한다. qualification matrix는 비어 있어 실제 공개 권리가 승인됐다는 의미가 없으며 default off를 유지한다. production 운영 Step 8은 이 검토와 별도 pending이다.

기술부채 등록·commit·push·deploy는 수행하지 않았다. H180-01은 이 유닛의 복구 계약에 속하므로 부채로 미루기보다 수정 후 검증이 필요하다.
