"""Immutable CLI-provider selection shared by bootstrap and CI (u155)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Provider = Literal["claude", "codex"]
CLAUDE_REQUIRED = ("CLAUDE_CODE_OAUTH_TOKEN",)
NOTIFICATION_REQUIRED = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHANNEL_ID",
    "TELEGRAM_OPERATOR_CHAT_ID",
)


class LlmConfigError(ValueError):
    """Only a trusted variable name may appear in the error."""

    def __init__(self, variable: str) -> None:
        self.variable = variable
        super().__init__(f"Invalid or missing {variable}")


@dataclass(frozen=True, slots=True)
class LlmExecutionConfig:
    provider: Provider = "claude"
    model: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in ("claude", "codex"):
            raise LlmConfigError("INVESTO_LLM_PROVIDER")
        if self.provider == "codex" and (
            self.model is None
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", self.model) is None
        ):
            raise LlmConfigError("INVESTO_CODEX_MODEL")
        if self.provider == "claude" and self.model is not None:
            raise LlmConfigError("INVESTO_CODEX_MODEL")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> LlmExecutionConfig:
        provider = env.get("INVESTO_LLM_PROVIDER", "").strip() or "claude"
        if provider == "claude":
            return cls()
        if provider == "codex":
            return cls("codex", env.get("INVESTO_CODEX_MODEL", "").strip())
        raise LlmConfigError("INVESTO_LLM_PROVIDER")


def required_environment(config: LlmExecutionConfig, *, dry_run: bool) -> tuple[str, ...]:
    auth = (
        CLAUDE_REQUIRED
        if config.provider == "claude"
        else (
            "INVESTO_CODEX_MODEL",
            "INVESTO_CODEX_HOME",
        )
    )
    return (*auth, *(() if dry_run else NOTIFICATION_REQUIRED), "SITE_URL_BASE")


def missing_environment(env: Mapping[str, str], config: LlmExecutionConfig) -> tuple[str, ...]:
    return tuple(
        name
        for name in required_environment(
            config, dry_run=env.get("INVESTO_DRY_RUN", "").strip() == "1"
        )
        if not env.get(name, "").strip()
    )
