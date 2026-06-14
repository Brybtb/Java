"""Calculator unit + property tests. Money math must be exact and invariant
under input reordering."""
from datetime import date
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from foo_agent.calculators import CalcContext
from foo_agent.calculators import debt, employer_match
from foo_agent.calculators.money import D, cents, total


def _ctx(profile, params=None):
    return CalcContext(profile=profile, params=params or {}, as_of=date(2026, 6, 14))


def test_employer_match_forfeited():
    prof = {
        "income": {"gross_annual": 100000},
        "contributions": {"employer_401k": {"pct": 0.03}},
        "accounts": {"employer_401k": {"match_pct_cap": 0.06, "match_rate": 0.5}},
    }
    out = employer_match.capture_full(_ctx(prof))
    # full match = 100000 * 0.06 * 0.5 = 3000; captured = 100000*0.03*0.5 = 1500
    assert out["full_match_annual"] == "3000.00"
    assert out["forfeited_match_annual"] == "1500.00"


def test_debt_avalanche_order_is_deterministic():
    prof = {"debts": [
        {"id": "b", "type": "x", "balance": 1000, "apr": 0.10},
        {"id": "a", "type": "x", "balance": 1000, "apr": 0.20},
        {"id": "c", "type": "x", "balance": 1000, "apr": 0.05},
    ]}
    params = {"debt": {"high_interest_apr_threshold": "0.08"}}
    out = debt.high_interest(_ctx(prof, params))
    # Only the two above 8%, highest APR first.
    assert [d["id"] for d in out["payoff_order"]] == ["a", "b"]
    assert out["count"] == 2


def test_total_is_order_stable():
    vals = [D("0.1"), D("0.2"), D("0.3")]
    assert total(vals) == total(list(reversed(vals)))
    assert total([D("0.1"), D("0.2")]) == D("0.3")


@given(st.lists(st.integers(min_value=0, max_value=10_000_000), min_size=1, max_size=20))
@settings(max_examples=50)
def test_sum_permutation_invariant(xs):
    a = total([D(x) for x in xs])
    b = total([D(x) for x in reversed(xs)])
    assert a == b


@given(st.decimals(min_value=0, max_value=10_000, allow_nan=False, allow_infinity=False, places=4))
@settings(max_examples=50)
def test_cents_idempotent(x):
    once = cents(x)
    assert cents(once) == once
    assert once.as_tuple().exponent == -2
