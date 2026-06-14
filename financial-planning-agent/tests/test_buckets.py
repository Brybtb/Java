"""C07: multi-bucket accumulation (taxable / tax-deferred / tax-free).

The projection now tracks three tax buckets that grow independently — taxable net
of a tax drag, the others untaxed — and sum to the single-pot total, so a drag of 0
reproduces the pre-C07 path exactly (parity)."""
import json
import os

from foo_agent.projection import project
from foo_agent.projection.accounts import PlanInputs, _annual_contribution, _investable_total
from foo_agent.projection.buckets import bucket_balances_d, bucket_contributions_d
from foo_agent.projection.cashflow import project_deterministic

HERE = os.path.dirname(__file__)
AS_OF = "2026-06-14"


def _load(name):
    with open(os.path.join(HERE, "golden", "profiles", name), "r", encoding="utf-8") as f:
        return json.load(f)


# --- classification: coexisting Roth IRA + pre-tax 401k route correctly --------
def _mixed_profile():
    return {
        "schema_version": "1.0.0", "as_of": AS_OF,
        "household": {"filing_status": "single", "state": "TX", "primary_age": 40},
        "income": {"gross_annual": 180000}, "expenses": {"monthly_essential": 5000},
        "accounts": {
            "cash_emergency": {"balance": 30000},                 # NOT investable
            "employer_401k": {"balance": 40000, "match_offered": True,
                              "match_rate": 0.5, "match_pct_cap": 0.06},  # pre-tax
            "roth_ira": {"balance": 12000},                       # tax-free
            "hsa": {"eligible": True, "balance": 1500},           # tax-free
            "taxable": {"balance": 30000},                        # taxable
        },
        "contributions": {
            "employer_401k": {"pct": 0.06},                       # 10800 deferral + 5400 match
            "roth_ira": {"annual": 7000},                         # tax-free
            "hsa": {"annual": 4000},                              # tax-free
        },
    }


def test_balances_route_to_the_right_buckets():
    b = {k: float(v) for k, v in bucket_balances_d(_mixed_profile()).items()}
    assert b == {"taxable": 30000.0, "tax_deferred": 40000.0, "tax_free": 13500.0}
    # cash_emergency (30000) is excluded entirely
    assert _investable_total(_mixed_profile()) == 83500.0


def test_contributions_route_pretax_401k_and_match_vs_roth_and_hsa():
    c = {k: float(v) for k, v in bucket_contributions_d(_mixed_profile()).items()}
    # 401k deferral 0.06*180000=10800 + match 0.06*180000*0.5=5400 = 16200 -> tax_deferred
    assert c["tax_deferred"] == 16200.0
    # Roth IRA 7000 + HSA 4000 = 11000 -> tax_free  (coexisting with the pre-tax 401k)
    assert c["tax_free"] == 11000.0
    assert c["taxable"] == 0.0
    assert _annual_contribution(_mixed_profile()) == 27200.0


# --- parity + drag at the projection level ------------------------------------
def _pi(**over):
    base = dict(start_age=40, retire_age=65, end_age=90,
                initial_balance=0.0, annual_contribution=0.0,
                annual_spend_retire=40000.0, inflation=0.025, mean_return=0.06, stdev=0.11)
    base.update(over)
    base["initial_balance"] = base["taxable_balance"] + base["deferred_balance"] + base["free_balance"]
    base["annual_contribution"] = base["taxable_contrib"] + base["deferred_contrib"] + base["free_contrib"]
    return PlanInputs(**base)


def test_drag_zero_makes_bucket_placement_irrelevant_parity():
    # With no tax drag, $100k in taxable must grow identically to $100k tax-deferred.
    in_taxable = _pi(taxable_balance=100000.0, deferred_balance=0.0, free_balance=0.0,
                     taxable_contrib=0.0, deferred_contrib=0.0, free_contrib=0.0, taxable_drag=0.0)
    in_deferred = _pi(taxable_balance=0.0, deferred_balance=100000.0, free_balance=0.0,
                      taxable_contrib=0.0, deferred_contrib=0.0, free_contrib=0.0, taxable_drag=0.0)
    a = project_deterministic(in_taxable)
    b = project_deterministic(in_deferred)
    assert a["balance_at_retirement"] == b["balance_at_retirement"]
    assert a["funded_ratio"] == b["funded_ratio"]


def test_taxable_drag_lowers_taxable_bucket_growth():
    no_drag = _pi(taxable_balance=100000.0, deferred_balance=0.0, free_balance=0.0,
                  taxable_contrib=0.0, deferred_contrib=0.0, free_contrib=0.0, taxable_drag=0.0)
    with_drag = _pi(taxable_balance=100000.0, deferred_balance=0.0, free_balance=0.0,
                    taxable_contrib=0.0, deferred_contrib=0.0, free_contrib=0.0, taxable_drag=0.01)
    a = float(project_deterministic(no_drag)["balance_at_retirement"])
    b = float(project_deterministic(with_drag)["balance_at_retirement"])
    assert b < a                                  # drag eats taxable growth
    # the same drag on a tax-DEFERRED dollar must NOT bite (untaxed bucket)
    deferred_drag = _pi(taxable_balance=0.0, deferred_balance=100000.0, free_balance=0.0,
                        taxable_contrib=0.0, deferred_contrib=0.0, free_contrib=0.0, taxable_drag=0.01)
    assert float(project_deterministic(deferred_drag)["balance_at_retirement"]) == a


# --- projection output exposes the per-bucket breakdown -----------------------
def test_projection_reports_buckets_that_sum_to_balance_at_retirement():
    p = project(_mixed_profile(), AS_OF)
    bk = p["buckets"]
    s = sum(float(bk[k]) for k in ("taxable", "tax_deferred", "tax_free"))
    # whole-dollar rounding per bucket -> allow a couple dollars of rounding slack
    assert abs(s - float(p["balance_at_retirement"])) <= 2
    assert float(bk["taxable_drag"]) == 0.005      # from the CMA


def test_young_saver_has_no_taxable_bucket():
    # parity sentinel: the golden profile has no taxable money, so the drag is inert.
    p = project(_load("young_saver_TX.json"), AS_OF)
    assert float(p["buckets"]["taxable"]) == 0.0


def test_projection_is_deterministic():
    a = project(_mixed_profile(), AS_OF)
    b = project(_mixed_profile(), AS_OF)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
