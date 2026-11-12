"""Write per-zone quest digests (Markdown) for route authors.

Usage: python -I digest.py [--route orc-shaman]  -> research/digest/<route>/<zone>.md and _index.md
Includes every quest the route's race/class (Horde) can take, merging ForeverChanges lists (Forever XP,
new/changed tags) with Questie data (givers, prerequisites, objectives).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_route as B  # noqa: E402


def npc_desc(D, started, which):
    if not started:
        return ''
    out = []
    for kind_i, ids in enumerate(started):
        if not ids:
            continue
        src = {0: D.npcs, 1: D.objects}.get(kind_i)
        for eid in ids[:2]:
            if src is None:
                it = D.items.get(str(eid), {})
                out.append(f"item:{it.get('name', eid)}")
                continue
            e = src.get(str(eid), {})
            loc = ''
            sp = e.get('spawns') or {}
            if sp:
                z = next(iter(sp))
                pts = sp[z]
                if pts:
                    c = B.centroid([p for p in pts if isinstance(p, list)])
                    if c:
                        loc = f" @{B.zone_label(D, int(z))} {c[0]},{c[1]}"
            out.append(f"{e.get('name', eid)}{loc}")
    return '; '.join(out)


def main():
    args = sys.argv[1:]
    key = args[args.index('--route') + 1] if '--route' in args else 'undead-mage'
    P = B.use_profile(key)
    D = B.Data()
    outdir = B.RES / 'digest' / key
    outdir.mkdir(parents=True, exist_ok=True)
    index = [f"# Quest digests by zone ({P['title']}, {P['side']})", '',
             '| zone | quests | new | changed | dungeon zone |', '|---|---|---|---|---|']
    for slug, info in D.fc_zones.items():
        if slug.capitalize() in B.CLASS_PAGES and slug.capitalize() != P['class']:
            continue
        rows = []
        for r in info['quests']:
            qid = str(r['id'])
            if P['side'] not in r['sides']:
                continue
            q = D.quests.get(qid, {})
            races = q.get('requiredRaces')
            if races and not (races & P['race_bit']):
                continue
            classes = q.get('requiredClasses')
            if classes and not (classes & P['class_bit']):
                continue
            fc = D.fc.get(qid, {})
            pins = {p['role']: p for p in fc.get('pins', [])}
            def pz(pin):
                z = fc.get('zone')
                if z in B.CLASS_PAGES or not z:
                    aid = D.zone_of_named(pin['name'], pin['x'], pin['y'])
                    z = B.zone_label(D, aid) if aid is not None else f'{z}-page'
                return z
            start = (f"{pins['Start']['name']} @{pz(pins['Start'])} {pins['Start']['x']},{pins['Start']['y']}"
                     if 'Start' in pins else npc_desc(D, q.get('startedBy'), 'start'))
            end = (f"{pins['End']['name']} @{pz(pins['End'])} {pins['End']['x']},{pins['End']['y']}"
                   if 'End' in pins else npc_desc(D, q.get('finishedBy'), 'end'))
            pre = []
            if q.get('preQuestSingle'):
                pre.append('one of ' + ','.join(map(str, q['preQuestSingle'])))
            if q.get('preQuestGroup'):
                pre.append('all of ' + ','.join(map(str, q['preQuestGroup'])))
            if q.get('breadcrumbForQuestId'):
                pre.append(f"breadcrumb->{q['breadcrumbForQuestId']}")
            if q.get('exclusiveTo'):
                pre.append('excl ' + ','.join(map(str, q['exclusiveTo'])))
            nxt = q.get('nextQuestInChain')
            obj = '; '.join(q.get('objectivesText') or []) or ''
            if not obj and fc.get('text'):
                t = fc['text']
                i = t.find('Quest Objectives')
                if i >= 0:
                    obj = ' '.join(t[i + 17:i + 260].split())
            flags = []
            if r.get('status'):
                flags.append(r['status'].upper())
            if r.get('elite'):
                flags.append('ELITE')
            if classes:
                flags.append(P['class'].upper())
            rows.append((r.get('level') or q.get('questLevel') or 0, qid, r, start, end, pre, nxt, obj, flags))
        rows.sort(key=lambda x: (x[0], int(x[1])))
        lines = [f"# {slug} ({'DUNGEON - do not use' if info.get('dungeon') else 'zone'})", '',
                 'Columns: id | name | lvl | req | ForeverXP | flags | start | end | prereqs | next | objective', '']
        for lvl, qid, r, start, end, pre, nxt, obj, flags in rows:
            lines.append(f"{qid} | {r['name']} | {lvl} | {r.get('reqLevel') or ''} | {r.get('xp') or ''} | "
                         f"{' '.join(flags)} | {start} | {end} | {' '.join(pre)} | {nxt or ''} | {obj[:220]}")
        (outdir / f"{slug}.md").write_text('\n'.join(lines) + '\n', encoding='utf-8')
        index.append(f"| {slug} | {len(rows)} | {sum(1 for x in rows if 'NEW' in x[8])} | "
                     f"{sum(1 for x in rows if 'CHANGED' in x[8])} | {'yes' if info.get('dungeon') else ''} |")
    (outdir / '_index.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    print('\n'.join(index))


if __name__ == '__main__':
    main()
