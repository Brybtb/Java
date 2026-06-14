"""The safe condition DSL: correctness, fail-closed semantics, and that it
cannot execute arbitrary code."""
import pytest

from foo_agent.engine.condition import compile_condition
from foo_agent.engine.errors import ConditionError

FACTS = {
    "age": 34,
    "household": {"filing_status": "single", "state": "TX"},
    "accounts": {"hsa": {"eligible": True}},
    "params": {"limit": 7500},
}


@pytest.mark.parametrize("expr,expected", [
    ("age < 50", True),
    ("age >= 50", False),
    ("age == 34", True),
    ("accounts.hsa.eligible == true", True),
    ("household.filing_status in ['single','head_of_household']", True),
    ("household.filing_status in ['married_filing_jointly']", False),
    ("age < 50 and accounts.hsa.eligible == true", True),
    ("age > 50 or accounts.hsa.eligible == true", True),
    ("not (age > 50)", True),
    ("age < params.limit", True),
    ("exists(accounts.hsa.eligible)", True),
    ("exists(accounts.nonexistent)", False),
])
def test_eval(expr, expected):
    assert compile_condition(expr).evaluate(FACTS) is expected


def test_missing_field_fails_closed():
    # A comparison on a missing field is False, never an error.
    assert compile_condition("accounts.missing.x > 5").evaluate(FACTS) is False
    assert compile_condition("accounts.missing.x == 5").evaluate(FACTS) is False


def test_no_code_execution():
    # These must parse-fail or evaluate harmlessly, never execute Python.
    for bad in ["__import__('os').system('echo hi')", "1; import os", "x = 5"]:
        with pytest.raises(ConditionError):
            compile_condition(bad).evaluate(FACTS)


def test_empty_condition_rejected():
    with pytest.raises(ConditionError):
        compile_condition("   ")


def test_numeric_equality_is_type_tolerant():
    # 0.06 as float vs Decimal-from-string compare equal.
    facts = {"a": 0.06, "params": {"cap": 0.06}}
    assert compile_condition("a == params.cap").evaluate(facts) is True
    assert compile_condition("a < params.cap").evaluate(facts) is False
