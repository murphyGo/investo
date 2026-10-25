# Event v3 content-quality repair

The user correctly rejected the first actual preview as insufficient for judgment.
Sealed documents and passing technical tests did not establish useful reader content.
The previous output is not a positive human acceptance case.

## Actual diagnosis

Run `40125141798` used source `817b356c`. US routed 174 items but its final 24KiB
classification context contained four FRED observations and six calendar documents:
**zero news documents**. Earlier candidate reservation was lost at the byte-budget boundary.
Domestic and crypto outputs also had no terminal events. All three were source-limited.

The repair reserves source-confirmed releases, then shares actual context bytes among
news sources before optional calendar/reference rows. Repeated observations without an
explicit release remain optional reference material and do not consume mandatory event
slots. Required explicit releases, stable source/item remapping, 24KiB/16KiB bounds and
whole-document deferral remain enforced. Schema-two/shadow selection is unchanged.

## Evidence and action proof

Independent review found both false negatives for ordinary performed news verbs and
false positives where a detached `reported` marker blessed another action. Native text
facts now need one closed source-owned subject/action/value assertion. Final displayed
changes/digests preserve that frame's actor, value, specific action and modality. The
bounded action check also covers optional background/meaning/reaction. Numeric facts
do not grant an unproved directional change. Korean grammatical subjects and common
data concepts no longer masquerade as new company names.

Canonical text values preserve a bounded tagged semantic action and value hash, while
reader-visible `original_value` stays literal. Cancelled and completed facts in one slot
therefore differ and enter conflict/correction handling rather than disappearing as a
repeat. Closed story-action decoding preserves completion/cancellation behavior.

The first repaired actual run `40185092305`, source `9bbf8bec`, transmitted 15 news/filing
documents (14 SEC 8-K and one SEC newsroom item), with zero mandatory old observations.
It stopped at classification with `context.status_unbound`, two recorded calls. This
failure was retained and not presented as a new preview. Source-positive grammar included
`today`, plural possessives and an annual named publication. Follow-up `c3e19427` accepts
these exact constructions, with years restricted to closed named-event/publication phrases;
standalone years, amounts, shares and quantitative suffixes remain rejected. Both stored
classifier responses replay successfully under that repair without changing their refs.

## Validation and boundaries

- Local full collection before the concurrent main merge: 7,147 passed, one skipped,
  1,224.83 seconds. Subsequent focused runs cover all changed proof/identity/story paths.
- Merged `9bbf8bec`: exact-source quality run `40185091175` succeeded with 7,386 passed,
  one skipped in 633.86 seconds; Ruff (821 files), mypy (346 source files), Node29 and
  policy/documentation guards passed.
- Independent QA on `9bbf8bec`: 106 focused tests and eight closed decoder cases passed;
  no open P1/P2 in the bounded repair scope.
- Independent QA on `c3e19427`: 116 focused tests and 24 synthetic boundary cases passed;
  no open P1/P2. This does not certify general free-language semantics or human quality.
- Follow-up exact-source quality `40185897748`: 7,395 passed / one skipped / one
  failed DART transport-budget test. Its 30ms budget expired while normalizing the
  100-row first page, before the asserted second request. Local reproduction confirmed
  the same failure. The test now uses a protocol-valid one-row page and 100ms budget;
  cancellation, partial preservation and bounded elapsed-time assertions remain intact.
  All 48 source-window tests pass; production DART code is unchanged.
- `40185929996` passed classification with 15 news/filing documents and stopped after
  two synthesis attempts: one malformed chunk ID, then an inserted parenthetical alias
  that violated the closed assertion. No failed document was displayed. Prompt-only
  repairs `fb73afe1` / `b06147c9` require the complete source assertion, with a closed
  component-based fallback for token-only status refs; independent QA: 22 passed, P1/P2=0.
- Actual `b06147c9` run `40186613927`: sealed one US article using two model calls,
  324 collected / 174 routed items, 28 successful / nine zero / two failed sources.
  All four publication/notification/production-write flags are false. Markdown and model
  recording hashes verified. The article has 125 characters of source assertion, no
  background or meaning, and reaction unavailable. **This is still too shallow for a
  normal positive content-acceptance case.** Human acceptance is not incremented.
- Further independent code review preserved independently assigned optional evidence,
  including whole-assertion qualifiers, instead of forcing background/meaning to repeat
  the primary fact. Coordinated noun objects and released publications are supported;
  already-published unscheduled calendar-category releases are not forced into reference
  panels. Scheduled items remain references. QA: 122 focused / 12 boundary cases and
  E1 rejection/positive cases passed; no open P1/P2 in that bounded scope.

## Content readiness

Live preview currently supplies collected feed/API items directly; it does not call the
official body-enrichment stage. Existing feed descriptions can be too short to support
why/background. Observed reaction additionally needs its own timestamp/asset/value proof;
neither publication dates nor market closes establish causation. The 16KiB protected
context can defer optional refs even after news input is restored.

Existing qualified historical body bytes for Fed/CFTC can be parsed offline after their
committed hashes are checked. A separately labeled, developer-authored reference example
now illustrates source-backed content without pretending to be today's automatic report,
a live LLM run or a human-accepted corpus document. It does not change source qualification
or operational HTTP permission. New body HTTP remains blocked by the explicit operational
approval check in `models/enrichment.py`; SEC body access remains blocked.

Two offline reference examples were sealed through the real native classifier/parser,
generator and sole finalizer using authored two-stage replay responses: US policy dated
2026-09-16 and crypto regulation dated 2026-09-24. Each has one article with background
and source-reported meaning; reaction remains unavailable. This used zero live model calls
and zero new HTTP requests. Source body hashes match the existing qualified manifests;
excerpts are 963 and 1,126 characters. The examples' Markdown hashes are respectively
`9480b3cfcd04feaedc78d730a946aa32d1efb269ab12736b59690ecca0ae2a10` and
`fd8f8e69ec437fc7b4ee5547a8028ea0a6bae7eb8d6595b834240c26474bc18e`.
They are explicitly labeled developer-authored historical content examples. They are not
counted as live producer success, current-day coverage, scored human documents or qualified
source slots. The raw inputs, authored responses and reader page remain local/ignored.

The concurrent public-insights integration and its production pin `0025497d` are preserved.
Only `REVIEWED_EVENT_PREVIEW_SHA` was changed to reviewed preview code. No production
schema-three capability, source-body access/activation, publication, Telegram, production
cursor or receipt write is authorized by this repair. Existing qualified-source slots,
human annotations, viewport, performance, scheduled observation, cutover and retirement
gates remain pending. Raw source/model data and recipient keys remain in private ignored
artifacts; public evidence contains only closed counts, codes, identifiers and hashes.

Plan and proof details: [content-quality repair](../../aidlc-docs/construction/event-news-v3/content-quality-repair-20261025.md).
