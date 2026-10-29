# 사건·기사 v3 실제 검수 재개 — 2026-10-28

사용자 요청은 u171–u173, u184–u186의 검수와 운영 전환 진행이다. 시작 기준은 `4cc54675`, 실제 preview pin은 `aa51e6be`, production pin은 `2619455c`다. 현재 작업공간의 다른 u163–u166/데이터 탐색 변경은 보존한다. [기계 판독 증거](evidence.json).

## 이번 실행 결과

| 항목 | 관측 | 수용 의미 |
| --- | --- | --- |
| 기존 공식 feed | FOMC 20, Fed speech/testimony 15, CFTC 12개 정규화; FSC 실패 | parser 재검증이며 뉴스 포착률/사람 평가가 아님 |
| 기존 허용 Fed body | 공통 preparation의 2요청 모두 enriched | 기존 host/path/selector/6000자 정책을 재사용 |
| u173 정책 결정 | actor/decision/size_or_scope 3개 원문 좌표 재생 | 로컬 source-slot verified, 시점 unknown·runtime not_run |
| u173 공식 발언 | speaker/quoted_claim 2개 원문 좌표 재생 | 로컬 source-slot verified, 시점 unknown·runtime not_run |
| 나머지 6 slot | blocked 유지 | 실제 필수 field/권리/parser/runtime를 추가 확인해야 함 |
| 10월 27일 기준 국내 preview | 1 call, sealed, terminal event 0 | source_limited/content_not_ready, 정상 기사 양성 아님 |
| 같은 기준 미국 preview | 2 calls 후 composition_invalid | 실제 원문/응답 재생의 수치 gate 충돌; 봉인 0 |
| 같은 기준 crypto preview | 1 call, sealed, terminal event 0 | source_limited/content_not_ready, 정상 기사 양성 아님 |
| 과거 Fed 원문 기사 preview | 3 calls, 1편 sealed, separate review 통과 | 현재 수집한 과거 원문 시험. brief_only/detailed0이며 실제 인수 corpus에 합산하지 않음 |

