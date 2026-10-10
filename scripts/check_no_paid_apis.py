#!/usr/bin/env python3
"""CI cost guard — reject paid APIs and u145 provider fallback drift.

Implements NFR-002 AC-2.2: a CI grep guard, executed by the lint job
(or by ``tests/unit/sources/test_no_paid_apis.py`` as a subprocess
during ``pytest``), fails the build if any source file under
``src/investo/sources/`` matches a known-paid-API pattern.

The blocklist below is intentionally narrow: it catches paid-first market data
providers and provider-specific SDK/env-var references, but does not block broad
terms such as ``API_KEY`` because the repo intentionally uses free/public keys
for official providers.

Usage::

    python scripts/check_no_paid_apis.py

Exit codes:
    0 — no paid-API references found
    1 — at least one offender; details printed to stderr
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Patterns are matched case-insensitively against every line of
# every ``.py`` file under ``SOURCES_ROOT``. Each entry should be a
# regex string (not a compiled pattern) so this list stays readable.
#
BLOCKLIST: list[str] = [
    r"\bblpapi\b",
    r"\bbloomberg(?:professional|terminal)?\.com\b",
    r"\bBLOOMBERG_[A-Z0-9_]*",
    r"\brefinitiv\b",
    r"\beikon\b",
    r"\bREFINITIV_[A-Z0-9_]*",
    r"\bEIKON_[A-Z0-9_]*",
    r"\bfactset\b",
    r"\bFACTSET_[A-Z0-9_]*",
    r"\bcapitaliq\b",
    r"\bcapital\s+iq\b",
    r"\bCAPITALIQ_[A-Z0-9_]*",
    r"\bmorningstar\s+direct\b",
    r"\bMORNINGSTAR_DIRECT_[A-Z0-9_]*",
    r"\bnasdaq\s+data\s+link\b",
    r"\bquandl\b",
    r"\bNASDAQ_DATA_LINK_[A-Z0-9_]*",
    r"\bQUANDL_[A-Z0-9_]*",
]

SOURCES_ROOT = Path(__file__).resolve().parent.parent / "src" / "investo" / "sources"
YAHOO_ADAPTER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "investo"
    / "sector_dashboard"
    / "yahoo_data.py"
)

# u145 is a deliberately single-provider product. Parse its syntax rather
# than trusting comments or a finite fallback blocklist: the fixed assignments
# must match, every URL/domain literal must be the accepted Yahoo host, provider
# SDK imports are excluded by allowlist, and runtime endpoint identifiers are
# forbidden.
YAHOO_REQUIRED_ASSIGNMENTS: dict[str, object] = {
    "YAHOO_API_BASE": "https://query2.finance.yahoo.com/v8/finance/chart",
    "YAHOO_API_HOST": "query2.finance.yahoo.com",
    "YAHOO_QUERY": (("interval", "1d"), ("includePrePost", "false")),
}
YAHOO_ALLOWED_DOMAIN_LITERALS = frozenset({"query2.finance.yahoo.com"})
YAHOO_ALLOWED_NON_PROVIDER_DOTTED_LITERALS = frozenset(
    {
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
    }
)
YAHOO_ALLOWED_IMPORT_MODULES = frozenset(
    {
        "__future__",
        "asyncio",
        "collections",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "httpx",
        "json",
        "math",
        "time",
        "typing",
        "urllib.parse",
        "investo._internal.redaction",
        "investo.models.sector",
        "investo.models.sector_public",
        "investo.models.market_groups",
        "zoneinfo",
        "investo.models.market_calendar",
    }
)
YAHOO_FORBIDDEN_RUNTIME_IDENTIFIERS = frozenset(
    {"base_url", "endpoint", "fallback", "provider_url", "runtime_url"}
)
_DOMAIN_LITERAL_RE = re.compile(
    r"(?<![A-Za-z0-9_-])([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})"
    r"(?![A-Za-z0-9-])"
)


def _static_constructed_string(node: ast.AST) -> str | None:
    """Evaluate only closed, side-effect-free string construction shapes."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_constructed_string(node.left)
        right = _static_constructed_string(node.right)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and not node.keywords
        and len(node.args) == 1
    ):
        separator = _static_constructed_string(node.func.value)
        values = node.args[0]
        if separator is None or not isinstance(values, (ast.List, ast.Tuple)):
            return None
        parts = [_static_constructed_string(element) for element in values.elts]
        if any(part is None for part in parts):
            return None
        return separator.join(part for part in parts if part is not None)
    return None


def _keyword_literal(call: ast.Call, name: str, expected: object) -> bool:
    matches = [keyword.value for keyword in call.keywords if keyword.arg == name]
    if len(matches) != 1:
        return False
    try:
        return ast.literal_eval(matches[0]) == expected
    except (ValueError, TypeError):
        return False


