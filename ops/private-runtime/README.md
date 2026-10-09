# Investo private CLI runtime

비공개 `murphyGo/investo-runtime` 저장소에서 Codex 브리핑을 실행한다.
`daily-briefing.yml`은 수동 dry-run 템플릿이고, `production-briefing.yml`은
실제 발행용이다. 2026-10-04 공개 Claude daily를 중지하고 비공개 Codex
운영 workflow를 활성화했다. 정확한 SHA, 실행 결과와 남은 확인 사항은
`docs/sessions/2026-10-04-u155-production-activation.md`를 참조한다.

`event-preview.yml`은 별도 수동 비게시 사건 미리보기다. CI와 독립 검토를
통과한 code SHA를 `REVIEWED_EVENT_PREVIEW_SHA`로 고정한다. production의
`REVIEWED_CODE_SHA`를 변경하지 않으며 같은 auth concurrency 잠금을 사용한다.
입력은 기준일, 시장, 로컬에서 만든 임시 recipient 공개키다. publish/Telegram
자격증명을 전달하지 않고 ciphertext만 하루 보관한다. 개인키는 로컬에 둔다.
사건 active/사람 의미 검수/예약 shadow 수용은 미리보기 배치와 별개다.
증거는 `docs/sessions/2026-10-04-news-event-main-and-rollout.md`에 기록한다.

## 설치 전 조건

1. 이 변경을 검토·통합한 공개 Investo의 정확한 커밋 SHA를 확정한다.
2. GitHub 계정이 비공개 Environment Secrets를 지원하는지 확인한다.
   현재 비공개 Environment의 실제 Secret 전달은 run `34384978043`으로
   확인했다. 계정 요금제와 이번 달 포함 분량·과금 제한은 별도 확인한다.
3. 비공개 저장소와 `codex-runtime` Environment를 구성한다.
   `REVIEWED_CODE_SHA` Repository Variable에 검토한 40자리 SHA를 둔다.
4. `daily-briefing.yml`을 비공개 저장소의
   `.github/workflows/daily-briefing.yml`로 복사한다.
5. 실제 모델 이름은 Codex 선택 때 `codex_model` 입력으로 지정한다.
   개인 Codex 프로필의 모델이나 CLI 기본값을 추정하지 않는다.

## 인증 등록

자동화 전용 로그인은 별도의 빈 디렉터리에서 만든다. 기존 개인
인증 파일을 읽거나 복사하거나 로그아웃하지 않는다. GitHub에 등록할
원문을 채팅, 명령 인자, 로그, 문서 또는 커밋에 붙이지 않는다.
아래 명령은 전용 로그인 파일이 준비된 뒤 운영자가 실행할 예시다.

```bash
gh secret set CODEX_AUTH_JSON --repo murphyGo/investo-runtime --env codex-runtime < /absolute/path/to/dedicated-automation/auth.json
```

`CODEX_AUTH_JSON`은 반드시 Environment Secret이어야 한다.
Repository Secret은 큐에 들어갈 때의 값이 고정되어 인증 갱신 시
다음 실행이 오래된 값을 가져올 수 있다. 런타임은 Environment의
Secret 메타데이터 존재를 별도로 확인한다.

| Environment Secret | 용도 |
|---|---|
| CODEX_AUTH_JSON | 전용 ChatGPT 로그인 전체 JSON, 48 KiB 미만 |
| CODEX_SECRET_WRITE_TOKEN | 비공개 런타임 저장소에 한정된 fine-grained token, Environments write |
| CLAUDE_CODE_OAUTH_TOKEN | Claude 선택 시에만 필요 |
| FRED_API_KEY 등 기존 선택 소스 키 | 필요에 따라 현재 소스 구성 이전 |

GitHub writer 토큰은 해당 저장소의 Environment 관리 권한을 가지며
개별 Secret 하나로 권한 범위를 제한하는 ACL은 아니다. 런타임 코드는
저장소·Environment·Secret 이름을 고정한다. 만료일과 권한을 확인한다.
초기 dry-run에는 공개 발행 토큰과 Telegram 토큰을 주입하지 않는다.

Codex는 자체적으로 `auth.json`을 갱신한다. 런타임은 갱신 파일을
검증하고 암호화해 같은 Secret에 저장한 다음 공개 발행 경계를 연다.
실패·취소 때도 보존을 시도하며, 빈 파일이나 손상된 파일로 덮어쓰지 않는다.
저장 실패는 실행 실패이고, 같은 실행에서 Claude/API로 자동 전환하지 않는다.
강제 runner 종료 때는 보존을 보장할 수 없으므로 전용 로그인 재등록이
필요할 수 있다.

## 검증과 운영 전환

- 처음에는 수동 dry-run으로 시황 최종 검증과 인증 보존 결과를 확인한다.
  공개 Git ref와 Telegram 전송이 변하지 않았는지 별도로 확인한다.
