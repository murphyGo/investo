# u183 요구사항 대조

2026-10-25 · FR-029/026, US-013, AC183.1–7/NF183.1–4. Primary agent의 대조이며 독립 code-review와 구별한다.

| 기준 | 로컬 결과 | 증거와 한계 |
| --- | --- | --- |
| AC183.1 7slot source/unit/provider/계약/clock/집계 | PASS | source5/9definitions, Decimal/range/clock-role gates. dominance/FNG0..100·FNGinteger, USDpeg공급/TVL/venueUSD OI의고정범위. 원문prose·global/flow추론 없음 |
| AC183.2 fraction/cycle/명목OI | PASS | .0001→.01% 정확변환, intervalHours/explicit source cycles. current_period와settFundingRate/settState구별, cycle미확인funding만억제. coin/contracts→USD 임의변환0 |
| AC183.3 Bybit우선/OKXfallback/dedupe | PASS | sameprovider/contract/timestamp/value만dedupe, newer유효sample선택,동시상충provider억제,failedstandalone과fallbackorigin분리. provider/interval/정의이력단절 |
| AC183.4 원천/응답/수집구간/36h | PASS | CGupdated_at/FNGtimestamp/Bybitresponse/OKXts/DeFi실제request구간을구별. window.end를sourceUpdated로승격0. unknown/future/stale억제와 원시각last-good회귀 |
| AC183.5 권리·공개보관·출처 | PASS / 미확인정의차단 | source별9정의1allow/8blocked, Alternative.me notice를값·이력표·그래프·JSON에보존. publicGit와retention gate/철회에서current/history삭제. 형제지표유지 |
| AC183.6 current-only/history/UI/예산 | 로컬 PASS | current7card/noJS,UTC collection-day D/D-7/30samples·same-day교체vs동일clock수정, lazy same-origin manifest/hash. 실제crypto16·macro16renders/keyboard/noJS/theme/nav/hash차단. HTML100KiB/공통CSS+JSgzip20KiB/current256KiB/history4MiB,resource상한 |
| AC183.7 code/runtime/Pages/5회 분리 | 기록 PASS / 운영 DEFERRED | defaultoff·module기본macro, Demo/key/source/routing/fallback/sector/eventactivation불변. latestmain/exact implementationSHA/privatepin·mode/Pages/5회scheduled는Step8 pending |

NF183.1: 기존5adapter의legacyJSON/request/parity와fallback을mock replay로검사했다. NF183.2:권리1/8상태와상호독립 공개/분석보관을검사한다. NF183.3:source정의/단위/시각/negativecase/historycompatibility와C1origin결속을검사한다. NF183.4:noJS/coreUI/lazy/budgets와실제두viewport/theme/keyboard/200%상당을확인했다.

실제7개endpoint 개발조회는200,typed9개를offline replay했다. 새rawfixture를공개repo에복사하지않았고Source/GHA전체정상이나재배포승인으로확대하지않는다. UI는example.invalid권리fixture의합성자료다. 200%는CSSviewport절반+DPR2이며Browserconnector설치경로오류와u145waiver는미해소다. 사용자profile은사용하지않았다. localbareGit수용은production배포가아니다.

전체검증의기존DST PBT실패는HEAD/현재모델에서동일하게재현됐다. JSON-visiblefields/UTCinstant 보존을검사하도록테스트만수정했고imaginary/두fold회귀3개를추가했다. broadtimezone생성을유지했으며독립검토에서계약약화가아님을확인했다.

[검증과입력hash](../../aidlc-docs/construction/u183-crypto-market-internals-dashboard/code/validation.json) · [구현](../../aidlc-docs/construction/u183-crypto-market-internals-dashboard/code/summary.md) · [독립리뷰](../../aidlc-docs/construction/u183-crypto-market-internals-dashboard/code/review-u183-final.md). 운영Step8/기존DEBT-090·다른유닛gate는그대로이며새미해결finding/debt는없다.
