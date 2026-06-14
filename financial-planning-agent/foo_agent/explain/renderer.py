"""Explanation rendering. The default renderer is deterministic and uses NO LLM —
it simply narrates the Result. An external LLM may optionally be supplied; its
output is passed through the guard before being returned, so the decision can
never be altered."""
from __future__ import annotations

from typing import Callable

from .guard import validate
from .prompt import build_prompt


def render_plain(result: dict) -> str:
    """Deterministic plain-English narration — no network, no LLM."""
    lines = [f"Here is your plan as of {result['as_of']}.", ""]
    proj = result.get("projection")
    if proj:
        g = proj["goal"]
        lines.append(
            f"Your retirement goal is currently '{g['status']}', with a funded "
            f"ratio of {g['funded_ratio']} and a projected balance of "
            f"${proj['balance_at_retirement']} at age {proj['retire_age']}."
        )
        mc = result.get("monte_carlo")
        if mc:
            lines.append(
                f"Across {mc['trials']} modeled scenarios, the probability of "
                f"success is {mc['probability_of_success']:.0%}."
            )
        lines.append("")
    lines.append("Recommended next actions, in order:")
    for r in result["recommendations"]:
        lines.append(f"  {r['step']}. {r['headline']}")
    if result.get("insights"):
        lines += ["", "Things to note:"]
        for i in result["insights"]:
            lines.append(f"  - ({i['severity']}) {i['message']}")
    lines += ["", "— " + result["disclosures"][0]]
    return "\n".join(lines)


def render_with_llm(result: dict, llm: Callable[[str], str], *, strict: bool = True) -> str:
    """Render via an external LLM callable, then guard the output. ``llm`` takes a
    prompt string and returns text. Any introduced id/figure is rejected."""
    text = llm(build_prompt(result))
    return validate(text, result, strict=strict)
