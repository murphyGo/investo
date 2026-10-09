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

`37361460038` 미국은 봉인 성공, SHA-256 `a2d6945dce9ca7798bff7482d3827f1806fd6254431daf815247dc7406011f3f`를 로컬에서 대조했다. 사건0/source_limited이므로 양성 사건 품질 수용으로 계수하지 않는다. `37361465517` 코인은 Actions 성공을 확인했으나, 중단 중 하루 보관 기간이 지나 artifact가 없어 본문/해시를 대조하지 못했다. 이후 로그의 집계 manifest에서 선정1/최종1/상세근거 제한1을 확인했다. 로그상 해시 선언을 실제 파일 대조로 대신하지 않는다. 성공 여부만으로 과거 compliance 원인이 수정됐다고 주장하지 않는다.

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

## 보정 배포와 실제 결과

코드 `269a15dc6753d48ba6f58f0834401400379244a5`를 main에 전달하고 exact remote를 확인했다. [quality37910973447](https://github.com/murphyGo/investo/actions/runs/37910973447)은 최종 전체 **6197/324.34s**와 정적·정책·strict docs·Material 검사를 통과했다. 로컬 전체6195/668.91s는 분류 feedback 추가 전 스냅샷이며, 최종 결합 내용의 전체 증거는 이 원격 CI다.

preview 전용 pin을 해당 코드로 지정했다. private workflow의 SHA 전달3줄은3983069로 커밋했다. 동시 원격f74c040의 AI 보고서 문서3개 때문에 최초 push가 거부되어 이를 merge한 `d432c4a0e1dd909a4c32ad622ffcef89ddf9228d`로 정상 push하고 exact remote를 확인했다. `queue: max`를 제외한 실제 YAML과 검토 template의 동일성을 확인했다. 배포 전 잡힌37911904499는 취소·정리 완료했고 수용에 계수하지 않는다.

배포 후 [preview37912037986](https://github.com/murphyGo/investo-runtime/actions/runs/37912037986)을 같은 대상일2026-10-08로 실행했다. 독립 live 수집이므로 동일 입력 replay나 특정 retry 사용 여부의 인과 증거로 과장하지 않는다.

| 시장 | 이력 조회 | 선정/최종/요약 | 상세근거 제한/완전설명 | 상태 |
|---|---|---|---|---|
| 국내 | 정상, data SHA269a15dc | 5/5/3 | 5/0 | sealed, 본문 hash 일치 |
| 미국 | 정상, data SHA269a15dc | 3/3/3 | 3/0 | sealed, 본문 hash 일치 |
| 코인 | 생성 실패 manifest에는 미기록 | 검증된 최종 문서 없음 | 미평가 | synthesis3회 후 event.entity_unsupported |

국내 본문 SHA-256은 `e3cd2313fb6cfc4ca6fb5c46b91420b41e2e0ca510b6ae320eb1e2e39fdab936`, 미국은 `910f4fecb658d04ceb229be74464b7050d504c51f6882928b2945c112e03a420`다. 각 artifact를 완료 직후 내려받아 실제 파일과 대조했다. 두 시장 모두 unsupported0/issue0, 선택 사건의 본문 반영률1.0, qualified coverage0.0이다. 상세 근거가 제한된 사건을 완전한 설명으로 표시하지 않는다. 게시·알림·production receipt/cursor 쓰기는 모두 false다. 실제 사건 보존은 확인됐지만 frozen12 사람 의미 검수와 뉴스 풍부한 날의 외부 baseline 수용은 여전히 별도다.

코인은 synthesis3회 후 `event.entity_unsupported`로 실패했다. 원문을 보관하지 않으므로 어떤 개체/문장이 원인인지 추정하지 않는다. 앞선 `compliance.generated/action.11`과 다른 최신 결과이며 이전 금지 표현 문제의 영구 해결을 뜻하지 않는다. 이번 run 전체 Actions 결과는 failure이고, 국내·미국 두 성공을 취소하거나 전체 성공으로 합치지 않는다. 모델 호출을 더 늘려 성공할 때까지 반복하지 않았다.

시장별 job은 국내09:33:54~09:37:53UTC(239초), 미국09:37:57~09:43:35UTC(338초), 코인09:43:38~09:50:37UTC(419초)다. 세 job의 setup/auth를 포함한 순차 미리보기이며 production end-to-end p95 측정과 동일하지 않다. 성능 수용이나 기존 DEBT-090 완료를 주장하지 않는다.

최종적으로 main 통합·코드 검증·private preview 배포·예약 shadow5회 관찰은 완료됐다. 사건 본문 active, 뉴스 cursor active, 신규 공식 본문 HTTP는 off다. frozen12 사람 점수표는12행 모두 비어 있고 뉴스 풍부한 날의 외부 사람 baseline도 없다. 실제 사건 보존 증거는 국내5·미국3으로 확보했으나 상세 근거 제한과 코인 실패를 포함한 운영 수용은 pending이다. active 첫3회 게시/알림/Pages는 아직 실행할 조건을 충족하지 못했다.

## 동시 u155 저장소 이름 변경 — 09:54 UTC 스냅샷

별도 사용자 승인 작업의 [u155 이름 변경 계획](../../aidlc-docs/construction/plans/u155-shared-runtime-rename-plan.md)에 따라 private 저장소가 같은 repository ID로 `murphyGo/automation-runtime`으로 변경됐다. main의 이름 변경 준비 커밋9ff1bcbc는 CI37912699732를 통과했으며 현재 작업트리에 그대로 보존했다. 뉴스 보정 코드도 그 조상이다.

09:54 UTC 원격 값은 production pin `ca0ef610cdaafea7de188551f06d2107247e8472`, preview pin `9ff1bcbc5be79d9e811676c56e4e5e7069ed41de`, `CODEX_PRODUCTION_ENABLED=0`이다. private daily와 preview workflow는 disabled_manually, 새 이름의 diagnostic37914320588은 실행 중이다. 이는 이름 변경 자격검증 동안의 의도적인 중지이며 앞선 운영1/기존pin 기록은 그 이전 시점이다. 이 작업은 별도 이전 담당자의 중지·코드 지정값을 덮어쓰지 않았다. 이후 정상 스케줄 복원은 해당 u155 계획의 자격검증 및 상태 복원 단계로 추적한다. 역사적 run의 이전 저장소 URL은 GitHub의 같은 저장소 이름 변경 경로를 통해 연결된다.
