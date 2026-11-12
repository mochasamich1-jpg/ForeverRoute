"""Polite scraper for foreverchanges.pro quest lists and quest pages (personal research use).

Usage: python -I scrape_fc.py <out_dir> [--side alliance] [--dungeons]
  --side alliance   fetch the quest pages an Alliance character can take (default: Horde)
  --dungeons        also fetch the pages of dungeon quests (for routes/dungeons/*.dungeon)
Writes <out_dir>/zones.json and <out_dir>/quests/<id>.json (resumable).
"""
import html as H
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = 'https://foreverchanges.pro'
UA = {'User-Agent': 'Mozilla/5.0 (personal leveling-route research; 1 req/s)'}
DELAY = 1.1

ZONES = [
    # Horde questing zones 1-60 (+ new Forever zones)
    'tirisfal-glades', 'undercity', 'silverpine-forest', 'the-barrens', 'orgrimmar', 'durotar',
    'mulgore', 'thunder-bluff', 'stonetalon-mountains', 'ashenvale', 'hillsbrad-foothills',
    'alterac-mountains', 'thousand-needles', 'stranglethorn-vale', 'desolace', 'arathi-highlands',
    'riverglades', 'dustwallow-marsh', 'swamp-of-sorrows', 'badlands', 'tanaris', 'feralas',
    'the-hinterlands', 'searing-gorge', 'ungoro-crater', 'azshara', 'felwood', 'winterspring',
    'western-plaguelands', 'eastern-plaguelands', 'burning-steppes', 'blasted-lands', 'silithus',
    'moonglade', 'wetlands', 'thoradins-wall', 'city-of-dalaran', 'excavation-site-wetlands',
    'shendralas', 'zephras-isle', 'darkspear-islands',
    # Alliance zones (added for the Dwarf Shaman route)
    'dun-morogh', 'ironforge', 'loch-modan', 'elwynn-forest', 'stormwind-city', 'westfall',
    'redridge-mountains', 'duskwood', 'darkshore', 'darnassus', 'teldrassil', 'deeprun-tram',
    'blackrock-mountain',
    # class / misc
    'mage', 'shaman', 'druid', 'camping', 'first-aid', 'special', 'reputation', 'epic',
    # dungeons (listed so their quests can be EXCLUDED)
    'ragefire-chasm', 'wailing-caverns', 'shadowfang-keep', 'blackfathom-deeps', 'razorfen-kraul',
    'gnomeregan', 'scarlet-monastery', 'razorfen-downs', 'uldaman', 'zulfarrak', 'maraudon',
    'sunken-temple', 'blackrock-depths', 'blackrock-spire', 'the-hall-of-thanes',
    'ruins-of-lordaeron', 'ruins-of-lordaeron-dungeon', 'excavation-site-wetlands-dungeon',
    'dire-maul', 'scholomance', 'stratholme', 'the-deadmines', 'the-stockade',
    'city-of-dalaran-dungeon', 'the-drowned-city', 'kroldok-stronghold', 'alcaz-prison', 'blackmaw-hold',
    'the-shapers-terrace', 'zulfarrak-dungeon',
]
DUNGEON_ZONES = set(ZONES[ZONES.index('ragefire-chasm'):])


def get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=40).read().decode('utf-8', 'replace')
        except Exception as e:  # noqa
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))


def text_of(fragment):
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', fragment, flags=re.S)
    t = H.unescape(re.sub(r'<[^>]+>', '\n', t))
    return re.sub(r'\n\s*\n+', '\n', t)


