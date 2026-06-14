"""Tax-aware decumulation projection (C08) — the bucket-aware drawdown C07 left blended.

Starting from the per-bucket balances at retirement (C07), this runs a deterministic
year-by-year retirement drawdown that:
  * honors Required Minimum Distributions (RMDs) from the tax-deferred bucket at the
    statutory age (reuses calculators.rmd),
  * sources the remaining spending need in tax-efficient order — taxable, then
    tax-deferred, then Roth (reuses projection.withdrawal.DEFAULT_ORDER),
  * fills low-bracket years implicitly (drawing ordinary income through the brackets),
  * computes each year's ORDINARY tax (progressive brackets) + LTCG tax exactly, and
  * reports lifetime tax paid and after-tax terminal wealth.

Goal (owner's inversion framing): keep more, grow longer, least tax drag.

Modeling choices (deterministic, documented — flagged for CMA/tax verification before
client use):
  * Social Security: up to 85% of the benefit is treated as ordinary taxable income
    (the statutory maximum inclusion; real taxation is provisional-income based).
  * Taxable-bucket withdrawals realize gains on a fixed fraction (``GAIN_FRACTION``)
    taxed at ``LTCG_RATE``; Roth withdrawals are tax-free; tax-deferred (incl. RMD)
    is ordinary income.
  * Voluntary withdrawals are sized with a single-pass marginal gross-up (no iterative
    solver); the tax REPORTED each year is computed exactly on realized income, so
    net spendable can differ from the target by the marginal-vs-effective gap.
"""
from __future__ import annotations

from ..calculators.money import D, whole
from ..calculators.rmd import rmd_amount, rmd_start_age
from .withdrawal import DEFAULT_ORDER

# Documented placeholders (verify against CMA / tax authority before client use).
LTCG_RATE = D("0.15")        # long-term capital-gains rate on realized taxable gains
GAIN_FRACTION = D("0.5")     # share of a taxable withdrawal assumed to be gain
SS_TAXABLE_FRACTION = D("0.85")  # statutory max share of Social Security that is taxable


def _ordered(brackets):
    def key(b):
        up = b.get("up_to")
        return D("Infinity") if up is None else D(up)
    return sorted(brackets, key=key)


def ordinary_tax(taxable, brackets) -> D:
    """Progressive federal tax on a taxable amount. Pure, exact, hand-verifiable."""
    taxable = D(taxable)
    if taxable <= 0:
        return D(0)
    owed, lower = D(0), D(0)
    for b in _ordered(brackets):
        up = b.get("up_to")
        top = D("Infinity") if up is None else D(up)
        rate = D(b.get("rate", 0))
        if taxable > lower:
            owed += (min(taxable, top) - lower) * rate
        lower = top
        if top == D("Infinity") or taxable <= top:
            break
    return owed


def marginal_rate(taxable, brackets) -> D:
    taxable = D(taxable)
    rate = D(0)
    lower = D(0)
    for b in _ordered(brackets):
        up = b.get("up_to")
        top = D("Infinity") if up is None else D(up)
        if taxable > lower:
            rate = D(b.get("rate", 0))
        lower = top
        if top == D("Infinity") or taxable <= top:
            break
    return rate


