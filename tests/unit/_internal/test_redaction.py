"""Tests for the u27 redaction chokepoint.

These tests pin two contracts:

1. The five canonical secret-shaped patterns
   (env-var values / Telegram bot token / Telegram chat id /
   OAuth-JWT-PAT base64 / HTTP query string) are all redacted by a
   single ``redact_text`` call regardless of the calling surface.

2. The four call sites
   (``__main__._redact_diagnostic_text``,
   ``models.coverage.sanitize_source_error_message``,
   ``visuals.provenance.sanitize_provenance_text``,
   ``briefing.leak_guard.scan``) ride on the same chokepoint —
   adding a new pattern in :mod:`investo._internal.redaction` is
   immediately visible at every surface.

Hypothesis-style PBT is intentionally not used here: the canonical
secret shapes are deterministic literals from the project's threat
model, not a generative property.
"""

from __future__ import annotations

import re

import pytest

from investo.__main__ import _redact_diagnostic_text
from investo._internal.redaction import (
    SECRET_ENV_VARS,
    SECRET_PATTERNS,
    RedactionPolicy,
    redact_text,
    scan_for_leak,
)
from investo.briefing.leak_guard import scan
from investo.models import sanitize_source_error_message
from investo.visuals.provenance import sanitize_provenance_text

# ---------------------------------------------------------------------------
# Canonical fixtures — one per secret-shaped pattern family
# ---------------------------------------------------------------------------

# Telegram bot token shape — nine-digit ID, colon, 35-char tail.
_BOT_TOKEN = "1234567890:ABCDEF-thisIsALongerThan20Chars_xyz"
# Long numeric chat id (≥ 7 digits triggers the chat-id regex).
_CHAT_ID = "987654321"
# 60-char base64 alphabet run (≥ 40 floor — triggers oauth_long_base64).
_LONG_BASE64 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ab"
# HTTP query-string with an api_key=... segment.
_API_KEY_URL = "https://api.example.com/data?api_key=hunter2&start=2026-05-01"
# JWT shape (eyJ.eyJ.signature).
_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signaturepartXY-_AB"
# GitHub PAT shape.
_GITHUB_PAT = "ghp_" + "A" * 40
# AWS Access Key ID shape.
_AWS_KEY = "AKIA" + "QRSTUVWXYZ012345"


# ---------------------------------------------------------------------------
# Sanity: the chokepoint module's own behaviour
# ---------------------------------------------------------------------------


