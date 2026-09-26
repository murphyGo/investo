# u160 요구사항 cross-check

고정 계약 E11, 뉴스 clock/coverage/consumption 및 AC-160을 실제 코드 경로와 대조했다.

| 기준 | 근거 |
|---|---|
| AC-160.1 주말과 DST | `test_news_window_pipeline.py`: 주말 실제 v2 선정·본문·DTO와 금요일 가격 기준일, DST 23/25시간 재생의 최종 문서. |
| AC-160.2 재생과 dry-run | 동일 저장 창과 늦은 실행 clock의 prompt 동일; live Git read를 금지한 explicit replay/dry-run, cursor bytes 불변. 닫힌 로컬 manifest schema와 CLI exclusive replay 검증. |
| AC-160.3 source 시간/예산 | `test_news_window_coverage.py`: DART KST 자정 종료·날짜 정밀도·pagination/20초 합산 deadline, actual FOMC/정책과 예정 lookahead 분리. |
| AC-160.4 잘못된 전진 방지 | 실제 off/shadow 3/3 prompt·문서 parity; 실패 source, unknown/partial, hard-blocked 시장, custom generator만 hold. pinned/빈 RSS는 full 아님. |
| AC-160.5 원격 확정 transaction | `test_news_cursor_transaction.py`: pre/post-commit 실패, 응답 유실과 원격 descendant, clean rebase CAS 변경, pending 다음 실행 원격 기준점, 알림 실패. |
| AC-160.6 중첩과 공개 범위 | `test_news_window.py`: bootstrap72h/7d/24h, 변경 revision, recipient 분리, source union 일치, gap·coverage와 본문/quality 동일 projection. |

가격/history/예정 일정은 기존 owner를 유지한다. 원본 숫자·entity·compliance hard gate를 대체하지 않는다. 공개 필드에는 URL 원문이나 private document/hash trace를 넣지 않는다. source full은 해당 요청 구간의 제공자 조회 증거이며 전 세계 사건 완전성 보장이 아니다.

AC-160.1–6 코드 검증 PASS. 최종 전체 5798 passed/462.55s, Ruff/format648, mypy286, 정책 4종 및 strict MkDocs/Material PASS다. scheduled shadow와 운영 cursor 활성화는 별도 미실행이며 FR-023 전체 및 다른 유닛의 운영 gate를 완료로 변경하지 않는다.
