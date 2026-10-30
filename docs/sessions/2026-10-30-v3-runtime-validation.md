# 2026-10-30 — 기사형 v3 전달·실제 원문 검수

사용자는 검토한 변경의 커밋·푸시와 DART 원문 확인·비게시 기사 재생성을 승인했다. 공유 작업공간은 보존하고 분리 checkout에서 승인된 30개 파일만 커밋했다. `02bbcd2e`를 최신 데이터 확장 `b121ca01`과 통합한 공개 `a7e89802`를 main에 전달했다. state/audit 충돌은 양쪽 기록을 보존해 해결했고 archive/site_docs·다른 데이터 확장 코드·의존성은 그대로 유지했다.

## 전달과 실제 실행

- [정확한 코드 CI](https://github.com/murphyGo/investo/actions/runs/40924747358): **7,679 PASS/1 known skip/745.87초**, Python3.11.9 및 나머지 품질 단계 SUCCESS. 통합 집중299·독립101 PASS, 잔여 C/H/M0.
- private `6446e077`은 DART 수동 workflow 한 파일만 추가했다. 기존 daily/event-preview와 인증 queue:max를 보존했다. 원격 파일의 Git blob `8877cf36c066c6c826954a9a2b44653a1575f2af`가 승인 template과 일치한다.
- CI 후 preview pin만 `aa51e6be`→`a7e89802`로 갱신했다. 다른 세션에서 갱신된 production pin `91d5a4f3`를 보존했다. 실제 운영 schema·게시·알림·cron 설정은 변경하지 않았다.
- [DART 점검40926975241](https://github.com/murphyGo/automation-runtime/actions/runs/40926975241): 공시 `20261027000337`, HTTP200/요청1회, ZIP13,524bytes·XML79,039bytes·파일1개·980nodes·최대depth9. 암호문·복호화 파일·원본 해시와 0700/0600 경계를 확인했다. source qualification은 발급하지 않았다.
- [세 시장 preview40926979318](https://github.com/murphyGo/automation-runtime/actions/runs/40926979318): 국내/미국/crypto 분류1/7/2개, 작성 후보1/1/2개. 각2calls 뒤 `article.composition_invalid`로 종료했다. 세 작성 batch는 JSON schema를 통과했고 모든 prompt/stdout hash를 대조했다. 봉인·게시·알림은0이며 사람 수용으로 세지 않는다.

## DART 원문에서 확인한 범위

이는 **전환사채 발행 결정의 정정 공시**이며, 발행 계획을 완료된 발행으로 해석하면 안 된다. 발행 주체·결정 종류·정정 상태·금액/전환 조건·공시 locator의 다섯 후보가 있다. 원문에는 정정 전후 수치와 다른 차수의 채무도 함께 있어 단순 문자열 평탄화나 첫 금액 선택은 안전하지 않다.

COMPANY-NAME/AREGCIK, DOCUMENT-NAME의 ACODE와 PL_KND/SEQ_NO, CORRECTION/CRT_RSN/CRT_PLN 및 정정 후 열에 대응하는 조건 필드를 검토했다. XML 본문에는 접수번호 필드가 없다. 요청한 rcept_no·동일한 XML 파일명·응답 digest·기존 viewer URL을 함께 결속해야 한다. 정확한 공표 순간도 증명되지 않았다.

따라서 권리·접근 범위, versioned bounded XML→context parser, 정정 후 열과 정확한 source refs, clock 정밀도, context/policy/fixture hash 및 실제 factory replay가 남는다. **DART blocked·기존 source2 verified/runtime0·activation=false를 유지**한다. 이번 결과는 수집 가능성을 확인한 진단 증거다.

## 작성 결과의 차단 원인과 후속 수정

원래 packet과 source refs로 결정론적 검사를 재생했다. Fed 문장들은 수치·역할 근거가 유효했지만, 이니셜 마침표와 일반 개념어·관형형을 미확인 기관명으로 탐지했다. terminal period 처리를 대칭화하고, 이니셜은 인접한 전체 이름을 같은 원문 구간에서 확인하도록 보완했다. 서로 다른 사람의 이니셜 결합·대소문자/보이지 않는 문자 우회·서로 떨어진 refs를 거절하며, 인접한 packet span 경계를 가로지르는 진짜 이름은 보존한다. 수치 검사는 기존 방식 그대로다.

증가세/축적/표결과 되돌리는/만드는는 정확한 일반 개념·문법 형태로만 처리한다. 이 단어를 포함한 새 회사명은 계속 원문 근거를 요구한다. crypto 후보의 주체 없는 ‘소개됐다’는 허용하지 않았다. 회사 발언이 없는 제품 설명은 작성기가 ‘원문에서는 … 설명한다’처럼 문서에 귀속하도록 지시하고, 새 policy hash로 이전 readiness 재사용을 거절한다.

수정 후 기록된 Fed 후보3개·20문장의 atom/role/precheck는 통과했다. 원래 crypto의 agentless 문장은 여전히 `article.attribution_missing`이다. 이 결과는 녹화된 결정론적 검사이며 새 모델 review·봉인·사람 수용은 아니다. 독립 검수와 정확한 후속 코드 CI 및 실제 재생성 결과를 [검수 보고서](../cross-checks/2026-10-30-v3-runtime-validation.md)에 이어 기록한다.

후속 집중273PASS/3.35초, 독립101PASS/1.45초·잔여C/H/M0, Ruff/format852·mypy359 PASS다. 최대48KiB 근거를 포함한 composition prompt는59,700bytes이고 composition prompt 전체 크기65,536bytes는 허용하고65,537bytes는 거절했다. 이전 policy readiness는 terminal/finalizer 양쪽에서 거절했다.

## 남은 인수

브라우저 host를 다시 확인했으나 사용할 수 없어 exact viewport는 미완료다. human0/12, v3 실제 예약0, 성능·source 잔여·운영 전환·cleanup도 유지한다. [기계 증거](../../aidlc-docs/construction/event-v3-acceptance-20261028/runtime-20261030.json)는 원문과 키를 포함하지 않는다.
