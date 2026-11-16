# u22 card row-budget runtime candidate — 2026-11-17

User `진행시켜` authorized commit and deployment after local repair/verification.

- Production base: `b6b3fdc62abd5e63c19c1bcc2014c17a8a606bb7`.
- Public implementation: `5ab1641a8936fa3d93c60ee05708b82afaa5ff2c`.
- Only `src/investo/visuals/cards.py`, `src/investo/visuals/render.py`, and `tests/unit/visuals/test_data_confidence_row_budget.py` are carried from that reviewed public implementation. Both original source files were byte-identical between the public and production bases before applying the patch.
- Public repair evidence: 590 related tests, independent review PASS, 1,296 status combinations, sanitized operational-outcome replay and light/dark previews.
- Runtime candidate must pass its own CI before `REVIEWED_CODE_SHA` promotion. Other pins and workflows remain unchanged. No manual briefing/message dispatch.
- This fixes the source-row overflow; it does not claim to resolve unrelated domestic article-quality or upstream failures.