세 시장 실행은 [40705984134](https://github.com/murphyGo/automation-runtime/actions/runs/40705984134), 과거 Fed 원문 시험은 [40708356349](https://github.com/murphyGo/automation-runtime/actions/runs/40708356349)다. 실제 전송 prompt/stdout, 최종 Markdown과 projection hash를 각각 확인했다. publication/notification/production cursor/receipt 쓰기는 모두 false다. 원문·모델 출력·개인 recipient key는 ignored private 경로에만 보관한다.

## 현재 내용 병목

국내 분류 입력은 공시 제목과 접수번호 중심이다. 이 값으로 조치 조건을 추론하지 않고 article 0을 유지했다. Crypto에는 실제 뉴스 후보가 있었으나 classifier가 event 0을 반환했다. 따라서 source-limited라는 최종 표기만으로 "주요 사건이 없었다"거나 source 문제만이 원인이라고 결론 내리지 않는다. source/선정/지원 문법/내용 검증의 공백을 원래 입력과 따로 대조해야 한다.

미국 작성 응답은 원문의 영문 빈도 표현을 숫자 표현으로 바꿨다. 원래 전달된 packet/ref로 `validate_claim`을 재생하면 `event.fact_unsupported`가 발생한다. 현재 literal numeric 계약과 번역 표현 사이의 충돌로 기록하며, 이를 fact를 날조했다는 사람 판정이나 정상 양성으로 바꾸지 않는다. 기존 hard gate는 유지한다.

과거 Fed 기사는 원문에 있는 결정 폭·결정 후 금리 범위·공식 이유·경제 상황을 포함한다. 다만 기관·단위·날짜의 영문 literal이 남아 있어 한국어 표현의 자연스러움은 별도 편집 검토 대상이다. 모델의 supported 결과를 사람 5/5로 기록하지 않는다.

## 구현과 독립 검토

`SourceSlotParserCapture`가 private normalized item/received clock/정확한 ContextRef/승인 context hash를 담는다. 기존 `map_source_slot_context`를 그대로 재생하며, qualification matrix hash와 row의 승인 fixture hash를 모두 확인한다. CLI `--private-capture`는 gitignored·0600·일반 파일만 최대 1MiB 읽고, source/slot/code/count만 출력한다. 네트워크/LLM/HTTP 권한/발행은 추가하지 않는다.

독립 QA가 발견한 승인 fixture와 재계산한 자체 hash의 불일치 허용, matrix 재조회 사이의 불일치, 자기참조 symlink의 private 경로 오류를 수정했다. 재검토는 잔여 Critical/High/Medium 0, 집중 48 tests·Ruff/format/mypy PASS다. 실제 두 private sample/5 field binding도 같은 checker로 통과했다.

## 표면과 운영

봉인 Markdown bytes를 변경하지 않고 기존 MkDocs theme/hook/assets/nav 설정으로 private actual-data site를 strict build했다. 실제 Chrome 새 탭에서 Fed 본문→출처→자료 안내→면책 순서를 읽었다. Browser host는 unavailable이며 사용 중인 Chrome 창과 충돌하여 정확한 390×844/1440×900 측정과 화면 판정은 아직 pending이다. HTML build와 native 탭 열기를 viewport 통과로 세지 않는다. 별도 Chromium 검증 사용 여부는 사용자 응답을 기다린다.

검수 화면은 loopback `http://127.0.0.1:8765/human-review.html`에 있다. 서버 root는 렌더된 정적 site뿐이며 recipient key와 raw recording을 제공하지 않는다. 이 화면은 과거 표본의 편집 검토 자료이고 실제 corpus 인수가 아니다.

production/schema2와 preview pin, source body permissions, auth/cron/queue 설정은 이번 작업으로 변경하지 않았다. u173은 2 verified/6 blocked, runtime readiness 0이고 전체 유닛은 6/7을 유지한다. u184 Step5, u171 Step7, u172 실제 corpus/성능/전환/예약/cleanup도 미완료다. 실제 human0/12·genuine v3 scheduled0이다.

## 다음 실제 수용 작업

1. u184 Step5에서 국내 정책/DART/SEC의 source별 권리·현재 parser·필수 field 공백을 닫는다. 기존 SEC companyfacts adapter는 단위와 concept별 filing accession을 normalized summary에서 버리므로, 단순 API 200을 actual slot verified로 세지 않는다. 필요한 보강은 기존 호출 결과의 opt-in typed evidence에서 단위·기간·filing을 보존하고, snapshot을 새 발표로 만들지 않아야 한다.
2. Crypto의 event0을 원래 입력과 대조해 source gap과 현재 지원되지 않는 assertion 문법을 분리한다. 문법 확장은 actual/forecast/negation과 수치·단위·기간 음성 회귀를 유지해야 한다.
3. 검수 대상 뉴스창의 must-cover/required facts를 사람이 먼저 주석한 뒤 새 actual producer corpus를 만든다. 시장별4·발행일2 이상·정상 news-rich detailed 양성이 필요하다.
4. 실제 사람5/5·원문 fact100%·unsupported0·성능·정확한 viewport·runtime/source/cursor 준비를 결속한 후 u172 운영 전환을 실행한다. 최초3회/시장과 전체10회 genuine scheduled 이후에만 legacy cleanup을 수행한다.


## 최종 로컬 검증 — 2026-10-29 KST

운영과 같은 Python3.11.9, 공식 SHA256을 확인한 Node22.23.4와 기존 Homebrew Cairo 경로를 사용한 전체 pytest는 **7,602 PASS / 1 known skip / 982.06초**다. Ruff/format842파일·source mypy355·checker strict mypy, Node39, native57variants/12groups, 정책4종, strictMkDocs5.91초와 Material/Calendar 검사를 통과했다. `--require-ready`는 예상한 exit1로 전환을 거절하며 release_ready=false를 보존한다. 독립 최종 문서 대조에서 네 실제 preview의 hash/count가 모두 맞고 private/raw 유출과 수용 과장이 없음을 확인했다.

코드·로컬 소스 판정의 검증과 실제 기사·사람·운영 수용은 구별한다. source gate의6개 slot, 사람12개, 정확한 viewport와 end-to-end 성능, 운영 전환·예약·legacy cleanup은 여전히 미완료다.
