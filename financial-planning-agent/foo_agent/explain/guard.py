"""Guard for LLM-rendered text (explanations, copilot replies, proposer narration).

Rejects any output that introduces a rule/insight/module id, a dollar figure, a
percentage, or an age that is not present in the computed Result(s) for the turn —
so AI can phrase, but never author a number that reaches the client. Accepts a
single Result or a list of Results (a copilot turn may touch several tools).

C01 hardening (audit B7): the allowed-number set is built from CURATED value
fields only. Provenance (sha256 hashes, seeds, as_of dates, trials, ids, citations,
checksums, version strings) and list indices are NOT mined for numbers — so a
fabricated figure can no longer slip through because its digits happen to appear
inside a hash, a seed, or the as_of year. Spelled-out / magnitude dollar figures
("1.4 million dollars", "$5 million") are also checked.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ..engine.errors import FooError

_RULE_ID = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+\b")
_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_AGE = re.compile(r"\bage\s+(\d{1,3})\b", re.I)
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Keys whose VALUES are provenance / run-metadata, never client-facing figures.
# Their numbers must not become "allowed" (audit B7: $2026 from as_of, $2000 from
# trials, digits from input_hash were all wrongly accepted).
_PROVENANCE_KEYS = frozenset({
    "input_hash", "output_hash", "checksum", "ruleset_checksum",
    "schema_version", "engine_version", "ruleset_version", "cma_version", "version",
    "mc_seed", "seed", "trials", "as_of", "id", "rule_id", "rationale_key",
    "citations", "sources", "step",
})
# A value string carrying a hash / long hex run is never a source of figures.
_HASHISH = re.compile(r"sha256:|[0-9a-f]{16,}", re.I)

# Namespaced id prefixes we police (avoids flagging prose like "e.g."/"i.e.").
_ID_PREFIXES = (
    "foo.", "decum.", "contributions.", "emergency_fund.", "employer_match.",
    "debt.", "tax.", "protection.", "rmd.", "magi.", "decumulation.",
)

# Spelled-out / magnitude dollar figures (no "$" digit form to catch them otherwise).
_WORDNUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_MAG = {"thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000,
        "k": 1000, "m": 1_000_000, "b": 1_000_000_000}
_NUMWORD = "|".join(_WORDNUM)
_MAG_DOLLARS = re.compile(
    r"\b(\d+(?:\.\d+)?|" + _NUMWORD + r")\s+(thousand|million|billion)\s+dollars\b", re.I)
_DOLLAR_MAG = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s*(thousand|million|billion|[kmb])\b", re.I)


class GuardError(FooError):
    """The LLM text referenced something not in the Result(s)."""


def _as_list(result_or_results) -> list[dict]:
    if isinstance(result_or_results, list):
        return result_or_results
    return [result_or_results]


def _allowed_ids(results: list[dict]) -> set[str]:
    ids: set[str] = set()
    for r in results:
        for rec in r.get("recommendations", []) or []:
            ids.add(rec.get("rule_id", ""))
        for ins in r.get("insights", []) or []:
            ids.add(ins.get("id", ""))
        for m in (r.get("workflow", {}) or {}).get("selected_modules", []) or []:
            ids.add(m.get("id", ""))
    return ids


def _add_number(tok, allowed: set[str]) -> None:
    norm = str(tok).replace(",", "")
    if not norm or norm == ".":
        return
    allowed.add(norm)
    if "." in norm:
        allowed.add(norm.rstrip("0").rstrip("."))
    try:
        d = Decimal(norm)
    except InvalidOperation:
        return
    if 0 < d < 1:                                 # 0.22 -> "22"
        allowed.add(str((d * 100).normalize()))
        allowed.add(str(int(d * 100)))
    if d == d.to_integral_value():                # 22.0 -> "22"
        allowed.add(str(int(d)))


def _collect(node, key, allowed: set[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            _collect(v, k, allowed)
        return
    if isinstance(node, list):
        for item in node:
            _collect(item, key, allowed)          # list items inherit the parent key; indices ignored
        return
    if key in _PROVENANCE_KEYS:                    # leaf under a provenance key -> ignore its digits
        return
    if isinstance(node, bool) or node is None:
        return
    if isinstance(node, (int, float, Decimal)):
        _add_number(str(node), allowed)
    elif isinstance(node, str):
        if _HASHISH.search(node):
            return
        for tok in _NUM.findall(node):
            _add_number(tok, allowed)


def _allowed_numbers(results: list[dict]) -> set[str]:
    allowed: set[str] = set()
    for r in results:
        _collect(r, None, allowed)
    return allowed


def _num_in(value, allowed: set[str]) -> bool:
    norm = str(value).replace(",", "")
    if norm in allowed:
        return True
    trimmed = norm.rstrip("0").rstrip(".") if "." in norm else norm
    return trimmed in allowed


def _magnitude_value(base: str, mag: str):
    b = _WORDNUM.get(base.lower())
    if b is None:
        try:
            b = float(base)
        except ValueError:
            return None
    mult = _MAG.get(mag.lower())
    if mult is None:
        return None
    return b * mult


def _value_allowed(val, allowed: set[str]) -> bool:
    iv = int(val)
    return _num_in(str(iv), allowed) or (val != iv and _num_in(str(val), allowed))


def check(text: str, result_or_results) -> list[str]:
    """Return a list of violations (empty == clean)."""
    results = _as_list(result_or_results)
    issues: list[str] = []

    allowed_ids = _allowed_ids(results)
    for m in _RULE_ID.findall(text):
        if m.startswith(_ID_PREFIXES) and m not in allowed_ids:
            issues.append(f"unknown rule/calculator id referenced: {m}")

    allowed_nums = _allowed_numbers(results)
    for amt in _MONEY.findall(text):
        if not _num_in(amt, allowed_nums):
            issues.append(f"dollar figure not in Result: ${amt}")
    for pct in _PERCENT.findall(text):
        if not _num_in(pct, allowed_nums):
            issues.append(f"percentage not in Result: {pct}%")
    for ag in _AGE.findall(text):
        if not _num_in(ag, allowed_nums):
            issues.append(f"age not in Result: age {ag}")

    # Spelled-out / magnitude dollar figures (e.g. "1.4 million dollars", "$5 million").
    for base, mag in _MAG_DOLLARS.findall(text):
        val = _magnitude_value(base, mag)
        if val is not None and not _value_allowed(val, allowed_nums):
            issues.append(f"spelled-out dollar figure not in Result: {base} {mag} dollars")
    for num, mag in _DOLLAR_MAG.findall(text):
        val = _magnitude_value(num, mag)
        if val is not None and not _value_allowed(val, allowed_nums):
            issues.append(f"dollar figure not in Result: ${num} {mag}")

    return issues


def validate(text: str, result_or_results, *, strict: bool = True) -> str:
    issues = check(text, result_or_results)
    if issues and strict:
        raise GuardError("text rejected (AI introduced data not in the Result):\n  - "
                         + "\n  - ".join(issues))
    return text
