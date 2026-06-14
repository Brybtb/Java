"""Builds the prompt for an OPTIONAL external LLM whose only job is to render an
already-computed Result into plain English. The LLM never decides anything."""
from __future__ import annotations

import json

INSTRUCTION = (
    "You are explaining a financial plan that has ALREADY been computed by a "
    "deterministic engine. Your job is to restate it in clear, plain English for "
    "a client. Strict rules:\n"
    "  1. Do NOT add, remove, reorder, or change any recommendation.\n"
    "  2. Do NOT introduce any dollar figure, percentage, rule id, or source that "
    "is not present in the JSON below.\n"
    "  3. Do NOT give new advice or opinions; only explain what is given.\n"
    "  4. Preserve the disclosures.\n\n"
    "Plan JSON:\n"
)


def build_prompt(result: dict) -> str:
    return INSTRUCTION + json.dumps(result, indent=2, sort_keys=True, default=str)
