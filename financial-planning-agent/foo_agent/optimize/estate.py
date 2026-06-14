"""Deterministic estate-tax projection + wealth-transfer strategy modeling
(Vanilla / Luminary / Wealth.com style).

Computes the gross and taxable estate, the projected federal estate tax (and a
state-estate-tax flag), and models how much each transfer strategy removes from
the taxable estate and the federal tax it saves at the top rate.

All figures are TY2026, verified: $15,000,000 exemption per individual, 40% top
rate, $19,000 annual gift exclusion (OBBBA / IRS).
"""
from __future__ import annotations

from ..calculators.context import CalcContext
from ..calculators.money import D, whole

# Estate components pulled from the profile (besides accounts/debts).
_ESTATE_ASSET_KEYS = ("real_estate", "business", "other_assets")


def _gross_estate(profile: dict) -> dict:
    accts = profile.get("accounts", {}) or {}
    investable = D(0)
    for name, a in accts.items():
        if isinstance(a, dict) and "balance" in a:
            investable += D(a["balance"])
    estate = profile.get("estate", {}) or {}
    other = D(0)
    for k in _ESTATE_ASSET_KEYS:
        other += D(estate.get(k, 0))
    # Life insurance is in the taxable estate unless owned by an ILIT.
    life_face = D(estate.get("life_insurance_face", 0))
    life_in_ilit = bool(estate.get("life_insurance_in_ilit", False))
    life_in_estate = D(0) if life_in_ilit else life_face

    debts = D(0)
    for dbt in profile.get("debts", []) or []:
        debts += D(dbt.get("balance", 0))

    gross = investable + other + life_in_estate
    return {
        "investable": investable, "other_assets": other,
        "life_insurance_in_estate": life_in_estate, "life_insurance_face": life_face,
        "life_in_ilit": life_in_ilit, "debts": debts, "gross": gross,
        "net": gross - debts,
    }


def analyze(profile: dict, params: dict, as_of) -> dict:
    ctx = CalcContext(profile=profile, params=params, as_of=as_of)
    exemption_ind = D(ctx.param("estate.exemption_per_individual", 15000000))
    top_rate = D(ctx.param("estate.top_rate", "0.40"))
    annual_excl = D(ctx.param("estate.gift_annual_exclusion", 19000))

    g = _gross_estate(profile)
    taxable_estate = g["net"]
    if taxable_estate < 0:
        taxable_estate = D(0)

    filing = ctx.get("household.filing_status", "single")
    married = filing in ("married_filing_jointly", "qualifying_widow")
    # C4: prior taxable gifts use up lifetime exemption (unified credit).
    prior_gifts = D((profile.get("estate", {}) or {}).get("prior_taxable_gifts", 0))
    gross_exemption = exemption_ind * (2 if married else 1)  # portability for couples
    exemption = gross_exemption - prior_gifts
    if exemption < 0:
        exemption = D(0)

    over_exemption = taxable_estate - exemption
    if over_exemption < 0:
        over_exemption = D(0)
    federal_tax = over_exemption * top_rate

    # State estate / inheritance tax flags from the verified state lists.
    state = ctx.get("household.state", "")
    estate_states = set(ctx.param("estate.estate_tax_states", []) or [])
    inh_states = set(ctx.param("estate.inheritance_tax_states", []) or [])
    state_estate_tax = state in estate_states
    state_inheritance_tax = state in inh_states

    # C4: simplified state estate-tax dollar model where the state overlay provides
    # an exemption + top rate. Handles the NY "cliff" (no exemption if the estate
    # exceeds 105% of the threshold). Marked approximate.
    state_estate_block = ctx.param("state.estate_tax") or {}
    state_estate_tax_amount = D(0)
    if state_estate_tax and state_estate_block:
        s_exempt = D(state_estate_block.get("exemption", 0))
        s_rate = D(state_estate_block.get("top_rate", "0.16"))
        cliff = bool(state_estate_block.get("cliff", False))
        if cliff and taxable_estate > s_exempt * D("1.05"):
            state_taxable = taxable_estate                # cliff: whole estate taxed
        else:
            state_taxable = taxable_estate - s_exempt
        if state_taxable < 0:
            state_taxable = D(0)
        state_estate_tax_amount = state_taxable * s_rate

    # Strategy modeling — only meaningful when there's a taxable overage.
    donees = int((profile.get("estate", {}) or {}).get("donees", 0) or 0)
    horizon = int((profile.get("estate", {}) or {}).get("planning_years", 10) or 10)
    strategies = []
    if over_exemption > 0:
        # Annual exclusion gifting.
        if donees > 0:
            removed = annual_excl * donees * horizon
            removed = min(removed, over_exemption)
            strategies.append(_strategy(
                "annual_gifting", "Annual-exclusion gifting",
                f"${annual_excl}/donee x {donees} donees x {horizon} yrs",
                removed, top_rate))
        # ILIT — remove life insurance face from the estate.
        if g["life_insurance_in_estate"] > 0:
            removed = min(g["life_insurance_in_estate"], over_exemption)
            strategies.append(_strategy(
                "ilit", "Irrevocable Life Insurance Trust (ILIT)",
                "Move life-insurance death benefit out of the taxable estate",
                removed, top_rate))
        # SLAT / GRAT — move appreciating assets (+ growth) out of the estate.
        slat_amount = D((profile.get("estate", {}) or {}).get("slat_funding", 0))
        if slat_amount > 0:
            growth = D((profile.get("estate", {}) or {}).get("slat_growth_multiple", "1.5"))
            removed = min(slat_amount * growth, over_exemption)
            strategies.append(_strategy(
                "slat_grat", "SLAT / GRAT (freeze + transfer appreciation)",
                f"Fund ${whole(slat_amount)}, model {growth}x growth removed from estate",
                removed, top_rate))

    return {
        "as_of": str(as_of),
        "filing_status": filing,
        "gross_estate": str(whole(g["gross"])),
        "debts": str(whole(g["debts"])),
        "taxable_estate": str(whole(taxable_estate)),
        "prior_taxable_gifts": str(whole(prior_gifts)),
        "applicable_exemption": str(whole(exemption)),
        "amount_over_exemption": str(whole(over_exemption)),
        "projected_federal_estate_tax": str(whole(federal_tax)),
        "has_federal_estate_tax_exposure": over_exemption > 0,
        "state_estate_tax_applies": state_estate_tax,
        "projected_state_estate_tax": str(whole(state_estate_tax_amount)),
        "state_inheritance_tax_applies": state_inheritance_tax,
        "total_projected_estate_tax": str(whole(federal_tax + state_estate_tax_amount)),
        "annual_gift_exclusion": str(whole(annual_excl)),
        "strategies": strategies,
        "citation": "OBBBA 2025 / IRS estate & gift tax (2026)",
        "note": "Federal estate tax at the 40% top rate above the applicable exemption "
                "(reduced by prior taxable gifts). Couples assume full portability, which "
                "REQUIRES a timely Form 706 DSUE election at the first death. State estate "
                "tax is dollar-modeled only where the state overlay provides an exemption "
                "+ rate (approximate; the NY cliff is simplified). Confirm with an estate attorney.",
    }


def _strategy(sid, name, mechanism, removed, top_rate) -> dict:
    removed = whole(removed)
    return {
        "id": sid, "name": name, "mechanism": mechanism,
        "amount_removed_from_estate": str(removed),
        "federal_tax_saved": str(whole(D(removed) * top_rate)),
    }
