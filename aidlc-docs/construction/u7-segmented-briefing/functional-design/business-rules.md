# Business Rules — `u7 segmented briefing`

**Date**: 2026-05-07

Rules are listed in order of precedence.

---

## R1. Three independent market segments

Every successful daily run produces these segments:

1. 국내 증시 (`domestic-equity`)
2. 미국 증시 (`us-equity`)
3. 크립토 (`crypto`)

The segments are independent output artifacts. A strong domestic market story must not dominate the US or crypto briefing.

---

## R2. Deterministic segment routing before LLM

Market segmentation happens before Stage 1 classification and before Stage 2 synthesis.

Initial routing rules:

| Signal | Segment |
|--------|---------|
| `source_name == "yonhap-market"` or Korean exchange tickers like `[005930]` | domestic-equity |
| US index/ticker price items, Nasdaq/Yahoo/CNBC/SEC/FOMC/FRED/economic calendar items | us-equity |
| `source_name in {"coingecko-price", "theblock-crypto"}` or crypto asset names/tickers | crypto |
| Fed/macro/rates/liquidity items | us-equity, and crypto when the title/summary directly mentions crypto/liquidity/risk assets |

Routing must be implemented as transparent Python logic with unit tests. The LLM may classify within a segment, but it may not decide which market segment an item belongs to.

---

## R3. No cross-market filler

If a segment has too little direct signal, the generated segment must state the data limitation. It must not fill missing US equity or crypto coverage with domestic equity news.

Minimum v1 thresholds:

- `domestic-equity`: at least 3 routed items
- `us-equity`: at least 3 routed items
- `crypto`: at least 2 routed items

Below threshold, the segment is still generated, but the prompt includes a mandatory data-limited instruction.

---

## R4. Reuse u2 safety and formatting contracts

Each segment briefing reuses existing u2 contracts:

- Claude Code CLI only
- retry and total budget
- no Anthropic SDK
- disclaimer appended by code
- leak guard before publication
- Korean prose with ticker/index names preserved

Segment-specific prompts may add market-scope instructions but must not weaken these contracts.

---

## R5. Archive path and URL

Segmented archive path:

```text
archive/{segment}/YYYY/MM/YYYY-MM-DD.md
```

Public URL:

```text
{SITE_URL_BASE}/archive/{segment}/YYYY/MM/YYYY-MM-DD/
```

The existing unsegmented path remains readable for historical files but should not be used for new segmented runs after u7 ships.

---

## R6. Publish/notify policy

For v1, all three segment markdown files are written and committed together.

Failure policy:

- Collection failure: existing behavior.
- Segment generation failure for any segment: whole run fails, no segmented files are published.
- Telegram public notification failure: existing partial behavior.

Reasoning: public readers should not receive a run where only one of three markets silently vanished. Segment-level partial publication can be revisited later.

---

## R7. Telegram message shape

One public Telegram message per run:

```text
YYYY-MM-DD 데일리 시황

국내 증시: <one-line summary>
상세: <domestic URL>

미국 증시: <one-line summary>
상세: <US URL>

크립토: <one-line summary>
상세: <crypto URL>
```

The message must stay under Telegram's 4096-character limit. If summaries are long, truncate summaries and preserve all three URLs.

