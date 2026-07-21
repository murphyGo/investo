# Business Logic Model - `u144 public-document-finalization-contract`

**Date**: 2026-07-21
**Source**: `aidlc-docs/construction/plans/u144-public-document-finalization-contract-code-generation-plan.md`

This model fixes the canonical control flow. Rule IDs refer to
`business-rules.md`; entity IDs refer to `domain-entities.md`.

---

## 1. Production call graph

```text
GenerateStage
  -> Mapping[MarketSegment, Briefing] + typed absences   # generated drafts
  -> prepare assets in run-owned temporary staging root  # no public destination I/O
  -> build explicit pre-finalization supplements         # no final bytes yet
  -> finalize_public_bundle(briefings, context)           # pure E6 boundary
       -> bounded survivor fixed point
       -> assemble/project/repair/validate each candidate
       -> seal non-empty valid subset + typed outcomes
  -> PublishStage promotes staged assets + writes E5      # public I/O begins here
  -> index / OG / quality / git from read-only E5
  -> NotifyStage from read-only E5
```

No reader-facing archive/index/quality write or git staging may precede
successful E6 construction. Existing private operational state
(macro-carryover/forecast logs) is outside the public-document seal and cannot
enter E5/E6.

## 2. Bundle preflight

```python
def finalize_public_bundle(briefings, *, context):
    assert_unique_order(context.expected_segments)
    explained = set(briefings) | set(context.input_absences)
    if explained != set(context.expected_segments):
        raise PublicDocumentFinalizationError(
            target_date=context.target_date,
            segment=first_unexplained_or_duplicate_segment(...),
            phase="preflight",
            issue_codes=("document.segment_input_contract",),
        )

    drafts = tuple(
        PublicDocumentDraft.from_generated(
            segment=segment,
            briefing=briefings[segment],
            target_date=context.target_date,
        )
        for segment in context.expected_segments
        if segment in briefings
    )
    validate_bundle_context_shape(drafts, context.bundle_context)
    ...
```

Preflight also rejects a segment present in both inputs, cross-date inputs,
duplicate expected segments, naive `entity_observed_at_utc`, missing disclaimer
source fields, unknown segment keys, incomplete coverage for a generated
segment, invalid supplement order, duplicate/invalid artifact IDs or public
paths, and supplement-to-artifact reference mismatches. The staging owner has
already validated that each `staged_path` is beneath its temporary root; the
pure finalizer performs no filesystem resolution or digest read. It performs no
writes.

## 3. Survivor fixed-point coordinator

The u63/u94 partial contract requires navigation to describe the final
survivors, while hard trust gates can remove a generated segment. The finalizer
owns this bounded restart; the orchestrator no longer catches surface errors
and mutates the segment mapping.

```python
def finalize_public_bundle(briefings, *, context):
    blocked: dict[MarketSegment, tuple[str, ...]] = {}

    for pass_index in range(len(context.expected_segments)):
        active = tuple(
            segment
            for segment in context.expected_segments
            if segment in briefings and segment not in blocked
        )
        if not active:
            raise no_surviving_document_error(...)

        absence_state = build_absence_state(
            expected=context.expected_segments,
            generation_absent=context.input_absences,
            trust_blocked=blocked,
        )
        if context.bundle_context is None:
            active_bundle_context = None
        else:
            active_bundle_context = redecide_daily_thesis_for_active_segments(
                context.bundle_context,
                active,
            )
        validate_cross_segment_thesis_inputs(
            original_drafts=drafts,
            active_segments=active,
            bundle_context=active_bundle_context,
        )
        attempt = finalize_active_from_original_drafts(
            active,
            absence_state=absence_state,
            bundle_context=active_bundle_context,
            context=context,
        )
        newly_blocked = attempt.hard_blocked_not_in(blocked)
        if not newly_blocked:
            return seal_bundle(attempt.documents, absence_state, context)
        blocked.update(newly_blocked)

    raise PublicDocumentFinalizationError(
        phase="fixed_point",
        issue_codes=("document.survivor_fixed_point_exhausted",),
    )
```

