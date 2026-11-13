"""Make the Human Warrior route from the Human any-class route.

The warrior follows the same quests, binds and flights as every Human (routes/human, whose level 14+ files are
themselves generated from the Gnome route). This script copies all 25 Human files and adds what is the warrior's
own: the class quests, the warrior trainers at every training stop, and fight hints written for a warrior in place
of the class-neutral ones. Never edit routes/human-warrior by hand: change routes/human (or the Gnome file behind
it) or this script and run it again.

Usage: python -I tools/derive_warrior.py

Sources. Class quests, givers and positions: the installed Questie data (research/json/baked_quests.json,
baked_npcs.json). Ability levels: the Forever beta spell list (build 1.60.1.70755, forevercalc.com and
conquestcapped.com, both read 2026-11-13); they are named in TRAIN steps so the player knows what to look for, and
the trainer's own list always wins.
"""
import glob
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC, DST = 'human', 'human-warrior'

LLANE = '@ Elwynn Forest, 50.2, 42.3'
LYRIA = '@ Elwynn Forest, 41.1, 65.8'
WU = '@ Stormwind City, 80.5, 59.9'
KELV = '@ Ironforge, 70.3, 90.7'
KELV_WHO = 'Kelv Sternhammer, the warrior trainer in the Hall of Arms (Military Ward, south-east Ironforge)'
WU_WHO = 'Wu Shen, the warrior trainer in the Command Center in Old Town'

# New TRAIN lines per file, in order. Every TRAIN step of the Human file is replaced.
TRAIN = {
    1: ['TRAIN %s | Llane Beshere, the warrior trainer: learn everything he offers. A warrior fights in melee: keep Battle Shout up and press Heroic Strike whenever you have the Rage. Come back at levels 4 and 6' % LLANE,
        'TRAIN %s | Llane Beshere again for the level 4 skills: Charge (open every fight with it from now on) and Rend. Buy food from a vendor at the abbey. Not 4 yet? Come back after the next kobolds' % LLANE,
        'TRAIN %s | Llane Beshere: Charge and Rend, if you did not have them yet' % LLANE,
        'TRAIN %s | Llane Beshere: Thunder Clap, if you are 6 already. Otherwise you train in Goldshire. Sell and repair at the wagons in front of the abbey, and buy food' % LLANE],
    2: ['TRAIN %s | Lyria Du Lac, the warrior trainer at the smithy on the west side of Goldshire: Thunder Clap (level 6), for fights against two or more. Buy food from the innkeeper' % LYRIA,
        'TRAIN %s | Lyria Du Lac again if you are 8: Hamstring (it stops enemies that run for help at low health) and the new ranks' % LYRIA],
    3: ['TRAIN %s | Lyria Du Lac, at the Goldshire smithy, for level 10: Bloodrage, Sunder Armor and Taunt, and every new rank' % LYRIA],
    4: [],  # the Stormwind stop is rewritten as a block (the Defensive Stance chain), see EDITS
    5: ['TRAIN %s | %s: Demoralizing Shout and Revenge (level 14; Revenge works in Defensive Stance), and Overpower and Shield Bash (12) if you have not trained since Goldshire. Sell, repair, buy food' % (KELV, KELV_WHO)],
    6: ['TRAIN %s | %s: Disarm (18), Mocking Blow and Shield Block (16), and every new rank. You come back here at 20.' % (KELV, KELV_WHO),
        'TRAIN %s | %s: Victory Rush (new in Forever: usable after a kill that gives experience, it heals you, so press it after every kill), Cleave, Slam and Retaliation (all level 20).' % (KELV, KELV_WHO)],
    8: ['TRAIN %s | Optional, about 10 minutes: fly from Menethil Harbor to Ironforge, see %s for Execute (24) and Intimidating Shout (22), and fly back. Sell and repair there too.' % (KELV, KELV_WHO)],
    11: ['TRAIN %s | %s: Challenging Shout (26) and Shield Wall (28), plus Execute (24) and Intimidating Shout (22) if you skipped the optional stop' % (KELV, KELV_WHO)],
    12: ['TRAIN %s | %s, for level 30: Intercept, Berserker Rage and Berserker Stance. In Forever the trainer is reported to teach Berserker Stance himself; if it is not in his list, it is the reward of The Affray, the quest you take from him now' % (KELV, KELV_WHO),
         'TRAIN %s | %s: the level 32 ranks if you are 32. This is your last trainer stop until 36: the next two segments are in Kalimdor' % (KELV, KELV_WHO)],
    15: ['TRAIN %s | %s: Whirlwind (36) and every new rank since 32.' % (KELV, KELV_WHO)],
    16: ['TRAIN %s | %s: Pummel (38), your interrupt when you carry no shield. Count your gold: at level 40, at the end of this segment, you pay for Apprentice Riding.' % (KELV, KELV_WHO),
         'TRAIN %s | %s: the level 40 ranks. Warriors can wear plate from 40: in Classic the trainer sells the Plate Mail skill, so look for it in his list. Sell, repair and empty your bags at the bank: the next city stop is a long way off.' % (WU, WU_WHO)],
    19: ['TRAIN %s | %s: every new rank from level 42 to 46 (the route made no training stop in Kalimdor).' % (KELV, KELV_WHO)],
    25: ['TRAIN %s | %s: everything from level 48 to 56, with Recklessness (50) (the route made no training stop in Kalimdor)' % (KELV, KELV_WHO),
         'TRAIN %s | %s: the level 58 ranks.' % (KELV, KELV_WHO),
         'TRAIN %s | %s: the level 60 ranks. Route complete' % (KELV, KELV_WHO)],
}

