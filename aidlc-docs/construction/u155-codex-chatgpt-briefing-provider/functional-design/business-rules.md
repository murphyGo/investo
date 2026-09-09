# u155 — Business Rules

**Status**: R1–R14 approved by “진행시켜”, 2026-09-09 KST.

## R1. 제공자 선택

`INVESTO_LLM_PROVIDER`는 `claude`와 `codex`만 지원한다.
미설정/공백은 Claude, 그 외 값은 configuration error다.
선택은 실행 시작에 한 번 고정하며 실패 중 제공자 자동 전환은 없다.

## R2. Claude 호환

기존 Claude 인증, 프롬프트, fake runner, 분류와 본문 parser, 기본
정책을 유지한다. Codex를 사용하지 않는 실행에 Codex 바이너리·인증·모델
설정을 요구하지 않는다. 기존 import는 호환 shim으로 보존할 수 있다.

## R3. Codex는 ChatGPT 인증만

유효한 자동화 전용 ChatGPT 인증과 명시적 모델이 필요하다.
OpenAI API key, 다른 provider, 외부 token-host 방식으로 자동 전환하지 않는다.
전역 사용자 프로필·MCP·프로젝트 지침에 의존하지 않는 독립 실행 환경을 쓴다.
현재 사용자의 로컬 인증 파일을 검사·복사·로그아웃하지 않는다.

## R4. 프롬프트와 출력

목록형 subprocess 인자와 stdin으로 호출한다. `shell=True`는 없다.
진행 이벤트나 stderr를 최종 시황으로 해석하지 않는다. 결과는 기존
`SubprocessOutcome` 및 parser 계약으로 정규화한다. 모델에게 웹 검색,
명령 실행, 파일 읽기·편집을 맡기지 않는다. 읽기 전용 sandbox만으로
도구가 비활성화되었다고 간주하지 않으며 실제 지원 설정을 검증한다.

## R5. 예산과 직렬 호출

기존 GenerationPolicy와 RetryBudget을 재사용한다. 기본 per-call
120초, 두 단계 공유 300초 및 3회 시도/0·2·8초 backoff를 암묵적으로
늘리지 않는다. 실제 호출자의 override도 보존한다.
같은 인증을 쓰는 모든 Codex 호출은 실행 내부 lock으로 직렬화하고
대기 시간도 wall-clock 상한에 반영한다. 병렬 시장별로 lock을 새로
만들거나 단계 변경 시 예산을 초기화하지 않는다.

## R6. 실행·인증의 단일 소유자

비공개 workflow는 세션당 고정 concurrency group을 쓴다.
branch/date/provider별로 그룹을 나누지 않고 실행 중인 job을 새 실행이
취소하지 않는다. FIFO/모든 대기 작업 실행을 보장한다고 설명하지 않는다.
한 인증 파일은 같은 자동화 스트림에서만 사용한다.

## R7. 회전하는 Secret의 읽기 시점

`CODEX_AUTH_JSON`은 비공개 `codex-runtime` Environment Secret이다.
job 시작 후 읽어야 하므로 Repository/Organization Secret을 회전 저장소로
사용하지 않는다. workflow 직렬화와 Environment 로딩 순서를 통합 검증한다.
같은 이름의 Repository Secret으로 조용히 대체되지 않게 preflight한다.

## R8. 인증 보존

파일은 checkout 밖에서 제한된 권한으로 복원한다. 누락·과대·잘못된
JSON·잘못된 인증 방식·필수 token 누락·symlink는 거부한다.
원문과 token leaf를 출력하지 않는다. 유효한 갱신 파일만 암호화하여
같은 Environment Secret에 write한다. 기존 seed로 최신 파일을 덮어쓰지 않는다.
토큰 갱신은 CLI가 담당하며 별도 OAuth refresh 구현을 만들지 않는다.

## R9. 발행 전 checkpoint와 종료 보존

Codex 실행의 인증 보존 성공을 공개 발행의 선행 조건으로 둔다.
생성 실패/timeout에도 갱신된 인증은 보존을 시도한다.
빈 파일이나 invalid 상태로 Secret을 갱신하지 않는다.
저장 실패는 operation failure로 남기고 자동으로 유료 API/Claude를 호출하지 않는다.
강제 종료를 정상 종료처럼 처리하거나 영구 인증을 보장하지 않는다.

## R10. 자격 증명 격리

LLM child에는 필요한 최소 환경만 전달한다. Secret 갱신 토큰, GitHub
발행 토큰, Telegram 토큰, 선택 데이터 API 키를 전달하지 않는다.
자식이 읽을 수 있는 git credential/config·작업 디렉터리도 격리한다.
갱신용 자격 증명은 갱신 단계에만, 발행용 자격 증명은 발행 단계에만
제공한다. 모델 입력에 auth 경로·내용·계정 식별자를 포함하지 않는다.

## R11. 진단과 기록

제공자·고정 모델·단계·종료 분류·소요 시간 등 비밀이 아닌 진단만 기록한다.
auth JSON은 Actions masking만 신뢰하지 않는다. 토큰 leaf가 바뀐 이후에도
raw stderr/예외/HTTP body가 로그·summary·Telegram·artifact로 유출되지 않아야 한다.
인증 파일, 전체 CODEX_HOME, raw CLI 이벤트는 artifact/cache에 저장하지 않는다.
합성 인증 fixture만 커밋한다.

## R12. 검증·발행 계약

수집·분류·수치·링크·최종 문서·면책·부분 게시·알림 계약은 그대로 적용한다.
Codex 결과라는 이유로 검증을 생략하지 않는다.
발행 checkout은 고정된 공개 repository/branch이며 임의 입력 URL을 받지 않는다.
동일 날짜 재실행의 기존 commit/no-op 및 알림 행동을 검증한다.

## R13. 비용

추가 LLM API 요금을 사용하는 호출은 도입하지 않는다.
ChatGPT 사용 한도 소진은 생성 실패로 처리한다.
비공개 Actions의 포함 분량/환경 기능/소요 시간은 활성화 때 확인한다.
현재 공개 저장소 무제한 가정을 비공개 실행에 적용하지 않는다.

## R14. 활성화

초기 workflow는 수동 dry-run 전용이다. 공개 발행과 스케줄은 검증
후 별도 운영 전환에 포함한다. 공개 daily와 비공개 daily를 동시에
실행하지 않는다. rollback도 기존 실행 종료와 해당 날짜 발행 사실을 확인한다.
기존 sector-dashboard 활성화/브라우저 gate는 이 단위와 무관하게 유지한다.
