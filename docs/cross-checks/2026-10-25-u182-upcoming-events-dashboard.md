# u182 요구사항 대조

2026-10-25 · FR-028/026, US-012, AC182.1–6, NF182.1–4. Primary agent의 요구사항 대조이며 독립 code-review와 구별한다.

| 기준 | 로컬 결과 | 증거와 한계 |
| --- | --- | --- |
| AC182.1 네 어댑터 공식 일정·kind/range/원천/상한 | PASS | 기존 recordings off/on request1회·legacy JSON parity, 개발3 endpoint200/replay10·9·4 typed, calendar24 정의14allow/10blocked. 수집0과 missing/failed/권리차단을 구별 |
| AC182.2 date-only와 exact/DST | PASS | source-local date-only에는 exact_at 없음. BEA explicit Year/ET 검증, 봄·가을DST의21:30/22:30 KST, ambiguous/nonexistent clock은 date-only. 소스별오늘/KST오늘 range 경계 회귀 |
| AC182.3 기간·occurrence·보수적 중복 | PASS | Fed2일 연속 range/불완전 token 억제, meeting/statement/press/minutes 분리. 실제 같은발표자2행사 identity 충돌 수정. explicit period와null 구별, reviewed BEA/FRED family만 참조 병합, conflict제외/집계 |
| AC182.4 7/30·분류·128·noJS/부분 | PASS | source statuses/query caps, 결정적128/excluded, noJS30 native anchor, JS7/30와3분류+전체 DOM filters. Chromium16 cases·Enter/aria-pressed·재진입. 전체 일정 coverage를 주장하지 않음 |
| AC182.5 실제 발표/취소 추론 금지·기존 시황 경로 | PASS | 경과·누락은 결과미확인/후속 snapshot 제외. 원래 clock의 last-good·primary/refs/inactive 권리철회. 네source legacy/기존 lookahead 및 publication 회귀, 추가HTTP/LLM/Telegram0 |
| AC182.6 화면·예산·운영 분리 | 로컬 PASS / 운영 DEFERRED | 실제390/1440 두theme·JS유무·200%상당·keyboard/contrast/overflow, current256KiB/HTML120KiB/CSS+JSgzip15KiB. Step7 exact implementation SHA/main통합/private pin·mode/Pages·5회 scheduled pending |

NF182.1은 기존 registry44·source defaults/key/query/cap를 유지한다. NF182.2는 source-owned typed parsing과 합성/recorded edge cases, NF182.3은 noJS·keyboard·date basis·고정 guide, NF182.4는128/current/HTML/asset/history0으로 확인한다.

실제 UI는 별도 임시 Chromium154의 합성 일정이며 Browser connector는 설치 경로 오류로 실행되지 않았다. 200%는 절반 CSS viewport+DPR2의 등가 확대다. source개발조회·실제 응답 재생·합성 테스트·local bare Git 수용·production Pages는 각각 구별한다.

[검증](../../aidlc-docs/construction/u182-upcoming-events-dashboard/code/validation.json) · [구현](../../aidlc-docs/construction/u182-upcoming-events-dashboard/code/summary.md) · [독립 최종 리뷰](../../aidlc-docs/construction/u182-upcoming-events-dashboard/code/review-u182-final.md). 전체 최종 집계와 검증 입력은 validation에 기록한다. 신규 미해결 코드 finding/debt는 없고 DEBT-090 및 다른 유닛 gate는 유지한다.
