"""Required Minimum Distributions (RMDs) — IRS Uniform Lifetime Table (2022+).

SECURE 2.0: RMDs begin at age 73 for those reaching 72 after 2022 (age 75 for
those born in 1960 or later). RMD = prior-year-end tax-deferred balance / divisor.
Roth IRAs have no lifetime RMD; Roth 401(k)s no longer do from 2024. Pure +
deterministic.
"""
from __future__ import annotations

from .money import D, whole

# IRS Uniform Lifetime Table divisors (post-2022). Age -> distribution period.
UNIFORM_LIFETIME = {
    73: D("26.5"), 74: D("25.5"), 75: D("24.6"), 76: D("23.7"), 77: D("22.9"),
    78: D("22.0"), 79: D("21.1"), 80: D("20.2"), 81: D("19.4"), 82: D("18.5"),
    83: D("17.7"), 84: D("16.8"), 85: D("16.0"), 86: D("15.2"), 87: D("14.4"),
    88: D("13.7"), 89: D("12.9"), 90: D("12.2"), 91: D("11.5"), 92: D("10.8"),
    93: D("10.1"), 94: D("9.5"), 95: D("8.9"), 96: D("8.4"), 97: D("7.8"),
    98: D("7.3"), 99: D("6.8"), 100: D("6.4"), 101: D("6.0"), 102: D("5.6"),
    103: D("5.2"), 104: D("4.9"), 105: D("4.6"), 106: D("4.3"), 107: D("4.1"),
    108: D("3.9"), 109: D("3.7"), 110: D("3.5"),
}


def rmd_start_age(birth_year: int | None) -> int:
    """73 normally; 75 for those born 1960 or later (SECURE 2.0)."""
    if birth_year is not None and birth_year >= 1960:
        return 75
    return 73


def rmd_amount(age: int, tax_deferred_balance, birth_year: int | None = None) -> D:
    """RMD due at a given age for a tax-deferred balance. 0 before the start age."""
    bal = D(tax_deferred_balance)
    if bal <= 0 or age < rmd_start_age(birth_year):
        return D(0)
    divisor = UNIFORM_LIFETIME.get(min(age, 110), UNIFORM_LIFETIME[110])
    return bal / divisor


def rmd_summary(age: int, tax_deferred_balance, birth_year: int | None = None) -> dict:
    amt = rmd_amount(age, tax_deferred_balance, birth_year)
    return {
        "rmd_start_age": rmd_start_age(birth_year),
        "age": age,
        "tax_deferred_balance": str(whole(tax_deferred_balance)),
        "rmd_due": str(whole(amt)),
        "rmd_active": amt > 0,
    }
