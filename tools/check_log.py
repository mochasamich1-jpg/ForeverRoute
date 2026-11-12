"""Compare the in-game quest log (ForeverRouteLog SavedVariables) with a route.

Usage:
  python -I tools/check_log.py --route undead-mage [--class MAGE] [--since "11-08 11:00"]

Reports, for the character class that plays the route:
  * order: route A/T steps that happened in a different order than the route lists them
  * coords: accept / turn-in positions that differ from the route's coordinates
  * offroute: quests taken that the route does not list, and route quests that were passed by
  * levels: real level at each turn-in against the builder's estimate, and real quest XP against the model
  * slow: the longest gaps between two consecutive route events (where time was really spent)
  * skips and /fr note entries
It also saves what it saw to research/observed.json (--no-save to skip), which build_route.py uses.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_route as B
from luadata import tokenize, Parser

SV = Path(r'C:/Program Files (x86)/World of Warcraft/_forever_/WTF/Account')


def load_events():
    files = sorted(SV.glob('*/SavedVariables/ForeverRoute.lua'), key=lambda p: p.stat().st_mtime)
    text = files[-1].read_text(encoding='utf-8', errors='replace')
    body = text[text.index('{'):]
    p = Parser(tokenize(body))
    p.take()
    events = p.table()['events']
    cls = race = None
    for e in events:  # every event belongs to the character of the login before it
        if e['e'] == 'login':
            cls, race = e.get('class'), e.get('race')
        e['cls'], e['race'] = cls, race
    return events


def save_observed(events, D):
    """research/observed.json: real giver / turn-in positions and quest XP, from every character's events.
    build_route.py prefers these over Questie / ForeverChanges data (a manual '@ Zone, x, y' still wins)."""
    path = B.RES / 'observed.json'
    out = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for e in events:
        if e['e'] not in ('accept', 'turnin') or not e.get('q'):
            continue
        q = str(e['q'])
        rec = out.setdefault(q, {})
        zone = B.UIMAP_NAMES.get(e.get('map'))
        # only when a quest NPC / object was open: item-started quests are "accepted" wherever the item dropped
        if zone and e.get('npc') and e.get('x') is not None:
            rec['A' if e['e'] == 'accept' else 'T'] = {'zone': zone, 'x': e['x'], 'y': e['y'], 'npc': e['npc']}
        if e['e'] == 'turnin' and e.get('xpGain'):
            qlevel = (D.fc_rows.get(q) or {}).get('level') or D.quests.get(q, {}).get('questLevel')
            if qlevel and (e.get('lvl') or 0) - qlevel <= 5:   # not grey, so this is the full reward
                rec['xp'], rec['xpLevel'] = e['xpGain'], e.get('lvl')
        if not rec:
            del out[q]
    path.write_text(json.dumps(out, indent=1, sort_keys=True), encoding='utf-8')
    return len(out)


def stamp(e):
    return time.strftime('%m-%d %H:%M', time.localtime(e.get('time', 0)))


def main():
    args = sys.argv[1:]
    key = args[args.index('--route') + 1] if '--route' in args else 'undead-mage'
    B.use_profile(key)
    cls = args[args.index('--class') + 1] if '--class' in args else B.PROFILE['classes'][0]
    since = args[args.index('--since') + 1] if '--since' in args else ''
    D = B.Data()
    files = sorted((B.ROOT / 'routes' / key).glob('*.route'))
    steps, segments, _ = B.parse_routes(files)
    B.resolve_locations(steps, D)
    sys.stdout.reconfigure(encoding='utf-8')

    # simulated level at each T step (same model as the validator)
    est_level = {}
    level, xp = 1, 0
    for s in steps:
        if s.kind == 'T':
            for qid, _ in s.args:
                est_level[qid] = level
                xp += B.quest_xp(qid, D, level) * B.KILL_FACTOR
                while level < 60 and xp >= B.XP_TO_LEVEL[level]:
                    xp -= B.XP_TO_LEVEL[level]
                    level += 1
        elif s.kind == 'L' and s.args[0] > level:
            level, xp = s.args[0], 0

    route_pos = {}   # ('A'|'T', qid) -> (order, step)
    order = 0
    for s in steps:
        if s.kind in ('A', 'T'):
            for qid, _ in s.args:
                order += 1
                route_pos.setdefault((s.kind, qid), (order, s))
    route_quests = {q for (_, q) in route_pos}

    every = load_events()
    if '--no-save' not in args:
        print(f"observed.json: {save_observed(every, D)} quests with real positions / XP (rebuild the routes to use them)")
    # two routes can share a class (Orc and Dwarf Shaman): the race in the login event tells them apart
    mine = [e for e in every if e.get('cls') == cls and (not e.get('race') or e['race'] in B.PROFILE['races'])]
    ev = [e for e in mine if stamp(e) >= since]
    if not ev:
        print('no events for class', cls)
        return
    print(f"== {key}: {len(ev)} events for {cls}, {stamp(ev[0])} .. {stamp(ev[-1])}, level {ev[-1].get('lvl')}")

    qev = [e for e in ev if e['e'] in ('accept', 'turnin')]
    seen = []
    print('\n-- order: done later than something that comes after it in the route (A/T, 6+ quest-steps apart)')
    hi = (0, None, None)
    for e in qev:
        k = ('A' if e['e'] == 'accept' else 'T', str(e['q']))
        if k not in route_pos:
            continue
        o, s = route_pos[k]
        seen.append((o, e, s))
        if o > hi[0]:
            hi = (o, s, e)
        elif hi[0] - o >= 6:
            print(f"  {stamp(e)} L{e.get('lvl')} {k[0]} {k[1]} {D.quest_name(k[1])} ({s.line}) came {hi[0] - o} quest-steps "
                  f"after {hi[1].line}")

    print('\n-- coords: where it really happened vs the route (> 1.5 map units, or another zone)')
    for o, e, s in seen:
        name = D.quest_name(str(e['q']))
        if e.get('x') is None:
            continue
        if not s.loc:
            print(f"  {s.line} {s.kind} {e['q']} {name}: route has no coords; real {e.get('zone')} {e['x']}, {e['y']} ({e.get('npc')})")
            continue
        aid, zname, x, y = s.loc
        zname = B.UIMAP_NAMES.get(D.area_to_uimap.get(aid), zname)
        d = ((x - e['x']) ** 2 + (y - e['y']) ** 2) ** 0.5
        if zname != e.get('zone') or d > 1.5:
            print(f"  {s.line} {s.kind} {e['q']} {name}: route {zname} {x}, {y}; real {e.get('zone')} {e['x']}, {e['y']} ({e.get('npc')})")

    print('\n-- offroute quests taken')
    for e in qev:
        if str(e['q']) not in route_quests:
            print(f"  {stamp(e)} L{e.get('lvl')} {e['e']} {e['q']} {e.get('name') or D.quest_name(str(e['q'])) or ''} at {e.get('zone')} "
                  f"{e.get('x')}, {e.get('y')} ({e.get('npc')}) xp={e.get('xpGain')}")

    print('\n-- route quests passed by (accept step is before the furthest point reached, never accepted)')
    got = {str(e['q']) for e in mine if e['e'] == 'accept'}
    for (kind, qid), (o, s) in sorted(route_pos.items(), key=lambda kv: kv[1][0]):
        if kind == 'A' and o < hi[0] and qid not in got:
            print(f"  {s.line} A {qid} {D.quest_name(qid)}")

    print('\n-- levels: real level at turn-in vs estimate (printed when the gap changes), and XP model errors')
    tot_real = tot_model = 0
    last = 0
    for e in qev:
        if e['e'] != 'turnin':
            continue
        q = str(e['q'])
        if q not in est_level:
            continue
        if e.get('xpGain') is not None:
            model = B.quest_xp(q, D, e.get('lvl') or 1)
            tot_real += e['xpGain']
            tot_model += model
            if abs(e['xpGain'] - model) > max(60, 0.15 * model):
                print(f"  xp {q} {D.quest_name(q)}: real {e['xpGain']} vs model {model} at L{e.get('lvl')}")
        diff = (e.get('lvl') or 0) - est_level[q]
        if diff != last:
            print(f"  {stamp(e)} {route_pos[('T', q)][1].line} T {q}: real L{e.get('lvl')} vs estimated L{est_level[q]}")
        last = diff
    if tot_model:
        print(f"  quest XP total: real {tot_real} vs model {tot_model} ({tot_real / tot_model:.2f}x)")

    print('\n-- slow: longest gaps between consecutive events in one session')
    gaps = []
    for a, b in zip(ev, ev[1:]):
        if 'login' in (a['e'], b['e']) or 'objective' in (a['e'], b['e']):
            continue
        gaps.append((b['time'] - a['time'], a, b))

    def d(e):
        return f"{e['e']} {e.get('q') or e.get('step') or ''} {e.get('name') or D.quest_name(str(e.get('q'))) or ''}".strip()
    for g, a, b in sorted(gaps, key=lambda t: -t[0])[:12]:
        print(f"  {g // 60:4d} min  {stamp(a)} {d(a)}  ->  {d(b)}  ({b.get('zone')})")

    print('\n-- skips, notes, abandons')
    for e in ev:
        if e['e'] in ('skip', 'note', 'abandon'):
            print(f"  {stamp(e)} L{e.get('lvl')} {e['e']} {e.get('text') or e.get('key') or e.get('q')}")

    print('\n-- quest log size')
    log, mx = set(), 0
    for e in mine:
        if e['e'] == 'accept':
            log.add(e['q'])
        elif e['e'] in ('turnin', 'abandon'):
            log.discard(e['q'])
        mx = max(mx, len(log))
    limits = [e.get('maxQuests') for e in ev if e['e'] == 'login' and e.get('maxQuests')]
    print(f"  most quests held at once: {mx}; the client reports a limit of {limits[-1] if limits else '?'}")
    print(f"  in the log now ({len(log)}): " + ', '.join(f"{q} {D.quest_name(str(q))}" for q in sorted(log)))


if __name__ == '__main__':
    main()
