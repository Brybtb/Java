"""Employer retirement-match capture. The single highest-ROI step in the FOO:
an uncaptured match is a guaranteed, immediate return left on the table."""
from __future__ import annotations

from .context import CalcContext
from .money import cents, D


def capture_full(ctx: CalcContext) -> dict:
    """Compute the contribution rate needed to capture the full employer match
    and the annual free-match dollars currently being forfeited."""
    gross = D(ctx.get("income.gross_annual", 0))
    cur_pct = D(ctx.get("contributions.employer_401k.pct", 0))
    cap_pct = D(ctx.get("accounts.employer_401k.match_pct_cap", 0))
    match_rate = D(ctx.get("accounts.employer_401k.match_rate", 0))

    target_pct = cap_pct
    # Match the firm pays at the *target* (full) contribution.
    full_match = gross * cap_pct * match_rate
    # Match captured at the *current* contribution (capped at the match cap).
    captured_pct = cur_pct if cur_pct < cap_pct else cap_pct
    captured_match = gross * captured_pct * match_rate
    forfeited = full_match - captured_match
    if forfeited < 0:
        forfeited = D(0)

    return {
        "current_pct": str(cur_pct),
        "target_pct": str(target_pct),
        "match_rate": str(match_rate),
        "full_match_annual": str(cents(full_match)),
        "forfeited_match_annual": str(cents(forfeited)),
        "additional_contribution_annual": str(cents(gross * (target_pct - captured_pct))),
    }
