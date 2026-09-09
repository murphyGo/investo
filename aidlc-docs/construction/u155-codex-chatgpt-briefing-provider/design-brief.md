# u155 — Claude + Codex 시황 생성 선택 기능

**Date**: 2026-09-09 KST
**Status**: FD/NFR/Infrastructure 승인 완료; 로컬 Steps 1–7 구현·검증 완료. 운영 구성·활성화 별도.
**Baseline**: `origin/main@f93def427be2d16365685102c7e9dcf1cad073e1`
**Branch**: `codex/codex-provider-20260909`

## 승인된 요청과 이번 산출물

사용자 요청: “Claude와 더불어 Codex 옵션을 추가하고, Codex CLI +
ChatGPT 로그인 방식으로, 시크릿 정보는 githun actions secret으로
등록하는 방식으로 가능?” 이후 별도 비공개 실행 저장소 제안에
“오케이. 일단 작업 시작해줘”라고 응답했다.

승인된 범위는 Claude 유지, Codex 선택 기능, 구독 로그인, Actions
Secrets 보관, 비공개 실행 환경이다. 사용자가 기능 설계 승인과 다음
NFR·인프라 설계 진행을 묻는 인계에 “진행시켜”라고 답했다.
2026-09-08T18:06:59Z에 R1–R14 기능 설계 승인을 기록했다.
이후 “구현까지 진행시켜”로 NFR 수치와 구체적 인프라 배치 및 로컬
구현을 승인했다. 코드·비공개 수동 workflow 템플릿·합성 테스트를 작성했다.
원격 저장소 생성, 인증 복사·등록, 실제 계정 생성·발행과 스케줄 전환은
아직 실행하지 않았다.

## 변경 후 운영 흐름

1. 기본 제공자는 Claude다. 비공개 실행 저장소에서 `claude` 또는
   `codex`를 선택한다. 명시하지 않으면 Claude로 실행한다.
2. Codex를 선택하면 ChatGPT 로그인 세션을 사용하는 CLI에 현재와
   같은 수집 자료와 두 단계 프롬프트를 전달한다.
3. Codex가 갱신한 인증 파일을 Actions Environment Secret에 보존한다.
4. 기존 수치·출처·링크·면책·최종 문서 검증을 통과한 결과만 기존
   발행 경로로 전달한다. 인증 저장 실패는 신규 공개 발행을 막는다.
5. 운영 전환 이후 실행 스케줄의 소유자는 비공개 저장소 한 곳이다.
   공개 저장소는 코드와 게시 결과 및 Pages를 보유한다.

Codex 실패 시 같은 실행 중 Claude나 유료 API로 자동 전환하지 않는다.
운영자는 다음 수동 실행에서 Claude를 선택할 수 있다.

## 기준 코드에서 확인한 변경 지점과 구현 연결

| 기준 지점 | 구현 전 확인 사실 | 구현 연결 |
|---|---|---|
| `briefing/claude_code.py` | `["claude", "-p"]`, stdin 프롬프트, 결과 공통 타입 | 기존 Claude 호환 진입점을 유지하고 공통 제공자 호출로 연결 |
| `briefing/_core/orchestration.py` | 분류·본문 두 단계 모두 Claude 직접 호출 | 실행 시작에 결정한 동일 제공자 설정 전달 |
| `briefing/generation_contract.py` | `GenerationInput.runner` 주입 경계 존재 | 기존 runner 주입으로 설정·세션 객체 전달, fake runner 호환 |
| `__main__.py`, `scripts/check_daily_briefing_env.py` | Claude 토큰이 항상 필수 | 제공자별 필수 인증 검사를 같은 정책으로 통일 |
| `_internal/redaction.py`, `briefing/leak_guard.py` | 공통 R13 정책 | 신규 인증 진단의 원문 배제 및 합성 비밀값 회귀 |
| `orchestrator/pipeline.py` | 생성·발행·알림이 한 호출 안에서 진행 | 공개 발행 직전 인증 저장 checkpoint와 종료 시 보존 추가 |
| `publisher/git_ops.py` | cwd의 origin/main으로 발행 | 비공개 실행 코드와 공개 발행 checkout을 명확히 구분 |
| `.github/workflows/daily-briefing.yml` | 공개 저장소에서 실행, 저장소 단위 concurrency | 기존 Claude 기본값 유지; Codex 인증 workflow는 비공개 전용 |

경로는 `src/investo/` 기준이다(명시적으로 다른 루트를 쓴 항목 제외).
모델 이름 한 줄 교체로 끝나는 변경이 아니다. 특히 인증 보존을
workflow 마지막 단계에만 넣으면 이미 발행한 뒤 저장 실패가 발견된다.

기준 코드의 운영 override도 확인했다: CLI 호출당 1,800초, 미국 시장 공유
3,900초, 국내·크립토 공유 5,700초이며 Actions job 상한은 240분이다.
따라서 모듈 기본 120/300초만 보고 비공개 Actions 사용량이나 직렬화
후 성능을 추정하지 않는다. 상한은 NFR에 고정하고 실제 사용량은 운영 검증에서 측정한다.

## GitHub Actions Secrets 설계

