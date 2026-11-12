"""Parse QuestieDB raw Lua data tables into Python dicts and dump JSON.

Usage: python -I luadata.py <data_dir> <out_dir>
"""
import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(r"""
    (?P<ws>\s+|--[^\n]*)
  | (?P<num>-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<kw>nil|true|false)
  | (?P<p>[{}\[\]=,;])
""", re.X)


def tokenize(s):
    pos = 0
    out = []
    n = len(s)
    while pos < n:
        m = TOKEN.match(s, pos)
        if not m:
            raise ValueError(f"bad token at {pos}: {s[pos:pos+40]!r}")
        pos = m.end()
        k = m.lastgroup
        if k == 'ws':
            continue
        v = m.group(k)
        if k == 'num':
            out.append(('n', float(v) if ('.' in v or 'e' in v.lower()) else int(v)))
        elif k == 'str':
            body = v[1:-1]
            body = re.sub(r"\\(.)", lambda mm: {'n': '\n', 't': '\t'}.get(mm.group(1), mm.group(1)), body)
            out.append(('s', body))
        elif k == 'kw':
            out.append(('v', {'nil': None, 'true': True, 'false': False}[v]))
        else:
            out.append(('p', v))
    return out


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def take(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def value(self):
        k, v = self.take()
        if k in ('n', 's', 'v'):
            return v
        if k == 'p' and v == '{':
            return self.table()
        raise ValueError(f"unexpected {k}:{v} at token {self.i}")

    def table(self):
        arr = []
        hsh = {}
        idx = 1
        while True:
            k, v = self.peek()
            if k == 'p' and v == '}':
                self.take()
                break
            if k == 'p' and v == '[':
                self.take()
                key = self.value()
                assert self.take() == ('p', ']')
                assert self.take() == ('p', '=')
                hsh[key] = self.value()
            else:
                val = self.value()
                hsh[idx] = val
                idx += 1
            k, v = self.peek()
            if k == 'p' and v in (',', ';'):
                self.take()
        # Convert pure 1..n arrays (allowing nil holes) to lists, keep dicts otherwise
        if hsh and all(isinstance(x, int) and x >= 1 for x in hsh):
            mx = max(hsh)
            if mx <= len(hsh) * 2 + 4 and idx - 1 == len([x for x in hsh if x < idx]) and all(x < idx for x in hsh):
                return [hsh.get(j) for j in range(1, mx + 1)]
        return hsh


def parse_db(path, var):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    keys_m = re.search(r"QuestieDB\.%sKeys\s*=\s*\{(.*?)\n\}" % var, text, re.S)
    keys = {}
    if keys_m:
        for name, idx in re.findall(r"^\s*\['(\w+)'\]\s*=\s*(\d+)", keys_m.group(1), re.M):
            keys[int(idx)] = name
    body_m = re.search(r"QuestieDB\.%sData\s*=\s*\[\[return\s*(\{.*\})\s*\]\]" % var, text, re.S)
    toks = tokenize(body_m.group(1))
    p = Parser(toks)
    assert p.take() == ('p', '{')
    raw = p.table()
    out = {}
    items = raw.items() if isinstance(raw, dict) else enumerate(raw, 1)
    for eid, row in items:
        if row is None:
            continue
        rec = {}
        seq = row if isinstance(row, list) else [row.get(j) for j in range(1, max(row) + 1)]
        for j, val in enumerate(seq, 1):
            if val is not None:
                rec[keys.get(j, str(j))] = val
        out[int(eid)] = rec
    return out


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [jsonable(v) for v in o]
    return o


def main():
    data_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for fname, var in [('data_Forever_foreverQuestDB.lua', 'quest'),
                       ('data_Forever_foreverNpcDB.lua', 'npc'),
                       ('data_Forever_foreverObjectDB.lua', 'object'),
                       ('data_Forever_foreverItemDB.lua', 'item')]:
        db = parse_db(data_dir / fname, var)
        (out_dir / f"{var}s.json").write_text(json.dumps(jsonable(db)), encoding='utf-8')
        print(var, len(db))


if __name__ == '__main__':
    main()
