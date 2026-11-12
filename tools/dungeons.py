"""Weave optional dungeon runs into a built route (used by build_route.py).

The .route files stay quest-only. Each dungeon is described once in routes/dungeons/*.dungeon and is
placed into every route automatically, where that route already goes:

  - the run itself is offered at the end of the first visit to one of the dungeon's hubs while the
    route's estimated level is inside the dungeon's window;
  - each quest pick-up before the run goes to the last time the route passes that quest giver;
  - each hand-in after the run goes to the first time the route passes that NPC again.

Steps made here carry dg=<dungeon number>, so the addon can leave them out (the no-dungeon route).

Dungeon file format ('#' starts a comment line):
  @dungeon <name>
  @levels <lo>-<hi>                 the game's level range for the dungeon (say where it is from)
  @window <lo>-<hi>                 estimated route level at which the run may be offered
  @best <level>                     the hub visit closest to this estimated level gets the run (default: window low)
  @hub <Zone>, <x>, <y>[, <radius>] a place the route visits from which you go to the dungeon (repeatable)
  @entrance <Zone>, <x>, <y>        where the arrow points for the run step ("@entrance none": no arrow)
  A <qid> @ <Zone>, <x>, <y> | text         pick up before the run
  T <qid> @ <Zone>, <x>, <y> | text         hand in (before RUN: part of a lead-in chain; after RUN: reward)
  >A / >T ...                               must come after the previous line (chains); the addon also hides
                                            the step until the previous line's quest is taken / handed in
  RUN | text                                the run step; text = how to get in and what to do inside
A <qid> +<qid>[,<qid>] @ ... also needs those quests handed in first (for new Forever quests whose
prerequisites are not in the Questie data).
Add "[route-key]" right after A/T to keep a line for one route only, e.g. "A[orc-shaman] 1049 @ ...".
"""
import re
from pathlib import Path

CITIES = {'Orgrimmar', 'Undercity', 'Thunder Bluff', 'Ironforge', 'Stormwind City', 'Darnassus'}
DEFAULT_RADIUS = 10.0


class Dungeon:
    def __init__(self, path):
        self.path = Path(path)
        self.name, self.levels, self.window, self.best = None, None, None, None
        self.hubs, self.entrance = [], None
        self.items = []  # dicts: kind A/T/RUN, qid, loc, text, chain, only, line


def parse_loc(txt):
    m = re.fullmatch(r'\s*([^,]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\s*', txt)
    if not m:
        return None
    return (m.group(1).strip(), float(m.group(2)), float(m.group(3)), float(m.group(4)) if m.group(4) else None)


def parse_dungeon(path):
    d, errors = Dungeon(path), []
    for n, raw in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        where = f"{Path(path).name}:{n}"
        if not line or line.startswith('#'):
            continue
        text = ''
        if '|' in line:
            line, text = [p.strip() for p in line.split('|', 1)]
        if line.startswith('@'):
            key, _, val = line.partition(' ')
            val = val.strip()
            if key == '@dungeon':
                d.name = val
            elif key == '@best':
                d.best = int(val)
            elif key in ('@levels', '@window'):
                m = re.fullmatch(r'(\d+)-(\d+)', val)
                if not m:
                    errors.append(f"{where}: {key} needs lo-hi")
                    continue
                setattr(d, key[1:], (int(m.group(1)), int(m.group(2))))
            elif key == '@hub':
                loc = parse_loc(val)
                if loc:
                    d.hubs.append(loc)
                else:
                    errors.append(f"{where}: @hub needs 'Zone, x, y[, radius]'")
            elif key == '@entrance':
                loc = parse_loc(val)
                if val.lower() == 'none':
                    d.entrance = 'none'
                elif loc:
                    d.entrance = loc[:3]
                else:
                    errors.append(f"{where}: @entrance needs 'Zone, x, y'")
            else:
                errors.append(f"{where}: unknown header {key}")
            continue
        if line.upper().startswith('RUN'):
            d.items.append({'kind': 'RUN', 'text': text, 'line': where})
            continue
        m = re.fullmatch(r'(>?)\s*([AT])(?:\[([\w-]+)\])?\s+(\d+)\s*(?:\+([\d,]+))?\s*@\s*(.+)', line)
        if not m:
            errors.append(f"{where}: expected 'A|T <quest id> @ Zone, x, y'")
            continue
        loc = parse_loc(m.group(6))
        if not loc:
            errors.append(f"{where}: bad location")
            continue
        d.items.append({'kind': m.group(2), 'qid': m.group(4), 'loc': loc[:3], 'text': text,
                        'chain': bool(m.group(1)), 'only': m.group(3), 'line': where,
                        'after': m.group(5).split(',') if m.group(5) else []})
    for field in ('name', 'levels', 'window', 'entrance'):
        if not getattr(d, field):
            errors.append(f"{Path(path).name}: missing @{field}")
    if d.window and d.best is None:
        d.best = d.window[0]
    if not d.hubs:
        errors.append(f"{Path(path).name}: needs at least one @hub")
    if sum(1 for it in d.items if it['kind'] == 'RUN') != 1:
        errors.append(f"{Path(path).name}: needs exactly one RUN line")
    return d, errors


