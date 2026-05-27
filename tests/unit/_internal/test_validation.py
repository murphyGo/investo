"""u85 — shared validation gating contract + registry.

Pins the 3-valued severity, the ``block`` short-circuit semantics, the
raise-through behaviour, and the dropped ``downgrade`` / ``is_blocking``
review corrections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

import pytest

from investo._internal.validation import (
    Severity,
    ValidationRegistry,
    ValidationResult,
    Validator,
)


def test_severity_is_three_valued_no_downgrade() -> None:
    """Review 2026-05-28: severity = pass/warn/block only; downgrade dropped."""
    assert set(get_args(Severity)) == {"pass", "warn", "block"}


def test_no_is_blocking_on_protocol() -> None:
    """Review 2026-05-28: the protocol exposes only ``name`` + ``validate``."""
    assert not hasattr(Validator, "is_blocking")


def test_validation_result_is_block_property() -> None:
    assert ValidationResult(severity="block").is_block is True
    assert ValidationResult(severity="warn").is_block is False
    assert ValidationResult(severity="pass").is_block is False


@dataclass(frozen=True)
class _Recording:
    """A frozen-dataclass validator — proves frozen adapters satisfy the
    protocol (the read-only ``name`` property fix)."""

    name: str
    result: ValidationResult
    log: list[str]

    def validate(self) -> ValidationResult:
        self.log.append(self.name)
        return self.result


def test_frozen_dataclass_satisfies_protocol() -> None:
    v: Validator = _Recording(name="x", result=ValidationResult(severity="pass"), log=[])
    assert isinstance(v, Validator)


def test_registry_runs_in_order_and_returns_all_on_pass() -> None:
    log: list[str] = []
    reg = ValidationRegistry(
        name="t",
        validators=(
            _Recording("a", ValidationResult(severity="pass"), log),
            _Recording("b", ValidationResult(severity="warn", message="m"), log),
            _Recording("c", ValidationResult(severity="pass"), log),
        ),
    )
    results = reg.run()
    assert log == ["a", "b", "c"]
    assert [r.severity for r in results] == ["pass", "warn", "pass"]


def test_registry_short_circuits_on_first_block() -> None:
    log: list[str] = []
    reg = ValidationRegistry(
        name="t",
        validators=(
            _Recording("a", ValidationResult(severity="pass"), log),
            _Recording("b", ValidationResult(severity="block", message="stop"), log),
            _Recording("c", ValidationResult(severity="pass"), log),
        ),
    )
    results = reg.run()
    assert log == ["a", "b"]  # c never ran
    assert results[-1].is_block
    assert results[-1].message == "stop"


def test_registry_lets_raising_adapter_propagate() -> None:
    class _Boom:
        name = "boom"

        def validate(self) -> ValidationResult:
            raise RuntimeError("boundary raise")

    reg = ValidationRegistry(name="t", validators=(_Boom(),))
    with pytest.raises(RuntimeError, match="boundary raise"):
        reg.run()
