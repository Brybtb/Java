"""Attaches the compliance envelope to a Result. The report/PDF layer asserts
these fields are present before rendering, so output can never escape without its
disclosures and human-in-the-loop gate."""
from __future__ import annotations

from .disclaimers import disclosures, requires_advisor_review


def stamp(result: dict) -> dict:
    """Mutate-and-return: add disclosures + advisor-review flag if absent."""
    result.setdefault("disclosures", disclosures())
    result["requires_advisor_review"] = requires_advisor_review()
    return result


def assert_compliant(result: dict) -> None:
    if not result.get("disclosures"):
        raise ValueError("Result has no disclosures; refusing to render.")
    if "requires_advisor_review" not in result:
        raise ValueError("Result missing requires_advisor_review flag.")
