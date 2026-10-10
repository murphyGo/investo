# u179 Domain entities

Existing Path list and SegmentBundleState are unchanged. Render-only month grouping is dict[str,list[Path]], no stored date/quality DTO. Parsed date|None and canonical-parent bool are local render values. Sealed legacy input is Mapping[Path,FinalizedPublicDocument]|None; driver consumes optional tuple[FinalizedPublicDocument,...]. Current pipeline supplies only real finalized_bundle.documents after writer verification.

Future terminal_snippets and terminal_limitations are optional Mapping[Path,str]; strings are trusted already-selected public view values from u171. UI does not implement validation/hash/selection/availability. Zero content reads for default historical listing, current sealed text is in memory. Existing output Path and façade exports stay compatible.
