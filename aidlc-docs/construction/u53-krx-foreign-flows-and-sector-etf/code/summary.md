# u53 KRX Foreign Flows + Sector ETF Coverage — Code Generation Summary

**Date**: 2026-05-13
**Unit**: u53 krx-foreign-flows-and-sector-etf
**Status**: Complete (6/6 steps)
**Commit**: `224a422` (`Land u51 + u52 + u53 — reader-format, prior-briefing carryover, KRX flows + sector ETFs`)

## Goal

Fill two input-coverage gaps that the generated briefings explicitly exposed: domestic foreign/institutional flow data and US sector/macro ETF coverage.

## Key Deliverables

- `sources/krx_foreign_flows.py`: Naver Finance HTML adapter for KOSPI/KOSDAQ investor flows, explicit EUC-KR decode, adapter-local UA, no credentials, and per-market failure isolation.
- `sources/stooq_price.py`: expanded default coverage for sector SPDRs, SMH, IWM, TLT, GLD, USO, UUP, CL=F, and GC=F.
- `sources/yfinance.py`: fallback coverage for `BZ=F` and `^RUT`.
- `briefing/segments.py`: `krx-foreign-flows` domestic-only routing and commodity proxy routing tests.
- `sources/tiers.py`: `krx-foreign-flows` registered as tier A.
- R10 fixtures under `tests/unit/sources/fixtures/api/krx-foreign-flows/`, `stooq-price/`, and `yfinance-price/`.
- Regression coverage in `tests/unit/sources/test_krx_foreign_flows.py`, `tests/unit/sources/test_stooq_price.py`, `tests/unit/sources/test_yfinance.py`, `tests/unit/sources/test_plugin_contract.py`, and `tests/unit/briefing/test_segments_exclusivity.py`.

## Quality Gate

This unit landed as part of the combined Wave 7 commit with u51/u52. Combined gate at closeout:

| Gate | Result |
|------|--------|
| `ruff check .` | clean |
| `ruff format --check` | clean |
| `mypy --strict src/` | clean |
| `pytest -q` | 1910 passed after the combined u51/u52/u53 wave |
| `mkdocs build --strict` | clean |

## Notes

- Direct KRX `MDCSTAT02501` remained out of scope because the public endpoint returned `LOGOUT` and would require brittle token/session reverse engineering.
- Naver Finance is used as the public mirror surface, with KRX-originated data treated as tier A rather than tier S.
