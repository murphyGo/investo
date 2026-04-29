"""Shared pytest fixtures for u5 orchestrator unit tests.

Per-stage fixtures (fake ``Aggregator`` / ``GitRunner`` / mocked
``BriefingPublisher`` / ``OperatorAlerter`` / record-replay
``ClaudeCodeRunner``) land alongside the stage tests in Steps 4-9
of ``aidlc-docs/construction/plans/u5-orchestrator-code-generation-plan.md``.

This file is the canonical destination for any helper that more
than one orchestrator test needs (e.g., the eventual
``_dummy_briefing`` factory or the integration-test ``MockTransport``
constructor) — preventing the per-test-file duplication that
DEBT-010 / DEBT-013 / DEBT-016 already track for the other units.
"""
