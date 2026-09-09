"""Bounded encrypted write-back to one private Environment Secret (u155)."""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass

import httpx

from investo._internal.codex_auth import AuthDocument

RUNTIME_REPOSITORY = "murphyGo/investo-runtime"
RUNTIME_ENVIRONMENT = "codex-runtime"
AUTH_SECRET = "CODEX_AUTH_JSON"


class AuthPersistenceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("codex_auth_persistence_failed")


@dataclass(frozen=True, slots=True)
class SecretTarget:
    repository: str = RUNTIME_REPOSITORY
    environment: str = RUNTIME_ENVIRONMENT
    secret: str = AUTH_SECRET

    def __post_init__(self) -> None:
        if (self.repository, self.environment, self.secret) != (
            RUNTIME_REPOSITORY,
            RUNTIME_ENVIRONMENT,
            AUTH_SECRET,
        ):
            raise AuthPersistenceError()

    @property
    def path(self) -> str:
        return f"/repos/{self.repository}/environments/{self.environment}/secrets"


class EnvironmentSecretStore:
    def __init__(
        self,
        client: httpx.AsyncClient,
        token: str,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not token.strip():
            raise AuthPersistenceError()
        self._client = client
        self._token = token
        self._clock = clock
        self._target = SecretTarget()

    async def _request(
        self,
        method: str,
        path: str,
        deadline: float,
        *,
        payload: dict[str, str] | None = None,
    ) -> httpx.Response:
        for attempt in range(3):
            remaining = deadline - self._clock()
            if remaining <= 0:
                break
            try:
                async with asyncio.timeout(min(10.0, remaining)):
                    response = await self._client.request(
                        method,
                        f"https://api.github.com{path}",
                        headers={
                            "Authorization": f"Bearer {self._token}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        json=payload,
                        follow_redirects=False,
                        timeout=min(10.0, remaining),
                    )
                if response.status_code not in (429, 500, 502, 503, 504):
                    return response
                delay = (2.0, 8.0, 0.0)[attempt]
                retry_after = response.headers.get("Retry-After")
                if retry_after is not None:
                    with suppress(ValueError):
                        delay = max(delay, float(retry_after))
            except (httpx.HTTPError, TimeoutError):
                delay = (2.0, 8.0, 0.0)[attempt]
            if attempt == 2 or delay >= deadline - self._clock():
                break
            await asyncio.sleep(delay)
        raise AuthPersistenceError()

    async def verify_environment_secret(self) -> None:
        response = await self._request(
            "GET",
            f"{self._target.path}/{AUTH_SECRET}",
            self._clock() + 60,
        )
        # This endpoint returns metadata only; never reads credential plaintext.
        try:
            if response.status_code != 200 or response.json().get("name") != AUTH_SECRET:
                raise AuthPersistenceError()
        except (ValueError, AttributeError):
            raise AuthPersistenceError() from None

    async def persist(self, document: AuthDocument) -> None:
        # Optional operations dependency; plain Claude installation needs no NaCl.
        from nacl.public import PublicKey, SealedBox

        deadline = self._clock() + 60
        response = await self._request("GET", f"{self._target.path}/public-key", deadline)
        try:
            if response.status_code != 200:
                raise ValueError
            key = response.json()
            key_id = key["key_id"]
            if not isinstance(key_id, str) or not key_id:
                raise ValueError
            public_key = PublicKey(base64.b64decode(key["key"], validate=True))
            encrypted = base64.b64encode(SealedBox(public_key).encrypt(document.raw)).decode(
                "ascii"
            )
        except (ValueError, KeyError, TypeError):
            raise AuthPersistenceError() from None
        response = await self._request(
            "PUT",
            f"{self._target.path}/{AUTH_SECRET}",
            deadline,
            payload={"encrypted_value": encrypted, "key_id": key_id},
        )
        if response.status_code not in (201, 204):
            raise AuthPersistenceError()
