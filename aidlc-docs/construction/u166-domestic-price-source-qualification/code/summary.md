# u166 implementation

2026-10-10. Required FD/NFR finalized under user development/per-unit commit instruction. Existing source only:44 identities/tier/routing unchanged, no provider swap.

Current official V2 endpoint replaces the historical path; page100/max2 per basis date uses actual totalCount/page fields. Expected row counts and consistent per-date totals make incomplete retrieval observable. Valid rows survive later page errors/expiry; incomplete with no useful rows is typed failure. Eight-day lookback shares one60s deadline and decreasing shared retry budget/5MiB cap. Adapter is stateless; immutable receipts are local per call.

JSON/API/XML/schema/transport errors use fixed source reasons and allowlisted result codes without provider message, raw payload, query URL or cause. Extreme Decimal exponents/magnitude and JSON digit/depth errors stay inside the external-input parsing boundary. Cancellation, programmer errors and unrelated TimeoutError propagate. Numeric0 remains valid, quantities are exact integers, OHLC/finite/date constraints are enforced. Real basis-date/published timestamp remains unchanged; stale data is not promoted by HTTP200 or retrieval time.

Manual Actions workflow and CLI probe one fixed source with existing keys and contents:read. It has no schedule, raw artifact, model, publisher, notifier or private runtime pin. Console contains only fixed reasons/date/status/counts. Public FSC redistribution remains unqualified; KRX new key/service/schema/public-use proof is deferred and Yonhap stays best effort. DEBT-068 stays open. [Qualification](../qualification.md).

Focused48 tests PASS; broader source/retry/plugin/domestic/u149 regression152 PASS before final edge cases. Fresh independent review applied security, concurrency, data integrity, resource lifecycle, error, memory and performance protocols. Findings for paging completeness, Decimal overflow and resource-heavy JSON decoding were repaired with regression tests. Ruff/format684/mypy292 PASS. Exact full gate and runner receipt are recorded after completion.

Final independent review CLOSED:144 tests PASS3.44s; Ruff/format684/mypy292/diff PASS; no open findings. Policies4/strict docs/Material PASS. Prior unit u16521c979e4 exact CI37952883931 SUCCESS6357 PASS317.24s.

Final local gate:6400 tests PASS516.48s, independent144 PASS/review CLOSED; Ruff/format684/mypy292/policy4/strict docs/Material/diff PASS. Code complete6/7; step7 read-only authenticated runner probe follows delivery. Public rights/private activation/ten scheduled observations remain separate.

Integration preserves concurrent u154301d2c5a. Local full6400/516.48s was on u16521c979e4; rebased combined-head focused437 PASS14.44s, Ruff/format687/mypy293/strict docs/Material/diff PASS. Exact combined-head full verification follows in remote quality CI. Source code did not change during rebase; both audit records are retained.
