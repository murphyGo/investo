"""Hit/miss tests for ``briefing.leak_guard`` (NFR-007 AC-6.4, AC-7.3).

The R6 regex set (FD ``business-rules.md``) is closed. Each pattern has
at least one canonical hit example here. The miss-case curated list
documents strings that LOOK leak-like but should NOT match, calibrating
the false-positive rate.
"""

from __future__ import annotations

import pytest

from investo.briefing.leak_guard import LeakGuardHit, scan

# --- Hit cases — one canonical example per R6 pattern -----------------------


@pytest.mark.parametrize(
    "prefix",
    ["ghp", "ghs", "ghr", "gho", "ghu"],
)
def test_github_pat_all_prefixes(prefix: str) -> None:
    """Each of the 5 GitHub PAT prefixes (per R6 regex)."""
    text = f"key={prefix}_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "github_pat"
    assert hit.match_text.startswith(f"{prefix}_")


def test_aws_access_key() -> None:
    text = "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF in env"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "aws_access_key"


def test_jwt() -> None:
    # Synthetic JWT — three dot-separated base64url segments, with each
    # of the first two starting with ``eyJ`` (matching JSON ``{`` after
    # base64 encoding).
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signaturepartXY-_AB"
    hit = scan(f"token: {jwt}")
    assert hit is not None
    assert hit.pattern_name == "jwt"


def test_email() -> None:
    text = "Contact: user@example.com for support"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "email"


@pytest.mark.parametrize(
    "phone",
    ["010-1234-5678", "010 1234 5678", "01012345678"],
)
def test_korean_phone_formats(phone: str) -> None:
    """All three Korean phone formats (dashed, spaced, run-on)."""
    text = f"전화 {phone} 입니다"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "korean_phone"


def test_generic_long_base64_outside_url() -> None:
    """Long base64-alphabet run NOT inside an http(s) URL → flagged."""
    blob = "A" * 40
    text = f"key={blob}=="
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "oauth_long_base64"


# --- Miss cases — false-positive calibration --------------------------------


def test_clean_korean_text() -> None:
    text = "오늘 시장은 상승 마감했습니다."
    assert scan(text) is None


def test_clean_english_text() -> None:
    text = "S&P 500 closed at 5300, up 0.5%."
    assert scan(text) is None


def test_typical_briefing_section_is_clean() -> None:
    # Representative Stage 2 output — Korean prose with English tickers.
    text = (
        "## ② 전일 핵심 이슈\n"
        "AAPL은 0.3% 상승했으며 MSFT는 0.5% 하락했습니다. "
        "Federal Reserve의 발표가 시장 변동성을 높였습니다.\n"
    )
    assert scan(text) is None


def test_long_base64_inside_https_url_is_excluded() -> None:
    """AC-7.3 — base64-alphabet runs inside http(s) URLs are NOT
    treated as oauth tokens.
    """
    blob = "A" * 50
    text = f"See [doc](https://example.com/path/{blob}/page) for more"
    assert scan(text) is None


def test_long_base64_inside_http_url_is_excluded() -> None:
    blob = "B" * 60
    text = f"link: http://example.com/{blob} ..."
    assert scan(text) is None


def test_long_base64_after_url_with_whitespace_is_flagged() -> None:
    """If the candidate is AFTER an http URL but separated by
    whitespace, the URL-context exclusion does NOT fire — the candidate
    is in plain text, not URL.
    """
    blob = "C" * 50
    text = f"see https://example.com/x then {blob}=="
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "oauth_long_base64"


def test_long_base64_with_url_outside_lookback_window_is_flagged() -> None:
    """If a URL appears earlier in the text but outside the 200-char
    lookback window, the URL exclusion does NOT apply.
    """
    blob = "D" * 50
    # 250 chars of filler between the URL end and the candidate start.
    filler = "x" * 250
    text = f"https://example.com/foo {filler} {blob}"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "oauth_long_base64"


def test_short_base64_under_threshold() -> None:
    # 39 chars — under the 40-char minimum length in the regex.
    text = "data: " + ("A" * 39)
    assert scan(text) is None


