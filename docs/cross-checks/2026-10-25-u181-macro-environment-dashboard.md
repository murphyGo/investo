# u181 요구사항 대조

2026-10-25 · FR-027/026, US-011, AC-181.1–7, NF181.1–4. Primary agent의 `cross-check`이며 독립 코드 리뷰와 구별한다.

| 기준 | 로컬 결과 | 증거 |
| --- | --- | --- |
| AC181.1 13slot의 unit/source/period/SA | PASS | closed recipe13, typed source envelopes, source/domain/render tests. CPI index를 YoY로 변환하지 않고 Decimal 자릿수 보존 |
| AC181.2 같은 날짜의 정확한 spread | PASS | 4.30−4.10=20bp, 다른 SOFR/EFFR 유효일 억제, 긴 Decimal의 precision256 exact 연산, derived overflow 격리; 부모 권한 철회/보관 전파 |
| AC181.3 원천 cadence와 sibling 실패 | PASS, 실제 정상 운영은 별도 | date-only rates/weekly H.10/월간 period, 공개 고지/optional FRED 격리. 네 어댑터 off/on 요청 수·legacy JSON parity. 개발 BLS503을 정상으로 세지 않음 |
| AC181.4 current-only와 exact history | PASS | 첫 자료 준비 화면·현재 카드, exact5 business days, missing/revised/last-good 비교 억제, JS lazy read+hash/snapshot gate, 30개 관측 상한 |
| AC181.5 hub/nav/기존 경로 보존 | PASS, 내부 경로 | 기존 미국 섹터 이름·URL과 source Markdown 보존, 기존 SiteShell 회귀 및 실제 hub 재진입/섹터200. 날짜 링크는 confirmed Git tree의 실제 문서만. Treasury 외부 홈페이지 접근은 미확인으로 source 기록에 보존 |
| AC181.6 실제 rendering/accessibility/budget | PASS, 아래 범위 | Chromium154의 16 viewport/theme/JS/zoom 조합, keyboard Enter/details, native theme toggle, 넘침/새 page error0, source 단위·면책, 초기HTML100KiB와 criticalCSS+JSgzip50KiB 이내 |
| AC181.7 구현·권리·runtime·Pages/5회 분리 | 기록 PASS / 운영 DEFERRED | state/plan7/8, 원천별 allow/blocked와 HTTP/replay 기록, source/runtime 미확인 항목, pin/Pages/5회 관찰 pending. 배포 또는 권리 전체 승인으로 확대하지 않음 |

## NFR와 증거 제한

- NF181.1: source registry44 유지, 추가 runtime source HTTP/key/routing 0. 4 adapter parity 테스트와 기존 전체 회귀로 확인했다. 개발·브라우저 localhost 요청은 runtime source 호출과 구별한다.
- NF181.2: typed recipe/단위/seasonality/source date를 검사한다. 값의 공개·Git 과거·분석 이력 권한을 분리하고 파생 부모에도 적용한다.
- NF181.3: JS 없이 현재 카드/만기표/출처와 원본 이력 링크가 있다. 이력 표/SVG는 명시적 선택 후 검증해 읽는다. SVG 실패는 정확한 표를 제거하지 않는다.
- NF181.4: 실제 페이지와 추가 asset bytes/gzip을 계측한다. 대형 history는 initial HTML에 넣지 않는다.

200% 검증은 실제 headless Chromium에서 CSS viewport를 절반으로 줄이고 DPR2로 설정한 등가 확대다. Browser connector는 설치 경로 오류로 실행되지 않았으며 기존 u145 Browser waiver를 승계하지 않았다. production HTTPS/사용자 세션/운영 수용으로 표시하지 않는다.

전체 collection7046개에 대해 네 full shard+수정 shard+최종 scoped 결과를 node별 중복 제거했다. 7045 passed/1 기존 skip, 누락·미해결 실패0. 최종 scoped112 passed, reviewer source/domain/render29 passed. [검증 기록](../../aidlc-docs/construction/u181-macro-environment-dashboard/code/validation.json), [구현 요약](../../aidlc-docs/construction/u181-macro-environment-dashboard/code/summary.md).

FR-027은 로컬 구현 수용 상태이며 전체 운영 Complete는 아니다. 신규 debt로 넘긴 미해결 코드 finding은 없다. Step8과 기존 DEBT-090/타 유닛 gate는 그대로다.
