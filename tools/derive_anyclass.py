"""Make the level 14+ files of an any-class Alliance route from the class-neutral Gnome route.

Every Alliance route follows the same quests, binds and flights from level 14 (Gnome segment 04) on; only the
mount at level 40 and one or two race-only quests differ. This script copies the Gnome files and applies those
differences. The start-zone files of each race (segments 01-04; for Dwarf 01-03, which are the Gnome's) are
written by hand and never touched here.

Usage: python -I tools/derive_anyclass.py dwarf|human|night-elf|skyborne
"""
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

MOUNT_HEAD = '# ---------- Ironforge: level 40 and the mechanostrider ----------'
MOUNT_TAIL = 'N Take the boat from Menethil Harbor to Theramore'
KEEP = ('You keep 1137 (Fizzle, Mirage Raceway), 1111 and 1178 (Ratchet), 669 and 209 (Booty Bay), 212 (Stormwind). '
        'Your hearthstone stays in Southshore until Gadgetzan.')

MOUNTS = {
    'dwarf': '''# ---------- Ironforge: level 40 and the ram ----------
FLY Ironforge @ Hillsbrad Foothills, 49.3, 52.3 | Darla Harris, the Southshore gryphon master
TRAIN | Ironforge: visit your class trainer and learn your level 40 skills
N Walk out of the Ironforge gates to Amberstill Ranch @ Dun Morogh, 63.5, 50.6 | Down the ramp, then east along the road past Kharanos and Steelgrill's Depot. The ranch is on the right of the road, about eight minutes from the gate: your last long walk.
N Learn Apprentice Riding from Ultham Ironhorn @ Dun Morogh, 63.9, 50.1 | The ram riding trainer at the ranch. He also has a new Forever quest, Learning to Ride: take it if he offers it, it completes when you pay for the skill.
A 97017 @ Dun Morogh, 63.5, 50.6 | Your First Riding Ram, a new Forever quest (level 40). The giver is not in my data: it is Ultham Ironhorn or Veron Amberstill, the ram seller next to him. Per the quest text the first ram is free once you have the riding skill.
C 97017 @ Dun Morogh, 64.0, 50.4 | Walk up to the White, Brown and Gray Ram in the pen and inspect each one
T 97017 @ Dun Morogh, 63.5, 50.6 | Back to the NPC who gave the quest: choose your ram as the reward. Put it on your action bar: from here on the route says "ride".
FLY Menethil Harbor @ Ironforge, 55.5, 47.7 | Ride back up to Ironforge: Gryth Thurden
N Take the boat from Menethil Harbor to Theramore | %s''' % KEEP,
    'human': '''# ---------- Stormwind: level 40 and the horse ----------
FLY Stormwind @ Hillsbrad Foothills, 49.3, 52.3 | Darla Harris, the Southshore gryphon master. A long flight south over Ironforge.
TRAIN | Stormwind: visit your class trainer and learn your level 40 skills. Sell, repair and empty your bags at the bank: the next city stop is a long way off.
N Mount at level 40: walk to the Eastvale Logging Camp @ Elwynn Forest, 84.3, 64.9 | Leave Stormwind by the main gate and follow the road through Goldshire east to the logging camp (about eight minutes on foot, your last long walk). Randal Hunter teaches riding and Katie Hunter beside him has the horses. In Forever both have a new quest (Learning to Ride, Your First Horse) and Katie gives the first horse free once you have trained; the price of the training is not published: bring all your gold (about 100 in Classic). Put the horse on your action bar: from here on the route says "ride".
FLY Menethil Harbor @ Redridge Mountains, 30.6, 59.4 | Ride on east along the same road, past the Three Corners into Redridge, and over the bridge to Lakeshire (about four minutes on the horse). Ariena Stormfeather, the gryphon master, stands on the west side of town. This is shorter than riding back to Stormwind.
N Take the boat from Menethil Harbor to Theramore | %s''' % KEEP,
    'night-elf': '''# ---------- Ironforge at 40, then Darnassus for the nightsaber ----------
FLY Ironforge @ Hillsbrad Foothills, 49.3, 52.3 | Darla Harris, the Southshore gryphon master
TRAIN | Ironforge: visit your class trainer and learn your level 40 skills. Druids have no trainer in Ironforge: train in Darnassus, two steps on. Sell, repair and bank here.
FLY Menethil Harbor @ Ironforge, 55.5, 47.7 | Gryth Thurden
N Take the boat from Menethil Harbor to Auberdine, then the boat to Rut'theran Village | Two boats: in Menethil the Auberdine boat leaves from the northern pier (the other one goes to Theramore). In Auberdine walk to the other arm of the same dock for the Teldrassil boat. Step through the pink portal in Rut'theran Village to Darnassus.
N Mount at level 40: Jartsam in the Cenarion Enclave @ Darnassus, 38.7, 15.8 | The Cenarion Enclave is in the north-west of Darnassus. Jartsam teaches nightsaber riding and Lelanai beside him (38.3, 15.4) has the sabers. The other Alliance races get a free first mount from a new Forever quest once they have trained (Learning to Ride, Your First ...): ask both of them for quests. The price of the training is not published: bring all your gold (about 100 in Classic). Druids: your trainers are in this same enclave. Put the saber on your action bar: from here on the route says "ride".
FLY Theramore @ Teldrassil, 58.4, 94.0 | Back through the portal to Rut'theran Village: Vesprystus, the hippogryph master. A very long flight (Auberdine, Astranaar, Ratchet). Not checked: if he does not offer Theramore, take the boats back instead (Rut'theran -> Auberdine -> Menethil Harbor -> Theramore).
N You are in Theramore | %s''' % KEEP,
    'skyborne': '''# ---------- Ironforge: level 40 ----------
FLY Ironforge @ Hillsbrad Foothills, 49.3, 52.3 | Darla Harris, the Southshore gryphon master
TRAIN | Ironforge: visit your class trainer and learn your level 40 skills
N Mount at level 40 | The current Questie data lists one Skyborne riding trainer: Genn Fairweather, "Stablemaster and Riding Trainer", on Zephras Isle (53.8, 81.3, on the south coast near Valanaar). How to get back to Zephras Isle from here is not known to me (you left on the skycutter to Dalaran): ask a city guard or another Skyborne whether there is a trainer or a way back nearer by, and have 100 gold ready. Until you have a mount, read "ride" as "walk".
FLY Menethil Harbor @ Ironforge, 55.5, 47.7 | Gryth Thurden
N Take the boat from Menethil Harbor to Theramore | %s''' % KEEP,
}

