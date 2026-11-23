# DART 신탁계약 해지 결정 지원

사용자 “진행시켜”에 따라 u173 Step4/u184 Step5의 실제 원문 공급 후속을 구현했다. 공유 dirty root의 소스·HEAD·index를 건드리지 않고 `codex/dart-trust-termination-20261123` 격리 브랜치에 저장했다. source parser commit은 `27c926a59b6b60ab90af4d37806511f82d7da387`, 기사 검증 코드는 `386d1390b153de9b47b4e7a731dbb08518d9d17e`, 최종 개별 진단 코드는 `4737ec42fc287a37d70cdf1c587cd3db72a5c63b`다.

## 변경과 검증

`dart-trust-termination-6.2-v1`은 정정 없는 신탁계약 해지 결정 양식 ACODE11335/FORMULA6.2/ADATE20260723만 지원한다. 목록·원문 회사/접수/날짜,17행6열의 셀 소유권, 금액·주식 단위와 TU 날짜 속성을 검증한다. 결정/예정과 실제 완료를 구분하며 미기재 '-'를0으로 바꾸지 않는다. 해지예정주식을 소각으로 바꾸지 않는다. 기존 CB 파서 파일·기본 프로필·전역 사실 검증 문법은 유지했다.

전용 preview 자격은 원문 XML hash와 재생된 문맥 fixture hash를 구분한다. source-slot checker1sample5fields와 실제 XML32bindings/native5slots29refs/945자 재생이 통과했다. 다른7개 source 행과 canonical matrix는 보존했다. 새로운 유료 API/키/의존성은 없다.

| 검증 | 실제 결과 |
|---|---|
| 원문 probe45130745466 | HTTP1/4380bytes, XML1/27817bytes/340nodes; 원문 확보 |
| 원문 probe45136966583 | HTTP1 뒤 원문 안전 검사 차단; raw 미보관·원인 불명, 재요청 없음 |
| 기사 CI45139519315 | 8311passed/1skipped,818.36초; JS39, Ruff886, mypy374, docs9.19초 |
| 최종 CI45150453547 | 8316passed/1skipped,871.50초; JS39, Ruff887, mypy374, docs10.02초 |
| 개별 준비45152929626 | 회사별 현재 목록N → 현재접수목록Y → 원문, HTTP3/1.410751초/model0, enriched1/native1 |

독립 검수에서 TU 날짜 속성 누락 L1, 문맥 fixture와 XML hash 혼용 M1, 운영 캡처의 전체 설정·페이지·입력 결속·환경 변수 확인을 보강했다. 파서/자격/진단 코드와 캡처 도구의 잔여 C/H/M/L은0이다. 별도 실제 source 검수는 결과 파일에 기록한다.

## 실제 기사 결과

run45143245424는 source296/routed156/native39/Stage1전달15, model3,단신1,상세0,`source_limited`다. 단일 뉴스 기사의41refs·fact/claim·4개 근거 span이 같은 실행의 원천 문서와 일치한다. `core_only`/`expected_detail=False`/`brief_ready`가 정확하고 원인·시장 반응을 생성하지 않았다. 6파일63679bytes 암호문을 즉시 확보했다.

DART30건에 일반 지원 양식은0, `[첨부추가]` 변형1건이었다. 2선택건은 parser_unsupported/HTTP0,30건 모두 차단, DART context0. 알려진 일반 양식 공시는 이 수집 표본에 없었다. 따라서 이 실행은 DART 기사나 상세 기사 양성이 아니다.

그 후 기존 개별 진단에 explicit trust profile을 연결해 당일 알려진 공시를 새 목록에서 다시 찾았다. run45152929626에서 최신성 `as_observed`, XML hash `eee8f1c6d5cb2a2eeea92305d9a55f384326e382a0600d61103ef6ee59d3afbb`, 새 native context `21d8f835b303287f63c9da34f3b5b435857ba75528456414ec45e7ae07bb680d`를 검증했다. 5파일10246bytes 암호문,5slots29refs32XMLbindings/945자 재생 성공이다. 이전 공시를 기사에 주입하거나 모델을 재호출하지 않았다. 이는 현재 원문 준비의 기술적 양성이며 정식 runtime 자격·기사 수용은 아니다.

## 운영 상태와 남은 작업

- Private HEAD `aef573a71f8f2066562dc64c49e229e384367e99`. 기사 workflow는 profile choice1줄, 개별 진단 workflow는 choice/regex2추가1삭제만 수정했다. 개별 진단의 기존 v1-only 경로를 유지했다.
- Preview pin386d1390, DART preparation pin4737ec42. Production `REVIEWED_CODE_SHA=378bccee40065441d181f8ca2816a91907567634`, DART qualification 및 다른 repo 변수는 실행 전후 일치했다. codex-runtime 환경 변수는 빈 집합으로 확인했다.
- 게시·알림·production cursor/receipt 쓰기·운영 cutover는0. private 암호문1일 보관과 ignored0700/0600 원문 보관을 유지한다.
- 후속은 지원 양식이 일반 기사 입력에 도달하는 수집 범위 검증과 현재 DART 상세 기사 표본이다. 단일 회사 준비 성공으로 전체 수집 recall을 주장하지 않는다. `[첨부추가]` 양식은 미지원이다.
- 사람 사전 annotation·5/5·12corpus·externalrecall, viewport/성능, genuine 예약 인수는 남아 있다. human0/12·canonical local3/8/runtime0/activationfalse·v3 scheduled acceptance0을 유지한다. 부모 u173/u184/u172/u171을 완료 처리하지 않는다.

[계획](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-trust-termination-20261123/plan.md), [기사 결과](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-trust-termination-20261123/article-preview-result.json), [실제 준비 결과](../../aidlc-docs/construction/event-v3-acceptance-20261028/dart-trust-termination-20261123/preparation-result.json).