# Per-file edits, applied in order after the TRAIN steps are replaced.
#   ('sub', old, new)                exact text, must occur exactly once
#   ('line', prefix, [lines])        replace the one line that starts with prefix
#   ('before' / 'after', prefix, [lines])   insert next to the one line that starts with prefix
#   ('carry', 'id')                  add a quest to the @carry line
EDITS = {
    1: [
        ('line', 'N Marshal McBride also has a letter for your class',
         ['A 3100 | Marshal McBride: Simple Letter, the warrior\'s first class quest']),
        ('before', 'TRAIN ', None),  # placeholder, replaced below (first TRAIN only)
        ('sub', 'One wolf at a time; start each fight from as far away as your class can',
         'One wolf at a time: walk up and hit it, and press Heroic Strike whenever you have 15 Rage'),
        ('sub', 'then Garrick from full health, with everything your class has',
         'then Garrick from full health: Charge, Rend, then Heroic Strike'),
        ('sub', 'pull one from range if your class can and back up into the tunnel you already cleared, then kill them one at a time',
         'Charge one, kill it, then the other, and back up into the tunnel you already cleared if a third comes'),
    ],
    2: [
        ('sub', 'Bandages heal you between fights whatever your class is, and many classes have no heal at this level.',
         'A warrior has no heal: bandages are how you recover between fights.'),
        ('sub', 'and drink to full before the last room', 'and eat to full before the last room'),
    ],
    3: [
        ('sub', 'so kill them fast and interrupt or stun their casts if your class can',
         'so kill them fast (a warrior has no interrupt before Shield Bash at 12)'),
        ('sub', 'get on top of it or out-range it quickly, and interrupt its casts if your class can',
         'and Charge straight in so it gets fewer casts off'),
        ('sub', 'level 10 brings new skills and, for most classes, a class quest',
         'level 10 brings new skills and the warrior\'s class quest'),
        ('line', 'N Your trainer has a quest for you at level 10',
         ['A 1638 %s | Lyria Du Lac: A Warrior\'s Training (level 10). It sends you to Harry Burlguard in Stormwind and leads to Defensive Stance: the next segment starts there' % LYRIA]),
    ],
    4: [
        ('carry', '1638'),
        ('line', 'TRAIN ', [
            'T 1638 @ Stormwind City, 77.1, 53.3 | Walk east from the Trade District into Old Town: Harry Burlguard stands in the Pig and Whistle Tavern',
            'A 1639 | Harry Burlguard',
            'T 1639 | Bartleby, the drunk in the same tavern',
            'A 1640 | Bartleby',
            'C 1640 @ Stormwind City, 76.8, 52.6 | Bartleby (level 10) attacks as soon as you accept. Fight him until he gives up: he does not die. Be at full health first; lost? Wait for him to reset and take the quest again',
            'T 1640 | Bartleby',
            'A 1665 | Bartleby: he hands over his mug',
            'T 1665 | Harry Burlguard. Bartleby\'s Mug is the quest that gives Defensive Stance: put the stance on your bar. Battle Stance stays your leveling stance; Defensive Stance is for tanking and for fights that are going badly',
            'A 1666 | Harry Burlguard: Marshal Haggard. Keep it: Haggard lives at the Eastvale Logging Camp, which you pass on the road to Redridge at 17 (segment 06)',
            'TRAIN %s | %s, a few steps south-east of the tavern: anything you did not learn in Goldshire (Bloodrage, Sunder Armor, Taunt). Buy food in the city before you leave' % (WU, WU_WHO),
        ]),
        ('sub', 'Level 12 already? Then your class trainer here is an optional stop; otherwise you train in Ironforge next segment',
         'Level 12 already? Then Wu Shen in Old Town (80.5, 59.9) is an optional stop for Overpower and Shield Bash; otherwise you train in Ironforge next segment'),
    ],
    5: [('carry', '1666')],
    6: [
        ('carry', '1666'),
        ('line', 'A 244 ', [
            'T 1666 @ Elwynn Forest, 84.6, 69.4 | From the Dwarven District leave Stormwind by the main gate and follow the road east through Goldshire to the Eastvale Logging Camp. Marshal Haggard stands at the house on the east side of the camp',
            'A 1667 | Marshal Haggard',
            'C 1667 @ Elwynn Forest, 89.4, 79.0 | Dead-Tooth Jack\'s camp is south-east of Eastvale, in the corner of Elwynn south of the road, close to the Redridge border. Kill Jack (level 11) and the Defias with him, loot Dead-tooth\'s Key from him and open the strongbox in the camp for Marshal Haggard\'s Badge',
            'T 1667 | Marshal Haggard, back at Eastvale. This ends the level 10 warrior chain',
            'A 244 | Back on the road, east to the Three Corners crossroads just inside Redridge. Guard Parker walks the road there.',
        ]),
        ('sub', 'and your class\'s level 20 quests start there', 'and the warrior\'s level 20 quest starts there'),
        ('line', 'N Your class has its own quests at about this level',
         ['A 1698 %s | Kelv Sternhammer: Yorus Barleybrew, the warrior\'s level 20 quest. Yorus is in Lakeshire, where the next segment goes' % KELV]),
    ],
    7: [
        ('carry', '1698'),
        ('after', 'A 34 ', [
            'T 1698 @ Redridge Mountains, 21.5, 44.7 | Yorus Barleybrew, on the west side of Lakeshire (follow the arrow)',
            'A 1699 | Yorus Barleybrew: The Rethban Gauntlet. It is timed and fails if you die and release, so take it only when you are at full health with your bags sold',
            'C 1699 @ Redridge Mountains, 14.1, 24.7 | Run north-west out of Lakeshire into the Redridge Canyons: the Rethban Caverns are the cave in the north-west corner. Go in as far as the first fork until the objective ticks. Redridge gnolls (17-21) are on the way and in the cave: Charge, kill what blocks the tunnel and do not stop for the rest. Then run straight back',
            'T 1699 @ Redridge Mountains, 21.5, 44.7 | Yorus Barleybrew, before the timer runs out',
            'A 1702 | Yorus Barleybrew: The Shieldsmith. The Cask of Scalder goes to Furen Longbeard in Stormwind. Keep it: the route is next in the Dwarven District at 28 (segment 11)',
        ]),
    ],
    8: [('carry', '1702')],
    9: [('carry', '1702')],
    10: [('carry', '1702')],
    11: [
        ('carry', '1702'),
        ('after', 'N Take the Deeprun Tram from Tinker Town to Stormwind', [
            'T 1702 @ Stormwind City, 64.6, 37.2 | Furen Longbeard, at the forge in the Dwarven District, close to the tram exit',
            'N Furen offers Fire Hardened Mail next: optional, not in this route | It wants four drops: a Scorched Spider Fang (Leech and Cave Stalkers, Wetlands), a Charred Horn and a Galvanized Horn (chimaeras and the Chimaera Matriarch, Stonetalon Mountains) and a Vial of Phlogiston (Roogug, in the Razorfen Kraul dungeon). It leads on to more warrior armor from Grimand Elmore. Take it only if you run Razorfen Kraul',
        ]),
    ],
    12: [
        ('line', 'N Your class has its own quests at about this level',
         ['A 1718 %s | Kelv Sternhammer: The Islander, the warrior\'s level 30 quest. Klannoc Macleod lives on Fray Island off Ratchet: you carry this until the route walks to Ratchet at 35 (segment 14)' % KELV]),
    ],
    13: [('carry', '1718')],
    14: [
        ('carry', '1718'),
        ('after', 'F Ratchet ', [
            'T 1718 @ The Barrens, 68.6, 49.2 | Fray Island is the small island with the fighting ring, south-east of Ratchet: swim out from the shore south of the dock. Klannoc Macleod stands beside the ring',
            'A 1719 | Klannoc Macleod: The Affray',
            'C 1719 @ The Barrens, 68.6, 48.7 | Step on the grate in the middle of the ring. Affray Challengers (26-27) come at you one after the other, then Big Will (33). At 35 this is safe: use Victory Rush after each kill, and bandage if there is a pause before Big Will',
            'T 1719 | Klannoc Macleod. In Classic this hand-in teaches Berserker Stance; in Forever the trainer is reported to teach it at 30',
            'N Klannoc offers The Windwatcher next: optional, not in this route | It sends you to Bath\'rah the Windwatcher in the Alterac Mountains (80.5, 66.9) for the Whirlwind weapon: he wants 8 Liferoot, 30 Bloodscalp Tusks and an Essence of the Exile, and then you must kill Cyclonian, a level 40 elite. Worth doing with a healer or a group at about 38-40; alone it is too hard',
        ]),
    ],
    25: [
        ('after', 'TRAIN ', [
            'N Kelv Sternhammer has a level 50 warrior quest, A Troubled Spirit: optional, not in this route | It leads to the Fallen Hero of the Horde at the entrance of the Blasted Lands (34.3, 66.1) and ends in the Sunken Temple dungeon. The route does not go back to the Blasted Lands',
        ]),
    ],
}

