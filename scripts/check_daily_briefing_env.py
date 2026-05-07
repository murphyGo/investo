#!/usr/bin/env python3
"""CI guard for ``daily-briefing.yml`` required environment wiring.

The workflow injects GitHub Secrets as environment variables before
running ``python -m investo``. This script performs the cheap,
secret-safe boundary checks before the heavier pipeline starts:

- all five required variables are present and non-empty after strip,
- public Telegram channel and operator chat IDs are disjoint,
- ``SITE_URL_BASE`` is an HTTP(S) URL,
- ``OPENAI_API_KEY`` is required only when ``INVESTO_OPENAI_VISUALS=1``
  (u27 cost guard — CLAUDE.md #4 "free APIs only" enforced at the code
  level so an opt-in surface cannot run without the matching secret).

Failures are emitted as GitHub Actions ``::error::`` annotations that
name only the missing variable or failed invariant. Secret values are
never printed.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlparse

REQUIRED_ENV_VARS: tuple[str, ...] = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHANNEL_ID",
    "TELEGRAM_OPERATOR_CHAT_ID",
    "SITE_URL_BASE",
)

# u27: opt-in flag for the OpenAI visual surface. When equal to ``"1"``
# the API key becomes required; otherwise it is optional (the surface
# is disabled inside ``visuals.openai_image.load_openai_visual_config``
# regardless of whether the key is set).
OPENAI_VISUALS_FLAG_VAR = "INVESTO_OPENAI_VISUALS"
OPENAI_API_KEY_VAR = "OPENAI_API_KEY"


def validate_env(env: Mapping[str, str]) -> list[str]:
    """Return secret-safe validation error messages for ``env``."""
    values = {name: env.get(name, "").strip() for name in REQUIRED_ENV_VARS}
    errors: list[str] = []

    for name in REQUIRED_ENV_VARS:
        if not values[name]:
            errors.append(f"Missing required GitHub Secret: {name}")

    if (
        values["TELEGRAM_BRIEFING_CHANNEL_ID"]
        and values["TELEGRAM_OPERATOR_CHAT_ID"]
        and values["TELEGRAM_BRIEFING_CHANNEL_ID"] == values["TELEGRAM_OPERATOR_CHAT_ID"]
    ):
        errors.append("TELEGRAM_BRIEFING_CHANNEL_ID and TELEGRAM_OPERATOR_CHAT_ID must be disjoint")

    if values["SITE_URL_BASE"]:
        parsed = urlparse(values["SITE_URL_BASE"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("SITE_URL_BASE must be an HTTP(S) URL")

    # u27 OpenAI opt-in branch: only require the key when the operator
    # has explicitly enabled the cost-bearing surface. Default workflow
    # behaviour pins the flag to ``"0"`` so this branch never fires;
    # an experiment must flip both the flag and the secret together.
    if (
        env.get(OPENAI_VISUALS_FLAG_VAR, "").strip() == "1"
        and not env.get(OPENAI_API_KEY_VAR, "").strip()
    ):
        errors.append(f"{OPENAI_API_KEY_VAR} is required when {OPENAI_VISUALS_FLAG_VAR}=1")

    return errors


def main() -> int:
    errors = validate_env(os.environ)
    for message in errors:
        print(f"::error::{message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
