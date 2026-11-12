"""Skipped quests whose giver stands right where a route already stops, at a level that fits that stop.

Usage: python -I tools/questie_near.py [--route all]
A narrower cut of tools/questie_gaps.py: giver within 2.5 map units of one of the route's accept / turn-in steps,
quest level inside that segment's level range (-2 .. +3), not elite / dungeon / another class / camping.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_route as B  # noqa: E402
import questie_baked  # noqa: E402
from questie_gaps import places, route_quests  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    key = args[args.index('--route') + 1] if '--route' in args else 'all'
    db = questie_baked.load()
    D = B.Data()
    for rk in (list(B.PROFILES) if key == 'all' else [key]):
        P = B.use_profile(rk)
        used = route_quests(rk)
        lua = (B.ROOT / 'addon' / 'ForeverRoute' / 'Routes' / f"{P['lua']}.lua").read_text(encoding='utf-8')
        segs = {}
        head = lua[lua.index('segments = {'):]
        head = head[:head.index('}')]
        for i, m in enumerate(re.finditer(r'"(\d+)-(\d+) ([^"]*)"', head), 1):
            segs[i] = (int(m.group(1)), int(m.group(2)), m.group(3))
        stops = []  # (zone name, x, y, seg)
        for m in re.finditer(r'\{t="([AT])", seg=(\d+),(.*)', lua):
            body = m.group(3)
            if 'dg=' in body:
                continue
            z = re.search(r'zone="([^"]*)"', body)
            x = re.search(r'\bx=([\d.]+)', body)
            y = re.search(r'\by=([\d.]+)', body)
            if z and x and y:
                stops.append((z.group(1), float(x.group(1)), float(y.group(1)), int(m.group(2))))
        out = []
        for qid, q in db['Quest'].items():
            if qid in used or qid in D.dungeon_quests:
                continue
            races, classes = q.get('6') or 0, q.get('7') or 0
            if (races and not races & P['race_bit']) or (classes and not classes & P['class_bit']):
                continue
            name = q.get('1') or ''
            lv, req = q.get('5') or 0, q.get('4') or 0
            if lv <= 0 or lv > 60 or name.startswith('Camping 101'):
                continue
            row = D.fc_rows.get(qid, {})
            if row.get('elite'):
                continue
            if row and P['side'] not in row.get('sides', [P['side']]):
                continue
            old = D.quests.get(qid, {})
            if old.get('requiredClasses') and not old['requiredClasses'] & P['class_bit']:
                continue
            if old.get('requiredRaces') and not old['requiredRaces'] & P['race_bit']:
                continue
            best = None
            for nm, z, x, y in places(db, q.get('2')):
                if not z or x is None or not z.isdigit():
                    continue
                zn = B.zone_label(D, int(z))
                for sz, sx, sy, seg in stops:
                    if sz != zn or seg not in segs:
                        continue
                    lo, hi, _ = segs[seg]
                    if abs(sx - x) <= 2.5 and abs(sy - y) <= 2.5 and lo - 2 <= lv <= hi + 3 and req <= hi:
                        if best is None or seg < best[0]:
                            best = (seg, zn, nm, x, y)
            if best:
                out.append((best[0], best[1], lv, int(qid), name, best[2], best[3], best[4], row.get('xp'), q.get('13'), req))
        out.sort()
        print(f"\n===== {rk}: {len(out)} skipped quests with the giver at a route stop and a fitting level")
        for seg, zn, lv, qid, name, nm, x, y, xp, pre, req in out:
            print(f"  seg {seg:2d} {segs[seg][0]}-{segs[seg][1]} {zn:20s} {qid} L{lv} req{req} {name!r} | {nm} {x},{y} | xp {xp} | pre {pre}")


if __name__ == '__main__':
    main()