def _inside_named_function(node: ast.AST, tree: ast.Module, name: str) -> bool:
    return any(
        isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
        and function.name == name
        and node in ast.walk(function)
        for function in tree.body
    )


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_attribute(node: ast.AST, owner: str, name: str) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == name and _is_name(node.value, owner)


def _pinned_request_call(call: ast.Call, *, parent: ast.AST | None) -> bool:
    if (
        not isinstance(parent, ast.Assign)
        or len(parent.targets) != 1
        or not _is_name(parent.targets[0], "body")
        or len(call.args) != 2
        or not _is_name(call.args[0], "client")
    ):
        return False
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    url = call.args[1]
    return (
        None not in keywords
        and len(keywords) == 5
        and isinstance(url, ast.Call)
        and _is_name(url.func, "_chart_url")
        and len(url.args) == 2
        and not url.keywords
        and _is_name(url.args[0], "ticker")
        and _is_name(url.args[1], "target_date")
        and _is_name(keywords.get("accept"), "_JSON_MEDIA_TYPE")
        and _is_name(keywords.get("expected_media_type"), "_JSON_MEDIA_TYPE")
        and _is_attribute(keywords.get("response_limit"), "config", "json_response_limit")
        and _is_name(keywords.get("budget"), "budget")
        and _is_name(keywords.get("config"), "config")
    )


def _yahoo_contract_offenders(path: Path, text: str) -> list[tuple[Path, int, str, str]]:
    offenders: list[tuple[Path, int, str, str]] = []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return [(path, 0, "valid Python AST", "adapter syntax is invalid")]

    assignments: dict[str, list[object]] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        if isinstance(target, ast.Name) and value is not None:
            try:
                resolved: object = ast.literal_eval(value)
            except (ValueError, TypeError):
                resolved = value
            assignments.setdefault(target.id, []).append(resolved)

    for name, expected in YAHOO_REQUIRED_ASSIGNMENTS.items():
        values = assignments.get(name, [])
        stores = sum(
            isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name
            for node in ast.walk(tree)
        )
        if len(values) != 1 or values[0] != expected or stores != 1:
            offenders.append((path, 0, name, "required fixed Yahoo assignment missing or changed"))

    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    approved_send_count = 0
    approved_build_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in YAHOO_ALLOWED_IMPORT_MODULES:
                    offenders.append(
                        (path, node.lineno, alias.name, "non-allowlisted u145 adapter import")
                    )
                if alias.name == "httpx" and alias.asname is not None:
                    offenders.append(
                        (path, node.lineno, alias.asname, "aliased httpx import forbidden")
                    )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module not in YAHOO_ALLOWED_IMPORT_MODULES
        ):
            offenders.append(
                (path, node.lineno, node.module, "non-allowlisted u145 adapter import")
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "httpx":
            offenders.append((path, node.lineno, node.module, "from-httpx import forbidden"))

        if not isinstance(node, ast.Constant):
            constructed = _static_constructed_string(node)
            if constructed is not None:
                domains = [
                    match.group(1).casefold() for match in _DOMAIN_LITERAL_RE.finditer(constructed)
                ]
                if any(domain not in YAHOO_ALLOWED_DOMAIN_LITERALS for domain in domains):
                    offenders.append(
                        (
                            path,
                            node.lineno,
                            "constructed URL/domain",
                            "non-Yahoo constructed URL/domain forbidden",
                        )
                    )

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            method = node.func.attr
            approved_send = (
                method == "send"
                and isinstance(receiver, ast.Name)
                and receiver.id == "client"
                and _inside_named_function(node, tree, "_request_bounded")
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "request"
                and len(node.keywords) == 3
                and _keyword_literal(node, "stream", True)
                and _keyword_literal(node, "auth", None)
                and _keyword_literal(node, "follow_redirects", False)
            )
            if approved_send:
                approved_send_count += 1
            approved_build = (
                method == "build_request"
                and isinstance(receiver, ast.Name)
                and receiver.id == "client"
                and _inside_named_function(node, tree, "_request_bounded")
                and len(node.args) == 2
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "GET"
                and isinstance(node.args[1], ast.Name)
                and node.args[1].id == "url"
                and {keyword.arg for keyword in node.keywords} == {"headers", "timeout"}
            )
            if approved_build:
                approved_build_count += 1
            approved_mapping_get = method == "get" and (
                (isinstance(receiver, ast.Name) and receiver.id in {"headers", "meta", "quote"})
                or _is_attribute(receiver, "response", "headers")
                or _is_attribute(receiver, "client", "event_hooks")
            )
            network_sink = method in {
                "delete",
                "get",
                "handle_async_request",
                "open_connection",
                "patch",
                "post",
                "put",
                "request",
                "send",
                "stream",
                "urlopen",
            }
            if network_sink and not approved_send and not approved_mapping_get:
                offenders.append(
                    (path, node.lineno, method, "additional network sink in u145 adapter")
                )
            if method == "build_request" and not approved_build:
                offenders.append(
                    (path, node.lineno, method, "non-pinned request builder in u145 adapter")
                )
            if method == "AsyncClient":
                offenders.append((path, node.lineno, method, "adapter-owned HTTP client forbidden"))
            if method == "Request":
                offenders.append(
                    (path, node.lineno, method, "adapter-owned HTTP request forbidden")
                )

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id
            in {
                "__import__",
                "compile",
                "eval",
                "exec",
                "getattr",
                "globals",
                "locals",
                "setattr",
                "vars",
            }
        ):
            offenders.append(
                (path, node.lineno, node.func.id, "reflective network access forbidden")
            )

        if isinstance(node, ast.Attribute) and node.attr in {"__dict__", "__getattribute__"}:
            offenders.append((path, node.lineno, node.attr, "reflective network access forbidden"))

        if isinstance(node, ast.Attribute) and node.attr in {
            "delete",
            "get",
            "handle_async_request",
            "open_connection",
            "patch",
            "post",
            "put",
            "request",
            "send",
            "stream",
            "urlopen",
        }:
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                offenders.append(
                    (
                        path,
                        node.lineno,
                        node.attr,
                        "indirect network-capable method reference forbidden",
                    )
                )

        identifier: str | None = None
        if isinstance(node, ast.Name):
            identifier = node.id
        elif isinstance(node, ast.Attribute):
            identifier = node.attr
        if identifier is not None and identifier.casefold() in YAHOO_FORBIDDEN_RUNTIME_IDENTIFIERS:
            offenders.append(
                (path, node.lineno, identifier, "runtime/fallback endpoint identifier forbidden")
            )

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for match in _DOMAIN_LITERAL_RE.finditer(node.value):
                domain = match.group(1).casefold()
                if (
                    domain not in YAHOO_ALLOWED_DOMAIN_LITERALS
                    and domain not in YAHOO_ALLOWED_NON_PROVIDER_DOTTED_LITERALS
                ):
                    offenders.append(
                        (path, node.lineno, domain, "non-Yahoo domain literal in u145 adapter")
                    )
            if node.value.startswith(("http://", "https://")):
                host = urlsplit(node.value).hostname
                if host is None or host.casefold() not in YAHOO_ALLOWED_DOMAIN_LITERALS:
                    offenders.append(
                        (path, node.lineno, node.value, "non-Yahoo URL literal in u145 adapter")
                    )
    if approved_send_count != 1:
        offenders.append(
            (path, 0, "client.send", "exactly one pinned client.send call is required")
        )
    if approved_build_count != 1:
        offenders.append(
            (path, 0, "client.build_request", "exactly one pinned request builder is required")
        )

    request_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_name(node.func, "_request_bounded")
    ]
    indirect_request_refs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == "_request_bounded"
        and not (isinstance(parents.get(node), ast.Call) and parents.get(node).func is node)
    ]
    pinned_calls = (
        len(request_calls) == 1
        and not indirect_request_refs
        and _inside_named_function(request_calls[0], tree, "_fetch_ticker_once")
        and _pinned_request_call(
            request_calls[0], parent=parents.get(parents.get(request_calls[0]))
        )
    )
    if not pinned_calls:
        offenders.append(
            (
                path,
                0,
                "_request_bounded call sites",
                "exact fixed chart request call site is required",
            )
        )
    return offenders


