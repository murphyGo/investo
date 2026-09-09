# Investo private CLI runtime

이 템플릿은 별도 비공개 `murphyGo/investo-runtime` 저장소에서 수동
dry-run을 검증하기 위한 구성이다. 공개 Investo의 daily workflow는
기존 Claude로 유지된다. 템플릿을 복사하는 것만으로 운영 전환이 끝나지 않는다.

## 설치 전 조건

1. 이 변경을 검토·통합한 공개 Investo의 정확한 커밋 SHA를 확정한다.
2. GitHub 계정이 비공개 Environment Secrets를 지원하는지 확인한다.
   Pro/Team/Enterprise가 필요하며 현재 계정 요금제는 확인되지 않았다.
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
거부한다. 실제 요청의 도구 목록 전체와 비공개 Linux/model 실행은
아직 입증하지 않았으므로 Step 8에서 전용 인증 실행 전 추가 검증한다.
로컬 HTTP 모의 서버 probe는 모델 요청을 포착하지 못했으며 성공 근거로 쓰지 않는다.

설치에는 공식 릴리스의 native Linux 바이너리와 확인한 SHA-256을 쓴다.
npm registry에서는 0.153.4를 조회하지 못했다. 개인 환경의 CLI 설치나
로그인은 변경하지 않는다.

공식 근거:
[Codex 인증 자동화](https://learn.chatgpt.com/docs/auth/ci-cd-auth),
[Codex 설정](https://learn.chatgpt.com/docs/config-file/config-reference),
[0.153.4 도구 등록](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/tools/spec_plan.rs),
[고정 모델 목록](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/models-manager/src/manager.rs),
[GitHub Environment 기능](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).
