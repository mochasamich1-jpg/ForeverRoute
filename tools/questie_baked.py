"""Read the QuestieDB "baked" store: since the 2026-11 Questie build the Forever data lives in
QuestieDB_Forever.toc as `## X-<Kind>-<id>-<field>: <base64 CBOR>` lines, not in Lua data files.
The `-S` field is one map holding the scalar fields (name, levels, race / class masks, zone).
This is where Questie's own Forever quests (ids 9xxxx: Zephras Isle and the other new content) are;
research/json/*.json was extracted from the older Lua files and has none of them.

Usage:  python -I tools/questie_baked.py            -> research/json/baked_{quests,npcs,objects,items}.json
        from questie_baked import load              -> {'Quest': {id: {field: value}}, 'Npc': ..., ...}
Field numbers are Questie's own key indexes (quest: 1 name, 2 startedBy, 3 finishedBy, 4 requiredLevel,
5 questLevel, 6 requiredRaces, 7 requiredClasses, 8 objectivesText, 10 objectives, 12 preQuestGroup,
13 preQuestSingle, 17 zoneOrSort, 22 nextQuestInChain ...; npc: 1 name, 4 minLevel, 5 maxLevel, 6 rank,
7 spawns, 9 zoneID ...; object: 1 name, 4 spawns, 5 zoneID).
"""
import base64
import json
import re
import struct
import sys
from pathlib import Path

TOC = Path(r'C:/Program Files (x86)/World of Warcraft/_forever_/Interface/AddOns/QuestieDB/QuestieDB_Forever.toc')
OUT = Path(__file__).resolve().parent.parent / 'research' / 'json'


def cbor(b, i=0):
    """Minimal CBOR decoder: returns (value, next index)."""
    ib = b[i]
    major, info = ib >> 5, ib & 31
    i += 1
    if major == 7:
        if info == 20:
            return False, i
        if info == 21:
            return True, i
        if info in (22, 23):
            return None, i
        if info == 25:
            return struct.unpack('>e', b[i:i + 2])[0], i + 2
        if info == 26:
            return struct.unpack('>f', b[i:i + 4])[0], i + 4
        if info == 27:
            return struct.unpack('>d', b[i:i + 8])[0], i + 8
        raise ValueError(f'simple {info}')
    if info < 24:
        n = info
    elif info == 24:
        n, i = b[i], i + 1
    elif info == 25:
        n, i = int.from_bytes(b[i:i + 2], 'big'), i + 2
    elif info == 26:
        n, i = int.from_bytes(b[i:i + 4], 'big'), i + 4
    elif info == 27:
        n, i = int.from_bytes(b[i:i + 8], 'big'), i + 8
    else:
        raise ValueError(f'indefinite length not supported ({info})')
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major == 2:
        return b[i:i + n].decode('utf-8', 'replace'), i + n
    if major == 3:
        return b[i:i + n].decode('utf-8', 'replace'), i + n
    if major == 4:
        out = []
        for _ in range(n):
            v, i = cbor(b, i)
            out.append(v)
        return out, i
    if major == 5:
        out = {}
        for _ in range(n):
            k, i = cbor(b, i)
            v, i = cbor(b, i)
            out[str(k)] = v
        return out, i
    if major == 6:
        return cbor(b, i)
    raise ValueError(major)


def load(toc=TOC):
    db = {}
    pat = re.compile(r'^## X-(Quest|Npc|Object|Item)-(\d+)-(\w+): (\S+)')
    bad = 0
    with open(toc, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = pat.match(line)
            if not m:
                continue
            kind, eid, field, b64 = m.groups()
            try:
                val, _ = cbor(base64.b64decode(b64))
            except Exception:
                bad += 1
                continue
            rec = db.setdefault(kind, {}).setdefault(eid, {})
            if field == 'S' and isinstance(val, dict):  # the small scalar fields, packed into one map
                rec.update(val)
            else:
                rec[field] = val
    db['_bad'] = bad
    return db


if __name__ == '__main__':
    d = load()
    print('undecodable lines:', d.pop('_bad'))
    for kind, name in (('Quest', 'quests'), ('Npc', 'npcs'), ('Object', 'objects'), ('Item', 'items')):
        (OUT / f'baked_{name}.json').write_text(json.dumps(d.get(kind, {})), encoding='utf-8')
        print(kind, len(d.get(kind, {})))
