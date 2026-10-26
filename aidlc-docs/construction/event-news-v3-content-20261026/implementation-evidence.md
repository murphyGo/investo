# article_v2 구현·검증 기록

2026-10-26. 사용자 “개발 진행시켜”, “gogo”로 FD/NFR와 구현 진행을 승인했다. 별도 worktree `event-v3-article-development-20261026`, 기준 `4e3fccad`. 기존 root의 관련 없는 dirty 항목은 보존했다.

## 구현된 처리

- u184: preview/production 공통 collection-level 보강, source별 자격/hash/retention, 완결 passage·원문 offset·truncation 진실, Stage1 synopsis와 source-diverse 기존24KiB, Stage2 compact packet48KiB 및 후순위 사건 deferral. 전체 run HTTP6/동시2/20초 유지.
- u185: 한국어 paragraph/bullets/typed table과 문장 claim 연결, original canonical proof·수치/단위/기간/status/entity gate, schema3/content_contract2, version1 byte/hash 보존, 단일 finalizer의 exact review·terminal survivor 검증. 일반 안내/면책 하단과 기사별 조건·근거는 승인된 편집 그대로다.
- u186: 동일 기존 CLI의 별도 의미 검사, 정상3회/수정 포함최대5회·3900초, source preparation·기존 elapsed·local wall time·runner deadline 합산, 수정 후 재검증과 동일 failing draft의 무변경 재제출 거절, 단계별 실제 bytes/time trace. 실제 사람 점수는 생성하지 않는다.
- u172 연결: annotation/profile/policy hash·review/projection·detailed event IDs를 결속하고 news-rich all-brief는 자동 인수 실패다. source/AI readiness와 사람5/5를 구별한다. active readiness는 false다.

## 실제 source 확인

[공식 원문 접근·parser 재검증](source-preview-qualification.json)은 과거 공식 문서를 대상으로 한2026-10-26의 bounded 실제 HTTP다. Fed 발표200/963자·완전 보존, Fed 연설200/3,001자·누락flag true, CFTC403/blocked를 확인했다. 공식 재이용 조건은 [Fed](https://www.federalreserve.gov/disclaimer.htm), [CFTC](https://www.cftc.gov/WebPolicy/index.htm)를 다시 읽었다. 기관 작성 text만 범위에 포함하고 외부 저작물·첨부·미디어·로고는 제외한다. 원문 bytes는 ignored private directory에만 둔다.

기존 body qualification 중 Fed2개에만 private6000자 범위를 명시했고 CFTC는 현재 access blocked로 갱신했다. SEC body도 기존blocked다. 코드의 preview capability는 구현/검증된 consumer를 뜻하며 mode 기본off, `--official-body-preview` 기본false, schema3/article_v2와 pinned code manifest hash/Fed-only allowlist가 모두 필요하다. production body 활성화는 여전히false다. u173의8개 정보 slot verified는0/8이며 이 source probe를 slot·actual corpus·사람 점수로 세지 않는다.

## 설계에서 구체화한 사항

1. shared narrative/claim/packet/readiness/trace 타입은 순환 의존성을 피하려고 `models/event_article.py`에서 소유하고 `models/event_document.py`가 소비한다. pure packet과 검증은 `_internal`에 두어 publisher가 briefing을 import하지 않는다.
2. canonical numeric proof는 writer가 고른 claim kind와 관계없이 모든 문장에 적용한다. observation도 기존 v3의 asset/window/unit/value·실제 observed clock 검증을 유지한다.
3. version2의 numeric containment는 문장을 임의 재작성하지 않고 원래 hard finding으로 시장을 차단한다. legacy/role_v1의 기존 국소 격리는 유지한다. exact review가 결속된 narrative를 안전하게 재검증할 수 없는 경우의 보수적 실패 경로다. 유효 sibling은 유지한다.
4. 단순 context-impact 사건만 policy상 brief가 가능하고, 정상 news-rich 양성은 최소1개의 detailed 기사를 요구한다. 글자 수·목차 칸 수는 인수 기준이 아니다.
5. 검증된 설명·반응 metadata는 approved narrative의 claim/question에서 파생한다. legacy180자 역할 필드를 다시 채워 산문을 중복 생성하지 않는다.

## 로컬 검증과 독립 리뷰

정적 검사 Ruff/mypy353, 집중 tests·native57/12groups replay, strict MkDocs8.17초/Material·Node29·유료 API/SDK/assets 정책 검사를 수행했다. 전체 pytest와 exact-source 원격 CI는 아래 마감 기록에 별도로 적는다. synthetic model/review fixtures와 historical source probe는 실제 자동 생성12편 또는 실제 사람 수용이 아니다.

별도 read-only reviewer2명이 source/privacy/budget/claim/finalization/compatibility를 검토했다. 발견된 실제→예상 우회, observation·clock 결속, prior elapsed, 잘못된 plan의 sibling 손실, public meaning 인수, inline table·중복행, truncation flag 및 legacy cap을 수리했다. version1 세 시장의 원래 serializer 대비 bytes/hash는7,398/7,386/7,380bytes로 정확히 같다. 모든 finding은 새 음성/양성 회귀와 재검증에 연결했다.

## 진행 상태와 외부 인수

u184 Step1–4 구현, Step5는 Fed2개 확인·CFTC/SEC blocked·국내 정책/DART/SEC filing의 추가 자격/본문 범위는 u173 인계다. 이 부분이 남아 source 확장 전체 완료로 세지 않는다. u185/u186의 코드와 실제 비게시 generation 수용·사람/viewport/performance/운영 release는 구별한다. 현재 production pin·schema/profile·cron·알림·cursor는 변경하지 않았다. 실제 human0/12·slot0/8·v3예약0은 유지한다.

## 마감 검증

로컬 전체 회귀: 7,502 PASS/1 known skip, 1294.98초. 이 실행 뒤 추가한 detailed/brief 자동 인수·table 중복 및 packet wire 검증은 집중 재검증하며, 최종 exact-source 원격 CI와 actual producer 결과는 후속으로 결속한다.
