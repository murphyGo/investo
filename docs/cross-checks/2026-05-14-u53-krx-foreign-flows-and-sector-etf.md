# Cross-Check: u53 KRX Foreign Flows + Sector ETF Coverage

**Scope**: u53 krx-foreign-flows-and-sector-etf
**Date**: 2026-05-14
**Checked by**: Codex

## Summary

| Status | Count |
|--------|-------|
| Complete | 6 |
| Deferred | 1 |
| Gap | 0 |

**Overall Compliance**: Complete for the source-adapter scope. The optional operator dry-run remains outside code-generation closeout.

## DoD Mapping

| DoD Item | Status | Evidence |
|----------|--------|----------|
| `krx-foreign-flows` adapter | Complete | `sources/krx_foreign_flows.py`; replay and failure tests in `tests/unit/sources/test_krx_foreign_flows.py`. |
| Stooq sector/macro ETF expansion | Complete | `sources/stooq_price.py`; fixture coverage for new tickers and N/D skip behavior. |
| yfinance Brent/Russell fallback | Complete | `sources/yfinance.py`; fixture coverage in `tests/unit/sources/test_yfinance.py`. |
| Segment routing and tier registration | Complete | `briefing/segments.py`, `sources/tiers.py`; tests in `test_segments_exclusivity.py` and `test_plugin_contract.py`. |
| R10 fixture-backed parsing | Complete | KRX/Naver HTML, Stooq CSV, and yfinance JSON fixtures committed under `tests/unit/sources/fixtures/api/`. |
| Quality gate | Complete | Combined u51/u52/u53 gate passed: ruff, format, mypy strict, pytest 1910, mkdocs strict. |
| Operator dry-run | Deferred | Manual runtime validation is operator-facing and not required for code-generation closeout. |

## Residual Risk

Naver Finance HTML layout can drift. The adapter fails closed with zero items and source diagnostics rather than blocking the daily run.

## Status

u53 construction and cross-check complete.
