# Event v3 실제 비게시 preview 재개

2026-10-25 KST. 사용자 “진행시켜” 지시에 따라 native v3 개발의 남은 증거 수집을 재개했다.
기존 root의 dirty 파일은 보존하고 별도 public worktree를 현재 `origin/main` `dd113ae4`에서 만들었다.
이 기준과 이전 delivery `3e399447` 사이의 source/scripts/ops/docs는 같고, 차이는 생성 자료뿐이다.

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
현재 사람 수용 corpus 0/12, review 0, verified slot 0/8,
genuine v3 예약 0이며 cutover와 legacy 제거는 미실행이다.

## Source capture와 viewport

기존 Fed/CFTC/FSC adapter의 실제 feed capture와 u167 factory 결과는
[u173 count/hash 기록](../../aidlc-docs/construction/u173-official-event-source-slot-qualification/code/feed-parser-capture-20261025.json)으로 남겼다.
Fed/CFTC 36개 context와 정확한 span 84개 대조는 성공했고 FSC adapter는 실패했다. 원문은 ignored private 저장소에만
있으며 feed capture를 official body·rights·필수 slot·runtime 성공으로 바꾸지 않는다.
추가 기존 SEC/Nasdaq 한정 capture 69개 context/148개 span도 성공했다. 합계 105개 context/232개 span이며
공개 추가 기록은 [structured count/hash](../../aidlc-docs/construction/u173-official-event-source-slot-qualification/code/structured-parser-capture-20261025.json)다.

Browser 연결은 설치된 runtime이 필요한 `browser-service.mjs`의 이전 버전 경로를 찾지 못해 실패했다.
실제 390×844/1440×900 화면은 미검증이다. MkDocs 빌드를 화면 수용으로 대신 기록하지 않는다.
