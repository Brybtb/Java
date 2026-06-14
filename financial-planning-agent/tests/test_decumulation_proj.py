"""C08: tax-aware decumulation projection — drawdown order, RMDs, exact yearly tax,
lifetime tax, after-tax terminal wealth. Deterministic."""
import json
import os

from foo_agent.calculators.money import D
from foo_agent.projection import decumulation_projection
from foo_agent.projection.decumulation import decumulate, marginal_rate, ordinary_tax

HERE = os.path.dirname(__file__)
AS_OF = "2026-06-14"

# A simple two-bracket schedule for hand-checked tax math.
_BR = [{"up_to": 12400, "rate": 0.10}, {"up_to": 50400, "rate": 0.12}, {"up_to": None, "rate": 0.22}]


# --- pure tax math, hand-verifiable -------------------------------------------
def test_ordinary_tax_progressive_hand_calc():
    # 20000 taxable: 12400@10% (1240) + 7600@12% (912) = 2152
    assert ordinary_tax(20000, _BR) == D("2152.0")
    assert ordinary_tax(0, _BR) == D(0)
    assert ordinary_tax(-500, _BR) == D(0)
    # 60000: 1240 + (50400-12400)*.12 (4560) + (60000-50400)*.22 (2112) = 7912
    assert ordinary_tax(60000, _BR) == D("7912.0")


def test_marginal_rate_picks_the_right_bracket():
    assert marginal_rate(5000, _BR) == D("0.10")
    assert marginal_rate(20000, _BR) == D("0.12")
    assert marginal_rate(60000, _BR) == D("0.22")


# --- decumulate() invariants --------------------------------------------------
def _run(**over):
    base = dict(
        buckets={"taxable": 100000, "tax_deferred": 800000, "tax_free": 50000},
        retire_age=65, end_age=95, annual_spend_retire=60000, inflation=0.025,
        mean_return=0.05, taxable_drag=0.005, ss_annual=24000, ss_claim_age=67,
        birth_year=1961, brackets=_BR, std_deduction=15000,
    )
    base.update(over)
    return decumulate(**base)


def test_schedule_spans_retirement_and_is_deterministic():
    a = _run()
    b = _run()
    assert len(a["schedule"]) == 95 - 65
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_taxable_drains_before_roth_is_touched():
    # Roth is last: in the first year, with taxable + tax-deferred available, roth=0.
    yr0 = _run()["schedule"][0]
    assert D(yr0["draw_roth"]) == 0
    # something was drawn or covered by SS — net spendable should be > 0
    assert D(yr0["net_spendable"]) > 0


def test_rmd_is_forced_at_statutory_age():
    out = _run(birth_year=1961)               # born >=1960 -> RMD start age 75
    assert out["rmd_start_age"] == 75
    rmd_years = [r for r in out["schedule"] if D(r["rmd"]) > 0]
    assert rmd_years and all(r["age"] >= 75 for r in rmd_years)
    # before the start age, no RMD
    assert all(D(r["rmd"]) == 0 for r in out["schedule"] if r["age"] < 75)


def test_rmd_start_age_73_for_pre_1960():
    assert _run(birth_year=1955)["rmd_start_age"] == 73


def test_lifetime_tax_is_nonneg_and_after_tax_terminal_discounts_tax_deferred():
    out = _run()
    assert D(out["lifetime_tax_paid"]) >= 0
    # after-tax terminal wealth discounts the tax-deferred bucket by the terminal rate,
    # so it is <= the raw sum of ending balances.
    last = out["schedule"][-1]
    raw = D(last["end_taxable"]) + D(last["end_tax_deferred"]) + D(last["end_tax_free"])
    assert D(out["after_tax_terminal_wealth"]) <= raw


def test_lifetime_tax_equals_sum_of_yearly_taxes():
    out = _run()
    summed = sum(D(r["ordinary_tax"]) + D(r["ltcg_tax"]) for r in out["schedule"])
    # per-year values are whole-dollar rounded; allow a few dollars of rounding slack
    assert abs(summed - D(out["lifetime_tax_paid"])) <= len(out["schedule"])


def test_no_taxable_bucket_means_no_ltcg_tax():
    out = _run(buckets={"taxable": 0, "tax_deferred": 800000, "tax_free": 50000})
    assert all(D(r["ltcg_tax"]) == 0 for r in out["schedule"])


# --- profile wrapper ----------------------------------------------------------
def test_decumulation_projection_from_profile():
    with open(os.path.join(HERE, "golden", "profiles", "near_retiree_TX.json")) as f:
        prof = json.load(f)
    out = decumulation_projection(prof, AS_OF)
    assert out["drawdown_order"] == ["taxable", "tax_deferred", "roth"]
    assert int(out["rmd_start_age"]) in (73, 75)
    assert out["schedule"] and "net_spendable" in out["schedule"][0]
    assert D(out["lifetime_tax_paid"]) >= 0