Every pass starts from original E2 `generated` inputs; already transformed
Markdown is never fed back. A repairable R8 surface finding cannot enter
`newly_blocked`. With three expected segments, at most three passes execute.

`redecide_daily_thesis_for_active_segments(...)` is the current pure
`redecide_daily_thesis_for_successful_segments` behavior moved from
`orchestrator.bundle_context` to `_internal.daily_thesis_decision`, an allowed
neutral owner. Orchestrator compatibility code and the publisher finalizer call
that one owner; publisher never imports orchestrator. Cross-segment thesis
validation and phase-1 injection use `active_bundle_context`, so a removed
segment cannot remain in thesis support or wording.

`None` is an exact compatibility branch: `context.bundle_context is None`
produces `active_bundle_context is None`, skips thesis/cause injection, sets
the corresponding E3 expectation flags false, and never calls the redecision
helper. `validate_cross_segment_thesis_inputs()` runs inside every fixed-point
pass after redecision and before any active draft is assembled. Preflight
checks only bundle-context/date/segment shape, not survivor-specific wording.

## 4. Assembly phase

For each segment in canonical order:

```python
assemble(draft, context, *, active_bundle_context):
  producer_plan = build_public_producer_plan(
      target_date=draft.target_date,
      segment=draft.segment,
      segmented_mode=True,
      supplements=context.supplements_by_segment.get(segment, ()),
      active_bundle_context=active_bundle_context,
      channel_inputs=context.items_by_segment.get(segment, ()),
      reconciled_anchors=context.anchors_by_segment.get(segment, ()),
  )
  expectation = producer_plan.region_expectation
  markdown = draft.source_briefing.rendered_markdown

  markdown = apply_prebuilt_supplements(
      markdown,
      supplements=context.supplements_by_segment.get(segment, ()),
  )

  markdown = replace_or_inject_anchor_table(markdown, producer_plan.reconciled_anchors)
  markdown = enforce_anchor_assertions(markdown, canonical_anchor_symbols)
  markdown = apply_reader_structure_without_public_projection(markdown)

  markdown = inject_shared_macro_block(markdown, producer_plan.shared_macro)
  markdown = inject_crypto_indicator_block(markdown, producer_plan.crypto_indicators)
  markdown = inject_channel_anchor_block(markdown, producer_plan.channel_anchors)
  markdown = inject_cause_map_line(markdown, producer_plan.cause_map)
  markdown = inject_daily_thesis_line(markdown, producer_plan.daily_thesis)

  markdown = repair_compliance_language(markdown, segment)
  scan_compliance(markdown, segment)          # raw §⑥ prose visible here
  watchpoints = render_watchpoint_matrix_result(markdown, segment=segment)
  markdown = watchpoints.markdown
  draft = draft.with_limitation_reasons(watchpoints.limitation_reasons)
  scan_compliance(markdown, segment)          # rendered cards visible here

  markdown = render_partial_bundle_navigation(
      markdown,
      expected=context.expected_segments,
      active=active_segments,
      absences=absence_state,
  )
  markdown = ensure_canonical_disclaimer(markdown, segment)
  markdown = emit_first_viewport_disclaimer(markdown, segment)
  markdown = reflow_first_viewport(markdown, segment=segment)
  markdown = repair_first_viewport_summary(markdown)

  evidence = count_rendered_evidence(markdown, ...)
  markdown = render_body_used_count(markdown, evidence)

  return draft.advance(
      "assembled",
      PublicDocumentLayout.reindex(markdown, expectation=expectation),
  )
```

`apply_reader_structure_without_public_projection` may be an explicit new
chain or the existing `apply_reader_format` split so u108 projection is no
longer embedded before downstream producers. Individual pass algorithms remain
owned by their existing modules. `build_public_producer_plan()` calls each
existing pure eligibility owner once; the typed payloads and
`PublicRegionExpectation` booleans are two views of that same result, preventing
producer/index expectation drift.

