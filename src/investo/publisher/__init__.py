"""Publisher (u3) — static-site archive writer + git commit/push (US-003, US-006).

This package consumes a ``Briefing`` (defined in ``investo.models``)
and:

1. Verifies the disclaimer is present (NFR-004).
2. Writes ``rendered_markdown`` atomically to
   ``archive/YYYY/MM/YYYY-MM-DD.md`` (FR-006 directory contract).
3. Stages, commits, and pushes the file via list-form ``git`` subprocess.

The package's public surface is finalized in Step 7 of the Code
Generation plan; this docstring is the bootstrap placeholder.

Reference:
    aidlc-docs/construction/plans/u3-publisher-code-generation-plan.md
    aidlc-docs/inception/application-design/component-methods.md
"""

__all__: list[str] = []
