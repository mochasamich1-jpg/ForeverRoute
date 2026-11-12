"""Quests the installed Questie shows that a route does not use.

Usage: python -I tools/questie_gaps.py [--route <key> | --route all] [--all-zones]

Reads the baked QuestieDB (tools/questie_baked.py), keeps the quests the route's race / class / faction can take,
and lists those that no step of the route mentions. By default only quests whose giver stands in a zone where the
route accepts at least one quest are shown, sorted by zone and level, with a flag:
  UNKNOWN  = the quest is in neither the old Questie export (research/json/quests.json) nor the ForeverChanges
             zone lists, so nobody could have planned it
  known    = it was in the data when the route was written and was left out (on purpose or not)
"""
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_route as B  # noqa: E402
import questie_baked  # noqa: E402

ALLIANCE = 1 | 4 | 8 | 64 | (1 << 32)
HORDE = 2 | 16 | 32 | 128


def pts_of(sp):
    """spawns -> {zone: [points]} whatever shape the store used."""
    out = {}
    if isinstance(sp, dict):
        for z, pts in sp.items():
            out[str(z)] = [p for p in (pts or []) if isinstance(p, list) and len(p) >= 2]
    elif isinstance(sp, list):
        for item in sp:
            if isinstance(item, list) and len(item) == 2 and isinstance(item[1], list):
                out[str(item[0])] = [p for p in item[1] if isinstance(p, list) and len(p) >= 2]
    return out


def places(db, ent):
    """startedBy / finishedBy -> [(name, zone id, x, y)]"""
    out = []
    if not isinstance(ent, list):
        return out
    for i, ids in enumerate(ent):
        if not isinstance(ids, list):
            continue
        for e in ids:
            if i == 2:
                out.append((f"item:{db['Item'].get(str(e), {}).get('1', e)}", None, None, None))
                continue
            rec = db['Npc' if i == 0 else 'Object'].get(str(e), {})
            sp = pts_of(rec.get('7' if i == 0 else '4'))
            if not sp:
                out.append((rec.get('1', str(e)), None, None, None))
            for z, pts in sp.items():
                if pts:
                    out.append((rec.get('1', str(e)), z, pts[0][0], pts[0][1]))
                else:
                    out.append((rec.get('1', str(e)), z, None, None))
    return out


def route_quests(key):
    used = set()
    for f in glob.glob(str(B.ROOT / 'routes' / key / '*.route')):
        for line in open(f, encoding='utf-8'):
            m = re.match(r'^(A|C|T)\s+([\d:,\s]+)', line)
            if m:
                used.update(re.findall(r'(\d+)(?::\d+)?', m.group(2)))
    return used


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    key = args[args.index('--route') + 1] if '--route' in args else 'all'
    all_zones = '--all-zones' in args
    db = questie_baked.load()
    D = B.Data()
    known_old = set(D.quests) | set(D.fc_rows)
    for rk in (list(B.PROFILES) if key == 'all' else [key]):
        P = B.use_profile(rk)
        used = route_quests(rk)
        side = ALLIANCE if P['side'] == 'Alliance' else HORDE
        # zones where the route takes quests (from the baked giver positions)
        zones = set()
        for q in used:
            for _, z, _, _ in places(db, db['Quest'].get(q, {}).get('2')):
                if z:
                    zones.add(z)
        rows = []
        for qid, q in db['Quest'].items():
            if qid in used:
                continue
            races, classes = q.get('6') or 0, q.get('7') or 0
            if races and not (races & P['race_bit']):
                continue
            if not races and False:
                continue
            if classes and not (classes & P['class_bit']):
                continue
            st = places(db, q.get('2'))
            if not st:
                continue
            zs = {z for _, z, _, _ in st if z}
            if not all_zones and not (zs & zones):
                continue
            # a quest with no race mask can still be one-sided: judge by the giver's faction letters when present
            giver_side = None
            for i, ids in enumerate(q.get('2') or []):
                for e in (ids or []) if i == 0 else []:
                    f = db['Npc'].get(str(e), {}).get('13')
                    if f in ('A', 'H', 'AH'):
                        giver_side = f
            if giver_side and P['side'][0] not in giver_side:
                continue
            if qid in D.dungeon_quests:
                continue
            z = sorted(zs & zones)[0] if (zs & zones) else (sorted(zs)[0] if zs else '?')
            rows.append((z, q.get('5') or 0, int(qid), q, st))
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        unknown = [r for r in rows if str(r[2]) not in known_old]
        print(f"\n===== {rk}: {len(rows)} takeable quests not in the route "
              f"({len(unknown)} of them UNKNOWN to the data the route was written from)")
        zone = None
        for z, lv, qid, q, st in rows:
            if z != zone:
                zone = z
                print(f"--- zone {B.zone_label(D, int(z)) if z.isdigit() else z} ({z})")
            s = st[0]
            en = places(db, q.get('3'))
            e = en[0] if en else ('?', None, None, None)
            flag = 'known  ' if str(qid) in known_old else 'UNKNOWN'
            pre = ''
            if q.get('13'):
                pre += f" pre1:{q['13']}"
            if q.get('12'):
                pre += f" preAll:{q['12']}"
            obj = (q.get('8') or [''])
            obj = obj[0] if isinstance(obj, list) and obj else ''
            print(f"  {flag} {qid} L{lv} req{q.get('4')} {q.get('1')!r} | {s[0]} {s[2]},{s[3]} -> {e[0]} {e[2]},{e[3]}"
                  f"{pre} | cls {q.get('7') or ''} | {str(obj)[:110]}")


if __name__ == '__main__':
    main()