- 다음 직렬 실행에서 저장한 인증을 다시 읽는지 확인한다. 실제 토큰
  갱신이 관찰되지 않은 두 번의 성공은 갱신 보존의 실증을 대신하지 않는다.
- CLI 도구 제한, 모델 접근, Linux 실행 시간, Actions 포함 분량 및
  ChatGPT 사용 한도를 확인한다. 모든 CLI 호출은 한 인증 스트림으로 직렬화한다.
- 운영 전환 시 공개 daily 실행을 멈추고 종료를 확인한 뒤 비공개
  스케줄을 설정한다. 두 저장소의 concurrency는 서로 잠그지 않는다.
- 운영용 공개 발행 토큰에는 공개 Investo Contents write와 Pages
  dispatch용 Actions write가 필요하다. 토큰 주입, Git 인증 연결,
  실제 push 및 Pages dispatch는 별도 전환 검토 대상이다.
- rollback은 비공개 실행이 끝난 뒤 공개 Claude daily를 복원한다.
  같은 날짜의 게시·알림 이력을 확인하고 중복 전송을 피한다.

실행 코드와 공개 데이터 checkout을 분리한다. 코드는 승인 SHA에서
비편집 설치하고, 최신 공개 checkout을 cwd로 사용한다. 후자의
`uv run`이나 스크립트를 실행하면 승인하지 않은 코드가 선택될 수 있으므로
설치된 절대 Python 경로와 `-I`를 사용한다. 비공개 Claude child도 빈 cwd/HOME과 설정·MCP·도구 제한을 사용한다.
두 CLI는 취소 시 프로세스 그룹을 종료한다. 225분 runtime 중 마지막
120초는 종료·인증 보존에 예약하고, Codex 생성은 210분까지 제한한다.
기존 finalizer/publisher를
재사용하며 산출물 전체나 인증 디렉터리를 artifact/cache에 올리지 않는다.

## CLI qualification evidence

Codex 0.153.4의 공식 모델 스키마와 도구 등록 코드를 근거로
서버 모델 목록 대신 고정된 로컬 모델 메타데이터에서
`shell_type=disabled`, `apply_patch_tool_type=null`,
`experimental_supported_tools=[]`를 설정한다. 개별 실행 도구,
web/apps/plugins/hooks/agents도 비활성화한다. macOS native `debug models`로
이 모델 목록의 실제 해석을 확인했다(개인 인증 파일 사용 없음). CLI 버전이 다르면 실행을
거부한다. 초기 로컬 HTTP probe는 모델 요청을 포착하지 못해 성공 근거로
사용하지 않았다. 이후 비공개 Linux probe `34384975431`과 선택 모델
probe `34388520247`에서 운영 정책의 실제 요청 도구 목록이 비어 있음을
확인했고, 양성 대조군에는 `update_plan`이 나타났다.

2026-10-03 실계정 dry-run `37130989203`은 `gpt-6-astra`로 세 시장 모두
생성·최종 검증을 통과하고 283.882초에 종료 코드 0으로 끝났다.
`37128670838`에서 실제 인증 갱신을 암호화 저장했고 이후 실행이
저장한 인증을 재사용했다. 공개 발행·알림은 dry-run으로 생략했다.
상세 근거와 남은 활성화 조건은
`docs/sessions/2026-10-03-u155-codex-cutover.md`에 기록한다.

설치에는 공식 릴리스의 native Linux 바이너리와 확인한 SHA-256을 쓴다.
npm registry에서는 0.153.4를 조회하지 못했다. 개인 환경의 CLI 설치나
로그인은 변경하지 않는다.

## 준비된 정기 전환 템플릿 (2026-10-03)

`production-briefing.yml`은 검증이 끝난 뒤 비공개 저장소의
`.github/workflows/daily-briefing.yml`로 설치할 운영 템플릿이다.
`CODEX_PRODUCTION_ENABLED=1`이 아니면 수동/예약 job 모두 실행되지 않는다.
공개 저장소의 daily workflow를 중지하고 실행 중/대기 중 job이 없는지
확인한 뒤 이 변수를 설정한다. 변수와 템플릿 준비만으로 전환 완료를
표시하지 않는다.

- 모델은 기존에 선택한 `gpt-6-astra`, 제공자는 `codex`로 고정한다.
- 평일 07:00/토요일 09:00 KST와 기존 주간 발행 판정을 유지한다.
- `REVIEWED_CODE_SHA`에는 이 템플릿과 인증 helper를 포함해 검토한
  공개 커밋을 지정한다. 최신 archive checkout의 코드는 실행하지 않는다.
