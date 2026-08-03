# Business Logic Model — `u141 image-selection-and-insertion`

**Date**: 2026-08-03

## 1. Build the narrative context

```text
build_image_narrative_context(segment, rendered_markdown):
  conclusion = extract canonical conclusion from reader-visible body
  drivers = extract canonical key drivers from reader-visible body
  issue = body owned by H2 "② 전일 핵심 이슈"
  first_story = first H3 block within issue
  if issue/first_story absent:
      return empty hero/issue scopes
  hero = canonical_join(conclusion, drivers, first_story)
  digest = sha256(fixed_json(segment, hero, issue))
  return ImageNarrativeContext(segment, hero, issue, digest)
```

The output is captured before image/card supplements. It is therefore the closest stable representation of the final reader narrative available before asset insertion, and it cannot be contaminated by the image being selected.

## 2. Select stored feed usage

```text
select_image_usage(context, target_date, ledger_root, store_root):
  rows = current-date ledger rows for context.segment
  index = deterministic recurrence index
  hero_eligible = []
  card_eligible = []

  for row in rows:
    issue_offset = exact occurrence of row.item_url in context.issue_markdown
    if issue_offset is absent: continue
    if current rights truth is blocked: continue
    card_eligible += rank(row, issue_offset, first_seen, candidate_id)

    hero_offset = exact occurrence of row.item_url in context.hero_markdown
    if hero_offset is absent: continue
    if not current rights truth cleared: continue
    if dimensions missing or width < 600 or height < 338: continue
    if no valid store binary + sidecar pair: continue
    hero_eligible += rank(row, hero_offset, first_seen, candidate_id)

  hero = min(hero_eligible) or None
  card = first card_eligible whose candidate_id != hero.candidate_id, or None
  return ImageUsageSelection(hero, card, context.digest, bounded reason)
```

No title similarity, recurrence popularity, wall clock, network access, or raw-item order participates.

## 3. Select a curated semantic asset

```text
select_curated_asset(segment, context, library, registry):
  for registry key in explicit registry priority:
    if segment not in key affinity: continue
    scope = context.hero_markdown for person keys and primary entries
    aliases = entry-owned semantic aliases
    if an alias occurs as a bounded term in scope:
      choose the first valid asset id for that key
      return selection(asset, key, alias+scope reason, context.digest)
  return None
```

Person aliases contain names only. Topic entries may contain institution/role aliases. Thus “Kevin Warsh / FOMC” can select a Federal Reserve topic asset but never Jerome Powell's portrait; “Jerome Powell said …” may select Powell when that story is editorially primary.

## 4. Prepare assets and supplements

```text
prepare_segment_visual_assets(..., stored_selection, curated_selection):
  if stored hero exists:
    copy store bytes to external-context-image slot
    reconstruct validated provenance with selection evidence
    skip optional runtime external fetch for the same slot
  else:
    existing runtime-external path remains policy gated
  prepare curated / AI / data-confidence assets as before
  existing hero priority chooses external > curated > AI > data

  if card candidate exists:
    render typed visual supplement containing title, credit/source, item_url
    never render image_url or create asset bytes
```

The card supplement is placed after the first H3 story by the existing pre-finalization supplement lifecycle. Reapplication replaces its owned marker region instead of duplicating it.

## 5. Pipeline sequence and degradation

```text
route items
run U-137 candidate ledger/index/store stage          # failure isolated
generate three finalizable narrative briefings
for each segment:
  try build context and selections                    # segment isolated
  except: empty selections + bounded warning
  try prepare assets                                  # existing fallback chain
  except: text-only visuals result
  try apply source-card supplement
  except: omit card
continue carryover/charts/watchpoints/finalization/publish/notify
```

Selection diagnostics contain counts, reason codes, candidate/key ids, and the context digest only. They do not log body text, image URLs, or secrets.

## 6. Data-backed constants

The implementation-start snapshot contains 11 distinct ledger dates, 804 rows, 748 unique candidates, and 42 candidates seen on two or more dates (5.6%). US rows are low-resolution Yahoo thumbnails (130x86); domestic rows lack dimension/credit metadata; crypto rows carry dimensions but no credit; the committed cleared store contains no binaries. Therefore:

- `seen_count` is excluded from ranking;
- minimum hero dimensions are 600x338 and missing dimensions fail closed;
- absent credit falls back to `source_name` in the text card;
- the cleared hero path is production-dark until an operator clearance/store pair exists, but is fully exercised by fixtures;
- the link-card slice remains in U-141 because its fallback label and title contract are now fixed.