def find_offenders() -> list[tuple[Path, int, str, str]]:
    """Return ``(path, line_no, pattern, line_text)`` for every match.

    Returns an empty list when no source file matches.
    """
    compiled = [(re.compile(p, re.IGNORECASE), p) for p in BLOCKLIST]
    offenders: list[tuple[Path, int, str, str]] = []
    for path in sorted(SOURCES_ROOT.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for regex, pattern in compiled:
                if regex.search(line):
                    offenders.append((path, line_no, pattern, line.rstrip()))
    if not YAHOO_ADAPTER_PATH.is_file():
        offenders.append((YAHOO_ADAPTER_PATH, 0, "u145 fixed Yahoo adapter", "missing adapter"))
        return offenders

    try:
        yahoo_text = YAHOO_ADAPTER_PATH.read_text(encoding="utf-8")
    except OSError:
        offenders.append((YAHOO_ADAPTER_PATH, 0, "u145 fixed Yahoo adapter", "unreadable adapter"))
        return offenders

    offenders.extend(_yahoo_contract_offenders(YAHOO_ADAPTER_PATH, yahoo_text))
    return offenders


def main() -> int:
    offenders = find_offenders()
    if not offenders:
        return 0
    repo_root = SOURCES_ROOT.parent.parent.parent
    print("Paid-API or u145 provider-contract drift detected (NFR-002):", file=sys.stderr)
    for path, line_no, pattern, line in offenders:
        rel = path.relative_to(repo_root)
        print(f"  {rel}:{line_no}: matched {pattern!r}: {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
