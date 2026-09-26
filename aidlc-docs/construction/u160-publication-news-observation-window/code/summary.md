# u160 주말·장후 뉴스 관측기간

u159 `f056fbde` 원격 전달 이후 7개 개발 단계를 완료했다. 가격 기준일과 뉴스 조회 시계를 분리하고, 실제 생성·봉인·원격 게시 증거로만 뉴스 커서를 전진시킨다. 기본 off 및 운영 active capability false를 유지한다.

## 구현

- scheduled run 시작 UTC를 한 번 고정한다. source×recipient 기준 최초 72시간, 기존 커서의 24시간 중첩, 최대 7일 범위를 계산한다. source union은 한 번 조회하고 최종 수신 시장에서 다시 필터·document/revision 중복 제거한다. 같은 문서의 새 revision은 다시 평가한다.
- 명시적 target_date는 replay다. 시장 calendar day, paired UTC override 또는 닫힌 저장 manifest를 사용하고 live cursor를 읽거나 쓰지 않는다. 23/25시간 DST 날짜를 보존한다. `INVESTO_NEWS_MANIFEST_PATH`는 explicit replay 전용이다.
- 기존 SourceSpec에 opt-in과 수신 시장을 선언한다. 기존 fetch API는 unknown coverage로 감싸며, finite RSS의 오래된 항목·빈 XML을 full 증거로 삼지 않는다. cap/parse 손실은 partial이다. coverage의 범위는 정확한 source union과 같아야 한다.
- DART는 KST 날짜 구간 교차와 종료 시각 직전 날짜를 사용한다. 총 3페이지·20초에 재시도/대기를 포함하며 제공자 pagination이 일치해야 full이다. 날짜만 있는 발표는 날짜 정밀도를 유지한다. 공식 정책 실제 발표와 예정 lookahead를 구분한다.
- 실제 기본 생성기의 GenerationResult만 소비 receipt를 반환한다. 최종 문서 봉인 때 동일 window/baseline을 검증하고 Markdown SHA를 결합한다. 미생성·custom generator·hard 차단·minimal fallback은 소비 증거를 만들지 않는다.
- 뉴스 커서와 run manifest는 기존 E11 archive transaction에 포함된다. v2 사건 ledger와 같은 고정 원격 baseline을 쓴다. 정확한 full coverage와 sealed consumption이 있는 source×recipient만 전진한다. pre-commit 복원, post-commit pending, 응답 유실 후 ancestry 확인, clean rebase CAS 변경 거부를 재사용한다. 다음 실행은 원격 확정 tree만 읽고 알림 실패는 확정 게시를 되돌리지 않는다.
- 봉인 본문과 공개 quality history는 같은 typed projection으로 뉴스 조회 envelope, 가격 기준일, source별 범위/gap/full·partial·unknown을 표시한다. 전체 뉴스 완전 수집을 주장하지 않는다. 양 단계 prompt에 뉴스 관측기간과 가격 기준일을 함께 전달하여 주말 발표를 금요일 종가의 원인으로 혼동하지 않도록 한다.

## 검증 범위

실제 Collect/Generate/Publish/Notify stage, 기존 2단계 producer와 finalizer 및 local bare Git transaction을 사용한다. 소스 통신과 LLM 응답은 합성 기록이다. 주말 v2 사건은 실제 선정·최종 본문·알림 DTO까지 도달하고 가격 기준일은 금요일을 유지한다. off/shadow 3/3 게시의 prompt·문서·커서 bytes 일치, replay/dry-run live cursor I/O 없음, 실패 source와 차단 시장만 hold, CAS/응답 유실/알림 실패를 검사한다.

전체 5798개 회귀가 462.55초에 통과했다. window61, source227 및 교정59, 실제 통합20, parent projection11, CLI6개도 통과했다. 독립 리뷰 P2 네 건을 수정·재확인했고 미해결 P1/P2는 없다. Ruff/format648, mypy286, 정책 검사4종, strict MkDocs9.22s와 Material 계약 PASS다.

[OpenDART 공식 문서](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)의 날짜·pagination 규약은 확인했으나 이 작업을 live source qualification으로 간주하지 않는다. 사람 의미 수용, scheduled shadow, 운영 cursor 전환 및 실제 게시/알림/Pages 검증은 실행하지 않았다. 최종 수치는 `validation.json`과 cross-check에 기록한다.
