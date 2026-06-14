"""Tax-bucket classification (C07) — the single source of truth for which dollars
are taxable, tax-deferred, or tax-free.

Three buckets, by tax treatment:
  * taxable        — brokerage; growth carries an annual tax drag, withdrawals are
                     (mostly) return of basis + LTCG.
  * tax_deferred   — pre-tax 401(k) / traditional IRA + the employer match; grows
                     untaxed, taxed as ordinary income at withdrawal, RMD-bound.
  * tax_free       — Roth IRA / Roth 401(k) / HSA (retirement use); grows and (when
                     qualified) is withdrawn tax-free.

Both the projection and Monte Carlo consume these splits. ``accounts.py`` sums them,
so the single-bucket totals stay byte-identical to the pre-C07 engine (parity) while
the split unlocks tax-aware growth here and tax-aware decumulation in C08.
"""
from __future__ import annotations

from ..calculators.money import D

# Account key -> bucket. Matches projection.accounts.INVESTABLE (cash_emergency is
# liquidity, never invested). employer_401k is treated as pre-tax; a Roth 401(k) is
# its own key.
BUCKET_OF = {
    "employer_401k": "tax_deferred",
    "ira": "tax_deferred",
    "trad_ira": "tax_deferred",
    "roth_ira": "tax_free",
    "roth_401k": "tax_free",
    "hsa": "tax_free",
    "taxable": "taxable",
    "brokerage": "taxable",
}
BUCKETS = ("taxable", "tax_deferred", "tax_free")


def _empty() -> dict:
    return {b: D(0) for b in BUCKETS}


def bucket_balances_d(profile: dict) -> dict:
    """Current investable balances per bucket (Decimal, exact)."""
    accounts = profile.get("accounts", {}) or {}
    out = _empty()
    for key, bucket in BUCKET_OF.items():
        acct = accounts.get(key)
        if isinstance(acct, dict):
            out[bucket] += D(acct.get("balance", 0))
    return out


def bucket_contributions_d(profile: dict) -> dict:
    """Annual contributions per bucket (Decimal, exact).

    Mirrors the pre-C07 ``_annual_contribution`` arithmetic exactly, but routes each
    flow to its bucket: 401(k) deferral + captured employer match -> tax_deferred;
    Roth IRA -> tax_free; HSA -> tax_free. (No taxable-brokerage contribution input
    exists yet; that arrives with C09, so the taxable bucket's contribution is 0.)
    """
    gross = D(profile.get("income", {}).get("gross_annual", 0))
    contrib = profile.get("contributions", {}) or {}
    accts = profile.get("accounts", {}) or {}

    deferral_pct = D(contrib.get("employer_401k", {}).get("pct", 0))
    deferral = gross * deferral_pct
    match_rate = D(accts.get("employer_401k", {}).get("match_rate", 0))
    match_cap = D(accts.get("employer_401k", {}).get("match_pct_cap", 0))
    captured = deferral_pct if deferral_pct < match_cap else match_cap
    match = gross * captured * match_rate

    roth = D(contrib.get("roth_ira", {}).get("annual", 0))
    hsa = D(contrib.get("hsa", {}).get("annual", 0))

    out = _empty()
    out["tax_deferred"] = deferral + match
    out["tax_free"] = roth + hsa
    return out
