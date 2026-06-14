#!/usr/bin/env python3
"""foo-plan — command line for the deterministic financial planning agent.

Subcommands
-----------
    validate-ruleset            load + integrity-check the knowledge base
    plan        --profile P     Financial Order of Operations recommendations
    project     --profile P     deterministic multi-year projection
    montecarlo  --profile P     seeded Monte Carlo probability of success
    scenario    --base P --scenario S [S ...]   side-by-side what-if comparison
    interview   --profile P     next guided-interview question for a partial profile
    explain     --profile P     plain-English narration of the full plan
    report      --profile P [--brand B] [--pdf out.pdf] [--md out.md]

Determinism: pass --as-of (else read from the profile). Never uses the clock.
"""
from __future__ import annotations

import argparse
import json
import sys


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _emit(obj, out: str | None) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True, default=str)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[foo-plan] wrote {out}", file=sys.stderr)
    else:
        print(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="foo-plan", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--profile", required=True)
        p.add_argument("--as-of", default=None)
        p.add_argument("--out", default=None)

    sub.add_parser("validate-ruleset")

    p_plan = sub.add_parser("plan"); common(p_plan)
    p_proj = sub.add_parser("project"); common(p_proj)

    p_mc = sub.add_parser("montecarlo"); common(p_mc)
    p_mc.add_argument("--seed", type=int, default=None)
    p_mc.add_argument("--trials", type=int, default=None)

    p_sc = sub.add_parser("scenario")
    p_sc.add_argument("--base", required=True)
    p_sc.add_argument("--scenario", nargs="+", required=True)
    p_sc.add_argument("--as-of", default=None)
    p_sc.add_argument("--seed", type=int, default=424242)
    p_sc.add_argument("--trials", type=int, default=10000)
    p_sc.add_argument("--out", default=None)

    p_iv = sub.add_parser("interview"); common(p_iv)
    p_ex = sub.add_parser("explain"); common(p_ex)

    p_rp = sub.add_parser("report"); common(p_rp)
    p_rp.add_argument("--brand", default=None)
    p_rp.add_argument("--pdf", default=None)
    p_rp.add_argument("--md", default=None)
    p_rp.add_argument("--seed", type=int, default=None)
    p_rp.add_argument("--trials", type=int, default=None)

    args = ap.parse_args(argv)

    import foo_agent
    from foo_agent.version import DEFAULT_MC_SEED, DEFAULT_MC_TRIALS

    if args.cmd == "validate-ruleset":
        rs = foo_agent.load_ruleset()
        _emit({
            "version": rs.version, "schema_version": rs.schema_version,
            "checksum": rs.checksum, "rules": len(rs.rules),
            "sources": len(rs.sources), "status": "ok",
        }, None)
        return 0

    if args.cmd == "plan":
        _emit(foo_agent.plan(_load(args.profile), args.as_of), args.out)
        return 0

    if args.cmd == "project":
        from foo_agent.projection import project
        prof = _load(args.profile)
        _emit(project(prof, args.as_of or prof.get("as_of")), args.out)
        return 0

    if args.cmd == "montecarlo":
        from foo_agent.montecarlo import run
        prof = _load(args.profile)
        _emit(run(prof, args.as_of or prof.get("as_of"),
                  seed=args.seed if args.seed is not None else DEFAULT_MC_SEED,
                  trials=args.trials if args.trials is not None else DEFAULT_MC_TRIALS), args.out)
        return 0

    if args.cmd == "scenario":
        from foo_agent.scenarios.compare import compare
        base = _load(args.base)
        scenarios = [_load(s) for s in args.scenario]
        _emit(compare(base, scenarios, args.as_of or base.get("as_of"),
                      seed=args.seed, trials=args.trials), args.out)
        return 0

    if args.cmd == "interview":
        from foo_agent.interview.statemachine import next_question, remaining
        prof = _load(args.profile)
        q = next_question(prof)
        _emit({"next_question": q, "remaining": remaining(prof),
               "complete": q is None}, args.out)
        return 0

    if args.cmd == "explain":
        from foo_agent.explain.renderer import render_plain
        res = foo_agent.full_plan(_load(args.profile), args.as_of)
        print(render_plain(res))
        return 0

    if args.cmd == "report":
        res = foo_agent.full_plan(
            _load(args.profile), args.as_of,
            seed=args.seed if args.seed is not None else DEFAULT_MC_SEED,
            trials=args.trials if args.trials is not None else DEFAULT_MC_TRIALS,
        )
        if args.md:
            from foo_agent.report.markdown import render_markdown
            with open(args.md, "w", encoding="utf-8") as f:
                f.write(render_markdown(res))
            print(f"[foo-plan] wrote {args.md}", file=sys.stderr)
        if args.pdf:
            from foo_agent.report.pdf import write_pdf
            write_pdf(res, args.pdf, args.brand)
            print(f"[foo-plan] wrote {args.pdf}", file=sys.stderr)
        if not args.md and not args.pdf:
            _emit(res, args.out)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