# the first TRAIN step of segment 01 gets the hand-in of the letter in front of it
EDITS[1][1] = ('before', 'TRAIN %s | Llane Beshere, the warrior trainer: learn everything' % LLANE,
               ['T 3100 %s | Llane Beshere, the warrior trainer, in the front part of the abbey' % LLANE])


def interrupt_tool(level):
    if level < 11:
        return None
    if level < 12:
        return 'Shield Bash (level 12, with a shield on)'
    if level < 38:
        return 'Shield Bash if you carry a shield'
    return 'Pummel'


def rules(level):
    tool = interrupt_tool(level)
    r = []
    if tool:
        r += [(r'([Ii])nterrupt or stun (.+?) if your class can', r'\1nterrupt \2 with ' + tool),
              (r'interrupt it if your class can, otherwise kill them fast', 'it does nothing to a warrior'),
              (r"stop the healers' heals if your class can", "stop the healers' heals with " + tool)]
    r += [
        (r' \(if you have a pet, send it first\), slow or disable the others if your class can,',
         ', put Thunder Clap and Demoralizing Shout on all three,'),
        (r'slow or stun him and keep your distance if your class can', 'keep Demoralizing Shout and Thunder Clap on him'),
        (r'slow or stun him if your class can, and beat him', 'Hamstring him so he cannot run, and beat him'),
        (r'slow or stun him if your class can to get room to heal or bandage, and use a potion if you have one',
         'keep Demoralizing Shout and Thunder Clap on him, and use a healing potion if you have one'),
        (r'slow him and keep him at range if your class can, and heal or drink a potion early; if you have a pet, send it first',
         'keep Demoralizing Shout and Thunder Clap on him, and use a healing potion early'),
        (r' \(and full mana, if you use it\)', ''),
        (r' \(if you have a pet, send it first\)', ''),
        (r'fight him alone with everything your class has', 'fight him alone: Charge, Rend, Heroic Strike'),
        (r'cure it if your class can, otherwise bandage and eat', 'a warrior cannot cure it, so bandage and eat'),
        (r'you may not be able to heal (him|her)', r'you cannot heal \1'),
        (r' \(they drain mana: kill them fast\)', ''),
        (r' at full health and mana', ' at full health'),
        (r' Felhounds drain mana: kill them fast\.', ''),
        (r'heal or bandage early', 'bandage or use a healing potion early'),
        (r',? and use Escape Artist if he roots you', ''),
        (r'([Ee])at, drink or bandage', r'\1at or bandage'),
        (r' \(Escape Artist breaks them\)', ''),
        (r'; Escape Artist breaks the roots', ''),
        (r'\(slow or stun it if your class can\)',
         '(Hamstring it)' if level >= 8 else '(Hamstring it once you have it, at level 8)'),
        (r'([Ee])at and drink', r'\1at'),
        (r'food, drink and', 'food and'),
        (r'food and (water|drink)', 'food'),
        (r'Buy food here\.', 'Buy food here.'),
    ]
    return r