def load_dungeons(folder):
    out, errors = [], []
    for f in sorted(Path(folder).glob('*.dungeon')):
        d, errs = parse_dungeon(f)
        errors += errs
        if not errs:
            out.append(d)
    return out, errors


def weave(steps, D, profile, dungeons, B):
    """steps: base route steps (no @headers), each with .loc and .lv (estimated level).
    Returns (steps with dungeon steps inserted, report lines, dungeon table for the Lua file, error count)."""
    report, n_err = [], 0

    def zone_of(s):
        if not s.loc:
            return None
        aid = s.loc[0]
        return B.UIMAP_NAMES.get(D.area_to_uimap.get(aid), s.loc[1]) if aid is not None else s.loc[1]

    zones = [zone_of(s) for s in steps]

    def dist(i, loc):
        s = steps[i]
        return ((s.loc[2] - loc[1]) ** 2 + (s.loc[3] - loc[2]) ** 2) ** 0.5

    def near(i, loc, radius=None):
        if zones[i] != loc[0]:
            return False
        if loc[0] in CITIES and radius is None:
            return True
        return dist(i, loc) <= (radius or DEFAULT_RADIUS)

    def visits(loc, radius=None):
        """Lists of step indexes: each list is one stay near loc (steps without a position do not end a stay)."""
        out, cur = [], None
        for i in range(len(steps)):
            if zones[i] is None:
                continue
            if near(i, loc, radius):
                if cur is None:
                    cur = []
                    out.append(cur)
                cur.append(i)
            else:
                cur = None
        return out

    base_turnin = {}
    for i, s in enumerate(steps):
        if s.kind == 'T':
            for qid, _ in s.args:
                base_turnin.setdefault(qid, i)

    inserts = {}  # base index -> [Step,...] placed after that step
    table = []
    dg_handed = set()  # quests handed in by earlier dungeons' steps
    for d in dungeons:
        dg = len(table) + 1
        head = f"{d.name} ({d.levels[0]}-{d.levels[1]})"
        # 1. where the run goes: end of the first hub visit inside the level window
        # (the hub visit whose level is closest to @best; ties go to the hub listed first, then the later visit)
        anchor, score = None, None
        for h, hub in enumerate(d.hubs):
            for v in visits(hub[:3], hub[3]):
                end = v[-1]
                if d.window[0] <= steps[end].lv <= d.window[1]:
                    sc = (abs(steps[end].lv - d.best), h, -end)
                    if score is None or sc < score:
                        anchor, score = end, sc
        if anchor is None:
            report.append(f"DUNGEON ERROR {head}: the route never visits a hub at level {d.window[0]}-{d.window[1]}; not added")
            n_err += 1
            continue
        table.append({'name': d.name, 'levels': f"{d.levels[0]}-{d.levels[1]}"})
        run_at = next(i for i, it in enumerate(d.items) if it['kind'] == 'RUN')
        placed = {}   # item index -> base index
        dropped = {}  # item index -> reason
        taken = set()  # quests picked up by this dungeon's steps
        handed = {}   # quest -> item index of its T line

        def usable(k, it):
            qid = it['qid']
            if it['only'] and it['only'] != profile['key']:
                return 'other route'
            if not D.exists(qid):
                return 'quest not in Questie or ForeverChanges data'
            q, row = D.quests.get(qid, {}), D.fc_rows.get(qid, {})
            races, classes = q.get('requiredRaces'), q.get('requiredClasses')
            if races and not (races & profile['race_bit']):
                return f"not for {profile['race']}"
            if classes and not (classes & profile['class_bit']):
                return f"not for {profile['class']}s"
            if row and row.get('sides') and profile['side'] not in row['sides']:
                return 'other faction only'
            return None

        # 2. lines before RUN, last to first, so chains keep their order
        upper = anchor
        for k in range(run_at - 1, -1, -1):
            it = d.items[k]
            why = usable(k, it)
            nxt = d.items[k + 1] if k + 1 < run_at else None
            bound = placed.get(k + 1, anchor) if (nxt and nxt['chain']) else anchor
            if nxt and nxt['chain'] and (k + 1) in dropped:
                bound = anchor
            if why is None:
                req = D.fc_rows.get(it['qid'], {}).get('reqLevel') or D.quests.get(it['qid'], {}).get('requiredLevel') or 1
                best = None
                first = 0
                if it['kind'] == 'A':
                    q = D.quests.get(it['qid'], {})
                    one = [base_turnin[str(p)] for p in (q.get('preQuestSingle') or []) if str(p) in base_turnin]
                    every = [base_turnin[str(p)] for p in list(q.get('preQuestGroup') or []) + it['after'] if str(p) in base_turnin]
                    first = max([min(one)] if one else [0]) if not every else max(every + ([min(one)] if one else []))
                for v in visits(it['loc']):
                    ok = [i for i in v if first <= i <= bound and (it['kind'] == 'T' or steps[i].lv >= req - 1)]
                    if ok:
                        best = min(ok, key=lambda i: (round(dist(i, it['loc']), 1), -i))
                if best is None:
                    why = 'giver is not on the route before the run'
                else:
                    placed[k] = best
            if why:
                dropped[k] = why
        # a chained line whose earlier link was dropped cannot be done either
        for k in range(run_at):
            it = d.items[k]
            if k in placed and it['chain'] and (k - 1) in dropped:
                dropped[k] = 'needs the previous step'
                del placed[k]
        for k in range(run_at - 1):
            it, nxt = d.items[k], d.items[k + 1]
            if k in placed and it['kind'] == 'A' and nxt['chain'] and nxt['kind'] == 'T' and nxt['qid'] == it['qid']                     and (k + 1) in dropped:
                dropped[k] = 'its hand-in is not on the route before the run'
                del placed[k]
        # prerequisites from the quest data: must be handed in by the base route (or by this dungeon) earlier
        for k in range(run_at):
            it = d.items[k]
            if k not in placed:
                continue
            if it['kind'] == 'A':
                q = D.quests.get(it['qid'], {})
                singles = [str(p) for p in (q.get('preQuestSingle') or [])]
                group = [str(p) for p in (q.get('preQuestGroup') or [])] + it['after']
                it['need'] = next((p for p in singles + group if p in dg_handed and p not in base_turnin), None)

                def have(p):
                    return (p in base_turnin and base_turnin[p] <= placed[k]) or p in handed or p in dg_handed
                if (singles and not any(have(p) for p in singles)) or any(not have(p) for p in group):
                    dropped[k] = f"needs quest {'/'.join(singles + group)} first, which the route does not do before this point"
                    del placed[k]
                    continue
                taken.add(it['qid'])
            else:
                if it['qid'] not in taken:
                    dropped[k] = 'its pick-up was left out'
                    del placed[k]
                    continue
                handed[it['qid']] = k
        # 3. lines after RUN, first to last
        lower = anchor
        for k in range(run_at + 1, len(d.items)):
            it = d.items[k]
            why = usable(k, it)
            prev = k - 1
            bound = anchor
            if it['chain']:
                if prev in dropped:
                    why = why or 'needs the previous step'
                else:
                    bound = placed.get(prev, anchor)
            if why is None and it['kind'] == 'A' and not it['chain']:
                why = 'a pick-up after the run must be chained (>) to the hand-in before it'
            if why is None:
                best = None
                for v in visits(it['loc']):
                    ok = [i for i in v if i >= bound]
                    if ok:
                        best = min(ok, key=lambda i: (round(dist(i, it['loc']), 1), i))
                        break
                if best is None:
                    why = 'the route does not pass this NPC after the run'
                else:
                    placed[k] = best
            if why:
                dropped[k] = why
        # 4. make the steps
        names = lambda k: D.quest_name(d.items[k]['qid']) or f"Quest {d.items[k]['qid']}"  # noqa: E731
        carry = [names(k) for k in range(run_at) if k in placed and d.items[k]['kind'] == 'A'
                 and d.items[k]['qid'] not in handed]
        off_path = [f"{names(k)} ({d.items[k]['loc'][0]} {d.items[k]['loc'][1]:.0f}, {d.items[k]['loc'][2]:.0f})"
                    for k in range(run_at) if k in dropped and d.items[k]['kind'] == 'A'
                    and dropped[k].startswith('giver is not')
                    and not (k + 1 < run_at and d.items[k + 1]['chain'] and d.items[k + 1]['kind'] == 'T')]
        chain_missing = [names(k) for k in range(run_at) if k in dropped and d.items[k]['kind'] == 'A'
                         and dropped[k].startswith('needs quest')]
        later = [f"{names(k)} ({d.items[k]['loc'][0]})" for k in range(run_at + 1, len(d.items))
                 if k in dropped and d.items[k]['kind'] == 'T' and dropped[k].startswith('the route does not pass')
                 and (d.items[k]['qid'] in taken or not any(o['kind'] == 'A' and o['qid'] == d.items[k]['qid'] for o in d.items))]
        parts = [d.items[run_at]['text']]
        if carry:
            parts.append('Quests you picked up for it: ' + ', '.join(carry) + '.')
        if off_path:
            parts.append('Not on your path, only if you want the detour: ' + '; '.join(off_path) + '.')
        if chain_missing:
            parts.append('Needs an earlier quest chain this route does not do: ' + ', '.join(chain_missing) + '.')
        if later:
            parts.append('The route does not come back to these hand-ins, go when it suits you: ' + '; '.join(later) + '.')
        run = B.Step('N', [f"Optional dungeon: {d.name}, levels {d.levels[0]}-{d.levels[1]}"], ' '.join(p for p in parts if p),
                     steps[anchor].seg, d.items[run_at]['line'])
        if d.entrance != 'none':
            aid = D.name_to_area.get(d.entrance[0].lower())
            run.loc = (aid, d.entrance[0], d.entrance[1], d.entrance[2])
        run.dg, run.run, run.req = dg, True, None

        def make(k):
            it = d.items[k]
            s = B.Step(it['kind'], [(it['qid'], None)], it['text'], steps[placed[k]].seg, it['line'])
            s.loc = (D.name_to_area.get(it['loc'][0].lower()), it['loc'][0], it['loc'][1], it['loc'][2])
            s.dg, s.run, s.req = dg, False, None
            if it['chain'] and (k - 1) in placed:
                s.req = d.items[k - 1]['qid']
            elif it.get('need'):
                s.req = it['need']  # only offered after another dungeon's quest
            return s

        for k in range(run_at):
            if k in placed:
                inserts.setdefault(placed[k], []).append((dg, 0, k, make(k)))
        inserts.setdefault(anchor, []).append((dg, 1, run_at, run))
        for k in range(run_at + 1, len(d.items)):
            if k in placed:
                inserts.setdefault(placed[k], []).append((dg, 2, k, make(k)))
        # 5. report
        report.append(f"DUNGEON {head}: run offered after {steps[anchor].line} (route level about {steps[anchor].lv}), in \"{steps[anchor].seg}\"")
        xp = 0
        for k, it in enumerate(d.items):
            if it['kind'] == 'RUN':
                continue
            label = f"{it['kind']} {it['qid']} {names(k)}"
            if k in placed:
                s = steps[placed[k]]
                report.append(f"    {label}: after {s.line} (level about {s.lv})")
                has_pickup = [j for j, o in enumerate(d.items) if o['kind'] == 'A' and o['qid'] == it['qid']]
                if it['kind'] == 'T' and (not has_pickup or any(j in placed for j in has_pickup)):
                    xp += D.fc_rows.get(it['qid'], {}).get('xp') or 0
            elif dropped.get(k) != 'other route':
                report.append(f"    {label}: LEFT OUT - {dropped[k]}")
        report.append(f"    quest experience on the route for this run: {xp}")
        dg_handed |= {d.items[k]['qid'] for k in placed if d.items[k]['kind'] == 'T'}
        table[-1]['xp'] = xp
        table[-1]['at'] = steps[anchor].lv
    # merge
    out = []
    for i, s in enumerate(steps):
        out.append(s)
        for _, _, _, extra in sorted(inserts.get(i, []), key=lambda t: t[:3]):
            out.append(extra)
    return out, report, table, n_err
