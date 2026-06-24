# Business Rules - `u109 domestic-anchor-sanity-quarantine`

**Date**: 2026-06-23
**Source**: `aidlc-docs/construction/plans/u109-domestic-anchor-sanity-quarantine-code-generation-plan.md`

Rules are listed in precedence order. Entity ids (`E1`-`E6`) and invariants
(`I1`-`I18`) reference `domain-entities.md`. NFR ACs reference
`../nfr-requirements/nfr-requirements.md`.

---

## R1. Domestic exact values must cross a trust boundary before public use

KOSPI, KOSDAQ, USD/KRW, Samsung Electronics, and SK Hynix exact closes must be
classified through `DomesticAnchorTrust` before any public table, prose gate,
chart sidecar, visual text, or Telegram summary can consume them.

- Only `trusted` values may pass downstream as exact numbers.
- All non-trusted states are withheld from public precision and represented by
  public missing reasons or reader-safe quality notes.

## R2. Trust requires bounded symbol identity

Only the `DomesticExactClaimRegistry` symbols in E2 are classified by u109.

- A candidate whose symbol cannot be normalized to E2 is outside u109 scope.
- A large-cap candidate cannot satisfy an index symbol.
- Index/FX candidates can become trusted only from `stooq-kr-market` rows whose
  `raw_metadata["ticker"]` is `^KOSPI`, `^KOSDAQ`, or `KRW=X`.
- Samsung Electronics and SK Hynix candidates can become trusted only from
  `fsc-krx-stock-price` rows whose `raw_metadata["ticker"]` is `005930` or
  `000660`, canonicalized to `.KS` registry symbols.

## R3. Trust requires explicit provenance

A candidate can be trusted only when `source_name` is explicit in
`NormalizedItem.source_name`.

- Missing source provenance classifies as `provenance_missing`.
- `raw_metadata["provenance"]` may strengthen diagnostics for
  `stooq-kr-market`, but it does not replace `NormalizedItem.source_name`.
- A source outcome that is failed, terminal, zero-items for the relevant
  contract, or otherwise unavailable classifies as `provenance_missing` or
  `unavailable` according to the available candidate fields.

## R4. Trust requires accepted target-date freshness

The candidate `observed_at` / as-of date must match the report target date or
the accepted domestic market close window already used by the domestic anchor
pipeline.

- Outside the accepted window classifies as `stale`.
- Missing date classifies as `stale` when a close exists, otherwise
  `unavailable`.

## R5. Plausibility bands are hard quarantine guards

Use these inclusive numeric bands:

| Anchor | Close band | Daily percent move band |
|--------|------------|-------------------------|
| KOSPI | `[1000, 12000]` | absolute value `<= 30.0` |
| KOSDAQ | `[300, 3000]` | absolute value `<= 30.0` |
| USD/KRW | `[500, 2500]` | absolute value `<= 20.0` |
| Samsung Electronics | `[1000, 2000000]` KRW | absolute value `<= 30.0` |
| SK Hynix | `[1000, 2000000]` KRW | absolute value `<= 30.0` |

- Missing close classifies as `unavailable`.
- Unparsable close/change values classify as `implausible`.
- Bands are guards against impossible publication, not a source of truth.

## R6. Public rendering never displays quarantined exact values

For `unavailable`, `stale`, `implausible`, or `provenance_missing` candidates:

- anchor tables omit the row or render a number-free unavailable/stale label;
- body exact claims are blocked by the anchor assertion gate;
- chart sidecars, visual cards, and Telegram snapshots must not receive the
  quarantined number;
- public channel-depth wording uses the u74 public missing reason mapping.

## R7. Prose enforcement stays owned by u70

u109 filters and annotates domestic anchors before u70 consumes them. It does
not replace `enforce_anchor_assertions`.

- u109 must pass only trusted domestic anchors to the existing canonical anchor
  payload.
- The existing prose assertion gate remains the mechanism that blocks exact
  domestic claims without trusted anchors.

## R8. Quality metadata explains withholding without leaking diagnostics

When any domestic exact anchor is withheld, u109 emits
`DomesticAnchorQualityMetadata` through the existing u96 quality snapshot/history
path.

- Structured metadata may include bounded private reason values.
- Visible public quality wording uses `국내 기준값 일부 비공개` or an existing
  reader-safe u74 missing reason.
- Public prose must not render private trust state strings as labels.

## R9. The quarantine must run before visual and notification payloads fork

Ordering is binding:

1. classify domestic anchor candidates;
2. write `trusted` anchors and withheld reason metadata into stage context;
3. build public anchor table input from trusted anchors only;
4. prepare visual/card payloads from trusted anchors only;
5. reconcile canonical anchors through u70;
6. build Telegram market snapshots from trusted anchors or filtered price items.

No public fork may read domestic exact values directly from raw `price_items`
after quarantine data exists.

## R10. US, crypto, and non-registry domestic behavior remain unchanged

The u109 helper may be shared mechanically, but policy changes are limited to
the registry in E2.

- Existing US and crypto anchor tests must stay behavior-compatible.
- Domestic tickers outside E2 keep the current u55/u70 behavior.

## R11. No new infrastructure, source adapter, or live validation

u109 is a deterministic in-process gate. It adds no network call, paid/free
external service, GitHub Actions job, secret, environment variable, database, or
archive backfill command.