승인된 NFR/Infrastructure 배치는 기존 단일 프로세스 발행 구조를
유지하면서 하나의 `codex-runtime` Environment에 별도 권한 토큰을 둔다.
Codex child에는 전용 인증 파일 위치만 전달하며 writer·발행 토큰과
Telegram·소스 자격 증명은 전달하지 않는다.

| 고정 이름 | 위치 | 용도 |
|---|---|---|
| `CODEX_AUTH_JSON` | 비공개 저장소의 `codex-runtime` Environment Secret | 자동화 전용 ChatGPT 로그인으로 만든 전체 인증 파일 |
| `CODEX_SECRET_WRITE_TOKEN` | 같은 비공개 환경 | 해당 저장소의 Environment secret 갱신; 최소 `Environments: write` 권한 |
| `INVESTO_PUBLIC_PUBLISH_TOKEN` | 같은 비공개 환경(활성화 단계) | 공개 Investo 결과 commit/push와 명시적 Pages dispatch에 필요한 별도 권한 |
| 기존 Telegram/선택 소스 Secret | 비공개 실행 환경 | 현재 파이프라인에 필요한 값만 이전; 값은 문서에 기록하지 않음 |

`INVESTO_LLM_PROVIDER`, `INVESTO_CODEX_MODEL`, 검토된 코드 SHA는
비밀이 아닌 설정이다. Codex 모델은 활성화 전에 명시적으로 고정하고
계정 접근을 확인한다. 로컬 프로필의 모델을 운영 기본값으로 추정하지 않는다.
코드·템플릿에서 이름을 고정했으며 실제 등록은 아직 없다.

Repository Secret은 workflow가 queue될 때, Environment Secret은
참조 job이 시작할 때 읽힌다. 따라서 회전하는 인증은 Environment에
저장하고 workflow 전체를 인증 세션별 고정 concurrency group으로
직렬화한다. 그룹에 branch/date/provider를 넣어 동시에 실행시키지 않는다.
동일 인증 파일의 로컬·다른 저장소 재사용도 금지한다.

## 준비·활성화 경계

- 코드, 비공개 workflow 템플릿, 합성 인증 테스트는 로컬 구현했다.
- 비공개 저장소 이름은 `murphyGo/investo-runtime`을 제안한다.
  읽기 API는 404였으며 미생성/접근 불가를 구별하지 못한다.
  비공개 Environment Secrets 이용에 필요한 GitHub Pro 이상 여부는
  계정 API의 `plan: null`로 확인할 수 없어 사용자에게 질문했다.
- 초기 실행은 수동 dry-run이며 공개 push/Telegram/Pages를 실행하지 않는다.
- GitHub 비공개 Actions 무료 분량, 소요 시간, ChatGPT 사용 한도를 확인한다.
  구독 방식이라고 전체 운영비가 자동으로 0원이 되는 것은 아니다.
- 전환 때 공개 daily workflow를 멈추고 기존 실행 종료를 확인한 뒤
  비공개 스케줄을 켠다. 두 저장소의 concurrency는 서로 잠그지 않는다.
- rollback은 비공개 실행을 멈춘 뒤 공개 Claude 스케줄을 복원한다.
  같은 날짜의 게시·알림 여부를 확인하여 중복 전송을 피한다.

## 근거와 한계

2026-09-09 공식 문서와 GitHub API에서 확인했다. 공개 저장소
`murphyGo/investo`에 ChatGPT 인증 파일을 주입하는 설계는 채택하지 않는다.
공개 코드의 검토된 SHA를 비공개 작업에 사용하는 것은 이 설계의
추론이며, OpenAI가 Investo의 구성을 개별 승인했다는 의미는 아니다.

- [Codex 비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode):
  stdin과 최종 출력으로 생성 경계를 연결할 수 있다.
- [Codex 계정 인증 자동화](https://learn.chatgpt.com/docs/auth/ci-cd-auth):
  신뢰할 수 있는 비공개 자동화, 갱신 파일 보존, 동일 세션 직렬 사용.
- [GitHub Secret 읽기 시점](https://docs.github.com/en/actions/reference/security/secrets#when-github-actions-reads-secrets):
  대기 중인 workflow의 Repository Secret snapshot 문제.
- [Environment Secret API](https://docs.github.com/en/rest/actions/secrets#create-or-update-an-environment-secret):
  환경 secret write 권한과 암호화된 갱신 요청.

구독 인증의 영구 지속을 보장하지 않는다. 강제 종료·토큰 회전 직후
저장소 장애 등에는 새 자동화 전용 로그인으로 재등록이 필요할 수 있다.

## 문서 탐색

- [구현·검증 내역](code/summary.md)
- [독립 코드 리뷰](code/code-review.md)
- [Functional Design plan](../plans/u155-codex-chatgpt-briefing-provider-functional-design-plan.md)
- [Business logic](functional-design/business-logic-model.md)
- [Business rules](functional-design/business-rules.md)
- [Domain entities](functional-design/domain-entities.md)
- [Code Generation plan 및 검증 기준](../plans/u155-codex-chatgpt-briefing-provider-code-generation-plan.md)
- [NFR 및 검증 상한](nfr-requirements/nfr-requirements.md)
- [기술 선택](nfr-requirements/tech-stack-decisions.md)
- [인프라 배치 및 활성화 조건](infrastructure-design/infrastructure-design.md)
- [실행·실패·복구 순서](infrastructure-design/deployment-architecture.md)
