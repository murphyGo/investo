# Event/news v3 — 근거와 snapshot

**Analysis baseline**: `19c89b923f898c2291ba3933f9494f4ee0903b83`. **Final document base**: `487627931e27548a4a755a53df2dadc7c03543b8`, origin/main 최종 조회 2026-10-10. 이 문서는 설계가 출발한 근거를 보관한다. live 상태는 implementation/release 전에 다시 조회한다.

## 실제 공개물

시장별 최신3편 총9편을 검토했다. 국내·미국10-06/07/08,크립토10-05/06/07이며크립토10-08은미발행이다. 모두v3/v2eventmarker가없는legacy발행물이다. 가격표가요약보다앞인문서9/9,H1중복9/9,한눈에보기genericfallback6/9편·총12회다. 미국3편/코인3편의첫핵심이슈는같은주간CFTC잔액중심이고관전9편은가격/CFTC조건중심이었다.

미국10-08:67이첫CFTC이슈,77-79가유가/반도체보도의background attribution,112가CPI334.131이다. 국내10-08:71삼성전자결과비교는유용한변화설명이고127기업인수의후속설명은짧다. 코인10-06:137ETF신청과승인/거래개시를구별한다. 가격·숫자유무로뉴스품질을판정하지않는다.

[미국10-08배포페이지](https://murphygo.github.io/investo/archive/us-equity/2026/10/2026-10-08/)는분석당시HTTP200이며같은내용을확인했다. 기존공개물의문제를새activeeventmode의 성능으로귀속하지않는다.

## 실제 preview와 운영

[private preview37937493974](https://github.com/murphyGo/automation-runtime/actions/runs/37937493974): 국내selected5/terminal5/qualified0/details_limited5,미국2/2/0/2,코인synthesis3/event.narrative_invalid. 국내·미국봉인성공과matrix전체failure를구별한다. 게시/알림/cursor/productionreceipt쓰기없음이다.

분석당시runtime7bc6d287/eventactive/gate1,국내·미국active/cryptoshadow를API와실제code로확인했다. newswindow는shadow/bodyHTTPoff,firstactive0/3,human12/news-richpending이다. 실제privateworkflow는 newsfallbackshadow/enrichmentliteraloff였다. u163/u164main변경은당시runtimepin밖이다. 참고: [활성화기록](../../../docs/sessions/2026-10-09-event-active-rollout.md),[exact code CI](https://github.com/murphyGo/investo/actions/runs/37940803779).

qualified0은허위기사0/유효뉴스0의판정이아니다. `briefing/event_evidence.py:419-427`은내용/시간/history다른원인을묶고`publisher/event_blocks.py:233-240`은candidate상태/locator로terminalsupported를판정한다. 개별실제본문의사람점수와원인별분포는확보되지않았다.

## 코드 경로

| 근거 | 검토 지점 | 설계 결론 |
|---|---|---|
| 역할 refs가 identity/fact 중심 | briefing/event_evidence.py:155-164; _internal/event_rendering.py:169-174,222-251 | 독립meaning/reaction/후속ref 필요 |
| 품질 원인 통합 | briefing/event_evidence.py:419-427 | vector/시간/history/content분리 |
| span/hash 기반 identity | briefing/event_evidence.py:191-270,364-434 | source-backedentities/facts/실제delta |
| 7일remote receipts | orchestrator/event_receipts.py:96-133 | 장기story별상태/질문/해결근거 |
| 고정sectionmodel/80자/240자 | models/briefing.py; models/event_narratives.py:47-68; _internal/event_rendering.py:94-106,200-204 | 전체typed문서와summary/body분리 |
| 첫화면anchor-first 계획 | u154codeplan:63-72;requirementsFR-009 | 명시적v3target계약교체 |
| notifier한줄conclusion | notifier/summary.py:346-357 | sealed사건을모든표면에서소비 |
| officialHTTP닫힌범위 | sources/event_evidence.py:40-42,221-235;models/enrichment.py | source-slot별qualification과실제내용 |

## 실제 golden 범위

frozen `scripts/check_event_coverage.py`를부모와reviewer가실행했다.12그룹25변형25PASS이며human_semantic_review=pending이다. manifest의marketexpectation은US25/국내2/crypto0,qualified양성는 US16뿐이며국내2는 trustblocked음성이다. 이는goldencorpus의 범위이며다른단위테스트에국내/코인검증이전혀없다는주장은아니다.

내부selection_coverage는 terminal/selected,qualified_coverage는 supported_terminal/selected다. collectedcandidatecount는sourceinputrows다. containment-remove-fact는selected2/terminal1/qualified1/statequalified로PASS한다. 따라서구조상qualified/비율만으로완전포착·사람설명품질을 판정하지않는다.

## 공식 source 자료

[Fed FOMC 자료 목록](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)은성명서/ImplementationNote/기자회견/전망/의사록을구별한다. [BLS 고용발표일정](https://www.bls.gov/schedule/news_release/empsit.htm)은기준월와 공개시각을구분한다. [SEC Form8-K Item2.02](https://www.sec.gov/divisions/corpfin/forms/8-k.htm)는실적발표자료의내용경로다. 분석당시직접열어확인했다. 실제source추가/접근/재사용권한합격으로취급하지않는다.

## 한계

mobileviewport/실제activev3/사람semantic점수/외부mustcover전수는아직없다. previewbody의암호화자료를새publicfixture로복사하지않았다. sourceblocked나missingcapability를이설계에서복구완료로바꾸지않는다. 이전분석의localworkflow원본은repo내공식design으로이문서에bounded근거만옮겼다.

## 최종 main 갱신 확인

문서 작성 중 main이 48762793으로 전진했다. u154의 뉴스 우선·접힌 가격 자료 완료 기록, u165 source lifecycle, u166 index source 수정과 다른 sector 작업을 보존하며 문서 branch만 fast-forward했다. 원격에는 u167–u173/FR-024/025/TD-016 이름 충돌이 없었다. 최신 FinalizedPublicDocument의 Briefing payload·단일 seal, E1 generation absence, 본문 pre-seal visual과 post-seal OG 경로를 다시 확인했다. 위 9편/preview/golden/운영 pin 증거는 기존 분석 snapshot이며 최신 운영 성과로 재라벨링하지 않는다.
