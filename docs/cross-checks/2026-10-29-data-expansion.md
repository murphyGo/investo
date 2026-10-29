# KRX 월물 만기 / Coin Metrics 순유입 도입 cross-check

2026-10-29 KST. 기존 u43/u66 확장. 사용자 승인에 따른 코드 도입이며 배포 인수와 구분한다.

| 요구/위험 | 확인 결과 |
| --- | --- |
| 국내 월물 규칙/휴장/연도 제한 | 2026년 12개 월물 날짜, 연속 휴장·주말 조정, 연말 부분 범위, 미지원 연도 실패 검증 |
| 무료·무키 수집 | KRX 네트워크 없음; Community 한 batch GET. 유료 API checker 통과 |
| BTC/ETH native 순유입 | 같은 asset/day 유입-유출 Decimal; 낮은 ambient precision에서도 정확도 유지 |
| 결측/오류/시간 | 부분 결측·NaN·음수·과대 문자열·잠정/수정·중복 충돌·미래 상태시간·과거 재생·429/timeout·schema 검증 |
| 발행 경로 | schema 2 기존 일정·크립토 지표와 native v3 시장 기준 패널 모두 연결. native 패널은 수집 입력에서만 재구성 |
| 원천 cutoff | v3에도 evidence_received_at 전달, CollectStage→실제 adapter→native panel 테스트 |
| 가격 검증 | 검증된 순유입 행만 가격 검사에서 제외, 정상 USD 가격 공존·변조 행 검출 검증 |
| 공개 고지 | 관측 UTC 일자·유입/유출 상태·주소 범위·계산 설명·Coin Metrics/CC BY-NC 4.0 링크 |
| Telegram | native 패널 숫자는 알림에 복사하지 않음. 제한된 메시지에서도 상세보기 링크 유지 |
| 실제 HTTP/발행 경로 | 2026-10-28 15:26 UTC Community 200, BTC/ETH 2행 flash, KRX 11/12 1행. native finalizer 양쪽 통과, 외부 발행/송신 없음 |

## 검증 기록

- 넓은 회귀: sources/publisher/briefing/notifier 단위 및 관련 통합 **4,607 passed / 2 failed**. 신규 등록으로 바뀐 source count 44→46 테스트를 수정했다.
- 수정 후 집중 회귀 **89 passed**: 신규 source/model, source lifecycle, legacy/native finalizer, crypto clock, insights capture.
- 공유 작업공간 통합 후 registry/routing/실제 finalizer/수집 clock 집중 회귀 **144 passed**. 변경 source 17개 mypy 및 ruff/무료 API 검사 재확인.
- 독립 reviewer 재검증 **44 passed**, 최종 Pass. native 경로 누락·순유입의 가격 오인·v3 cutoff·Telegram 문서 계약 지적을 수정했다.
- 남은 넓은 회귀 실패 1건: `tests/unit/sources/test_event_evidence.py::test_malformed_html_preserves_original_and_successful_sibling`. 이번 코드를 통합하기 전 원래 작업공간에서도 같은 Python 환경으로 동일 실패 재현. 별도 세션이 편집 중인 event evidence 구현을 이 작업에서 수정하지 않았다.
- 변경 Python ruff/mypy, `scripts/check_no_paid_apis.py`, `git diff --check` 통과. 전체 테스트 무결점으로 보고하지 않는다.
- 실측 metadata: [live-smoke.json](../../aidlc-docs/construction/data-expansion-20261029/live-smoke.json). 응답 값 대신 URL·시각·상태·bytes·SHA-256을 저장.

## 완료와 잔여

2026-10-29 구현 단계에서 코드·로컬 실측·native/legacy 통합을 완료하고 공유 작업공간에 충돌 없이 통합했다. 당시 commit/push/배포·Telegram 전송은 수행하지 않았다. 배포 후 첫 예약 GHA 관측, 2027 KRX 달력 자격 갱신, 상업 이용 전 Coin Metrics 사용 조건 재검토가 잔여 운영 항목이다. DEBT-067/072 전체를 완료로 닫지 않는다. 청산·위클리·코인 일정·u182/u183 인사이트 dashboard 확장은 범위 밖이다.

## 2026-10-30 배포 전 확인

- 사용자 후속 요청 “커밋 배포해줘”에 따라 커밋·운영 버전 갱신·Pages 배포를 진행한다.
- 설치된 비공개 `daily-briefing.yml`과 변수를 함께 확인한 결과 운영은 schema 2 / role_v1이며 국내·미국 active, 크립토 shadow다. `INVESTO_EVENT_BRIEFING_MODE=active`만으로 native v3 운영을 추론했던 설명을 정정한다. 기존 모드와 워크플로는 변경하지 않는다.
- 공개 main에는 전체 구현·검증 기록을 반영한다. 운영 버전은 기존 고정 SHA `2619455c4099c33fbb1362655c4cc206aed8276c` 위에 이번 source/test 변경만 적용한 별도 커밋으로 만든다. main의 다른 미승격 변경을 함께 배포하지 않는다.
- 운영 반영본은 독립 리뷰 Pass. `event_edition.py`의 기존 `ContextRef`를 보존한 import 병합 외에 이번 구현 차이를 그대로 적용했으며 schema/profile/인증 정책 변경은 없다.
- 기존 malformed HTML 사례는 운영과 같은 Python 3.11.9에서 통과했다. 앞선 실패는 로컬 Python 3.11.18에서 재현된 차이로 기록한다.
- 공개 main 반영본 전체 회귀: Python 3.11.9에서 7,579 passed / 33 failed / 1 skipped. 실패는 Node 경로 2건과 Cairo 동적 라이브러리 경로 31건뿐이었다. 설치된 Node 22와 `/opt/homebrew/lib` 경로를 지정한 실패 항목 재실행은 **33 passed**. 합계 **7,612 passed / 1 skipped**, 남은 실패 없음.
- 공개 반영본 전체 Ruff check/format, mypy(359개 source), JavaScript 39개, 무료 API·SDK·이미지·Material·calendar 정책 검사 및 strict MkDocs 통과. 운영 반영본도 정적 검사(mypy 350개 source), 신규 경로 44개, JavaScript 39개, 동일 정책 검사와 strict MkDocs 통과.
