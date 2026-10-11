# u177 Business rules

D177.1: Explicit primary links rather than clickable whole cards; stable test IDs and headings. Quick market links appear before cards; natural content length, no clipping/ellipsis/clamping.
D177.2: Existing CoverageStatus labels normal/partial/limited/failed plus unknown; textual label always present. Quality is only the current sealed text's canonical status parser; no source-name/stale dashboard inference.
D177.3: Gate accepts optional `home_page_text: str|None=None` for old callers. Pipeline existing gate receives `home_page_path: Path|None=None`; current segmented publisher explicitly supplies generated home path. That read is mandatory, failure propagates for pre-git rollback. Parser compares exact date/segment/generated/status attributes and visible text, not data attributes alone. Cards absent in current snapshot cannot claim generated/normal.
D177.4: Fallback cards show `target_date 미발행` and `최근 발행 fallback_date`; no old conclusion/status. No history yields archive-index link, no fabricated target date URL.
D177.5: None driver retains historical compatibility; direct `update_index_hero` maintains original signature with optional bundle state argument. Existing blocks are migrated by known headers/markers; unknown sections/footer retained, idempotent writes and returned path tuple unchanged.
D177.6: Consume u176 CSS classes exactly; optional ticker/recent list in original concept not required.
D177.7: Choose escaped plain HTML for text fields and existing build-time Markdown for canonical primary links. Hrefs come from canonical date/segment path helpers, no raw interpolation/new regex sanitizer. Legacy summary emphasis is processed by existing MkDocs span parsing after HTML escaping; exact terminal snippets remain literal with markdown=0. No daily runtime Markdown dependency.

Future v3 accepts only already selected public plain snippets/quality text from u171 adapter. These fields bypass legacy extraction/projection and are escaped/wrapped as-is. The current runtime does not pretend schema3 API/hash validation exists. Trust semantics remain in existing owner; financial/status/date data are not inferred by CSS.