def one(lines, prefix):
    i = [k for k, l in enumerate(lines) if l.startswith(prefix)]
    assert len(i) == 1, (prefix, len(i))
    return i[0]


def main():
    out_dir = os.path.join(ROOT, 'routes', DST)
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, '*.route')):
        os.remove(old)
    left = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'routes', SRC, '*.route'))):
        base = os.path.basename(f)
        n = int(base[:2])
        lines = open(f, encoding='utf-8').read().split('\n')
        level = int(next(l for l in lines if l.startswith('@start-level')).split()[1])

        # header
        i = [k for k, l in enumerate(lines) if l.startswith('# Human, any class')]
        assert i, base
        lines[i[0]] = ('# Human Warrior. Made from routes/human/%s by tools/derive_warrior.py (never edit by hand): the\n'
                       '# warrior class quests, the warrior trainers and warrior fight hints are added. The source file says:\n'
                       % base) + lines[i[0]]
        lines = '\n'.join(lines).split('\n')

        # TRAIN steps
        new = list(TRAIN.get(n, []))
        idx = [k for k, l in enumerate(lines) if l.startswith('TRAIN')]
        if n != 4:
            assert len(idx) == len(new), (base, len(idx), len(new))
            for k, t in zip(idx, new):
                lines[k] = t

        # per-file edits
        for op in EDITS.get(n, []):
            if op[0] == 'sub':
                s = '\n'.join(lines)
                assert s.count(op[1]) == 1, (base, op[1], s.count(op[1]))
                lines = s.replace(op[1], op[2]).split('\n')
            elif op[0] == 'carry':
                k = one(lines, '@carry')
                lines[k] = lines[k].rstrip() + ',' + op[1]
            else:
                k = one(lines, op[1]) if op[0] != 'after' or op[1] != 'TRAIN ' else \
                    [j for j, l in enumerate(lines) if l.startswith('TRAIN ')][0]
                if op[0] == 'line':
                    lines[k:k + 1] = op[2]
                elif op[0] == 'before':
                    lines[k:k] = op[2]
                else:
                    lines[k + 1:k + 1] = op[2]

        # class-neutral wording -> warrior wording (step lines only)
        rs = rules(level)
        for k, l in enumerate(lines):
            if l.startswith('#') or l.startswith('@'):
                continue
            for pat, rep in rs:
                l = re.sub(pat, rep, l)
            lines[k] = l
            if re.search(r'your class|class can|class-specific|classes|a pet\b|\bdrink\b|\bmana\b(?! burn)|Escape Artist|class trainer', l):
                left.append('%s: %s' % (base[:2], l[:230]))
        open(os.path.join(out_dir, base), 'w', encoding='utf-8', newline='').write('\n'.join(lines))
        print('wrote', DST, base)
    if left:
        print('\nLEFT OVER (class-neutral wording that no rule covers):')
        for l in left:
            print('  ' + l)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