RACES = {
    'dwarf': dict(title='Dwarf', mount='ram', shift=0, first=0),
    'human': dict(title='Human', mount='horse', shift=1, first=3),
    'night-elf': dict(title='Night Elf', mount='nightsaber', shift=1, first=3),
    'skyborne': dict(title='Skyborne', mount='mount', shift=1, first=3),
}

BINGLES_N = 'N Could not take Find Bingles last time (it needs level 12)?'
BINGLES_A = ('A 2039 @ Ironforge, 69.2, 50.6 | Gnoarn, in Tinker Town, right by the tram entrance. '
             'Keep it: Bingles is on the east shore of the Loch, next segment')


def bump_segments(line, shift):
    """Segment numbers in comments and step text follow the renumbering (the Gnome route starts one file earlier)."""
    if not shift or "oute's segment" in line or line.startswith('@segment'):
        return line

    def fix(m):
        return m.group(1) + re.sub(r'\d+', lambda n: '%0*d' % (len(n.group(0)), int(n.group(0)) + shift), m.group(2))
    return re.sub(r'(\b[Ss]egments? )(\d+(?:(?:, | and |-| to )\d+)*)', fix, line)


def main(key):
    R = RACES[key]
    src = sorted(glob.glob(os.path.join(ROOT, 'routes', 'gnome', '*.route')))[R['first']:]
    out_dir = os.path.join(ROOT, 'routes', key)
    os.makedirs(out_dir, exist_ok=True)
    for f in src:
        base = os.path.basename(f)
        n = int(base[:2])
        s = open(f, encoding='utf-8').read()
        lines = [bump_segments(l, R['shift']) for l in s.split('\n')]
        s = '\n'.join(lines)
        s = s.replace('# Gnome, any class. From', '# %s, any class (made from the Gnome route by tools/derive_anyclass.py). From' % R['title'])
        s = s.replace('the Mechanostrider', {'dwarf': 'the Ram'}.get(key, 'Level 40'))
        if n == 15:
            a, b = s.index(MOUNT_HEAD), s.index(MOUNT_TAIL)
            e = s.index('\n', b)
            s = s[:a] + MOUNTS[key] + s[e:]
            s = s.replace("# earlier), with the Refuge Pointe gryphon as the fallback; the mount stop is Steelgrill's Depot (Binjy and Milli\n"
                          "# Featherwhistle, Dun Morogh 49.2, 48.1) and the mount quest is the gnome one, 97046 Your First Mechanostrider.",
                          '# earlier), with the Refuge Pointe gryphon as the fallback; the mount stop is the %s one (see the last block).' % R['title'])
            s = s.replace("Mount: Steelgrill's Depot at the very end, at level 40.", 'Mount: at the very end, at level 40.')
            s = s.replace('you pay Binjy Featherwhistle for Apprentice Riding', 'you pay for Apprentice Riding')
            s = s.replace('the mechanostrider needs level 40, and Dun Morogh is not on the route again for a long time',
                          'the mount needs level 40, and the trainer is not on the route again for a long time')
            assert '97046' not in s and 'Binjy' not in s, 'mount block left over'
        s = re.sub(r'\b(a|your|the|on your|off your) mechanostrider', lambda m: m.group(1) + ' ' + R['mount'], s)
        s = s.replace('the mount is the mechanostrider', 'the mount is the ' + R['mount'])
        s = s.replace('the mount is a mechanostrider', 'the mount is the ' + R['mount'])
        assert 'echanostrider' not in s, (base, [l for l in s.split('\n') if 'echanostrider' in l])
        if n == 4 and key != 'dwarf':
            # the start zones of these races do not pass Gnoarn at level 12: Find Bingles is taken here
            assert '@carry 263,1338,2039' in s
            s = s.replace('@carry 263,1338,2039', '@carry 263,1338')
            ls = s.split('\n')
            i = [k for k, l in enumerate(ls) if l.startswith(BINGLES_N)]
            assert len(i) == 1
            ls[i[0]] = BINGLES_A
            s = '\n'.join(ls)
        if n == 4 and key == 'night-elf':
            # the Night Elf walks from Loch Modan to Ironforge at the end of segment 04 and starts here in Ironforge
            ls = s.split('\n')
            i = [k for k, l in enumerate(ls) if l.startswith('FLY Ironforge | From Thorgrum Borrelson in Thelsamar')]
            assert len(i) == 1
            del ls[i[0]]
            s = '\n'.join(ls)
        if n == 4 and key == 'skyborne':
            # 98021 Journey to Sentinel Hill: Skyborne only (follows their arrival quest 94947)
            ls = s.split('\n')
            i = [k for k, l in enumerate(ls) if l.startswith('C 97237')]
            j = [k for k, l in enumerate(ls) if l.startswith('T 109 ')]
            assert len(i) == 1 and len(j) == 1 and i[0] < j[0]
            ls.insert(j[0] + 1, 'T 98021 @ Westfall, 56.3, 47.5 | Gryan Stoutmantle')
            ls.insert(i[0] + 1, 'A 98021 @ Stormwind City, 80.0, 38.5 | Highlord Bolvar Fordragon, in the throne room of the keep: '
                                'Journey to Sentinel Hill (Skyborne only)')
            s = '\n'.join(ls)
            s = s.replace('# Removed 2026-11-11: 98021 Journey to Sentinel Hill (Bolvar). The current Questie data makes it a Skyborne-only quest\n'
                          '# that follows their arrival quest 94947, so Bolvar does not offer it to this character.\n',
                          '# 98021 Journey to Sentinel Hill (Bolvar) is Skyborne-only (it follows their arrival quest 94947): it is in this route.\n')
        name = '%02d%s' % (n + R['shift'], base[2:])
        name = name.replace('-mount-', '-level-40-') if key != 'dwarf' else name
        for old in glob.glob(os.path.join(out_dir, '%02d-*.route' % (n + R['shift']))):
            os.remove(old)
        open(os.path.join(out_dir, name), 'w', encoding='utf-8', newline='').write(s)
        print('wrote', key, name)


if __name__ == '__main__':
    main(sys.argv[1])
