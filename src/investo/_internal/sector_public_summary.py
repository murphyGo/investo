"""Bounded, credential-screened operational JSON for public sector commands."""

from __future__ import annotations

import json
import os
import re

from investo._internal.redaction import SECRET_ENV_VARS, redact_text, scan_for_leak


def screen_public_summary(text: str) -> str | None:
    secrets = tuple(
        value for name in SECRET_ENV_VARS if (value := os.environ.get(name, "").strip())
    )
    if len(text) > 4096 or any(value in text for value in secrets):
        return None
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(canonical) > 4096 or any(value in canonical for value in secrets):
        return None
    screened = dict(payload)
    # These identities are already validated by the renderer or _probe.
    # Exact configured secrets were checked before and after JSON decoding.
    # Exempt only exact field/shape pairs from generic credential heuristics.
    for field, pattern in (
        ("snapshot_id", r"sha256:[0-9a-f]{64}"),
        ("commit", r"[0-9a-f]{40}"),
        ("run_id", r"[0-9]{1,20}"),
    ):
        identity = screened.get(field)
        if isinstance(identity, str) and re.fullmatch(pattern, identity):
            screened[field] = "[VERIFIED_ID]"
    scan_text = json.dumps(screened, sort_keys=True, separators=(",", ":"))
    if redact_text(scan_text) != scan_text or scan_for_leak(scan_text) is not None:
        return None
    return canonical
