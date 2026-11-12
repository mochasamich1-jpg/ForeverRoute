"""Compile ForeverRoute .route files into addon Lua data, resolve coordinates and validate.

Usage:
  python -I build_route.py --route orc-shaman   # build + validate routes/orc-shaman/*.route
                                                # -> addon/ForeverRoute/Routes/<Name>.lua
  python -I build_route.py --route all          # every route profile
  python -I build_route.py --check-only         # validate only, print report
  python -I build_route.py --no-dungeons        # leave out the optional dungeon steps (routes/dungeons/*.dungeon)
  python -I build_route.py --report FILE        # also write the report to FILE
  python -I build_route.py --route orc-shaman --only routes/orc-shaman/01-x.route   # one segment
(--route defaults to undead-mage)

Route DSL (one step per line, '#' starts a comment line):
  @segment <title>               start a new segment (e.g. "@segment 6-10 Tirisfal Glades")
  A <qid>[,<qid>...]             accept quest(s)
  C <qid>[:<obj>][,<qid>...]     complete quest objectives (optional objective index, 1-based)
  T <qid>[,<qid>...]             turn in quest(s)
  G <Zone Name>, <x>, <y>        go to a spot (auto-ticks when you arrive)
  L <level>                      grind until this level (auto)
  S <Inn/Town>                   set hearthstone here (auto when bound)
  H <Town>                       use hearthstone (manual tick)
  F <Flight point>               get the flight path (manual tick)
  FLY <Flight point>             fly to (manual tick)
  TRAIN                          visit your class trainer (manual tick)
  N <text>                       note / misc action (manual tick)
Any line may end with "| text" to add instructions, and A/T/C lines may add
"@ <Zone Name>, <x>, <y>" before the "|" to override coordinates.
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / 'research'
ADDONS = Path(r'C:/Program Files (x86)/World of Warcraft/_forever_/Interface/AddOns')

UNDEAD_RACE_BIT = 16
MAGE_CLASS_BIT = 128
# Route profiles: one folder of .route files per race/class, one generated Lua file each.
PROFILES = {
    'undead-mage': {'title': 'Undead Mage', 'race': 'Undead', 'class': 'Mage', 'race_bit': 16, 'class_bit': 128,
                    'races': ['Scourge'], 'classes': ['MAGE'], 'lua': 'UndeadMage'},
    'orc-shaman': {'title': 'Orc Shaman', 'race': 'Orc', 'class': 'Shaman', 'race_bit': 2, 'class_bit': 64,
                   'races': ['Orc', 'Troll'], 'classes': ['SHAMAN'], 'lua': 'OrcShaman'},
    # Alliance. Dwarf Shaman is a new combination in Forever (foreverchanges.pro/racials).
    'dwarf-shaman': {'title': 'Dwarf Shaman', 'race': 'Dwarf', 'class': 'Shaman', 'race_bit': 4, 'class_bit': 64,
                     'races': ['Dwarf'], 'classes': ['SHAMAN'], 'lua': 'DwarfShaman', 'side': 'Alliance',
                     'dungeons': 'dungeons-alliance'},
    # Skyborne is the new Forever race (Zephras Isle, 1-12). The Alliance side is the "High Order Skyborne",
    # race bit 2^32 in Questie; it can be a Druid (foreverchanges.pro/racials). The in-game race token
    # (UnitRace) is not known yet, so the addon picks this route by class (the only Druid route).
    'skyborne-druid': {'title': 'Skyborne Druid', 'race': 'Skyborne', 'class': 'Druid', 'race_bit': 4294967296,
                       'class_bit': 1024, 'races': ['Skyborne', 'HighOrderSkyborne'], 'classes': ['DRUID'],
                       'lua': 'SkyborneDruid', 'side': 'Alliance', 'dungeons': 'dungeons-alliance'},
    'skyborne-mage': {'title': 'Skyborne Mage', 'race': 'Skyborne', 'class': 'Mage', 'race_bit': 4294967296,
                      'class_bit': 128, 'races': ['Skyborne', 'HighOrderSkyborne'], 'classes': ['MAGE'],
                      'lua': 'SkyborneMage', 'side': 'Alliance', 'dungeons': 'dungeons-alliance'},
    # Human Mage: Northshire / Elwynn start, then the shared Alliance path of the Skyborne Mage route.
    'human-mage': {'title': 'Human Mage', 'race': 'Human', 'class': 'Mage', 'race_bit': 1, 'class_bit': 128,
                   'races': ['Human'], 'classes': ['MAGE'], 'lua': 'HumanMage', 'side': 'Alliance',
                   'dungeons': 'dungeons-alliance'},
    # Gnome, any class: the Dwarf Shaman path (same start, Coldridge Valley) with every class-specific part removed.
    # class_bit 0 makes any class-restricted quest a validation error; an empty 'classes' list means any class.
    'gnome': {'title': 'Gnome (any class)', 'race': 'Gnome', 'class': 'any class', 'race_bit': 64, 'class_bit': 0,
              'races': ['Gnome'], 'classes': [], 'lua': 'Gnome',
              'side': 'Alliance', 'dungeons': 'dungeons-alliance'},
    # Human Warlock: the Human Mage start (Northshire / Elwynn) and the class-neutral Gnome path from 14 on, with the
    # warlock's own quests (imp, Voidwalker, Felsteed) and warlock fight hints.
    'human-warlock': {'title': 'Human Warlock', 'race': 'Human', 'class': 'Warlock', 'race_bit': 1, 'class_bit': 256,
                      'races': ['Human'], 'classes': ['WARLOCK'], 'lua': 'HumanWarlock', 'side': 'Alliance',
                      'dungeons': 'dungeons-alliance'},
    # Any-class routes for the other Alliance races: their own start zone (segments 01-04; the Dwarf shares the
    # Gnome's 01-03), then the Gnome path from level 14 with the race's mount (tools/derive_anyclass.py).
    'dwarf': {'title': 'Dwarf (any class)', 'race': 'Dwarf', 'class': 'any class', 'race_bit': 4, 'class_bit': 0,
              'races': ['Dwarf'], 'classes': [], 'lua': 'Dwarf', 'side': 'Alliance', 'dungeons': 'dungeons-alliance'},
    'human': {'title': 'Human (any class)', 'race': 'Human', 'class': 'any class', 'race_bit': 1, 'class_bit': 0,
              'races': ['Human'], 'classes': [], 'lua': 'Human', 'side': 'Alliance', 'dungeons': 'dungeons-alliance'},
    'night-elf': {'title': 'Night Elf (any class)', 'race': 'Night Elf', 'class': 'any class', 'race_bit': 8,
                  'class_bit': 0, 'races': ['NightElf'], 'classes': [], 'lua': 'NightElf', 'side': 'Alliance',
                  'dungeons': 'dungeons-alliance'},
    'skyborne': {'title': 'Skyborne (any class)', 'race': 'Skyborne', 'class': 'any class', 'race_bit': 4294967296,
                 'class_bit': 0, 'races': ['Skyborne', 'HighOrderSkyborne'], 'classes': [], 'lua': 'Skyborne',
                 'side': 'Alliance', 'dungeons': 'dungeons-alliance'},
}
for _p in PROFILES.values():
    _p.setdefault('side', 'Horde')
    _p.setdefault('dungeons', 'dungeons')
PROFILE = dict(PROFILES['undead-mage'], key='undead-mage')  # set by use_profile()


def use_profile(key):
    global PROFILE
    PROFILE = dict(PROFILES[key], key=key)
    return PROFILE


# Classic uiMapIDs -> zone names (Questie's area names are sometimes odd, e.g. "Scenarios")
UIMAP_NAMES = {1411: 'Durotar', 1412: 'Mulgore', 1413: 'The Barrens', 1416: 'Alterac Mountains',
               1417: 'Arathi Highlands', 1418: 'Badlands', 1419: 'Blasted Lands', 1420: 'Tirisfal Glades',
               1421: 'Silverpine Forest', 1422: 'Western Plaguelands', 1423: 'Eastern Plaguelands',
               1424: 'Hillsbrad Foothills', 1425: 'The Hinterlands', 1426: 'Dun Morogh', 1427: 'Searing Gorge',
               1428: 'Burning Steppes', 1429: 'Elwynn Forest', 1430: 'Deadwind Pass', 1431: 'Duskwood',
               1432: 'Loch Modan', 1433: 'Redridge Mountains', 1434: 'Stranglethorn Vale',
               1435: 'Swamp of Sorrows', 1436: 'Westfall', 1437: 'Wetlands', 1438: 'Teldrassil',
               1439: 'Darkshore', 1440: 'Ashenvale', 1441: 'Thousand Needles', 1442: 'Stonetalon Mountains',
               1443: 'Desolace', 1444: 'Feralas', 1445: 'Dustwallow Marsh', 1446: 'Tanaris', 1447: 'Azshara',
               1448: 'Felwood', 1449: "Un'Goro Crater", 1450: 'Moonglade', 1451: 'Silithus',
               1452: 'Winterspring', 1453: 'Stormwind City', 1454: 'Orgrimmar', 1455: 'Ironforge',
               1456: 'Thunder Bluff', 1457: 'Darnassus', 1458: 'Undercity',
               # new Forever zone: the Skyborne starting island (Questie's name table files it under a wrong id)
               2521: 'Zephras Isle'}
def zone_label(D, aid):
    """Readable zone name for an area id (uiMap name when known)."""
    if aid is None:
        return '?'
    return UIMAP_NAMES.get(D.area_to_uimap.get(int(aid)), D.area_names.get(int(aid), str(aid)))


HORDE_RACES = 2 | 16 | 32 | 128  # orc, undead, tauren, troll (classic bits)
QUEST_LOG_LIMIT = 40  # the 1.60.1 client reports 40 (C_QuestLog.GetMaxNumQuestsCanAccept); 23 held at once in play

# Classic XP needed to go from level L to L+1
XP_TO_LEVEL = {1: 400, 2: 900, 3: 1400, 4: 2100, 5: 2800, 6: 3600, 7: 4500, 8: 5400, 9: 6500, 10: 7600,
               11: 8800, 12: 10100, 13: 11400, 14: 12900, 15: 14400, 16: 16000, 17: 17700, 18: 19400,
               19: 21300, 20: 23200, 21: 25200, 22: 27300, 23: 29400, 24: 31700, 25: 34000, 26: 36400,
               27: 38900, 28: 41400, 29: 44300, 30: 47400, 31: 50800, 32: 54500, 33: 58600, 34: 62800,
               35: 67100, 36: 71600, 37: 76100, 38: 80800, 39: 85700, 40: 90700, 41: 95800, 42: 101000,
               43: 106300, 44: 111800, 45: 117500, 46: 123200, 47: 129100, 48: 135100, 49: 141200,
               50: 147500, 51: 153900, 52: 160400, 53: 167100, 54: 173900, 55: 180800, 56: 187900,
               57: 195000, 58: 202300, 59: 209800}


def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


class Data:
    def __init__(self):
        j = RES / 'json'
        self.quests = load_json(j / 'quests.json')
        self.npcs = load_json(j / 'npcs.json')
        self.objects = load_json(j / 'objects.json')
        self.items = load_json(j / 'items.json')
        self.fc_zones = load_json(RES / 'fc' / 'zones.json') if (RES / 'fc' / 'zones.json').exists() else {}
        self.fc = {}
        qdir = RES / 'fc' / 'quests'
        if qdir.exists():
            for f in qdir.glob('*.json'):
                rec = load_json(f)
                self.fc[str(rec['id'])] = rec
        self.fc_rows = {}
        self.dungeon_quests = set()
        for z, info in self.fc_zones.items():
            for r in info['quests']:
                self.fc_rows.setdefault(str(r['id']), dict(r, zoneSlug=z))
                if info.get('dungeon'):
                    self.dungeon_quests.add(str(r['id']))
        self.xpdb = self._load_xp()
        # What the in-game logger saw (tools/check_log.py writes it): real NPC positions and quest XP
        obs = RES / 'observed.json'
        self.observed = load_json(obs) if obs.exists() else {}
        self.area_names, self.name_to_area = self._load_zone_names()
        self.area_to_uimap = self._load_uimap()
        # Questie's name table mislabels some zone ids ("Pet Battle" for Durotar, "Scenarios" for Dustwallow
        # Marsh...), so those zone names led to no area id and steps with a hand-written "@ Zone, x, y" lost
        # their map id (and with it their walking paths). Point every map's name at its zone id: of the
        # area ids on that map, the one the NPC spawn data uses as its zone key.
        used = {}
        for e in self.npcs.values():
            for z in (e.get('spawns') or {}):
                used[int(z)] = used.get(int(z), 0) + 1
        for mid, name in UIMAP_NAMES.items():
            if self.area_to_uimap.get(self.name_to_area.get(name.lower())) == mid:
                continue
            cands = [a for a, m in self.area_to_uimap.items() if m == mid]
            if cands:
                self.name_to_area[name.lower()] = max(cands, key=lambda a: (used.get(a, 0), -a))

    def _load_xp(self):
        p = ADDONS / 'QuestieDB' / 'support' / 'Forever' / 'QuestXP' / 'xpDB-classic.lua'
        out = {}
        if p.exists():
            for qid, lvl, xp in re.findall(r'\[(\d+)\]\s*=\s*\{(\d+),\s*(\d+)\}', p.read_text(encoding='utf-8', errors='replace')):
                out[qid] = (int(lvl), int(xp))
        return out

    def _load_zone_names(self):
        p = ADDONS / 'Questie' / 'Localization' / 'lookups' / 'lookupZones.lua'
        names = {}
        if p.exists():
            for aid, name in re.findall(r'\[(\d+)\]\s*=\s*"([^"]+)"', p.read_text(encoding='utf-8', errors='replace')):
                names.setdefault(int(aid), name)
        rev = {}
        for aid, name in names.items():
            rev.setdefault(name.lower(), aid)
        return names, rev

    def _load_uimap(self):
        p = ADDONS / 'QuestieDB' / 'support' / 'Forever' / 'Zones' / 'areaIdToUiMapId.lua'
        out = {}
        if p.exists():
            for aid, mid in re.findall(r'^\s*\[(\d+)\]\s*=\s*(\d+),', p.read_text(encoding='utf-8', errors='replace'), re.M):
                out.setdefault(int(aid), int(mid))
        return out

    def zone_of_named(self, name, x, y):
        """Area id of the NPC/object called `name` whose spawn is nearest (x, y) (for class-page pins)."""
        if not hasattr(self, '_by_name'):
            self._by_name = {}
            for src in (self.npcs, self.objects):
                for e in src.values():
                    if e.get('name') and e.get('spawns'):
                        self._by_name.setdefault(e['name'].lower(), []).append(e['spawns'])
        best = None
        for spawns in self._by_name.get(name.lower(), []):
            for z, pts in spawns.items():
                for p in pts:
                    if isinstance(p, list) and len(p) >= 2 and p[0] >= 0:
                        d = (p[0] - x) ** 2 + (p[1] - y) ** 2
                        if best is None or d < best[0]:
                            best = (d, int(z))
        return best[1] if best and best[0] <= 25 else None

    def quest_name(self, qid):
        q = self.quests.get(qid)
        if q:
            return q.get('name')
        r = self.fc_rows.get(qid) or self.fc.get(qid)
        return (r or {}).get('name') or (self.fc.get(qid) or {}).get('title')

    def exists(self, qid):
        return qid in self.quests or qid in self.fc_rows or qid in self.fc


_TAIL_ZONES = None


def page_pins(rec):
    """Start / End entries from the bottom of a ForeverChanges quest page: 'Start <npc> <zone> <x> , <y>'.
    Unlike rec['pins'] these name the map the NPC stands on. Returns [{'role', 'name', 'zone', 'x', 'y'}]."""
    global _TAIL_ZONES
    if _TAIL_ZONES is None:
        _TAIL_ZONES = '|'.join(re.escape(n) for n in sorted(UIMAP_NAMES.values(), key=len, reverse=True))
    text = ' '.join((rec.get('text') or '').split())
    out = []
    for role, name, zone, x, y in re.findall(r'(Start|End) ([^,]{2,60}?) (' + _TAIL_ZONES + r') ([\d.]+) , ([\d.]+)', text):
        out.append({'role': role, 'name': name.strip(), 'zone': zone, 'x': float(x), 'y': float(y)})
    return out


def centroid(points):
    """Centre of the densest cluster of points (radius 6 map-percent)."""
    if not points:
        return None
    best, best_n = None, -1
    for p in points:
        n = [q for q in points if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 <= 36]
        if len(n) > best_n:
            best, best_n = n, len(n)
    return (round(sum(q[0] for q in best) / len(best), 1), round(sum(q[1] for q in best) / len(best), 1))


def pick_spawn(spawns, prefer_zone=None, near=None):
    """spawns: {areaId(str): [[x,y],...]} -> (areaId, x, y)"""
    if not spawns:
        return None
    zones = list(spawns.keys())
    if prefer_zone is not None and str(prefer_zone) in spawns:
        zones = [str(prefer_zone)]
    best = None
    for z in zones:
        pts = [p for p in spawns[z] if isinstance(p, list) and len(p) >= 2 and p[0] >= 0]
        if not pts:
            continue
        c = centroid(pts)
        d = 0
        if near and near[0] == int(z):
            d = (c[0] - near[1]) ** 2 + (c[1] - near[2]) ** 2
        elif near:
            d = 1e6
        cand = (d, -len(pts), int(z), c[0], c[1])
        if best is None or cand < best:
            best = cand
    return None if best is None else (best[2], best[3], best[4])


class Step:
    def __init__(self, kind, args, text, seg, line, override=None):
        self.kind, self.args, self.text, self.seg, self.line, self.override = kind, args, text, seg, line, override
        self.loc = None  # (areaId or None, zoneName, x, y)
        self.lv = 1      # estimated level when the step is reached (set by validate)
        self.dg = None   # dungeon number for optional dungeon steps (tools/dungeons.py)


def parse_routes(files):
    steps, segments, errors = [], [], []
    seg = None
    for f in files:
        for n, raw in enumerate(Path(f).read_text(encoding='utf-8').splitlines(), 1):
            line = raw.strip()
            where = f"{Path(f).name}:{n}"
            if not line or line.startswith('#'):
                continue
            if line.startswith('@segment'):
                seg = line[len('@segment'):].strip()
                segments.append(seg)
                continue
            if line.startswith('@start-level') or line.startswith('@carry') or line.startswith('@done'):
                if seg is None:
                    errors.append(f"{where}: header before @segment")
                    continue
                key, _, val = line.partition(' ')
                steps.append(Step('@' + key[1:].upper(), re.findall(r'\d+', val), '', seg, where))
                continue
            if seg is None:
                errors.append(f"{where}: step before any @segment")
                continue
            text = ''
            if '|' in line:
                line, text = line.split('|', 1)
                line, text = line.strip(), text.strip()
            override = None
            m = re.search(r'@\s*([^,@]+),\s*([\d.]+),\s*([\d.]+)\s*$', line)
            if m:
                override = (m.group(1).strip(), float(m.group(2)), float(m.group(3)))
                line = line[:m.start()].strip()
            parts = line.split(None, 1)
            kind = parts[0].upper()
            arg = parts[1].strip() if len(parts) > 1 else ''
            if kind in ('A', 'T', 'C'):
                ids = []
                for tok in re.split(r'[,\s]+', arg):
                    if not tok:
                        continue
                    mm = re.fullmatch(r'(\d+)(?::(\d+))?', tok)
                    if not mm:
                        errors.append(f"{where}: bad quest token {tok!r}")
                        continue
                    ids.append((mm.group(1), int(mm.group(2)) if mm.group(2) else None))
                if not ids:
                    errors.append(f"{where}: {kind} needs a quest id")
                    continue
                steps.append(Step(kind, ids, text, seg, where, override))
            elif kind == 'G':
                mm = re.fullmatch(r'(.+?),\s*([\d.]+),\s*([\d.]+)', arg)
                if not mm:
                    errors.append(f"{where}: G needs 'Zone, x, y'")
                    continue
                steps.append(Step('G', [], text, seg, where, (mm.group(1).strip(), float(mm.group(2)), float(mm.group(3)))))
            elif kind == 'L':
                if not arg.isdigit():
                    errors.append(f"{where}: L needs a level")
                    continue
                steps.append(Step('L', [int(arg)], text, seg, where, override))
            elif kind in ('S', 'H', 'F', 'FLY', 'N', 'TRAIN'):
                if kind != 'TRAIN' and not arg and not text:
                    errors.append(f"{where}: {kind} needs text")
                steps.append(Step(kind, [arg], text, seg, where, override))
            else:
                errors.append(f"{where}: unknown step type {kind!r}")
    return steps, segments, errors


def resolve_locations(steps, D):
    last = None  # (areaId, x, y)
    for s in steps:
        loc = None
        if s.override:
            zname, x, y = s.override
            aid = D.name_to_area.get(zname.lower())
            loc = (aid, zname, x, y)
        elif s.kind in ('A', 'T', 'C'):
            qid, obj = s.args[0]
            fc = D.fc.get(qid)
            q = D.quests.get(qid, {})
            pref = last[0] if last else None
            seen = (D.observed.get(qid) or {}).get(s.kind) if s.kind in ('A', 'T') else None
            if seen and seen['zone'].lower() in D.name_to_area:
                # where the player really stood when the quest dialog was open
                loc = (D.name_to_area[seen['zone'].lower()], seen['zone'], seen['x'], seen['y'])
            if loc is None and s.kind in ('A', 'T') and fc and fc.get('pins'):
                role = 'Start' if s.kind == 'A' else 'End'
                pin = next((p for p in fc['pins'] if p['role'] == role), None)
                if pin and fc.get('zone') and fc['zone'].lower() in D.name_to_area:
                    loc = (D.name_to_area.get(fc['zone'].lower()), fc['zone'], pin['x'], pin['y'])
                    # The page's zone is the quest's category, not always where the NPC stands (a Redridge
                    # quest handed in at Stormwind): when the NPC is known at these coordinates on another
                    # map, that map wins.
                    real = D.zone_of_named(pin['name'], pin['x'], pin['y']) if pin.get('name') else None
                    if real is not None and D.area_to_uimap.get(real) and D.area_to_uimap.get(real) != D.area_to_uimap.get(loc[0]):
                        loc = (real, D.area_names.get(real, str(real)), pin['x'], pin['y'])
                elif pin:
                    # class-page quests (zone "Shaman"/"Mage") have no zone: find the NPC by name
                    aid = D.zone_of_named(pin['name'], pin['x'], pin['y'])
                    if aid is not None:
                        loc = (aid, D.area_names.get(aid, str(aid)), pin['x'], pin['y'])
            if loc is None and s.kind in ('A', 'T') and q:
                who = q.get('startedBy' if s.kind == 'A' else 'finishedBy') or []
                cands = {}
                for kind_i, ids in enumerate(who):
                    if not ids:
                        continue
                    src = D.npcs if kind_i == 0 else (D.objects if kind_i == 1 else None)
                    if src is None:
                        continue
                    for eid in ids:
                        e = src.get(str(eid))
                        if e and e.get('spawns'):
                            for z, pts in e['spawns'].items():
                                cands.setdefault(z, []).extend(pts)
                pick = pick_spawn(cands, pref, last)
                if pick:
                    loc = (pick[0], D.area_names.get(pick[0], str(pick[0])), pick[1], pick[2])
            if loc is None and s.kind in ('A', 'T') and fc:
                # new Forever NPCs that are in no database: the page's own Start / End line names map and spot
                role = 'Start' if s.kind == 'A' else 'End'
                pin = next((p for p in page_pins(fc) if p['role'] == role), None)
                if pin and pin['zone'].lower() in D.name_to_area:
                    loc = (D.name_to_area[pin['zone'].lower()], pin['zone'], pin['x'], pin['y'])
            if loc is None and s.kind == 'C':
                if fc and fc.get('dots') and fc.get('zone'):
                    c = centroid(fc['dots'])
                    loc = (D.name_to_area.get(fc['zone'].lower()), fc['zone'], c[0], c[1])
                elif q:
                    cands = {}
                    objs = q.get('objectives') or []
                    if isinstance(objs, dict):
                        objs = [objs.get(str(i)) for i in range(1, 7)]
                    for kind_i, lst in enumerate(objs[:3] if objs else []):
                        if not lst:
                            continue
                        for ent in lst:
                            eid = ent[0] if isinstance(ent, list) else ent
                            if kind_i == 0:
                                e = D.npcs.get(str(eid))
                                sp = e.get('spawns') if e else None
                            elif kind_i == 1:
                                e = D.objects.get(str(eid))
                                sp = e.get('spawns') if e else None
                            else:
                                sp = None
                                it = D.items.get(str(eid)) or {}
                                for src_key, src in (('npcDrops', D.npcs), ('objectDrops', D.objects)):
                                    for did in (it.get(src_key) or [])[:12]:
                                        e = src.get(str(did))
                                        if e and e.get('spawns'):
                                            sp = sp or {}
                                            for z, pts in e['spawns'].items():
                                                sp.setdefault(z, []).extend(pts)
                            if sp:
                                for z, pts in sp.items():
                                    cands.setdefault(z, []).extend(pts)
                    te = q.get('triggerEnd')
                    if not cands and te and isinstance(te, list) and len(te) > 1 and isinstance(te[1], dict):
                        for z, pts in te[1].items():
                            cands.setdefault(z, []).extend(pts)
                    pick = pick_spawn(cands, pref, last)
                    if pick:
                        loc = (pick[0], D.area_names.get(pick[0], str(pick[0])), pick[1], pick[2])
        s.loc = loc
        if loc and loc[0] is not None:
            last = (loc[0], loc[2], loc[3])
        elif loc:
            last = None


def quest_xp(qid, D, player_level):
    row = D.fc_rows.get(qid)
    qlevel, xp = None, None
    seen = D.observed.get(qid) or {}
    if seen.get('xp') is not None and seen.get('xpLevel'):
        # real reward at full value (logged while the quest was not grey), so the level scaling below still applies
        xp, qlevel = seen['xp'], (row or {}).get('level') or D.quests.get(qid, {}).get('questLevel') or seen['xpLevel']
    elif row and row.get('xp'):
        xp, qlevel = row['xp'], row.get('level')
    elif qid in D.xpdb:
        qlevel, xp = D.xpdb[qid]
    if xp is None:
        return 0
    qlevel = qlevel or D.quests.get(qid, {}).get('questLevel') or player_level
    diff = player_level - qlevel
    if diff >= 10:
        mult = 0.1
    elif diff >= 6:
        mult = {6: 0.8, 7: 0.6, 8: 0.4, 9: 0.2}[diff]
    else:
        mult = 1.0
    return int(round(xp * mult / 5.0) * 5)


CLASS_PAGES = {'Mage', 'Shaman', 'Warrior', 'Paladin', 'Hunter', 'Rogue', 'Priest', 'Warlock', 'Druid'}
SEG_STATE = {}  # segment title -> (quest log at segment end, level)


# Total XP earned per point of quest XP (mob kills, exploration, rested). Measured from the play log with
# tools/check_log.py: 1.7-2.0 for levels 5-16 on both characters. 1.35 (the first guess) ran 2 levels behind.
KILL_FACTOR = 1.7


def validate(steps, D, kill_factor=KILL_FACTOR, standalone=False):
    """standalone=True: a single segment file is checked on its own, so its @start-level/@carry/@done
    headers set the starting state. Otherwise headers are checked against the simulated state."""
    issues = []
    accepted, done, log = set(), set(), set()
    level, xp = 1, 0
    seg_levels = {}

    def warn(s, msg, sev='WARN'):
        issues.append((sev, s.line, s.seg, msg))

    for s in steps:
        if s.kind.startswith('@'):
            vals = [int(v) for v in s.args]
            if s.kind == '@START-LEVEL' and vals:
                if standalone:
                    level, xp = vals[0], 0
                elif abs(level - vals[0]) >= 2:
                    warn(s, f"segment expects level {vals[0]} but estimated level here is {level}")
            elif s.kind == '@CARRY':
                for v in map(str, vals):
                    if standalone:
                        accepted.add(v)
                        log.add(v)
                    elif v not in log:
                        warn(s, f"segment expects quest {v} {D.quest_name(v)} in the log, but it is not", 'ERROR')
            elif s.kind == '@DONE':
                for v in map(str, vals):
                    if standalone:
                        done.add(v)
                        accepted.add(v)
                    elif v not in done:
                        warn(s, f"segment expects quest {v} {D.quest_name(v)} already turned in, but it is not")
            continue
        if s.kind in ('A', 'T', 'C'):
            for qid, obj in s.args:
                if not D.exists(qid):
                    warn(s, f"quest {qid} not found in Questie or Forever data", 'ERROR')
                    continue
                q = D.quests.get(qid, {})
                row = D.fc_rows.get(qid, {})
                name = D.quest_name(qid)
                if s.kind == 'A':
                    if qid in accepted:
                        warn(s, f"{qid} {name}: accepted twice")
                    races = q.get('requiredRaces')
                    if races and not (races & PROFILE['race_bit']):
                        warn(s, f"{qid} {name}: not available to {PROFILE['race']} (race mask {races})", 'ERROR')
                    if row and row.get('sides') and PROFILE['side'] not in row['sides']:
                        warn(s, f"{qid} {name}: not a {PROFILE['side']} quest (sides {row['sides']})", 'ERROR')
                    classes = q.get('requiredClasses')
                    if classes and not (classes & PROFILE['class_bit']):
                        warn(s, f"{qid} {name}: not available to {PROFILE['class']}s (class mask {classes})", 'ERROR')
                    fcz = (D.fc.get(qid) or {}).get('zone') or ''
                    if fcz in CLASS_PAGES and fcz != PROFILE['class']:
                        warn(s, f"{qid} {name}: listed as a {fcz} quest on ForeverChanges", 'ERROR')
                    req = row.get('reqLevel') or q.get('requiredLevel')
                    if req and req > level:
                        warn(s, f"{qid} {name}: needs level {req}, estimated level {level}")
                    singles = q.get('preQuestSingle') or []
                    if singles and all(str(p) not in done for p in singles):
                        warn(s, f"{qid} {name}: needs one of {singles} turned in first")
                    for pre in (q.get('preQuestGroup') or []):
                        if str(pre) not in done:
                            warn(s, f"{qid} {name}: needs {pre} turned in first")
                    if qid in D.dungeon_quests:
                        warn(s, f"{qid} {name}: listed under a dungeon on ForeverChanges", 'ERROR')
                    if row.get('elite'):
                        warn(s, f"{qid} {name}: elite / group quest")
                    accepted.add(qid)
                    log.add(qid)
                    if len(log) > QUEST_LOG_LIMIT:
                        warn(s, f"quest log has {len(log)} quests (limit {QUEST_LOG_LIMIT})", 'ERROR')
                elif s.kind == 'C':
                    if qid not in accepted:
                        warn(s, f"{qid} {name}: completing a quest that was never accepted", 'ERROR')
                elif s.kind == 'T':
                    if qid not in accepted:
                        warn(s, f"{qid} {name}: turning in a quest that was never accepted", 'ERROR')
                    if qid in done:
                        warn(s, f"{qid} {name}: turned in twice", 'ERROR')
                    done.add(qid)
                    log.discard(qid)
                    xp += quest_xp(qid, D, level) * kill_factor
                    while level < 60 and xp >= XP_TO_LEVEL[level]:
                        xp -= XP_TO_LEVEL[level]
                        level += 1
        elif s.kind == 'L':
            target = s.args[0]
            if target > level:
                need = XP_TO_LEVEL[level] - xp + sum(XP_TO_LEVEL[l] for l in range(level + 1, target))
                warn(s, f"grind step to {target}: estimated {int(need)} XP of grinding needed from level {level}", 'INFO')
                level, xp = target, 0
        if s.kind in ('A', 'T', 'C', 'G') and s.loc is None:
            warn(s, f"no coordinates for {s.kind} {s.args}", 'WARN')
        s.lv = level
        seg_levels[s.seg] = level
        SEG_STATE[s.seg] = (sorted(log, key=int), level)
    for qid in sorted(accepted - done, key=int):
        issues.append(('INFO', '-', '-', f"{qid} {D.quest_name(qid)}: accepted but never turned in"))
    return issues, seg_levels


CAVE_WORDS = re.compile(r'\b(caves?|caverns?|mines?|tunnels?|burrows?|grotto|crypt|excavation)\b', re.I)


def add_paths(steps, D):
    """Give steps a walking path (s.path = [(x, y), ...] before the step's own point) read from the
    zone map art, and a cave entrance as the last path point when the step is inside a cave (s.cave).
    Never touches s.loc, so step keys (and saved progress) stay the same. See tools/pathmap.py."""
    try:
        if str(Path(__file__).resolve().parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
        import pathmap as PM
    except Exception as e:  # numpy / Pillow missing: build the route without paths
        print('paths skipped:', e)
        return 0, 0
    caves = PM.load_caves()
    prev = None  # (mapid, x, y) where the player stands after the previous step
    n_path = n_cave = 0
    for s in steps:
        s.path, s.cave = [], False
        if s.kind in ('H', 'FLY'):
            prev = None
            continue
        if not s.loc or s.dg:
            continue
        aid, _, x, y = s.loc
        mid = D.area_to_uimap.get(aid) if aid is not None else None
        if not mid:
            prev = None
            continue
        cave = None
        text = s.text or ''
        if s.kind == 'C':
            for q, _ in s.args:
                text += ' ' + ' '.join(D.quests.get(q, {}).get('objectivesText') or [])
        if s.kind in ('A', 'T', 'C', 'G') and CAVE_WORDS.search(text):
            cave = PM.nearest_cave(caves, mid, x, y)
        goal = cave or (x, y)
        if prev and prev[0] == mid and not 1453 <= mid <= 1458:   # city maps are drawings of buildings: no paths there
            s.path = list(PM.walk_path(mid, (prev[1], prev[2]), goal))
        if cave:
            s.path.append(cave)
            s.cave = True
            n_cave += 1
        if s.path:
            n_path += 1
        prev = (mid, goal[0], goal[1])  # after a cave step you come back out at its entrance
    return n_path, n_cave


def lua_str(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def emit_lua(steps, segments, D, dungeon_table=None):
    P = PROFILE
    out = [f"-- Generated by tools/build_route.py from routes/{P['key']}/. Edit the .route files, not this file.",
           'local _, ns = ...', 'ns.Routes = ns.Routes or {}', 'ns.Routes[' + lua_str(P['key']) + '] = {',
           'title = ' + lua_str(P['title']) + ',',
           'faction = ' + lua_str(P['side']) + ',',
           'races = {' + ','.join(lua_str(r) for r in P['races']) + '},',
           'classes = {' + ','.join(lua_str(c) for c in P['classes']) + '},',
           'segments = {']
    for s in segments:
        out.append(f'  {lua_str(s)},')
    out.append('},')
    out.append('steps = {')
    for s in steps:
        f = [f't={lua_str(s.kind)}', f'seg={segments.index(s.seg) + 1}']
        if s.kind in ('A', 'T', 'C'):
            f.append('q={' + ','.join(q for q, _ in s.args) + '}')
            objs = [o for _, o in s.args]
            if any(objs):
                f.append('obj={' + ','.join(str(o or 0) for o in objs) + '}')
            names = [D.quest_name(q) or f'Quest {q}' for q, _ in s.args]
            f.append('names={' + ','.join(lua_str(n) for n in names) + '}')
        elif s.kind == 'L':
            f.append(f'lvl={s.args[0]}')
        elif s.args and s.args[0]:
            f.append(f'arg={lua_str(s.args[0])}')
        if s.text:
            f.append(f'text={lua_str(s.text)}')
        if s.loc:
            aid, zname, x, y = s.loc
            mid = D.area_to_uimap.get(aid) if aid is not None else None
            if not mid:  # no map for this area id: take it straight from the zone name
                mid = next((m for m, n in UIMAP_NAMES.items() if n.lower() == str(zname).lower()), None)
            f.append(f'zone={lua_str(UIMAP_NAMES.get(mid, zname))}')
            if mid:
                f.append(f'map={mid}')
            f.append(f'x={x}')
            f.append(f'y={y}')
        if getattr(s, 'path', None):
            f.append('path={' + ','.join('{%s,%s}' % (px, py) for px, py in s.path) + '}')
            if s.cave:
                f.append('cave=true')
        if s.dg:
            f.append(f'dg={s.dg}')
            if s.run:
                f.append('run=true')
            if s.req:
                f.append(f'req={s.req}')
        out.append('  {' + ', '.join(f) + '},')
    out.append('},')
    if dungeon_table:
        # optional dungeon runs: steps with dg=<n> are only shown with "/fr dungeons on"
        out.append('dungeons = {')
        for d in dungeon_table:
            out.append(f"  {{name={lua_str(d['name'])}, levels={lua_str(d['levels'])}}},")
        out.append('},')
        # quest levels, so the addon can say when a quest has gone grey for a character that is ahead
        qids = sorted({int(q) for s in steps if s.kind in ('A', 'T', 'C') for q, _ in s.args})
        pairs = []
        for q in qids:
            lvl = (D.fc_rows.get(str(q)) or {}).get('level') or D.quests.get(str(q), {}).get('questLevel')
            if lvl and lvl > 0:
                pairs.append(f'[{q}]={lvl}')
        out.append('qlvl = {' + ','.join(pairs) + '},')
    out.append('}')
    return '\n'.join(out) + '\n'


def main():
    args = sys.argv[1:]
    if '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)
    key = args[args.index('--route') + 1] if '--route' in args else 'undead-mage'
    keys = list(PROFILES) if key == 'all' else [key]
    D = Data()
    ok = True
    for k in keys:
        ok = build(k, args, D) and ok
    sys.exit(0 if ok else 1)


def build(key, args, D):
    args = list(args)
    use_profile(key)
    SEG_STATE.clear()
    standalone = '--only' in args
    if standalone:
        files = [Path(args[args.index('--only') + 1])]
        args.append('--check-only')
    else:
        files = sorted((ROOT / 'routes' / key).glob('*.route'))
    steps, segments, errors = parse_routes(files)
    resolve_locations(steps, D)
    issues, seg_levels = validate(steps, D, standalone=standalone)
    steps = [s for s in steps if not s.kind.startswith('@')]
    lines = [f"route: {PROFILE['title']} ({key})  steps: {len(steps)}  segments: {len(segments)}"]
    dungeon_table, dungeon_lines, n_dg_err = None, [], 0
    if not standalone and '--no-dungeons' not in args:
        if str(Path(__file__).resolve().parent) not in sys.path:  # python -I leaves the script folder out
            sys.path.insert(0, str(Path(__file__).resolve().parent))
        import dungeons as DG
        defs, derrs = DG.load_dungeons(ROOT / 'routes' / PROFILE['dungeons'])
        errors += derrs
        base_count = len(steps)
        steps, dungeon_lines, dungeon_table, n_dg_err = DG.weave(steps, D, PROFILE, defs, sys.modules[__name__])
        lines[0] += f"  optional dungeon steps: {len(steps) - base_count} ({len(dungeon_table)} dungeons)"
    if not standalone and '--no-paths' not in args:
        n_path, n_cave = add_paths(steps, D)
        lines.append(f"walking paths from the map art: {n_path} steps ({n_cave} with a cave entrance)")
    lines += [f"PARSE ERROR {e}" for e in errors]
    for sev, where, seg, msg in issues:
        lines.append(f"{sev:5} {where:28} {msg}")
    lines.append(f'estimated level at end of each segment (quest XP x{KILL_FACTOR} for kills):')
    for seg in segments:
        lines.append(f"  {seg_levels.get(seg, '?'):>3}  {seg}")
    lines += dungeon_lines
    if dungeon_table:
        lines.append('extra quest experience if every optional dungeon is run (quests only, kills come on top):')
        for d in dungeon_table:
            pct = 100.0 * d['xp'] / XP_TO_LEVEL[min(max(d['at'], 1), 59)]
            lines.append(f"  {d['name']:28} {d['xp']:>6} XP = {pct:3.0f}% of level {d['at']}")
    if '--log-at-ends' in args:
        lines.append('quest log at the end of each segment (simulated):')
        for seg in segments:
            log_ids, _ = SEG_STATE.get(seg, ([], 0))
            lines.append(f"  {seg}: " + ', '.join(f"{q} {D.quest_name(q)}" for q in log_ids))
    report = '\n'.join(lines)
    sys.stdout.reconfigure(encoding='utf-8')
    print(report)
    if '--report' in args:
        Path(args[args.index('--report') + 1]).write_text(report, encoding='utf-8')
    n_err = len(errors) + n_dg_err + sum(1 for sev, *_ in issues if sev == 'ERROR')
    if '--check-only' not in args and not errors:
        target = ROOT / 'addon' / 'ForeverRoute' / 'Routes' / f"{PROFILE['lua']}.lua"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(emit_lua(steps, segments, D, dungeon_table), encoding='utf-8')
        print('wrote', target)
    return n_err == 0


if __name__ == '__main__':
    main()
