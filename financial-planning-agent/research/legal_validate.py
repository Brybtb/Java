#!/usr/bin/env python3
"""
Financial Planning Agent — Legal Validation (attorney lenses)
=============================================================
The attorney lenses of the syndicate are validated against PRIMARY LAW using the
legal MCP tools available in the Claude Code runtime, NOT a standalone HTTP call —
so this script's job is to (1) emit the precise legal questions each
jurisdiction-sensitive rule depends on, and (2) document exactly which MCP tool to
run for each. An agent then runs the tools and records the citations.

Why MCP and not a plain API call: the strongest validation for an ERISA / estate /
homestead / community-property rule is confirming the statute or case actually
says what the rule claims — which the Descrybe `verify_quote` and
`search_laws_and_rules` tools do directly against U.S. primary law.

MCP tools to use (load via ToolSearch first):
  * Descrybe Legal Engine:
      - search_laws_and_rules     -> find the controlling statute/regulation
      - search_cases_by_concept   -> issue-based case research
      - get_case_details          -> authority + treatment
      - verify_quote              -> confirm a quote/claim against primary law  (highest value)
  * Multi-jurisdictional legal-research (Legal Data Hunter):
      - search / get_document     -> cross-jurisdiction state overlays

Run `python3 legal_validate.py` to print the question pack (no network).
"""
from __future__ import annotations

import json

# Each item: the rule/overlay it backs, the legal question, and the MCP call to run.
LEGAL_QUESTIONS = [
    {
        "backs": "retirement rules / employer plan (ERISA)",
        "question": "What does ERISA require regarding employer retirement plan "
                    "matching contributions and vesting schedules?",
        "mcp_tool": "Descrybe.search_laws_and_rules",
        "verify_with": "Descrybe.verify_quote",
    },
    {
        "backs": "estate.rules — core documents & probate",
        "question": "What instruments are required for a valid will and durable "
                    "power of attorney, and how do beneficiary designations override a will?",
        "mcp_tool": "Descrybe.search_laws_and_rules",
        "verify_with": "Descrybe.verify_quote",
    },
    {
        "backs": "jurisdiction/TX & CA — homestead exemption",
        "question": "What is the homestead exemption protection in Texas vs California, "
                    "and what statute establishes it?",
        "mcp_tool": "legal-research.search",
        "verify_with": "Descrybe.search_laws_and_rules",
    },
    {
        "backs": "jurisdiction overlays — community property",
        "question": "Which states are community-property states, and how does that "
                    "affect step-up in basis at death?",
        "mcp_tool": "legal-research.search",
        "verify_with": "Descrybe.search_cases_by_concept",
    },
    {
        "backs": "tax rules — federal estate/gift exemption",
        "question": "What is the current federal estate and gift tax exemption and "
                    "annual gift exclusion under the Internal Revenue Code?",
        "mcp_tool": "Descrybe.search_laws_and_rules",
        "verify_with": "Descrybe.verify_quote",
    },
]


def main() -> None:
    print(json.dumps({"legal_question_pack": LEGAL_QUESTIONS}, indent=2))
    print(
        "\nNext: in the agent runtime, ToolSearch then run the listed MCP tools for "
        "each question; record the returned primary-law citations into "
        "../foo_agent/rules/data/citations/sources.json and each rule's "
        "`verification` block."
    )


if __name__ == "__main__":
    main()
