"""A small S-expression reader and writer for KiCad files (symbol libraries in, schematics out)."""
from __future__ import annotations

import re

TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """A bare (unquoted) atom."""


def parse(text: str):
    stack, cur = [], []
    for m in TOKEN.finditer(text):
        op, cl, qs, atom = m.groups()
        if op:
            stack.append(cur)
            cur = []
        elif cl:
            done, cur = cur, stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(qs[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        elif atom is not None:
            cur.append(Sym(atom))
    return cur[0] if len(cur) == 1 else cur


def q(s: str) -> str:
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(node, indent=0) -> str:
    """KiCad-style: one list per line when it holds lists, else inline."""
    pad = '\t' * indent
    if not isinstance(node, list):
        return pad + (str(node) if isinstance(node, Sym) or isinstance(node, (int, float)) else q(node))
    head = [x for x in node if not isinstance(x, list)]
    kids = [x for x in node if isinstance(x, list)]
    first = ' '.join(fmt(x) for x in head)
    if not kids:
        return f'{pad}({first})'
    inner = '\n'.join(dump(k, indent + 1) for k in kids)
    return f'{pad}({first}\n{inner}\n{pad})'


def fmt(x) -> str:
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        s = f'{x:.4f}'.rstrip('0').rstrip('.')
        return s if s not in ('-0', '') else '0'
    return q(x)


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None
