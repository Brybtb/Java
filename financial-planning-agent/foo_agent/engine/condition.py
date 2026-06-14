"""A tiny, safe boolean expression language evaluated over profile facts.

This is the determinism + security keystone: rule and insight conditions are
strings authored as data, so they must NEVER reach Python ``eval``/``exec``.
Instead we tokenize, parse into a fixed-grammar AST, and evaluate against an
immutable fact view.

Grammar (lowest to highest precedence)::

    expr        := or_expr
    or_expr     := and_expr ('or' and_expr)*
    and_expr    := not_expr ('and' not_expr)*
    not_expr    := 'not' not_expr | comparison
    comparison  := primary (op primary)?          # op: == != < <= > >= in
    primary     := '(' expr ')' | exists '(' path ')' | list | literal | path
    list        := '[' (literal (',' literal)*)? ']'
    literal     := NUMBER | STRING | 'true' | 'false' | 'null'
    path        := IDENT ('.' IDENT)*

Semantics designed to *fail closed*: a comparison touching a missing field
evaluates to ``False`` (the rule simply does not fire) rather than raising, so
incomplete data can never produce a spurious recommendation. ``exists(path)`` is
the one way to test presence. Numeric comparisons use ``Decimal`` to avoid float
drift, keeping evaluation deterministic.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .errors import ConditionError

# Sentinel for a path that does not resolve. Distinct from ``None`` (== JSON null).
MISSING = object()

_KEYWORDS = {"and", "or", "not", "in", "true", "false", "null", "exists"}
_COMPARATORS = {"==", "!=", "<", "<=", ">", ">="}


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
class _Tok:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: Any):
        self.kind = kind
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Tok({self.kind},{self.value!r})"


def _tokenize(src: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c in "()[],.":
            toks.append(_Tok(c, c))
            i += 1
            continue
        if c in "<>=!":
            two = src[i : i + 2]
            if two in _COMPARATORS:
                toks.append(_Tok("op", two))
                i += 2
                continue
            if c in "<>":
                toks.append(_Tok("op", c))
                i += 1
                continue
            raise ConditionError(f"unexpected character {c!r} at {i} in {src!r}")
        if c in "'\"":
            j = i + 1
            buf = []
            while j < n and src[j] != c:
                buf.append(src[j])
                j += 1
            if j >= n:
                raise ConditionError(f"unterminated string in {src!r}")
            toks.append(_Tok("string", "".join(buf)))
            i = j + 1
            continue
        if c.isdigit() or (c == "-" and i + 1 < n and src[i + 1].isdigit()):
            j = i + 1
            while j < n and (src[j].isdigit() or src[j] == "."):
                j += 1
            raw = src[i:j]
            try:
                toks.append(_Tok("number", Decimal(raw)))
            except InvalidOperation as exc:
                raise ConditionError(f"bad number {raw!r}") from exc
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            if word in _KEYWORDS:
                toks.append(_Tok(word, word))
            else:
                toks.append(_Tok("ident", word))
            i = j
            continue
        raise ConditionError(f"unexpected character {c!r} at {i} in {src!r}")
    toks.append(_Tok("eof", None))
    return toks


# --------------------------------------------------------------------------- #
# Parser -> AST (tuples). Node shapes:
#   ("or", a, b) ("and", a, b) ("not", a)
#   ("cmp", op, left, right)
#   ("path", ["a","b"]) ("lit", value) ("list", [values]) ("exists", ["a","b"])
# --------------------------------------------------------------------------- #
class _Parser:
    def __init__(self, toks: list[_Tok]):
        self.toks = toks
        self.pos = 0

    def _peek(self) -> _Tok:
        return self.toks[self.pos]

    def _next(self) -> _Tok:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def _expect(self, kind: str) -> _Tok:
        t = self._next()
        if t.kind != kind:
            raise ConditionError(f"expected {kind!r}, got {t.kind!r} ({t.value!r})")
        return t

    def parse(self):
        node = self._or()
        if self._peek().kind != "eof":
            raise ConditionError(f"trailing tokens near {self._peek().value!r}")
        return node

    def _or(self):
        node = self._and()
        while self._peek().kind == "or":
            self._next()
            node = ("or", node, self._and())
        return node

    def _and(self):
        node = self._not()
        while self._peek().kind == "and":
            self._next()
            node = ("and", node, self._not())
        return node

    def _not(self):
        if self._peek().kind == "not":
            self._next()
            return ("not", self._not())
        return self._comparison()

    def _comparison(self):
        left = self._primary()
        t = self._peek()
        if t.kind == "op":
            self._next()
            return ("cmp", t.value, left, self._primary())
        if t.kind == "in":
            self._next()
            return ("cmp", "in", left, self._primary())
        return left

    def _primary(self):
        t = self._peek()
        if t.kind == "(":
            self._next()
            node = self._or()
            self._expect(")")
            return node
        if t.kind == "exists":
            self._next()
            self._expect("(")
            path = self._path()
            self._expect(")")
            return ("exists", path[1])
        if t.kind == "[":
            return self._list()
        if t.kind == "number" or t.kind == "string":
            self._next()
            return ("lit", t.value)
        if t.kind in ("true", "false", "null"):
            self._next()
            return ("lit", {"true": True, "false": False, "null": None}[t.kind])
        if t.kind == "ident":
            return self._path()
        raise ConditionError(f"unexpected token {t.kind!r} ({t.value!r})")

    def _path(self):
        parts = [self._expect("ident").value]
        while self._peek().kind == ".":
            self._next()
            parts.append(self._expect("ident").value)
        return ("path", parts)

    def _list(self):
        self._expect("[")
        items = []
        if self._peek().kind != "]":
            items.append(self._literal_value())
            while self._peek().kind == ",":
                self._next()
                items.append(self._literal_value())
        self._expect("]")
        return ("list", items)

    def _literal_value(self):
        t = self._next()
        if t.kind in ("number", "string"):
            return t.value
        if t.kind in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[t.kind]
        raise ConditionError(f"list elements must be literals, got {t.kind!r}")


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def _resolve(path: list[str], facts: dict) -> Any:
    cur: Any = facts
    for seg in path:
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return MISSING
    return cur


def _as_decimal(v: Any):
    if isinstance(v, bool):
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(str(v))
    return None


def _compare(op: str, left: Any, right: Any) -> bool:
    if left is MISSING or right is MISSING:
        return False  # fail closed
    if op == "in":
        if not isinstance(right, (list, tuple)):
            return False
        return left in right
    if op in ("==", "!="):
        ld, rd = _as_decimal(left), _as_decimal(right)
        if ld is not None and rd is not None:
            eq = ld == rd
        else:
            eq = left == right
        return eq if op == "==" else not eq
    # ordered comparisons require numbers
    ld, rd = _as_decimal(left), _as_decimal(right)
    if ld is None or rd is None:
        return False  # fail closed: cannot order non-numbers
    if op == "<":
        return ld < rd
    if op == "<=":
        return ld <= rd
    if op == ">":
        return ld > rd
    if op == ">=":
        return ld >= rd
    raise ConditionError(f"unknown operator {op!r}")


def _eval(node, facts: dict) -> Any:
    tag = node[0]
    if tag == "or":
        return bool(_eval(node[1], facts)) or bool(_eval(node[2], facts))
    if tag == "and":
        return bool(_eval(node[1], facts)) and bool(_eval(node[2], facts))
    if tag == "not":
        return not bool(_eval(node[1], facts))
    if tag == "cmp":
        return _compare(node[1], _eval(node[2], facts), _eval(node[3], facts))
    if tag == "lit":
        return node[1]
    if tag == "list":
        return list(node[1])
    if tag == "exists":
        return _resolve(node[1], facts) is not MISSING
    if tag == "path":
        return _resolve(node[1], facts)
    raise ConditionError(f"unknown node {tag!r}")  # pragma: no cover


class Condition:
    """A compiled condition. Parsing happens once; ``evaluate`` is pure."""

    __slots__ = ("source", "ast")

    def __init__(self, source: str):
        self.source = source
        self.ast = _Parser(_tokenize(source)).parse()

    def evaluate(self, facts: dict) -> bool:
        return bool(_eval(self.ast, facts))

    def __repr__(self) -> str:  # pragma: no cover
        return f"Condition({self.source!r})"


def compile_condition(source: str) -> Condition:
    """Parse a condition string into a reusable :class:`Condition`."""
    if not isinstance(source, str) or not source.strip():
        raise ConditionError("condition must be a non-empty string")
    return Condition(source)