def parse_zone(h):
    rows = []
    for m in re.finditer(r'<div class="il-row qs-row">(.*?)(?=<div class="il-row qs-row">|</section>|<footer)', h, re.S):
        r = m.group(1)
        idm = re.search(r'href="/quest/(\d+)/[^"]*">([^<]*)</a>', r)
        if not idm:
            continue
        status = re.search(r'it-status-(\w+)', r)
        sides = re.findall(r'alt="(Horde|Alliance)"', r)
        nums = re.findall(r'<span class="il-num[^"]*">(?:<b[^>]*>)?([\d,]*)', r)
        rows.append({
            'id': int(idm.group(1)),
            'name': H.unescape(idm.group(2)),
            'status': status.group(1) if status else None,
            'sides': sides or ['Horde', 'Alliance'],
            'level': int(nums[0]) if len(nums) > 0 and nums[0] else None,
            'reqLevel': int(nums[1]) if len(nums) > 1 and nums[1] else None,
            'xp': int(nums[2].replace(',', '')) if len(nums) > 2 and nums[2] else None,
            'elite': 'Elite' in r or 'elite' in r,
        })
    return rows


def parse_quest(h, qid):
    out = {'id': qid}
    pins = []
    for m in re.finditer(r'aria-label="(Start|End): ([^"]*?), ([\d.]+), ([\d.]+)"', h):
        pins.append({'role': m.group(1), 'name': H.unescape(m.group(2)), 'x': float(m.group(3)), 'y': float(m.group(4))})
    out['pins'] = pins
    out['dots'] = [[float(a), float(b)] for a, b in re.findall(r'class="qp-dot" style="left:([\d.]+)%;top:([\d.]+)%"', h)]
    txt = text_of(h)
    i = txt.find('Quests\n › \n')
    body = txt[i:] if i >= 0 else txt
    j = body.find('\nClasses\nWarrior')
    body = body[:j] if j > 0 else body
    out['text'] = body[:6000]
    lv = re.search(r'A level (\d+) quest for (the Horde|the Alliance|both sides|[^,.]+)(?:, from level (\d+))?', body)
    if lv:
        out['level'] = int(lv.group(1))
        out['side'] = lv.group(2)
        out['reqLevel'] = int(lv.group(3)) if lv.group(3) else None
    zone = re.search(r'Quests\n › \n([^\n]+)\n', body)
    out['zone'] = zone.group(1).strip() if zone else None
    out['new'] = 'New in Forever' in body
    out['changed'] = 'Changed in Forever' in body
    return out


def main():
    out = Path(sys.argv[1])
    (out / 'quests').mkdir(parents=True, exist_ok=True)
    zfile = out / 'zones.json'
    zones = json.loads(zfile.read_text(encoding='utf-8')) if zfile.exists() else {}
    for z in ZONES:
        if z in zones:
            continue
        try:
            zones[z] = {'dungeon': z in DUNGEON_ZONES, 'quests': parse_zone(get(f'{BASE}/quests/{z}'))}
        except Exception as e:  # noqa
            zones[z] = {'dungeon': z in DUNGEON_ZONES, 'quests': [], 'error': str(e)}
        zfile.write_text(json.dumps(zones, indent=1), encoding='utf-8')
        print('zone', z, len(zones[z]['quests']), flush=True)
        time.sleep(DELAY)
    side = 'Alliance' if '--side' in sys.argv and sys.argv[sys.argv.index('--side') + 1].lower() == 'alliance' else 'Horde'
    want = []
    for z, info in zones.items():
        if info['dungeon'] and '--dungeons' not in sys.argv:
            continue
        for q in info['quests']:
            if side in q['sides']:
                want.append(q['id'])
    want = sorted(set(want))
    print('quest pages wanted', len(want), flush=True)
    for n, qid in enumerate(want, 1):
        f = out / 'quests' / f'{qid}.json'
        if f.exists():
            continue
        try:
            rec = parse_quest(get(f'{BASE}/quest/{qid}'), qid)
        except Exception as e:  # noqa
            rec = {'id': qid, 'error': str(e)}
        f.write_text(json.dumps(rec, indent=1), encoding='utf-8')
        if n % 50 == 0:
            print('quests', n, '/', len(want), flush=True)
        time.sleep(DELAY)
    print('done', flush=True)


if __name__ == '__main__':
    main()