class TestChokepointRedactText:
    def test_strict_redacts_bot_token(self) -> None:
        out = redact_text(f"connecting via {_BOT_TOKEN}", policy=RedactionPolicy.STRICT)
        assert _BOT_TOKEN not in out
        assert "[REDACTED_BOT_TOKEN]" in out

    def test_strict_redacts_long_chat_id(self) -> None:
        out = redact_text(f"posted to chat {_CHAT_ID}", policy=RedactionPolicy.STRICT)
        assert _CHAT_ID not in out
        assert "[REDACTED_CHAT_ID]" in out

    def test_strict_redacts_long_base64(self) -> None:
        out = redact_text(f"key={_LONG_BASE64}", policy=RedactionPolicy.STRICT)
        assert _LONG_BASE64 not in out
        # Replacement is ``[REDACTED]`` (catch-all marker for the
        # generic long-base64 family).
        assert "[REDACTED]" in out

    def test_strict_redacts_query_string_value(self) -> None:
        out = redact_text(_API_KEY_URL, policy=RedactionPolicy.STRICT)
        assert "hunter2" not in out
        assert "api_key" not in out
        # Query-key + value both replaced.
        assert "[REDACTED]=[REDACTED]" in out

    def test_strict_redacts_jwt(self) -> None:
        out = redact_text(f"Authorization: Bearer {_JWT}", policy=RedactionPolicy.STRICT)
        assert _JWT not in out
        assert "[REDACTED_JWT]" in out

    def test_strict_redacts_github_pat(self) -> None:
        out = redact_text(f"token={_GITHUB_PAT}", policy=RedactionPolicy.STRICT)
        assert _GITHUB_PAT not in out
        assert "[REDACTED_GITHUB_PAT]" in out

    def test_strict_redacts_aws_access_key(self) -> None:
        out = redact_text(f"key={_AWS_KEY}", policy=RedactionPolicy.STRICT)
        assert _AWS_KEY not in out
        assert "[REDACTED_AWS_KEY]" in out

    def test_strict_redacts_secret_env_var_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        secret_value = "rotating-token-value-2026-05-08"
        monkeypatch.setenv("OPENAI_API_KEY", secret_value)
        # u27: env-var value redaction works for OpenAI even when the
        # surface is disabled — defense-in-depth against a leaked key
        # appearing in a stderr stream.
        out = redact_text(f"openai status: {secret_value}", policy=RedactionPolicy.STRICT)
        assert secret_value not in out
        assert "[REDACTED]" in out

    def test_url_aware_skips_long_base64_inside_http_url(self) -> None:
        text = f"see https://example.com/path/{_LONG_BASE64}/page for details"
        out = redact_text(text, policy=RedactionPolicy.URL_AWARE)
        # URL-context filter preserves the long base64 inside the URL.
        assert _LONG_BASE64 in out

    def test_url_aware_still_redacts_long_base64_outside_url(self) -> None:
        text = f"raw value: {_LONG_BASE64}"
        out = redact_text(text, policy=RedactionPolicy.URL_AWARE)
        assert _LONG_BASE64 not in out

    def test_strict_redacts_long_base64_inside_http_url(self) -> None:
        # The strict policy is intentionally more aggressive than url-
        # aware; URL substrings are not preserved.
        text = f"see https://example.com/path/{_LONG_BASE64}/page"
        out = redact_text(text, policy=RedactionPolicy.STRICT)
        assert _LONG_BASE64 not in out


# ---------------------------------------------------------------------------
# Cross-surface equivalence: every site uses the chokepoint
# ---------------------------------------------------------------------------


