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


2026-10-26 exact source `9605aa6f369a3023a34249f48bf2939f15a0dca6`: 원격 quality40272481858 SUCCESS, pytest7,521 PASS/1knownskip/633.72초, Node39, Ruff840·mypy355, 정책·strictMkDocs5.79초·Material/calendar guards 모두PASS. 병행u187을 보존해 통합했다. source 구현e244df6b와 최신main merge9605aa6f이며 production 실행pin2619455c는 유지한다.

비게시 preview pin만658be680→9605aa6f로 변경한 뒤 private workflowe3c63dc(기준4824a79)의17줄 입력만 배포했다. schema2/role_v1/official_body_preview=false 기본값과auth queue:max를 유지한다. 실제 미국 preview40283909018은 target2026-10-23/schema3/article_v2/body opt-in/recording=true로 실행했으나 composition_invalid로 실패했다. 암호화 recipient private key는 ignored0600 로컬 파일에만 있다. 생성·내용 인수와 사람 점수는 실행 결과 뒤 별도 판정한다.


실제40283909018의 암호화 artifact를 로컬 복호화하고 모델2호출의 prompt/stdout SHA를 각각 확인했다. 작성 응답5편 모두 canonical fact의 독립 metric ref를 누락한 사실을 원래 packet으로 재생해 article.fact_proof_missing으로 확인했다. 본문은 각1문장에 그쳐 내용 합격도 아니다. actual/human/slot 표본에 합산하지 않는다. 원문 summary의 prior·범위 절이 packet에서 빠지는 입력 손실도 수리했다. 기존 body 우선·중복 제거·48KiB/64refs cap은 유지하며, writer에 canonical 전체 proof와 수치의 literal subject/metric/unit/period/status를 명시했다. profile policy hash를 새로 결속한다. 집중104 PASS·Ruff840/mypy355 PASS; 후속 exact CI와 실제 재생 결과는 별도 기록한다.

독립 후속 리뷰에서 summary 추가 시4 sources×(6 body+1 summary)=28개 passage 경계를 확인해 typed cap28과4-source 회귀를 추가했다. 기존 source4·allowed refs64·UTF8 packet48KiB·6body/source 한도는 유지한다. strictMkDocs7.44초 PASS.


후속 source826eb3eec21f4c29c7f7c53ddf87e683816f47af의 exact 원격CI40285888771 SUCCESS: pytest7,523 PASS/1knownskip/777.80초, Node39·Ruff840·mypy355·정책/strictMkDocs8.20초 모두PASS. 후속 독립 리뷰는29tests와source3개 정적 검사로 잔여P1/P2없음을 확인했다. source 전체body·summary cap과 실제 tests 경로를 설계/인계 문서에 맞췄다.

2026-10-27 01:16KST 원격을 재확인한 preview pin826eb3ee·productionpin2619455c·private preview workflowblob7691faa1은 유지됐다. 실제 재시도40357554455(target2026-10-23)와 공식피드에 남아있는 Fed 발표일40357557379(target2026-09-16)을 같은 schema3/article_v2/Fed-body opt-in으로 dispatch했다. auth queue:max에 따라 순차 실행했고 두 실행 모두 분류 단계context.status_unbound로 실패했다. 두 recipient key와 raw자료는 ignored0700/0600에 보존한다.


### 2026-10-27 분류 입력·관측값 정책 후속 수리

두 실제 artifact의1call prompt/stdout SHA를 각각 확인했다. 40357554455는 SEC 공지의 complement/status span이 단어 중간에서 잘렸다. 40357557379는 제안(proposed)·지원하지 않는 복수형 release를 actual text frame으로 강제하고 일부 actor/value span도 잘랐다. Fed statement title 자체의 원문 frame은 유효했다. 검증기는 이 응답들을 계속 거절하며 출력0건을 합격으로 세지 않는다.

article_v2에만 기존 prove_text_assertion을 통과한 원문의 subject/action/value/assertion 좌표 힌트를 제공한다. 영어·한국어를 지원하고 영어 will/plans to/expects to는forecast를 유지한다. 질문·부정·unsupported numeric text에는 actual hint를 만들지 않는다. 다중 단어 한국어 기관명에 조사처럼 보이는 음절이 중복되면 actor를 잘라 제안하지 않고 기존 exact-ref 경로를 유지한다. 검증기 허용 문법을 확장하거나 원문을 교정한 것이 아니다. source/frame hints bytes도24KiB evidence에 포함하며 schema/지시문/필수ID512bytes 여유를 실제 계산해 전체32KiB를 지킨다.

BLS/BEA adapter가 window.start를 observed_at/published_at에 넣는 코드와 최신 observation 조회를 확인했다. 새 profile은 실제 source-dated event 또는 required actual이 없는 통계 관측값을 reference로 배치한다. 후보96개 이전의 news 예약24개에서도 이를 적용해 공식 발표·국내 뉴스가 관측 통계에 밀리지 않게 했다. 기존 role_v1의 기본 selector/buffer/prompt bytes는 그대로다. 과거 Fed target은 과거 원문을 현재 수집하는 시험이며 다른 최신 관측 통계를 과거 시점에 알려졌던 정보로 인수하지 않는다.

최종 집중211 PASS/17.30초·native57variants/12groups PASS·Ruff841/mypy355 PASS. 독립 review의97tests PASS, 기존role_v1 0/1/5/25docs×3markets exact buffer/prompt bytes 동일을 확인했다. 발견한 질문 hint, 뉴스 예약, 한국어 누락/기관명 절단 지적을 회귀로 수리했고 잔여P1/P2없음을 재확인했다. 후속 exact source CI와 실제 재실행을 별도로 결속하며 human0/12·slot0/8·예약0은 유지한다.