## 5. Projection phase

```python
project(draft, context):
  coverage_limitations = derive_public_limitation_reasons(
      coverage=context.coverage_by_segment[draft.segment],
      source_outcomes=context.source_outcomes,
  )
  typed_limitations = stable_unique(
      (*coverage_limitations, *draft.limitation_reasons)
  )
  layout = project_public_markdown(
      draft.layout,
      limitation_reasons=typed_limitations,
  )
  return draft.advance(
      "projected",
      layout,
  )
```

`derive_public_limitation_reasons` implements the exhaustive E4 mapping from
existing `CoverageReasonCode` values and typed watchpoint outcomes. Projection
scans every public region after assembly. It does not alter:

- fenced/protected code;
- collapsed `수집/품질 진단` details content;
- structured metadata files;
- canonical disclaimer text.

It preserves original newline bytes and does not blanket-protect Markdown
tables; reader-visible watchpoint tables are public regions. The existing
one-argument `_internal.project_public_quality_language` is called only on
visible line/region fragments because it collapses internal whitespace.

Prompt/watchpoint producers are already public-safe, but projection remains
defense in depth.

## 6. Repair and containment phase

```python
repair(draft):
  layout = PublicDocumentLayout.reindex(
      repair_surface_artifacts(draft.layout.markdown),
      expectation=draft.layout.expectation,
  )
  findings = find_owned_surface_quality_issues(layout)
  grouped = group_findings_by_region(findings)
  attempts = set()
  outcomes = list(draft.block_outcomes)

  for region_id, region_findings in stable_region_order(grouped):
      region = layout.region(region_id)
      issue_codes = stable_unique_sorted(f.issue.code for f in region_findings)
      dispositions = tuple(
          disposition_for(code, region.block)
          for code in issue_codes
      )
      disposition = strongest_disposition(
          dispositions,
          precedence=(
              "block_segment",
              "omit_optional_block",
              "replace_block",
              "repair",
              "record_warning",
          ),
      )

      if region.region_id in attempts:
          return hard_blocked_segment("document.fallback_repeat", ...)
      attempts.add(region.region_id)

      match disposition:
          case "repair":
              layout = repair_owned_region_once(layout, region, region_findings)
          case "record_warning":
              pass
          case "replace_block":
              layout = layout.replace_region_body(
                  region.region_id,
                  region_aware_safe_fallback_body(region, issue_codes),
              )
          case "omit_optional_block":
              layout = layout.omit_optional_region(region.region_id)
          case "block_segment":
              return hard_blocked_segment(issue_codes, ...)

      outcomes.append(redacted_block_outcome(issue_codes=issue_codes, ...))

  # Every changed fragment crosses the same boundary again.
  layout = project_public_markdown(
      layout,
      limitation_reasons=typed_limitations,
  )
  markdown = repair_surface_artifacts(layout.markdown)
  return draft.advance(
    "repaired",
    PublicDocumentLayout.reindex(markdown, expectation=draft.layout.expectation),
    outcomes,
  )
```

Owned findings use the E3 bounded canonical section/marker index. It is not a
general Markdown parser. An unlocatable blocking finding maps to
`block_segment`, never a whole-document regex deletion.

## 7. Terminal validation phase

Terminal validation is read-only. The declared order is stable so the same
input yields the same first error and logs:

