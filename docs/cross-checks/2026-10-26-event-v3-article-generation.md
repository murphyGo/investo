# u184–u186 구현 대조

2026-10-26. 사용자 개발/계속 진행 승인. 비교 기준은 `aidlc-docs/construction/event-news-v3-content-20261026/`와 각 numbered AC다. 실제 source·human·운영 gate는 코드 통과와 구별한다.

| AC | 구현과 의미 있는 검증 | 판정 |
| --- | --- | --- |
| 184.1–2 | 공통 prepare_event_evidence, failed source 보존·preview capability/hash·off/shadow0·기존6/20초 HTTP·취소 회귀 | 코드 PASS |
| 184.3 | 1200자 이후 완결 조건·원문 offset, 문단 whitespace 완전 보존과 실제 추출 누락 flag·legacy4chunk 음성 | 코드 PASS |
| 184.4 | compact span wire·실제UTF8 cap·whole-event budget deferral 실제 generation→seal 회귀·필수 fact 유지 | 코드 PASS |
| 184.5 | Fed2개 scoped body200/6000자 bound 검증, CFTC403/SECblocked, 국내/DART/SEC filing 추가자격 미확정 | PARTIAL / 외부 source gate |
| 184.6 | immutable source/packet/hash, private raw 비노출, feed fallback·모듈 경계·valid sibling | 코드 PASS |
| 185.1–3 | 한국어 산문·선택 표/목록·전문장claim·모든kind numeric/status hard gate·조건/귀속/observed clock·별도 review | 코드 PASS |
| 185.4 | exact packet/draft/review/terminal 비교·stale 거절·원래 hard finding과 시장 block·정상 sibling 유지 | 코드 PASS; 새 narrative의 임의 numeric rewrite는 차단 |
| 185.5–6 | v1 원래 serializer bytes/hash3시장 동일, v2 typed version·inline table 순서/중복 거절·source privacy·footer1회·동일 seal | 코드 PASS |
| 186.1 | 정상3/수정5call, preparation/prior elapsed/local time/deadline·inclusive admission·고갈 시Stage1 호출0 | 코드 PASS |
| 186.2–4 | claim-kind 우회 음성·nested observation positive/negative·review ID/ref/hash/JSON·무근거 인과 즉시차단·수정/재검증·무변경 failing draft 거절 | 코드 PASS |
| 186.5–6 | reviewed public support·detailed/brief 공개 projection과news-rich all-brief 자동 실패, annotation/profile/policy/review/projection 결속·사람점수 별도 | 코드 PASS; 실제 corpus pending |

실제 테스트: `tests/unit/orchestrator/test_event_evidence_preparation_u184.py`, `tests/unit/briefing/test_event_packet_budget_u184.py`, `tests/unit/briefing/test_event_article_budget_u186.py`, `tests/unit/briefing/test_event_article_review_u186.py`, `tests/unit/publisher/test_event_article_projection_u185.py`, `tests/integration/test_event_article_acceptance_u186.py`, 기존u172 semantic/cutover/native57 replay와 source/context/preview 회귀.

로컬 full7502/1knownskip/1294.98초 이후 추가분 집중124+후속16 PASS, Ruff837/형식·mypy353·Node29·정책/strictMkDocs/Material을 확인했다. 최종 source SHA의 원격 전체 CI와 실제 비게시 producer는 [구현 기록](../../aidlc-docs/construction/event-news-v3-content-20261026/implementation-evidence.md)에 결속한다. AI reviewer2명은 인간 corpus의 검수자가 아니다. actualhuman0/12·slot0/8·v3예약0·DEBT-090·viewport와 운영 전환/cleanup은 미완료다.
