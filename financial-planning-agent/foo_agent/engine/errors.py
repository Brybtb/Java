"""Typed exceptions for the engine. Distinct types let callers (and tests)
distinguish authoring errors (bad ruleset) from input errors (bad profile)
from invariant violations (a determinism guarantee was broken)."""
from __future__ import annotations


class FooError(Exception):
    """Base class for all engine errors."""


class RuleError(FooError):
    """A rule or ruleset is malformed, mis-versioned, or self-inconsistent."""


class ProfileError(FooError):
    """The client profile is missing required data or fails schema validation."""


class ConditionError(FooError):
    """A rule/insight condition string could not be parsed or evaluated."""


class DeterminismError(FooError):
    """An invariant that guarantees deterministic output was violated."""


class AssumptionError(FooError):
    """A required, date-bracketed parameter set or CMA could not be resolved."""