def decumulate(*, buckets: dict, retire_age: int, end_age: int, annual_spend_retire,
               inflation, mean_return, taxable_drag, ss_annual, ss_claim_age,
               birth_year, brackets, std_deduction,
               ltcg_rate=LTCG_RATE, gain_fraction=GAIN_FRACTION,
               terminal_ordinary_rate=D("0.15")) -> dict:
    """Run the year-by-year tax-aware drawdown from the per-bucket retirement balances.

    ``buckets`` = {"taxable", "tax_deferred", "tax_free"} dollar balances at retirement.
    Returns a per-year schedule + lifetime_tax_paid + after_tax_terminal_wealth."""
    r = D(str(mean_return))
    drag = D(str(taxable_drag))
    infl = D(str(inflation))
    std = D(std_deduction)
    spend0 = D(str(annual_spend_retire))
    ss0 = D(str(ss_annual))

    tb = D(buckets.get("taxable", 0))
    td = D(buckets.get("tax_deferred", 0))
    tf = D(buckets.get("tax_free", 0))

    schedule = []
    lifetime_tax = D(0)
    depleted_age = None

    for age in range(retire_age, end_age):
        # grow each bucket (taxable net of drag); income/spend inflate from retirement
        tb *= (D(1) + r - drag)
        td *= (D(1) + r)
        tf *= (D(1) + r)
        yrs = age - retire_age
        spend = spend0 * (D(1) + infl) ** yrs
        ss = (ss0 * (D(1) + infl) ** yrs) if (ss_claim_age and age >= ss_claim_age) else D(0)
        ss_taxable = SS_TAXABLE_FRACTION * ss

        # forced RMD from the tax-deferred bucket
        rmd = rmd_amount(age, td, birth_year)
        if rmd > td:
            rmd = td
        td -= rmd

        # net cash from SS + RMD after the ordinary tax they alone create
        ord_pre = rmd + ss_taxable
        tax_pre = ordinary_tax(ord_pre - std, brackets)
        net_so_far = ss + rmd - tax_pre
        remaining = spend - net_so_far

        draw = {"taxable": D(0), "tax_deferred": D(0), "roth": D(0)}
        if remaining > 0:
            for name in DEFAULT_ORDER:
                if remaining <= 0:
                    break
                if name == "taxable":
                    eff = ltcg_rate * gain_fraction          # tax per $ withdrawn
                    cap_net = tb * (D(1) - eff)
                    take_net = remaining if remaining < cap_net else cap_net
                    gross = take_net / (D(1) - eff) if eff < 1 else take_net
                    tb -= gross
                    draw["taxable"] = gross
                    remaining -= take_net
                elif name == "tax_deferred":
                    mrate = marginal_rate(ord_pre - std + D(1), brackets)
                    cap_net = td * (D(1) - mrate)
                    take_net = remaining if remaining < cap_net else cap_net
                    gross = take_net / (D(1) - mrate) if mrate < 1 else take_net
                    td -= gross
                    draw["tax_deferred"] = gross
                    remaining -= take_net
                else:  # roth, tax-free
                    take = remaining if remaining < tf else tf
                    tf -= take
                    draw["roth"] = take
                    remaining -= take

        # exact taxes on realized income this year
        ordinary_income = rmd + draw["tax_deferred"] + ss_taxable
        ord_tax = ordinary_tax(ordinary_income - std, brackets)
        ltcg_tax = draw["taxable"] * gain_fraction * ltcg_rate
        year_tax = ord_tax + ltcg_tax
        lifetime_tax += year_tax

        gross_income = ss + rmd + draw["taxable"] + draw["tax_deferred"] + draw["roth"]
        net_spendable = gross_income - year_tax
        # RMD (or draws) that over-cover the need: reinvest the surplus into taxable
        surplus = net_spendable - spend
        if surplus > 0:
            tb += surplus
        if remaining > 0 and depleted_age is None:
            depleted_age = age

        schedule.append({
            "age": age,
            "spend_target": str(whole(spend)),
            "social_security": str(whole(ss)),
            "rmd": str(whole(rmd)),
            "draw_taxable": str(whole(draw["taxable"])),
            "draw_tax_deferred": str(whole(draw["tax_deferred"])),
            "draw_roth": str(whole(draw["roth"])),
            "ordinary_tax": str(whole(ord_tax)),
            "ltcg_tax": str(whole(ltcg_tax)),
            "net_spendable": str(whole(net_spendable)),
            "end_taxable": str(whole(tb)),
            "end_tax_deferred": str(whole(td)),
            "end_tax_free": str(whole(tf)),
        })

    after_tax_terminal = tb + tf + td * (D(1) - D(str(terminal_ordinary_rate)))
    return {
        "rmd_start_age": rmd_start_age(birth_year),
        "drawdown_order": list(DEFAULT_ORDER),
        "lifetime_tax_paid": str(whole(lifetime_tax)),
        "after_tax_terminal_wealth": str(whole(after_tax_terminal)),
        "terminal_ordinary_rate": str(D(str(terminal_ordinary_rate))),
        "depleted_age": depleted_age,
        "schedule": schedule,
        "assumptions": {
            "ltcg_rate": str(ltcg_rate),
            "gain_fraction": str(gain_fraction),
            "ss_taxable_fraction": str(SS_TAXABLE_FRACTION),
            "note": "PLACEHOLDER tax assumptions; verify vs CMA / IRS before client use.",
        },
    }
