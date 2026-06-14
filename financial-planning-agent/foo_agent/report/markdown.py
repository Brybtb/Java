"""Obsidian-style markdown report with disclosure callouts — matching the
sibling research subprojects' vault-ready style."""
from __future__ import annotations

from ..compliance.wrapper import assert_compliant
from .pdf import _detail


def render_markdown(result: dict) -> str:
    assert_compliant(result)
    L: list[str] = []
    L += [
        "---",
        'title: "Financial Plan"',
        "type: FinancialPlan",
        f"as_of: {result['as_of']}",
        f"engine: foo-agent {result['engine_version']}",
        f"ruleset: {result['ruleset_version']}",
        "tags: [financial-plan, foo-agent, decision-support]",
        "---",
        "",
        "# Financial Plan",
        "",
        "> [!warning] Decision-support draft",
        "> Requires review and approval by a qualified fiduciary adviser before use.",
        "",
    ]

    proj = result.get("projection")
    if proj:
        g = proj["goal"]
        L += [
            "## Retirement outlook",
            "",
            f"- **Goal status:** {g['status']}",
            f"- **Funded ratio:** {g['funded_ratio']}",
            f"- **Balance at age {proj['retire_age']}:** ${proj['balance_at_retirement']}",
        ]
        mc = result.get("monte_carlo")
        if mc:
            L.append(
                f"- **Monte Carlo P(success):** {mc['probability_of_success']:.0%} "
                f"({mc['trials']} trials, seed {mc['seed']}, CMA {result.get('cma_version')})"
            )
        L.append("")

    L += ["## Recommended next actions", "", "| # | Action | Detail | Sources |", "|---|---|---|---|"]
    for r in result["recommendations"]:
        L.append(f"| {r['step']} | {r['headline']} | {_detail(r)} | {', '.join(map(str, r['citations']))} |")
    L.append("")

    if result.get("insights"):
        L += ["## Insights", ""]
        for i in result["insights"]:
            L.append(f"- **[{i['severity']}]** {i['message']} _(sources: {', '.join(map(str, i['citations']))})_")
        L.append("")

    opt = result.get("optimizers") or {}
    if opt:
        L += ["## Planning modules", ""]
        rc = opt.get("roth_conversion")
        if rc and rc.get("fill_targets"):
            L.append(f"- **Roth conversion** (taxable ${rc['taxable_income']}): "
                     + "; ".join(f"fill to {float(t['fill_to_bracket_below_rate'])*100:.0f}% "
                                 f"= ${t['conversion_room']} room @ {float(t['blended_rate'])*100:.1f}%"
                                 for t in rc["fill_targets"]))
        ss = opt.get("social_security")
        if ss and ss.get("recommended_claim_age"):
            be = ss.get("breakeven_age_vs_62")
            L.append(f"- **Social Security**: claim at age {ss['recommended_claim_age']}"
                     + (f" (break-even vs 62 at {be})" if be else ""))
        wd = opt.get("withdrawal_plan")
        if wd and wd.get("order"):
            L.append(f"- **Withdrawal order**: {' → '.join(wd['order'])} "
                     f"(annual need ${wd['annual_need']})")
        rk = opt.get("risk")
        if rk:
            L.append(f"- **Risk**: tolerance {rk['tolerance_risk_number']} vs portfolio "
                     f"{rk['portfolio_risk_number']} → {rk['alignment'].replace('_',' ')}")
        es = opt.get("estate")
        if es:
            L.append(f"- **Estate**: taxable estate ${es['taxable_estate']}, projected "
                     f"federal estate tax ${es['projected_federal_estate_tax']}"
                     + (f"; strategies modeled: {', '.join(s['name'] for s in es['strategies'])}"
                        if es.get("strategies") else ""))
        L.append("")

    if result.get("sources"):
        L += ["## Sources", ""]
        for s in result["sources"]:
            L.append(f"{s['n']}. [{s.get('title','')}]({s.get('url','')})")
        L.append("")

    L += ["---", "> [!info] Disclosures"]
    for d in result["disclosures"]:
        L.append(f"> - {d}")

    return "\n".join(L)