- `git-credential-investo.sh`는 `https://github.com/murphyGo/investo`
  목적지에만 게시 토큰을 반환한다. 토큰은 git 설정이나 파일에 저장하지
  않으며 Codex child의 환경에도 전달되지 않는다. 인증 보존 checkpoint가
  성공한 뒤 기존 publisher가 같은 경로 검증·최종 문서 gate를 적용한다.
- PAT push가 시작한 같은 commit의 Pages 실행을 먼저 찾고, 진행 중이거나
  성공한 실행이 없으면 명시적으로 dispatch한다. 실패·취소된 이전 실행도
  재배포 대상이다. Pages 결과는 운영 검증에서 별도로 확인한다.
- pipeline의 0/1/2 종료 코드를 유지하며 Pages 작업도 같은 runtime
  시간 범위 안에서 수행한다.

추가 Environment Secrets:

| 이름 | 범위/용도 |
|---|---|
| `INVESTO_PUBLIC_PUBLISH_TOKEN` | 공개 `murphyGo/investo`만 선택한 fine-grained PAT, Contents 및 Actions 읽기/쓰기 |
| `TELEGRAM_BOT_TOKEN` | 기존 브리핑 봇, 이전 완료 |
| `TELEGRAM_BRIEFING_CHANNEL_ID` | 기존 공개 채널, 이전 완료 |
| `TELEGRAM_OPERATOR_CHAT_ID` | 기존 운영자 대화, 공개 채널과 달라야 함, 이전 완료 |
| `FRED_API_KEY`, `OPENDART_API_KEY` | 기존 소스 구성, 2026-10-03 비공개 Environment 등록 확인 |
| `BEA_API_KEY`, `CONGRESS_API_KEY`, `INVESTO_KRX_SERVICE_KEY` | 기존 공개 실행의 키 재사용, 이전 완료 |

2026-10-04 KST: 기존 공개 Investo의 Telegram 3종과 BEA/Congress/KRX
6개 Secret을 그대로 재사용하도록 비공개 Environment에 등록했다.
사용자에게 이 키들을 다시 발급하거나 수동 입력하도록 요청할 필요가 없다.
이전 run `37136372915`은 대상 Environment의 공개키로 암호화한 값만
전달했고 등록 후 임시 artifact와 일회성 원격 브랜치를 삭제했다.
위 표에서 이 6개와 FRED/OPENDART는 등록 완료이며,
`INVESTO_PUBLIC_PUBLISH_TOKEN`도 2026-10-04 등록을 확인했다.
점검 run `37209080763`에서 Git 연결과 실제 Pages dispatch를 통과했고,
Pages `37209101940`이 성공했다. 운영 run `37209545723`은 3개 시장 모두
최종 검증, 실제 push `e5e59729`, Telegram 148, Pages `37209833667`까지
성공했다. 현재 계정 전체의 잔여 Actions 분량·과금 차단 설정은 미확인이다.

GitHub 저장 Secret은 이름만 조회할 수 있다. 값은 채팅에 전달하지 않고
Environment UI 또는 전용 로컬 파일의 stdin 경로로 등록한다. 개인 GitHub
CLI 로그인 토큰을 운영 게시 토큰으로 복사하지 않는다.

활성화 전 실제 dry-run 결과, 갱신 인증의 다음 job 재사용, 남은 포함
Actions 분량과 초과 과금 차단을 확인한다. Billing API가 현재 CLI의
`user` scope 부족으로 거부되면 권한을 자동 확대하지 않고 계정 소유자가
Billing 화면에서 남은 분량과 차단 설정을 확인한다.

Rollback: private의 `CODEX_PRODUCTION_ENABLED=0`과 workflow 비활성화로
새 실행을 막고 현재 job 종료를 기다린 뒤 public `daily-briefing.yml`을
다시 활성화한다. 이미 공개된 commit과 Telegram 전송 여부를 확인한 뒤
같은 날짜 재실행을 결정한다. 자동으로 Claude를 재호출하지 않는다.

공식 근거:
[Codex 인증 자동화](https://learn.chatgpt.com/docs/auth/ci-cd-auth),
[Codex 설정](https://learn.chatgpt.com/docs/config-file/config-reference),
[0.153.4 도구 등록](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/tools/spec_plan.rs),
[고정 모델 목록](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/models-manager/src/manager.rs),
[GitHub Environment 기능](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

미리보기는 public-data checkout의 고정 commit 출력으로 발행 이력을 읽는다.
같은 SHA의 HEAD를 확인한 뒤 canonical loader를 사용하며, 정상 빈 이력과
읽기 실패를 구분한다. 로컬 미커밋 ledger는 사용하지 않고 Git fetch/write나
production receipt/cursor 쓰기를 수행하지 않는다. 코드 SHA와 데이터 이력
SHA는 별도이며 manifest에는 확인된 데이터 SHA만 기록한다.
