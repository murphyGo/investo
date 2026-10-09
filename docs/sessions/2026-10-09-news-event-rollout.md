# 사건 시황 운영 검증 — 2026-10-09

main 통합과 기존 발행 경로의 shadow 운영은 완료됐다. 실제 예약 관찰은 **5/5회**다. 사건 본문 active의 수용은 아직 완료되지 않았다. frozen12 사람 검수와 뉴스가 풍부한 날의 사람 baseline이 없고, 실제 사건 설명을 포함한 v2 미리보기의 수용도 남아 있다. 이 기록은 [이전 통합 기록](2026-10-04-news-event-main-and-rollout.md)의 후속이다.

## 원격 코드와 운영 owner

수정 코드 `1bb7d23ccfcbed8aadc522fb58c8da2c69b3f326`은 exact-SHA [quality37344940921](https://github.com/murphyGo/investo/actions/runs/37344940921)에서 전체6187/309.55s와 모든 gate를 통과했다. 로컬 전체6187/669s, 독립68/3.53s CLOSED도 확인했다. 이후 main `f3d09eb890b51f3018249ea6d4af52f173f7bbe8`까지 네 번의 archive/site 발행만 추가됐고 실행 코드·테스트·워크플로·의존성은 동일하다. 격리 작업트리를 fast-forward하여 모든 발행을 보존했다.

private `murphyGo/investo-runtime`이 유일한 예약 owner이고 공개 daily는 중지 상태다. `CODEX_PRODUCTION_ENABLED=1`, production pin `056dd8a1b4a8e599f44519e54b5bf4f486275dbd`를 유지한다. preview는 별도 reviewed pin을 사용한다. private main `ce772cf5`의 AI 보고서 변경과 동일 인증 잠금의 `queue: max`를 보존한다.

## 실제 예약 관찰 5회

| 실행일 KST | schedule run | 대상일 | 결과 | 게시 commit | Telegram | 성공 Pages |
|---|---|---|---|---|---|---|
| 10-05 | 37248296267 | 10-02 | 3발행, 국내 numeric degradation | 587787f3 | 149 | 37248604347 |
| 10-06 | 37402699684 | 10-05 | 3발행, 국내 numeric degradation | 3438a292 | 150 | 37403257144 |
| 10-07 | 37556640961 | 10-06 | 3발행, 국내 numeric degradation | 97282825 | 151 | 37556973254 |
| 10-08 | 37714190444 | 10-07 | 3발행, 전부 finalized | c3e21239 | 152 | 37714534129 |
| 10-09 | 37872017717 | 10-08 | 2발행, 코인 trust_blocked, partial/exit2 | f3d09eb8 | 153 | 37872333025 |

모두 GitHub event=schedule, replay=False다. 95개 source/segment 관측창에서 fetch/cursor 비변경, 15개 시장 관찰에서 reservation_starved=False를 확인했다. 첫 회차는 주말 직후다. 뉴스 수가 많다는 사실만으로 외부 주요 뉴스 포착률이나 뉴스 풍부한 날의 사람 수용을 대신하지 않는다. 다섯 번째 실패도 실제 관찰로 기록하되 정상 발행으로 바꾸지 않는다.

10-09 실행은 생성3개 성공 후 코인만 `markdown.broken_numeric_bold`로 최종 검증에서 차단됐다. 국내·미국은 정상 게시됐고 Telegram153과 Pages가 성공했다. pipeline207.757s, partial/exit2다. 코인 문서를 게시하거나 기존 archive를 재작성하지 않았다. 현재 legacy production의 부분 실패이며, 같은 날 v2 preview의 compliance 실패와 원인이 다르다.

추가 네 발행 SHA 각각의 quality와 Pages 성공을 확인했다. 10-05~10-08의 실제 게시11개 URL은 HTTP200이며 저장 문서의 긴 문단262개가 모두 공개 HTML에 존재했다. 현재 main에 production event receipt/news cursor/news window 경로가 없음을 재확인했다.

## 실제 비게시 미리보기

`37361460038` 미국은 봉인 성공, SHA-256 `a2d6945dce9ca7798bff7482d3827f1806fd6254431daf815247dc7406011f3f`를 로컬에서 대조했다. 사건0/source_limited이므로 양성 사건 품질 수용으로 계수하지 않는다. `37361465517` 코인은 Actions 성공을 확인했으나, 중단 중 하루 보관 기간이 지나 artifact가 없어 본문/해시/사건 수는 검증하지 못했다. 성공 여부만으로 과거 compliance 원인이 수정됐다고 주장하지 않는다.

최신 대상일2026-10-08의 [preview37909440445](https://github.com/murphyGo/investo-runtime/actions/runs/37909440445)는 다음과 같다. 세 artifact를 보관 기간 안에 내려받았으며 원본 모델 응답은 보관하지 않는다.

| 시장 | 결과 | 실제 관찰 |
|---|---|---|
| 국내 | sealed | 후보136, selected0/terminal0, source_limited; 본문 SHA `3e59a93aed7de000121be5271abbdcf080850c29ada9b50600fc11ed9f02e5b3` 일치 |
| 미국 | classification2회 후 실패 | `classification.invalid_evidence`, `evidence.fact_metadata_missing` |
| 코인 | finalization 실패 | `compliance.language`, `compliance.generated`, `compliance.rule.action.11` |

코인의 rule action.11은 현재 고정 catalog의 `청산`이다. 생성 본문에 금지어가 있었다는 것까지만 확인되며, 원문을 보관하지 않아 문장 맥락을 추정하지 않는다. 정책을 완화하거나 보호된 finding을 지워 성공 처리하지 않는다.

## 발견한 연결 문제와 제한된 보정

미리보기 script가 `event_baseline_available=False`를 항상 전달했다. 기존 canonical loader는 유효한 원격 Git tree에 ledger가 없는 초기 상태를 정상적인 빈 이력으로 정의한다. 미리보기의 고정 false는 그 상태도 조회 실패로 취급하여 novelty=unknown과 detail_limited로 낮췄다. 비공식 기업 사건은 기존 점수40으로 최소45에 못 미칠 수 있었다. 이는 실제 빈 이력과 조회 실패를 구분하는 기존 계약의 연결 문제다.

private workflow의 public-data checkout이 반환한 commit SHA를 전달하고, script는 해당 SHA와 실제 checkout HEAD가 같은지 확인한 뒤 canonical loader로 읽는다. 20초 한도 안의 Git 읽기만 허용하며 fetch/write나 미커밋 ledger 접근은 없다. SHA를 주지 않거나 이력 읽기에 실패하면 보수적인 unavailable을 유지한다. 점수·상한·검증 규칙은 바꾸지 않는다. 실제 파이프라인 회귀로 같은 비공식 기업 사건이 정상 빈 이력에서는 보존되고 조회 불가에서는 제한됨을 확인했다.

최신 미국의 기간/단위 근거 실패는 별도 문제다. Stage1의 기존 반복 요청에 해당 고정 오류가 있을 때만 같은 fact가 참조한 문서에서 period/unit을 정확히 복사하고 없으면 null로 두도록 안내를 추가했다. 근거·수치·actual/forecast 구분과 최대 시도 횟수를 유지한다. 원본 잘못된 응답을 다음 prompt나 로그에 삽입하지 않는다.

집중70/7.21s, Ruff/format668/mypy290, workflow actionlint PASS. 독립86/8.70s 및 리뷰 CLOSED/P1P2없음, strict docs/Material PASS. 전체 회귀·최종 코드 원격 CI·실제 재실행 결과는 후속으로 기록한다. 전체 로컬 회귀가 시작된 뒤 추가한 분류 feedback은 집중 검증과 최종 exact-SHA CI에서 별도 검증한다.