```python
validate(draft, context):
  assert_required_document_structure(draft.layout.markdown, draft.segment)
  numeric_findings = scan_anchor_assertions(
      draft.layout.markdown,
      segment=draft.segment,
      available_symbols=canonical_anchor_symbols,
  )
  if numeric_findings:
      return hard_blocked_segment("numeric.anchor_assertion", numeric_findings)

  entity_findings = scan_entity_fact_claims(
      draft.layout.markdown,
      context.fact_bundle,
      context.target_date,
      context.entity_observed_at_utc,
      segment=draft.segment,
  )
  if entity_findings:
      return hard_blocked_segment("entity.fact_contradiction", entity_findings)
  scan_compliance(draft.layout.markdown, draft.segment)
  public_leaks = find_owned_public_quality_leaks(
      draft.layout,
      evidence_predicate=first_forbidden_public_evidence,
  )
  if public_leaks:
      return hard_blocked_segment("public_language.residual", public_leaks)
  run_publish_boundary_registry(                  # u85 trio
      summary -> canonical disclaimer -> short disclaimer
  )
  blocking = tuple(
      issue for issue in find_surface_quality_issues(draft.layout.markdown)
      if issue.severity == "block"
  )
  if blocking:
      return hard_blocked_segment(sorted_issue_codes(blocking), ...)
  try:
      notification_summary = derive_public_notification_summary(
          draft.layout,
          segment=draft.segment,
          target_date=draft.target_date,
          coverage=context.coverage_by_segment[draft.segment],
      )
  except PublicNotificationSummaryError as exc:
      return hard_blocked_segment(exc.issue_code, ...)
  return draft.advance(
      "validated",
      draft.layout,
      notification_summary=notification_summary,
  )
```

Existing structure/compliance/summary/disclaimer exceptions are caught only at
this segment-attempt boundary and normalized to bounded hard-block codes. A
programmer/input-contract error is not normalized and raises E8. Production
control flow never relies on Python `assert` for a trust decision.

`find_owned_public_quality_leaks` is a layout traversal, not a second phrase
scanner: it calls the existing u108 `first_forbidden_public_evidence` predicate
on every `reader_visible` region, including Markdown table rows, and skips only
the typed protected/exact regions.

Assembly uses existing `gate_body_assertions()` to obtain rewritten Markdown
and typed findings. Terminal validation uses the new exact read-only API
`scan_anchor_assertions(markdown, *, segment, available_symbols)`. The legacy
`enforce_anchor_assertions()` may wrap these for compatibility but has zero
default segmented call sites. Do not call a rewriting helper after validation
begins.

## 8. Sealing

```python
seal(validated_draft, context):
  assert validated_draft.phase == "validated"
  final_briefing = validated_draft.source_briefing.model_copy(
      update={"rendered_markdown": validated_draft.layout.markdown}
  )
  digest = sha256(validated_draft.layout.markdown.encode("utf-8")).hexdigest()
  artifact_ids = artifact_ids_referenced_by_layout_and_outcomes(
      validated_draft.layout,
      context.supplements_by_segment.get(validated_draft.segment, ()),
      validated_draft.block_outcomes,
  )
  notification_summary = require_validated_notification_summary(validated_draft)
  return FinalizedPublicDocument._from_validated(
      segment=validated_draft.segment,
      target_date=validated_draft.target_date,
      briefing=final_briefing,
      markdown_sha256=digest,
      staged_artifact_ids=artifact_ids,
      notification_summary=notification_summary,
      block_outcomes=validated_draft.block_outcomes,
      warnings=bounded_warning_codes(...),
  )
```

This is the only production `Briefing.model_copy(rendered_markdown=...)` after
the finalizer migration. An architecture test pins the construction site.

`artifact_ids_referenced_by_layout_and_outcomes()` joins marker-backed region
IDs to the unique E1 `supplement_id` values, excludes regions with one E7
`omitted` outcome, and emits the remaining declared artifact IDs in
`(stable_order, kind, supplement_id, artifact_id)` order. It does not scan
Markdown links. An omitted supplement retains its empty marker shell for
structural determinism but contributes no promotion ID.

After the active subset seals:

```python
documents = tuple(seal(draft, context) for draft in validated_drafts)
return FinalizedPublicBundle(
    target_date=context.target_date,
    documents=documents,
    expected_segments=context.expected_segments,
    segment_outcomes=build_segment_outcomes(...),
    promotion_manifest=promotion_manifest_for_survivors(
        documents,
        context.staged_artifacts_by_segment,
    ),
)
```

