# Event v3 실제 비게시 preview 재개

2026-10-25 KST. 사용자 “진행시켜” 지시에 따라 native v3 개발의 남은 증거 수집을 재개했다.
기존 root의 dirty 파일은 보존하고 별도 public worktree를 현재 `origin/main` `dd113ae4`에서 만들었다.
이 기준과 이전 delivery `3e399447` 사이의 source/scripts/ops/docs는 같고, 차이는 생성 자료뿐이다.

## 최종 실제 생성 확인

동일 source `817b356c75e7e7cf32235cd1b217707e2993e211`의
[세 시장 private preview 40125141798](https://github.com/murphyGo/automation-runtime/actions/runs/40125141798)가
모두 성공했다. runtime workflow SHA는 `a9bd69741cacbbf2c4ab57d9f23f2afd6cd0068e`, target date는
2026-10-23이다. 세 artifact 복호화, Markdown hash 및 각 prompt/stdout recording hash 대조를 통과했다.

| 시장 | sealed 문서 | terminal 사건 | model calls | availability |
| --- | ---: | ---: | ---: | --- |
| 국내 | 1 | 0 | 1 | source_limited |
| 미국 | 1 | 4 | 2 | source_limited |
| 가상자산 | 1 | 0 | 3 | source_limited |

각 시장은 344개 수집, source ok28/zero9/failed2였고 라우팅은 국내145/미국174/코인22였다.
코인은 두 번의 상태 근거 거절 뒤 기존 세 번째 분류 시도에서 통과했다. 근거 없는 사실은 수용하지 않았다.
게시·Telegram·운영 cursor/receipt 쓰기는 전부 false, 사람 수용0/12·verified slot0/8·genuine 예약0이다.
원문은 ignored private 경로에만 있다. [전체 이력과 최종 snapshot](../../aidlc-docs/construction/event-news-v3/private-preview-20261025.json)의
top-level failed/0은 초기 실행 기록이며 `latest_same_source_validation`이 위 최종 결과다.

이는 실제 비게시 생성 성공이다. 국내·코인 0건과 모든 source_limited 상태를 인간 의미 수용으로 바꾸지 않는다.
사람 사전 주석, source body/rights/slot, native viewport, 실제 성능·release·예약 관찰과 legacy 제거는 남아 있다.

최종 source의 exact-SHA [quality 40125122575](https://github.com/murphyGo/investo/actions/runs/40125122575)는
**7,123 PASS/1 skipped(765.72s)**, Node29, Ruff/format777·mypy328 및 전체 policy/docs/Material/calendar 검사를
성공했다. 최종 문서 정합성 독립 검토도 열린 P1/P2=0이다. 마감 기록은 문서만 변경하며 이 검증된
source/test/workflow/config는 유지한다.

최종 repo 변수 재조회에서도 preview pin만 `817b356c`, production pin `35ea6c6e`, production gate1,
기존 schema2 event mode active와 AI report pin/gate는 그대로다. environment override는 없고
공개 workflow template과 private workflow는 기존 `queue: max` 외에는 byte 일치한다.

## 이전 delivery와 이번 검증

`3e399447b804ba1053202b9d17af0ab240d0c3d2`의 정확한
[quality 38166319085](https://github.com/murphyGo/investo/actions/runs/38166319085)는 2026-10-11 19:15:13 UTC에
전체 검사 성공으로 끝났다. 이전 로컬 전체 회귀 7,066 PASS/1 skipped는 당시 코드 증거다.

이번 private workflow 변경은 `6ff635c6258bcf308b28a30d73c2f1ab7ca60b97`의 8줄이며 원격 `main`과
일치를 확인했다. schema 2(default)/3 선택만 추가하고 기존 private queue·auth lock·암호화 설정을 유지했다.
preview 전용 pin은 `eea56bd0`에서 검증된 `3e399447`로 변경했다. production pin `35ea6c6e`,
production gate 1, 기존 event mode active 및 AI report pin/gate는 전후 재조회에서 같았다.
기존 active는 schema 2 운영의 상태이며 v3 활성화를 뜻하지 않는다.

이번 native 진단 보완은 집중 67 PASS(7.03s), Ruff/format 775 files, mypy 328 source files와
paid API·SDK·curated/image guards를 확인했다. 별도 [독립 리뷰](../code-reviews/2026-10-25-event-v3-preview-diagnostics.md)의
열린 P1/P2는 0이다. 해당 코드는 분류 실패에서 이미 존재하는 닫힌 원인만 보존하며 생성/gate/예산은 바꾸지 않는다.

## 실제 preview와 제한

[실제 private preview 40114529910](https://github.com/murphyGo/automation-runtime/actions/runs/40114529910)는
target date 2026-10-23, schema 3, 세 시장으로 수동 실행했다. 로컬 일회용 private key는 ignored 경로의
0600 파일로만 보관하고 Actions에는 public key와 암호화 artifact만 전달했다.

첫 시도는 세 시장 모두 분류 실패로 끝났다(국내 3회, 미국 2회, 코인 3회). 세 artifact는 정상 복호화됐고
각각 실패 manifest만 포함한다. [닫힌 결과와 hash](../../aidlc-docs/construction/event-news-v3/private-preview-20261025.json)를 기록했다.
기존 manifest가 native closed reason을 누락한 문제를 이번 변경으로 수정했다. 미완료 시장이나 실패를
sealed 문서로 세지 않으며 반복·수동 실행을 genuine scheduled 관찰로 세지 않는다.
진단 수정 `1036ff8b`의 [미국 재생 40115832486](https://github.com/murphyGo/automation-runtime/actions/runs/40115832486)은
2회 후 `context.fact_invalid`를 반환했다. 이 코드는 실패 범주이며 원문 응답이 없으므로 정확히 어떤 field/span이
잘못됐는지는 판정하지 않았다. 기존 검증기의 숫자 value-only 참조, source metadata field 역할, 1–240 Unicode
span 규칙을 Stage 1 지시에 명시했다. 검증기·예산·재시도·원본 buffer는 그대로다. 실제 효과는 추가 preview로 확인한다.
이 지시 변경은 로컬 focused 85 PASS(5.63s), 독립 focused 104 PASS와 열린 P1/P2 0을 확인했다.
`6f4f461d`의 [후속 미국 preview 40116589238](https://github.com/murphyGo/automation-runtime/actions/runs/40116589238)는
2회 후 `context.required_missing`으로 끝났다. 필수 item과 actual fact의 metric/unit/period/status refs를
유지해야 한다는 기존 gate 조건도 prompt에 명시했다. 빈 event 배열로 필수 사실을 피하는 응답은 계속 거부한다.
원문 모델 응답이 없으므로 사유 변화만으로 정확한 근본 원인이나 최종 의미 수용을 확정하지 않는다.

`1036ff8b`의 [전체 CI 40115806931](https://github.com/murphyGo/investo/actions/runs/40115806931)는
7069 PASS/1 skipped/2 FAILED(733.52s)였다. 두 실패는 directory/flat 홈 build 검사였다. 당시 테스트가
본문 어디에나 있는 제한 문구를 짧은 홈 요약에도 요구했지만 실제 홈은 별도의 canonical partial/limited
상태를 표시했다. 각 카드의 보이는 품질 문구와 data-quality를 대조하고, 발행본의 기존 canonical status
owner와도 대조하도록 검사를 수정했다. 링크·날짜·미발행 조건은 유지했다. 이 수정과 필수 actual 지시는
로컬 집중 106 PASS(21.43s)를 확인했으며 최종 전체 CI를 별도로 수행한다.
독립 검토는 focused 125 PASS와 홈 품질 변조 4건 거부, 열린 P1/P2 0을 확인했다.
수정 source `e82144f756a30a46fde967de5125eb182933710e`의 exact-SHA
[quality 40117402920](https://github.com/murphyGo/investo/actions/runs/40117402920)는
7,073 PASS/1 skipped(746.33s)와 전체 static/policy/docs/Node/Material/calendar 검사를 성공했다.
다만 같은 코드의 [실제 미국 preview 40117426046](https://github.com/murphyGo/automation-runtime/actions/runs/40117426046)는
분류 2회 후 다시 `context.fact_invalid`였다. 따라서 prompt 보완의 실제 해결 효과나 source/human-ready를 주장하지 않는다.

정확한 입력/응답 조사에 필요한 opt-in R10 model recording을 기존 암호화 preview 안에 추가했다.
기본 false, 최대12회/1MiB, 원문은 ignored private artifact에만 있고 public status에는 담지 않는다.
모델 stderr/argv/auth state는 제외하며 실패에도 기록을 보존하고 incomplete/whole unavailable을 구별한다.
이는 사전 human oracle/전체 ingestion 분모를 대체하지 않는다. 집중80PASS와 독립 검토 P1/P2=0을 확인했으며
새 source 코드의 전체 CI와 실제 기록을 추가 검증한다.

실제 기록 [40119627476](https://github.com/murphyGo/automation-runtime/actions/runs/40119627476)은 complete 2 calls였고
두 응답은 `context.required_missing`이었다. 같은 validator 재생으로 네 required FRED actual의 다른 조건은
모두 충족하지만 unit_refs가 비었음을 확인했다. 입력 source metadata에 단위가 없었다.
[FRED 단위 수리와 primary metadata](../../aidlc-docs/construction/event-news-v3/fred-unit-metadata-repair.md)에
원인·변경·제한을 기록했다. 기존 5개 default series의 원래 unit만 source owner에서 전달하며 unknown은 그대로 둔다.
로컬 focused115/독립130과 네 지표의 합성 native seal1/issue0을 확인했고 실제 결과는 추가 preview로 검증한다.
현재 사람 수용 corpus 0/12, review 0, verified slot 0/8,
genuine v3 예약 0이며 cutover와 legacy 제거는 미실행이다.

FRED 단위 수리 source `29978b46`의 [세 시장 실제 preview 40121638323](https://github.com/murphyGo/automation-runtime/actions/runs/40121638323)는
국내·코인 sealed, 미국 분류 실패로 끝났다. 세 artifact를 복호화했고 sealed Markdown hash도 manifest와
일치했다. 성공 sibling은 모두 `source_limited`/terminal event 0이므로 인간 수용으로 세지 않는다.
미국의 complete 2-call 기록은 metric/unit 메타데이터 좌표가 1차 -1, 2차 +1 codepoint임을 확인했다.
2차 응답에 정확한 위치만 적용한 로컬 진단은 기존 classifier를 통과했고, 1차의 잘못된 subject field는
여전히 거절됐다. 이 진단을 새 모델 성공으로 집계하지 않는다.

[메타데이터 범위 전달 수리](../../aidlc-docs/construction/event-news-v3/metadata-span-transport-repair.md)는
기존 source-owned chunk별 field 위치를 서버가 계산해 Stage 1과 공유한다. 원본 document/revision,
출력 ContextRef 및 모든 gate는 유지한다. 지도 bytes도 기존 24KiB에 포함하며 필수 문서는 먼저 예약한다.
집중 94 PASS(7.22s), Ruff/format 776/mypy328을 확인했고 독립 검토와 새 실제 검증을 진행한다.

FRED 수리 source `29978b46e5d11ce03499a664d9f68565422f65ad`의 exact-SHA
[quality 40121607322](https://github.com/murphyGo/investo/actions/runs/40121607322)는
7,098 PASS/1 skipped(758.93s), Node29와 static/policy/docs/Material/calendar 전체 검사를 성공했다.
직전 recording source `8e423add`의 [quality 40119569331](https://github.com/murphyGo/investo/actions/runs/40119569331)도
7,086 PASS/1 skipped(623.07s)와 전체 검사 성공이었다. 이 CI 성공은 실제 미국 preview 성공과 구별한다.

[후속 미국 preview 40122882991](https://github.com/murphyGo/automation-runtime/actions/runs/40122882991)는
source `8ee57c71`로 분류를 1회에 통과하고 합성 2회 후 `event.entity_unsupported`로 끝났다.
complete 3-call 기록을 같은 document/binding/plan으로 재생하고 protected JSON 13,345 bytes 일치도 확인했다.
모든 필수 주체·대상은 포함했지만 일반 성분명 ‘관측값’, ‘단위’를 근거 없는 이름으로 판정한 오탐이었다.
이 두 표현만 기존 generic noun과 같이 처리한 뒤에는 별도의 fact subject ref 누락이 드러났다.
[성분명·근거 전달 수리](../../aidlc-docs/construction/event-news-v3/korean-component-label-repair.md)는
그 누락도 거부하면서 이미 전달된 compact draft.facts의 모든 근거 복사를 Stage 2에 명시한다.
payload·schema·예산·출력 자동수리는 바꾸지 않는다. 두 실제 응답의 로컬 진단은 누락 근거만 보완하면
기존 최종 계약을 통과했다. fresh model 성공과 구별하며 집중94 PASS(3.41s)를 확인했다.

[실제 미국 preview 40123873052](https://github.com/murphyGo/automation-runtime/actions/runs/40123873052)는
source `d44a5df3b7ff75f7cff5132a07768c975157269a`에서 **성공**했다. complete recording 2 calls,
sealed schema 3 문서 1개/terminal event 4개이며 Markdown hash를 복호화 원문과 대조했다.
344개 수집/174개 라우팅, source 상태 ok28/zero9/failed2로 availability는 `source_limited`다.
사람 검수는 pending, 게시·Telegram·운영 cursor/receipt 쓰기는 모두 false다.
같은 source의 [가상자산 40124247148](https://github.com/murphyGo/automation-runtime/actions/runs/40124247148)는
1 call/terminal event0/source_limited로 sealed했다. [국내 40124245399](https://github.com/murphyGo/automation-runtime/actions/runs/40124245399)는
분류 통과 뒤 post_validation 실패였다. 기록 재생은 한 텍스트 fact의 status_refs 부재로 canonical owner가
identity.fact_unbound를 반환함을 확인했다. 다른 두 event는 fact가 없어 정상 정규화됐다.
[상태 근거 재시도 수리](../../aidlc-docs/construction/event-news-v3/status-proof-retry-repair.md)는
기존 canonical 필수 조건을 classifier 수락 시점에도 검사해 기존 재시도로 보완할 수 있게 한다.
lower context의 limited-support 평가는 유지하며 없는 상태를 코드가 추정하지 않는다.
직전 `d44a5df3`의 [전체 CI 40123857168](https://github.com/murphyGo/investo/actions/runs/40123857168)는
7,117 PASS/1 skipped(761.90s), Node29 및 전체 static/policy/docs 성공이다.

## Source capture와 viewport

기존 Fed/CFTC/FSC adapter의 실제 feed capture와 u167 factory 결과는
[u173 count/hash 기록](../../aidlc-docs/construction/u173-official-event-source-slot-qualification/code/feed-parser-capture-20261025.json)으로 남겼다.
Fed/CFTC 36개 context와 정확한 span 84개 대조는 성공했고 FSC adapter는 실패했다. 원문은 ignored private 저장소에만
있으며 feed capture를 official body·rights·필수 slot·runtime 성공으로 바꾸지 않는다.
추가 기존 SEC/Nasdaq 한정 capture 69개 context/148개 span도 성공했다. 합계 105개 context/232개 span이며
공개 추가 기록은 [structured count/hash](../../aidlc-docs/construction/u173-official-event-source-slot-qualification/code/structured-parser-capture-20261025.json)다.

Browser 연결은 설치된 runtime이 필요한 `browser-service.mjs`의 이전 버전 경로를 찾지 못해 실패했다.
실제 390×844/1440×900 화면은 미검증이다. MkDocs 빌드를 화면 수용으로 대신 기록하지 않는다.