class TestSurfacesShareChokepoint:
    """For each canonical secret shape, every surface must redact it.

    The cross-test pins that no surface drifts — adding a new shape to
    :data:`SECRET_PATTERNS` should immediately propagate to every
    redaction site at next test run.
    """

    @pytest.mark.parametrize(
        ("payload", "forbidden_substring"),
        [
            (f"call {_BOT_TOKEN} now", _BOT_TOKEN),
            (f"chat {_CHAT_ID} replied", _CHAT_ID),
            (f"key={_LONG_BASE64}", _LONG_BASE64),
            (f"api_key={_GITHUB_PAT}", _GITHUB_PAT),
            (f"id {_AWS_KEY}", _AWS_KEY),
        ],
    )
    def test_main_redact_diagnostic_text(self, payload: str, forbidden_substring: str) -> None:
        out = _redact_diagnostic_text(payload)
        assert forbidden_substring not in out

    @pytest.mark.parametrize(
        ("payload", "forbidden_substring"),
        [
            (f"call {_BOT_TOKEN} now", _BOT_TOKEN),
            (f"chat {_CHAT_ID} replied", _CHAT_ID),
            (f"key={_LONG_BASE64}", _LONG_BASE64),
            (f"api_key={_GITHUB_PAT}", _GITHUB_PAT),
            (f"id {_AWS_KEY}", _AWS_KEY),
        ],
    )
    def test_coverage_sanitize_source_error_message(
        self, payload: str, forbidden_substring: str
    ) -> None:
        out = sanitize_source_error_message(payload)
        assert forbidden_substring not in out

    @pytest.mark.parametrize(
        ("payload", "forbidden_substring"),
        [
            (f"call {_BOT_TOKEN}", _BOT_TOKEN),
            (f"chat {_CHAT_ID}", _CHAT_ID),
            (f"value={_LONG_BASE64}", _LONG_BASE64),
            (f"x={_GITHUB_PAT}", _GITHUB_PAT),
            (f"x={_AWS_KEY}", _AWS_KEY),
        ],
    )
    def test_provenance_sanitize_provenance_text(
        self, payload: str, forbidden_substring: str
    ) -> None:
        out = sanitize_provenance_text(payload)
        assert forbidden_substring not in out

    def test_secret_env_var_values_redacted_at_every_surface(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "very-secret-123abcDEF456ghiJKL"
        monkeypatch.setenv("OPENAI_API_KEY", secret)

        for surface_name, fn in (
            ("__main__", _redact_diagnostic_text),
            ("coverage", sanitize_source_error_message),
            ("provenance", sanitize_provenance_text),
        ):
            out = fn(f"observed: {secret}")
            assert secret not in out, f"{surface_name} did not redact OPENAI_API_KEY value"


class TestProvenanceCoverageEquivalence:
    """``sanitize_provenance_text`` and ``sanitize_source_error_message``
    must produce identical output for any payload short enough to avoid
    coverage's 120-char SVG-row truncation. They share the chokepoint
    so equivalence is the structural pin.
    """

    @pytest.mark.parametrize(
        "payload",
        [
            f"failure: {_BOT_TOKEN}",
            f"chat {_CHAT_ID} dropped",
            f"value {_LONG_BASE64}",
            f"jwt {_JWT}",
            "no secret in this short message",
        ],
    )
    def test_chokepoint_equivalence(self, payload: str) -> None:
        # coverage strips/collapses whitespace then truncates; for short
        # single-space-separated payloads the two outputs are equal.
        coverage_out = sanitize_source_error_message(payload)
        provenance_out = sanitize_provenance_text(payload)
        # provenance does not collapse whitespace; coverage does. Apply
        # the same collapse to provenance to compare body-level equality.
        provenance_collapsed = " ".join(provenance_out.split())
        assert coverage_out == provenance_collapsed


# ---------------------------------------------------------------------------
# Leak-guard URL-aware vs strict
# ---------------------------------------------------------------------------


class TestLeakGuardURLAware:
    def test_long_base64_inside_url_is_skipped(self) -> None:
        markdown = f"See [news article](https://example.com/articles/{_LONG_BASE64}/page)\n"
        # The leak guard filters URL-context base64 — no hit.
        assert scan(markdown) is None

    def test_long_base64_outside_url_is_caught(self) -> None:
        markdown = f"raw token: {_LONG_BASE64}"
        hit = scan(markdown)
        assert hit is not None
        assert hit.pattern_name == "oauth_long_base64"

    def test_jwt_is_caught_outside_url(self) -> None:
        markdown = f"Authorization: Bearer {_JWT}"
        hit = scan(markdown)
        assert hit is not None
        assert hit.pattern_name == "jwt"

    def test_github_pat_takes_precedence_over_long_base64(self) -> None:
        # A github_pat-shaped string also matches the generic oauth_long_base64
        # pattern; precedence (per SECRET_PATTERNS order) reports github_pat.
        # Pad the PAT prefix so the suffix-only match is unambiguous.
        markdown = f"token: {_GITHUB_PAT}"
        hit = scan(markdown)
        assert hit is not None
        assert hit.pattern_name == "github_pat"


# ---------------------------------------------------------------------------
# Module shape — enforce single source of truth
# ---------------------------------------------------------------------------


class TestSingleSourceOfTruth:
    def test_secret_env_vars_includes_openai(self) -> None:
        assert "OPENAI_API_KEY" in SECRET_ENV_VARS

    def test_secret_env_vars_covers_known_secrets(self) -> None:
        # Pin the exact set so a future contributor adding a new env-var
        # registers it here AND triggers a test failure if redaction
        # surfaces drift.
        assert set(SECRET_ENV_VARS) == {
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_BRIEFING_CHANNEL_ID",
            "TELEGRAM_OPERATOR_CHAT_ID",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "OPENAI_API_KEY",
            "FRED_API_KEY",
            "INVESTO_KRX_SERVICE_KEY",
            "INVESTO_DATA_GO_KR_SERVICE_KEY",
            "OPENDART_API_KEY",
        }

    def test_secret_env_vars_includes_krx_service_key(self) -> None:
        # FSC KRX adapters (index-price, stock-price) read this env var
        # at fetch time; its value must be redacted from any operator-/
        # reader-facing surface.
        assert "INVESTO_KRX_SERVICE_KEY" in SECRET_ENV_VARS

    def test_secret_env_vars_includes_data_go_kr_fallback(self) -> None:
        # Legacy fallback name consulted by both FSC KRX adapters when
        # ``INVESTO_KRX_SERVICE_KEY`` is unset; redaction must apply
        # identically.
        assert "INVESTO_DATA_GO_KR_SERVICE_KEY" in SECRET_ENV_VARS

    def test_secret_env_vars_includes_opendart(self) -> None:
        # u41 OpenDART disclosure adapter — enrolled ahead of the
        # adapter shipping so the GHA secret cannot leak from a
        # pre-adapter cron probe.
        assert "OPENDART_API_KEY" in SECRET_ENV_VARS

    def test_redact_text_scrubs_krx_service_key_value(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # KRX service keys arrive URL-encoded (``%2B`` / ``%2F`` /
        # ``%3D``). Verify the env-var-value scrub fires regardless of
        # encoding shape — this is the substring path, not a regex.
        secret_value = "abc%2BdEf%2Fghi%3D"
        monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", secret_value)
        diagnostic = (
            f"GET https://apis.data.go.kr/1160100/service?serviceKey={secret_value} -> HTTP 401"
        )
        scrubbed = redact_text(diagnostic)
        assert secret_value not in scrubbed
        assert "[REDACTED]" in scrubbed

    def test_redact_text_scrubs_opendart_api_key_value(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # OpenDART keys are 40-char hex; verify env-var scrub fires
        # before the adapter exists (the regex catalogue would also
        # match the long-base64 shape, but the env-var path is the
        # primary guarantee).
        secret_value = "0123456789abcdef0123456789abcdef01234567"
        monkeypatch.setenv("OPENDART_API_KEY", secret_value)
        scrubbed = redact_text(f"crc_key={secret_value}&corp_code=00126380")
        assert secret_value not in scrubbed

    def test_secret_patterns_include_all_canonical_shapes(self) -> None:
        names = {defn.name for defn in SECRET_PATTERNS}
        # Pin the canonical pattern names so the chokepoint cannot be
        # silently narrowed (a regression that would weaken every surface).
        assert names == {
            "github_pat",
            "aws_access_key",
            "bot_token",
            "jwt",
            "email",
            "korean_phone",
            "chat_id",
            "oauth_long_base64",
        }

    # ------------------------------------------------------------------
    # Structural anti-regression — every redaction surface delegates
    # ------------------------------------------------------------------
    #
    # u27 QA M2: extend the original ``__main__``-only scan to cover
    # every redaction surface in the project. The four surfaces below
    # MUST NOT carry their own ``re.compile`` calls; redaction policy
    # lives exclusively in :mod:`investo._internal.redaction`. A new
    # surface adopting the chokepoint should be added to
    # ``_REDACTION_SURFACES`` so this guard fires on regression.

    @pytest.mark.parametrize(
        ("module_path", "expected_chokepoint_marker"),
        [
            # (importable module, a substring proving the chokepoint
            # API is referenced in that file — guards against
            # "delete the regex but never call the chokepoint" drift)
            ("investo.__main__", "redact_text"),
            ("investo.models.coverage", "redact_text"),
            ("investo.visuals.provenance", "redact_text"),
            ("investo.briefing.leak_guard", "scan_for_leak"),
            # u27 M1: notifier._telegram folded into the chokepoint.
            ("investo.notifier._telegram", "redact_text"),
        ],
    )
    def test_redaction_surface_does_not_carry_local_regex(
        self, module_path: str, expected_chokepoint_marker: str
    ) -> None:
        """Every redaction surface delegates to the chokepoint.

        Two structural assertions per surface:

        1. The surface's source file references the chokepoint API
           (``redact_text`` for replace-all sites,
           ``scan_for_leak`` for the leak guard). Catches the
           "deleted local regex but never wired up the chokepoint"
           regression.
        2. The surface's source file contains zero ``re.compile``
           calls AND zero secret-shaped regex literals. Catches the
           reverse — re-introducing a local bot-token / chat-id /
           long-base64 / query-string / OAuth-or-JWT pattern after
           the chokepoint migration.

        Adding a new surface: append ``(module_path, marker)`` to the
        parametrization above and the guard inherits.
        """
        import importlib

        module = importlib.import_module(module_path)
        source = module.__file__
        assert source is not None, f"{module_path} has no __file__"
        text = open(source, encoding="utf-8").read()  # noqa: SIM115

        # (1) chokepoint reference present.
        assert expected_chokepoint_marker in text, (
            f"{module_path} does not reference the chokepoint "
            f"(expected substring {expected_chokepoint_marker!r}); "
            "redaction surfaces must delegate to "
            "investo._internal.redaction"
        )

        # (2) zero ``re.compile`` (the chokepoint owns all compilation).
        assert "re.compile" not in text, (
            f"{module_path} reintroduces a local re.compile() call; "
            "the chokepoint owns all secret-shaped regex compilation"
        )

        # (3) Spot-check for canonical secret-shaped regex literals.
        # These are the exact shapes the chokepoint redacts. Detecting
        # them in any surface's source means a contributor copy-pasted
        # a pattern instead of importing the chokepoint.
        forbidden_literal_patterns = (
            # bot-token shape: "\d{N,}:[A-Za-z0-9_-]{M,}" anywhere in a
            # raw string literal.
            (r"r['\"][^'\"]*\\d\{\d+,?\}:\[A-Za-z0-9", "bot-token regex"),
            # generic long base64 floor: "[A-Za-z0-9+/]{N,}" with N >= 20.
            (r"\[A-Za-z0-9\+/?\]\{[2-9]\d,", "long-base64 regex"),
            # OAuth/JWT shape: literal "eyJ" header start followed by a
            # base64-url charset.
            (r"r['\"][^'\"]*eyJ\[A-Za-z0-9", "JWT regex"),
            # Query-string capture: "(\?|&)" followed by "=".
            (r"\(\\\?\|&\)[^)]*=", "query-string redact regex"),
        )
        for forbidden, label in forbidden_literal_patterns:
            assert re.search(forbidden, text) is None, (
                f"{module_path} contains a {label} literal — use the "
                "chokepoint instead of redefining the pattern"
            )


# ---------------------------------------------------------------------------
# scan_for_leak directly (chokepoint API)
# ---------------------------------------------------------------------------


class TestScanForLeak:
    def test_clean_text_returns_none(self) -> None:
        assert scan_for_leak("ordinary briefing prose with no secrets") is None

    def test_returns_none_on_empty(self) -> None:
        assert scan_for_leak("") is None

    def test_email_matches(self) -> None:
        hit = scan_for_leak("contact: ops@example.com")
        assert hit is not None
        assert hit.pattern_name == "email"

    def test_korean_phone_matches(self) -> None:
        hit = scan_for_leak("연락처: 010-1234-5678")
        assert hit is not None
        assert hit.pattern_name == "korean_phone"