## 9. Writer and staged-asset sequence

Before E6, files produced by current visual/chart supplements (and any future
file-backed carryover) exist only beneath a run-owned temporary root and are
represented as
`StagedArtifact(artifact_id, segment, kind, relative_public_path, staged_path,
sha256)`. Current text-only carryover performs no file I/O. E1 supplements
reference staged files by ID; E5 freezes non-omitted surviving references;
E6 is the exact promotion manifest. After E6, the existing publish transaction
revalidates root ownership and digests, promotes only manifest artifacts, then
writes Markdown and derived public pages. Rollback restores public destinations
on promotion, write, or quality failure before git; `finally` removes the
temporary root. Once commit/push begins, existing `PublisherGitError` recovery
semantics apply and no automatic history compensation is claimed.

```python
write_finalized_document(document):
  if sha256(document.briefing.rendered_markdown) != document.markdown_sha256:
      raise PublisherIOError(... seal mismatch ...)
  if not verify_disclaimer(document.briefing.rendered_markdown, document.segment):
      raise PublisherDisclaimerError(...)
  if document.briefing.target_date != document.target_date:
      raise PublisherIOError(... date mismatch ...)
  path = archive_path(document.target_date, segment=document.segment)
  write_atomic(path, document.briefing.rendered_markdown)
  return path
```

Verification completes before `archive_path` parent creation or any write.

## 10. Pipeline failure routing

```text
finalize_public_bundle returns 3 documents
  -> all three write/commit
  -> notify ok     => SUCCESS / complete / exit 0
  -> notify failed => PARTIAL / complete / exit 0 (delivery-only)

finalize_public_bundle returns 1 or 2 documents
  -> valid subset writes/commits with u63 absence navigation
  -> operator alert
  -> PARTIAL / content-partial / exit 2
  -> Pages dispatch runs, then daily job re-emits exit 2 (red)

finalize_public_bundle raises E8 / returns zero survivors
  -> zero public-destination writes/commit
  -> operator alert
  -> FAILED / none / exit 1
```

Optional visual generation may fail before finalization; text-only supplements
are then supplied. That is not permission to omit a segment.

## 11. Interaction with later public surfaces

- Site index and OG builders consume the final `Briefing` view from E5.
- Evidence/quality calculation uses the final Markdown. Any generated quality
  side artifact is separate; it cannot rewrite E5.
- Default segmented notification receives each E5
  `PublicNotificationSummary` plus its URL and existing typed lookahead/price
  inputs. `build_segmented_summary(
  summaries: Mapping[MarketSegment, PublicNotificationSummary], ...)` checks
  key/segment/date consistency, uses DTO coverage state/watchlist, and has no
  `Briefing` or `Briefing.market_summary` fallback on this path. Publisher
  derivation uses canonical `_internal.briefing_extract` prefixes plus shared
  `_internal.public_summary_extract` cleanup; missing/unsafe conclusion is a
  typed trust block. An AST/call-contract test pins the DTO-only input. Legacy
  unsegmented notification may retain its existing fallback outside u144.
- `quality_consistency` remains a defensive cross-artifact gate with existing
  rollback semantics.
- u143/future producers supply staged supplements before assembly completes.

## 12. Idempotence and composition properties

Required properties:

```text
P1 same generated inputs + same E1 -> byte-equal E6 and outcomes
P2 every replacement crosses projection and terminal validation
P3 zero producer executes after projection except deterministic repair
P4 zero mutation executes after validation begins
P5 every E5 digest matches exact UTF-8 archive bytes
P6 every expected segment has exactly one final/absent/blocked outcome; E6 has at least one E5
P7 protected diagnostics retain raw state while public regions contain none
P8 fallback outcome/code ordering is stable under mapping input order changes
P9 default segmented notification prose is a projection of E5 DTOs, never generated Briefing fields
```

Property tests target pure functions and serialization/digest behavior only,
consistent with the project's partial-PBT policy.
