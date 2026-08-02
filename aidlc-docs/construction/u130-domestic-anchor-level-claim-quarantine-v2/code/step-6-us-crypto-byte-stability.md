# u130 Code Generation Step 6 — US/Crypto Byte Stability

## Scope Delivered

Proved that u130's domestic-only level-claim and consistency extensions do not alter existing US or crypto gate behavior. Step 6 is validation-only: no production source or test case was modified.

## Baseline Method

- Baseline: pre-u130 commit `08b241f43824463370b9c1faf6e504cc0170f7a4` (`ac79288^`).
- Current: `41e2042` after Steps 1-5.
- Loaded each revision's `anchor_assertion_gate` implementation in an isolated process.
- Compared the complete result for each case: rendered Markdown bytes plus ordered finding tuples.

## Characterization Results

| Case | Available anchors | SHA-256 | Result |
|------|-------------------|---------|--------|
| US missing-anchor move (`나스닥 종합은 0.5% 상승 마감했다.`) | `^GSPC` | `a81d584717fc77c1aa38de361d5240a6d3eddd020e82d8bd372c8a3ce3df0785` | baseline = current |
| US missing-anchor bare level (`나스닥 종합은 15,000.00을 나타냈다.`) | `^GSPC` | `c95c68e37ffb395150bde17247f995914482435aaf4ec65681cd78d126ba6a00` | baseline = current |
| Crypto present-anchor move (`비트코인은 3.2% 급등했다.`) | `BTC-USD` | `e759768f3e9f21e7f2174da791723e28e1f7e5df224a20688ee92c1407e18741` | baseline = current |
| Crypto missing-anchor bare level (`비트코인은 100,000.00을 나타냈다.`) | none | `1f1245ec4fbacbcab73a30a0cf5d3b0f6407a8b308992dfd8159b90b6f04e9cd` | baseline = current |

The US missing-anchor move retains the existing deterministic data-limited rewrite and finding. The other three cases remain unchanged with no findings. This also confirms bare-level matching remains domestic-only.

## Existing-Test Integrity

`git diff 08b241f..41e2042 -- tests/unit/publisher/test_anchor_assertion_gate.py` confirmed that the pre-u130 US/crypto cases were not edited. u130 only added domestic coverage and one explicit compatibility-wording pin.

## Review

Fresh-eyes review independently repeated the same-process baseline/current comparison and approved AC-130.6 with no Critical, High, Medium, or Low findings.

## Validation

- Existing focused US/crypto cases — 3 passed, 42 deselected.
- Full `test_anchor_assertion_gate.py` — 45 passed.
- Four baseline/current outputs and finding sequences — byte-identical.

## Extensions

- Property-Based Testing: not applicable because Step 6 adds no production function or serialization boundary.
- Security Baseline: disabled by project opt-in state; no source, secret, dependency, or external I/O was added.

## TECH-DEBT

None added.

## Next Step

Step 7 runs the full u130 quality gate and cumulative review.