def test_korean_010_room_number_not_phone() -> None:
    """``010실`` is "room 010" in Korean — should not match the phone
    pattern (which requires 010 followed by 4-4 digits).
    """
    text = "오늘 010실에서 회의가 있었습니다"
    assert scan(text) is None


def test_at_symbol_without_dotted_domain() -> None:
    """A bare ``@username`` without a dotted domain after does NOT
    match the email pattern (``[^\\s@]+@[^\\s@]+\\.[^\\s@]+`` requires
    the ``.<suffix>`` segment).
    """
    text = "Twitter handle @username only"
    assert scan(text) is None


def test_email_long_no_dot_completes_quickly() -> None:
    """Regression guard for the ReDoS-safe email regex (Step 3 H1).

    The original FD R6 pattern ``\\S+@\\S+\\.\\S+`` had overlapping
    quantifiers that backtracked quadratically on long no-match input
    (``"a"*N + "@" + "b"*N`` with no ``.``). The current
    ``[^\\s@]+@[^\\s@]+\\.[^\\s@]+`` form has no overlap. This test
    pins linear behavior — any future regression that re-introduces
    ``\\S+@\\S+`` would slow this test from sub-millisecond to seconds.
    """
    import time

    # Use chars that are non-whitespace but NOT in any other R6 pattern's
    # alphabet (no base64 alphabet, no digits, no ``gh*_`` / ``AKIA`` /
    # ``eyJ`` prefixes, no ``010`` digit run). Isolates the test to the
    # email regex's backtracking behavior.
    adversarial = ("!" * 5000) + "@" + ("?" * 5000)  # no dot — no email match
    start = time.monotonic()
    assert scan(adversarial) is None
    elapsed = time.monotonic() - start
    # Generous bound: linear behavior should complete in << 0.1 s; we
    # allow 1 s for slow CI. The original quadratic pattern would take
    # several seconds on this input on most machines.
    assert elapsed < 1.0, f"email regex took {elapsed:.2f}s — possible ReDoS regression"


def test_autolink_https_excludes_long_base64() -> None:
    """Markdown autolink ``<https://...>`` form — the URL exclusion
    correctly fires (Step 3 H2 regression pin).
    """
    blob = "A" * 50
    text = f"see <https://example.com/path/{blob}> here"
    assert scan(text) is None


def test_mailto_link_is_flagged_as_email() -> None:
    """``mailto:user@example.com`` in markdown still triggers the email
    pattern — defensible: a mailto link in the public archive IS an
    email leak. Documented behavior (Step 3 M2 regression pin).
    """
    text = "[Contact](mailto:user@example.com)"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "email"


# --- Result shape -----------------------------------------------------------


def test_hit_is_namedtuple() -> None:
    text = "AKIA1234567890ABCDEF"
    hit = scan(text)
    assert isinstance(hit, LeakGuardHit)
    assert isinstance(hit.pattern_name, str)
    assert isinstance(hit.match_text, str)


def test_match_text_truncated_to_excerpt_limit() -> None:
    """Long matches are truncated to ≤64 chars in the LeakGuardHit
    so logs don't echo unbounded credential-shaped content.
    """
    # 200-char base64-alphabet run — full match is 200 chars; excerpt
    # must be ≤64.
    blob = "A" * 200
    text = f"k={blob}"
    hit = scan(text)
    assert hit is not None
    assert len(hit.match_text) <= 64


def test_first_pattern_wins() -> None:
    """When multiple patterns could match the same span, the order in
    ``_PATTERNS`` decides — github_pat before oauth_long_base64.
    """
    # ``ghp_`` followed by 36+ base64-alphabet chars matches both
    # github_pat AND oauth_long_base64. Specific credential pattern
    # must win.
    text = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    hit = scan(text)
    assert hit is not None
    assert hit.pattern_name == "github_pat"


def test_clean_input_returns_none() -> None:
    assert scan("") is None
    assert scan("hello world") is None
