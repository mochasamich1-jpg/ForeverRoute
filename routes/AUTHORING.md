# How to write a Forever Route segment

You are writing one segment of a personal 1-60 leveling route for **WoW: Forever** (client 1.60.1).
There is one route per race/class, each in its own folder:

| route key | folder | character |
|---|---|---|
| `undead-mage` | `routes/undead-mage/` | Horde Undead Mage (finished, reviewed) |
| `orc-shaman` | `routes/orc-shaman/` | Horde Orc Shaman |
| `dwarf-shaman` | `routes/dwarf-shaman/` | Alliance Dwarf Shaman |
| `skyborne-druid` | `routes/skyborne-druid/` | Alliance (High Order) Skyborne Druid |
| `skyborne-mage` | `routes/skyborne-mage/` | Alliance (High Order) Skyborne Mage |
| `human-mage` | `routes/human-mage/` | Alliance Human Mage |
| `gnome` | `routes/gnome/` | Alliance Gnome, any class |
| `human-warlock` | `routes/human-warlock/` | Alliance Human Warlock |
| `human-warrior` | `routes/human-warrior/` | Alliance Human Warrior (generated, see below) |
| `dwarf` `human` `night-elf` `skyborne` | `routes/<key>/` | Alliance, any class, one per race |

The route is loaded by a custom addon that auto-ticks steps from quest state and points an arrow at
coordinates. Solo player, first playthrough.

## Hard rules
- Quest-only. **No dungeons, no dungeon quests** in the `.route` files (dungeons live in `routes/dungeons/`, see below), no raids. Skip ELITE / group quests unless the
  plan says they are trivially soloable.
- Only quests the route's race/class can take (Horde for the first two routes, Alliance for `dwarf-shaman`). Class quests: that class only. Race quests:
  that race only (or any-race Horde quests). The validator checks race/class masks per route.
- Quest log limit 40 (what the 1.60.1 client reports; 23 were held at once in play). Still hand quests in when you
  pass their NPC: a short log is easier to follow.
- Efficient: accept everything at a hub before leaving, batch objectives that share an area into one
  `C` step, turn in everything when back at the hub, use hearthstone / flight paths / zeppelins.
- TUGs (All Rights Reserved) may be used for route ORDER and knowledge, but write every instruction
  in your own words. Never copy TUGs text.
- Write instructions plainly and briefly ("Kill the spiders in the cave", not lore).

## File format (`routes/<route>/NN-name.route`)
```
@segment 10-14 Silverpine Forest
@start-level 10
@carry 445            # quests already in the log when this segment starts (from earlier segments)
@done 375,361         # quests that earlier segments turned in that matter for prerequisites here
A 445                 # accept quest(s):            A 435,449
C 435                 # complete objectives:         C 437,447,429  (several quests done together)
C 1359:2              # a single objective (1-based index) of a quest
T 435                 # turn in quest(s)
G Silverpine Forest, 45.6, 42.6 | Talk to Karos Razok and take the flight path
F The Sepulcher       # get a flight path (manual tick)
FLY Undercity         # fly somewhere (manual tick)
S The Sepulcher       # bind hearthstone here (auto-ticks when bound; text should match the inn's town name)
H Undercity           # use hearthstone (manual tick)
L 14                  # grind until level 14 (only when really needed)
TRAIN | Orgrimmar, Valley of Wisdom: learn your level 12 spells
N Take the zeppelin from the tower outside Undercity to Orgrimmar
```
- `| text` at the end of any line adds an instruction shown under the step. Use it for anything the
  player needs to know (which mobs, where the item drops, "the cave entrance is east", etc.).
- A/T/C steps get coordinates automatically from Questie + ForeverChanges data. Add an override
  `@ Zone Name, x, y` before the `|` only when you know the auto data is wrong or missing
  (e.g. new Forever quests whose giver location you found, or an objective area).
- Zone names must be the in-game names (e.g. `Tirisfal Glades`, `Undercity`, `The Barrens`).

## Data
- Zone digests per route: `research/digest/<route>/<zone>.md` (every quest that route's race/class
  can take: id, name, level, required level, Forever XP, NEW/CHANGED/ELITE/class flags, start/end
  NPC with coordinates, prerequisites, next quest in chain, objective text). Dungeon digests are
  marked DUNGEON. Class quests are in `<class>.md` (e.g. `research/digest/orc-shaman/shaman.md`).
- Raw ForeverChanges quest pages (parsed): `research/fc/quests/<id>.json` (pins = start/end with x,y;
  dots = objective map points; text = full page text incl. objectives and description).
- Questie data as JSON: `research/json/quests.json` (keys: name, startedBy, finishedBy,
  requiredLevel, questLevel, requiredRaces, requiredClasses, objectivesText, preQuestSingle,
  preQuestGroup, nextQuestInChain, exclusiveTo, breadcrumbForQuestId...), `npcs.json`, `objects.json`, `items.json`.
- TUGs Guidelime Horde route: `research/tugs/x/GuideLime_TUGs_Forever/TUGs/Horde/*.lua`
  ([QA id] accept, [QC id] complete, [QT id] turn in, [A Class] / [A Race] = only for that class/race,
  [G x,y Zone] goto). Its files chain by [NX next guide]. Orc path: `1-6 Valley of Trials` ->
  `6-9 Durotar` -> `9-12 Orgrimmar` -> `12-14 The Barrens` -> the shared Horde files from there.
  Undead path: Deathknell -> Tirisfal -> Silverpine 10-12 -> Barrens 12-14 -> shared.
- The finished Undead Mage route (`routes/undead-mage/*.route`, plan in `routes/undead-mage/PLAN.json`)
  already replaces every TUGs dungeon block with open-world questing and was reviewed twice. Its
  quest choices from about level 14 on are valid for any Horde race; its travel is NOT (see below).

## Orc Shaman specifics (`orc-shaman`)
- Starts in the Valley of Trials (Durotar). Hearthstone starts bound there.
- **No teleports or portals.** Travel only by foot, flight paths, hearthstone, zeppelins and boats:
  Orgrimmar tower (just outside Orgrimmar's west gate area, Durotar ~50,13) <-> Undercity (Tirisfal tower
  ~60,58) and <-> Grom'gol (Stranglethorn ~31,29); Undercity <-> Grom'gol; Ratchet <-> Booty Bay boat.
  Every Kalimdor <-> Eastern Kingdoms crossing costs real time, so group EK work into as few trips as
  possible and never hop continents just to train. The Undead Mage route hops a lot because mages
  teleport; re-sequence those parts.
- **Astral Recall** (learned at level 30): a second hearthstone (same bind location, 15 min cooldown).
  Use it like `H`: `N Cast Astral Recall (back to <town>)`. Before 30 there is only the hearthstone.
- **Ghost Wolf** (level 20 spell, +40% run speed outdoors) is the travel form until the mount.
- **Shaman trainers**: Orgrimmar Valley of Wisdom (Kardris Dreamseeker 38.8,36.4; Sian'tsu 37.8,36.5;
  Sagorne Creststrider 38.7,35.9), Thunder Bluff Pools of Vision under Spirit Rise, beside Apothecary Zamah (Beram/Siln/Tigor Skychaser ~22-24,19-21),
  Razor Hill (Swart 54.4,42.6), Valley of Trials (Shikrik 42.4,69.0), Bloodhoof Village (Narm Skychaser,
  Mulgore 47.4,62.5), **Stonard (Haromm, Swamp of Sorrows 48.2,57.9)** - the only one in the Eastern
  Kingdoms. Train every 2 levels when you pass a trainer; it is fine to train 2-4 levels at once.
  There is no shaman trainer in Undercity, Tarren Mill, Hammerfall, Kargath or Grom'gol.
- **Class quests** (all in `research/digest/orc-shaman/shaman.md`):
  - 4: Call of Earth 1516 -> 1517 -> 1518 (Canaga Earthcaller, Valley of Trials; Spirit Rock) = Earth totem.
  - 10: Call of Fire 2983 (Swart, Razor Hill) or 1522 (Searn Firewarder, Orgrimmar) -> 1524 Kranal Fiss
    (Barrens 56.0,19.9) -> 1525 Telf Joolam (Durotar 38.5,59.0; Fire Tar from Razormane in the Barrens +
    Reagent Pouch from Burning Blade in Durotar) -> 1526 Brazier of the Dormant Flame (fight Minor
    Manifestation of Fire) -> 1527 back to Kranal Fiss = Fire totem. Take only ONE of the four
    starters (they are mutually exclusive).
  - 20: Call of Water 1528 (Orgrimmar) / 2985 (Razor Hill) -> 1530 Islen Waterseer (Barrens 65.8,43.8)
    -> 1535/1536 Brine (Southern Barrens 43.4,77.4; one waterskin at Brine's watering hole, one at the
    Tarren Mill well in Hillsbrad) -> 1534/220 -> 63 Brazier of Everfount (Silverpine 38.3,44.6,
    Corrupt Manifestation of Water) -> 100 -> 96 back to Islen = Water totem. Read the digest for the
    exact chain order. Fits naturally into a Hillsbrad/Silverpine trip.
  - 30: Call of Air 1531 (Searn Firewarder, Orgrimmar). Forever also lists a NEW Call of Air 96136
    (level 35) with no giver data: if it is not resolvable, add an `N` step at the trainer telling the
    player to take any new shaman quest offered so the logger records it.
  - 50+: Elemental Mastery 8410 (Haromm, Stonard) and follow-ups; include only if soloable and on the way.
- **Mount at 40**: Wolf Riding from Kildar (Orgrimmar Valley of Honor 69.4,13.1); wolves from
  Ogunaro Wolfrunner next to him. Plan a gold reminder before 40.
- Combat hints in `| text` must suit a shaman (melee + shocks + totems + self-heals): e.g. Earth Shock
  to interrupt casters, Earthbind Totem to stop runners, Stoneclaw Totem for adds, Healing Wave between
  pulls, Frost Shock (20+) to kite. Never mention Frost Nova, Polymorph, Blink, Blizzard, conjured
  water/food, Runes of Teleportation, mage trainers or portals.

## Dwarf Shaman specifics (`dwarf-shaman`, ALLIANCE)
Dwarf Shaman is a new race/class combination in Forever (foreverchanges.pro/racials). This is the first
Alliance route: nothing from the two Horde routes can be reused except neutral-hub quests (Booty Bay,
Gadgetzan, Ratchet, Everlook, Cenarion Hold, Marshal's Refuge, Light's Hope...) that both factions can take.
- **Only Alliance quests.** The validator rejects Horde-only quests and anything a Dwarf or a Shaman cannot
  take. Zone digests: `research/digest/dwarf-shaman/<zone>.md`. TUGs Alliance order:
  `research/tugs/x/GuideLime_TUGs_Forever/TUGs/Alliance/*.lua` (dwarf start: `1-6 Coldridge Valley` ->
  `6-9 Dun Morogh` -> `9-11 Dun Morogh&Loch Modan` -> the shared Alliance files). TUGs runs dungeons;
  replace every dungeon block with open-world questing (dungeons are added separately, see below).
- Starts in Coldridge Valley (Dun Morogh). Hearthstone starts bound in Anvilmar.
- **No teleports or portals.** Travel by foot, gryphon/hippogryph flight paths, hearthstone and:
  Deeprun Tram Ironforge (Tinker Town) <-> Stormwind (Dwarven District); boats Menethil Harbor <-> Auberdine
  (Darkshore), Menethil Harbor <-> Theramore (Dustwallow Marsh), Auberdine <-> Rut'theran (Darnassus),
  Booty Bay <-> Ratchet. (Boat and tram routes are Classic knowledge, not re-checked in 1.60.1: keep the
  wording simple, e.g. "Take the boat from Menethil Harbor to Auberdine".) Every Eastern Kingdoms <->
  Kalimdor crossing costs real time: group Kalimdor work into as few trips as possible.
- Flight masters (Questie): Ironforge Gryth Thurden 55.5,47.7; Thelsamar Thorgrum Borrelson (Loch Modan
  33.9,51.0); Menethil Shellei Brondir (Wetlands 9.5,59.7); Stormwind Dungar Longdrink 71.0,72.5; Sentinel
  Hill Thor (Westfall 56.6,52.6); Lakeshire Ariena Stormfeather (Redridge 25.5,59.4); Refuge Pointe Cedrik
  Prose (Arathi 45.7,46.1); Auberdine Caylais Moonfeather (Darkshore 36.3,45.6); Astranaar Daelyshia
  (Ashenvale 34.4,48.0); Booty Bay Gyll (27.5,77.8). Look others up in `research/json/npcs.json`.
- **Astral Recall** (30) is a second hearthstone; **Ghost Wolf** (20) is the travel form until the mount.
- **Shaman trainers** (from the ForeverChanges class quest pages; these NPCs are NOT in the Questie data, and
  whether more Alliance shaman trainers exist is unverified): Teo Hammerstorm (Anvilmar, Dun Morogh 28.8,66.2),
  Ingrid Dunwald (Kharanos, Dun Morogh 47.4,52.0), Eldrun Stormbreaker (Ironforge 47.6,13.5). Train every 2
  levels when passing Ironforge or Kharanos; never cross a continent just to train. Use
  `TRAIN | Ironforge: Eldrun Stormbreaker (47.6, 13.5)` style text.
- **Class quests** (all in `research/digest/dwarf-shaman/shaman.md`; new Forever quests, ids 9xxxx):
  - 1: Archaic Rune 98581 (Sten Stoutarm -> Teo Hammerstorm, Anvilmar).
  - 4: Call of Earth 94373 (2 Frostmane/Iceclaw Bear Pendants) -> 94374 (drink Earth Sapta at the Spirit
    Stone, Minor Manifestation of Earth at Dun Morogh 25.0,61.9) -> 94375 back to Teo = Earth totem.
    (96243 is a level 10 pointer from Ingrid to Teo for shamans who skipped it: not needed.)
  - 10: Call of Fire 94449 (Ingrid Dunwald, Kharanos) -> Bruegs Kindleborn (Dun Morogh 87.6,43.7, far east)
    -> 94465 to Braldir Ashmantle (Loch Modan 32.1,66.1) -> 94466 (1 Fire Tar + 1 Reagent Pouch: read the
    quest page for where they drop) -> 94467 (Minor Manifestation of Fire, Brazier of the Dormant Flame at
    Loch Modan 31.9,64.5) -> 94468 back to Bruegs = Fire totem.
  - 20: Call of Water 94494 (Eldrun Stormbreaker, Ironforge) -> Norric Lochthane (Loch Modan 41.9,19.0) ->
    94495 to Hervdana Saegrund (Wetlands 65.7,76.4) -> 94497 (waterfall below her cave) -> 94499 (Stonewatch
    Falls, Redridge) -> 94500 (Astranaar, Ashenvale) -> 94501 back to Norric -> 94502 (Stendel's Pond,
    Westfall) -> 94503 -> 94505 back to Norric = Water totem. Spread the waterskins over trips the route
    makes anyway (Redridge, Ashenvale, Westfall).
  - 30: Call of Air 94789 (Eldrun, Ironforge) -> Veyric Thunderhame (Arathi Highlands 59.8,27.6). The rest of
    that chain (96264 Elemental Aid needs Razorfen Kraul, then 79358 / 96135 / 96016) is dungeon-gated:
    leave it out of the quest-only route.
- **Mount at 40**: Ram Riding from Ultham Ironhorn, rams from Veron Amberstill (Amberstill Ranch, Dun Morogh
  63.9,50.1). Plan a gold reminder before 40.
- Combat hints as for the Orc Shaman (melee + shocks + totems + self-heals). Dwarf racial: Stoneform removes
  poison, disease and bleeds.

## Skyborne Druid specifics (`skyborne-druid`, ALLIANCE)
Skyborne is the new Forever race; the Alliance side ("High Order Skyborne") can be a Druid
(foreverchanges.pro/racials). Segments 01-04 are new (Zephras Isle 1-14, then Dalaran -> Stormwind -> Moonglade
-> Loch Modan I). Segments 05-25 are the Dwarf Shaman route's segments 04-24 (same quests, same order, same
hearth binds) with everything shaman- or dwarf-specific replaced. Keep it that way: do not re-plan the quest
order, only adapt it.
- **Only quests an Alliance Skyborne Druid can take.** The validator knows the profile; shaman quests
  (Call of Water 94494-94505, Call of Air 94789...) are errors. Remove their steps AND any travel that was
  only made for them; keep travel that also serves other quests.
- **No Ghost Wolf, no Astral Recall, no totems, no shocks.** Before level 30 a druid has no travel form:
  where the Dwarf text says "Ghost Wolf", just walk (levels below 30) or say "Travel Form" (30-39).
  Every `N Cast Astral Recall ...` step must become real travel: a flight, a walk, or the Hearthstone when it
  has clearly not been used for an hour in that segment. Say which in the segment's header comment.
- **Travel Form** (level 30, from the trainer): +40% speed outdoors, instant. **Aquatic Form** (16) for swims.
- **Teleport: Moonglade** (learned at 12-14 in segment 04): free trip to Nighthaven from anywhere. Loganaar,
  the druid trainer, stands at Moonglade 52.5, 40.6 and Dendrite Starblaze at 56.2, 30.6. There is NO verified
  way back for this character except the Hearthstone (the Nighthaven flight master needs neighbouring flight
  paths the route may not have yet), so only write a Moonglade training trip where the Hearthstone is ready and
  the bind town is where the route wants to be next: `N Cast Teleport: Moonglade` /
  `TRAIN @ Moonglade, 52.5, 40.6 | Loganaar ...` / `H <bind town>`.
- **Druid trainers** (Questie + ForeverChanges): Stormwind, the Park: Sheldras Moontree (Stormwind City
  35.8, 67.4); Moonglade: Loganaar (52.5, 40.6); Zephras Isle (Xyton Silverwind, Lotheluum Starbreeze).
  Darnassus (Cenarion Enclave) is Classic knowledge, not re-checked. There is NO druid trainer in Ironforge:
  every Dwarf-route `TRAIN ... Ironforge: Eldrun Stormbreaker` stop must move. If the same segment passes
  Stormwind, train at Sheldras there; otherwise use the Moonglade trip above when the Hearthstone allows it,
  or drop that stop and train two or three levels' worth at the next one. Never cross a continent to train.
  A trip to Ironforge that existed ONLY to train must be removed or redirected, not kept.
- **Class quests**: Bear Form is learned on Zephras Isle (segment 03). At 14 and 16 the Classic night-elf
  quests (Cure Poison 6121-6125, Aquatic Form 27/29/272/5061) are race-masked to Night Elves in the data and
  NOT confirmed for Skyborne: at the first training stop at 14+ and at 16+ add an `N` step telling the player
  to take whatever class quest the trainer or Dendrite offers (the logger records it). Cat Form (from 20): per the
  ForeverChanges Cat Form guide the Alliance Skyborne chain starts and ends with Mathrengyl Bearwalker in
  Darnassus (35.2, 8.0): 98393 The Great Cat Spirit -> Teleport: Moonglade -> Dendrite Starblaze (Moonglade
  56.2, 30.6) -> 98341 The Great Windborne Cat Spirit -> Avatar of Saeyleenan (Moonglade 44.0, 73.5) ->
  98404 (three relics in the Stormrage Barrow Dens, door at Moonglade 71.2, 61.5; the statue at the door
  hides you for five minutes) -> 98738 back to Dendrite -> 98397 To Darnassus (Cat Form is taught at this
  hand-in). All need `@ Zone, x, y` overrides. It is placed once, in segment 09 (Darkshore, one boat from
  Darnassus), about level 24-25; before that the druid has no Cat Form. Nature's Grasp is a trained spell
  from level 10 in Forever (not a talent).
- **Mount at 40**: the Skyborne riding trainer and mount vendor are NOT in our data (unverified). Replace
  the Dwarf route's ram purchase (Amberstill Ranch) with an `N` step saying so: "ask a city guard or other
  Skyborne where your riding trainer is; have 100 gold ready". Remove travel that only went to the ram vendor.
- **Combat hints** must suit a druid: caster form (Wrath, Moonfire, Starfire from 20, Entangling Roots
  outdoors, Rejuvenation / Regrowth / Healing Touch), Bear Form from 10 (Maul, Swipe, Demoralizing Roar,
  Bash from 14 = stun / interrupt), Cat Form from segment 09 on (Claw, Rake, Rip, Prowl to sneak past things, Dash from
  26), Hibernate from 18 (beasts and dragonkin), Faerie Fire from 18, Cure Poison 14 / Abolish Poison 26,
  Remove Curse 24, Nature's Grasp from 10, Barkskin from 44, Innervate from 40. Never mention
  totems, shocks, Lightning Bolt, Healing Wave, Purge, Stoneform (dwarf racial), Ghost Wolf, Astral Recall,
  weapon imbues, saptas or shaman trainers. Skyborne racials: Walk on Air (slow fall, glide), Read Leyline.
- Segment titles and file names that name shaman things ("Call of Water", "Water Sapta", "Totems", "the Ram")
  are renamed (`@segment` line only; the file name stays so segment numbers keep their order).

## Skyborne Mage specifics (`skyborne-mage`, ALLIANCE)
Alliance (High Order) Skyborne can be Mages (foreverchanges.pro/racials). The route is the Skyborne Druid
route with everything druid-specific replaced: same quests, same order, same hearth binds. Segments 01-04
(Zephras Isle, Dalaran, Stormwind, Loch Modan I) are done. Segments 05-25 start as copies of the DRUID files.
Do not re-plan the quest order, only adapt it.
- **Only quests an Alliance Skyborne Mage can take.** Druid quests are validator errors: the Cat Form chain
  98393 / 98341 / 98404 / 98738 / 98397 in segment 09 goes, together with the whole Auberdine -> Rut'theran ->
  Darnassus -> Moonglade -> Darnassus -> Auberdine detour and the `S Auberdine` bind that existed only as its
  fallback (compare routes/dwarf-shaman/08-*.route to see that segment without the detour).
- **No forms, no heals, no roots.** Never mention Bear / Cat / Travel / Aquatic / Dire Bear Form, Bash, Maul,
  Swipe, Prowl, Entangling Roots, Hibernate, Rejuvenation, Regrowth, Healing Touch, Moonfire, Wrath, Starfire,
  Faerie Fire, Cure / Abolish Poison, Remove Curse (druid), Barkskin, Innervate, Nature's Grasp, Teleport:
  Moonglade, Loganaar, Dendrite, Sheldras Moontree, or druid trainers. A mage walks until the mount (no travel
  form): where the druid text says "Travel Form", just walk / run, or "Blink" for short gaps. Swims: plain swim.
- **Mage trainers** (Questie): Stormwind, Wizard's Sanctum in the Mage Quarter: Jennea Cannon (Stormwind City
  49.6, 85.8); Ironforge, Hall of Mysteries: Bink (Ironforge 27.3, 8.3); Zephras Isle. Darnassus has NO mage
  trainer. So unlike the druid, a mage CAN train in Ironforge: where the druid file trains at Sheldras in
  Stormwind, use Jennea Cannon instead (same city, different quarter: mind the walking order inside Stormwind);
  where the route stands in Ironforge anyway, a `TRAIN @ Ironforge, 27.3, 8.3 | Bink ...` stop is fine.
- **Teleports** (Classic levels, not re-checked in Forever: write "from level 20" and give the fallback):
  Teleport: Stormwind and Teleport: Ironforge are taught at 20 by the Portal Trainers, NOT the mage trainers:
  Larimaine Purdue (Stormwind City 50.4, 86.0, beside the mage trainers) and Milstaff Stormeye (Ironforge
  25.5, 7.1). Teleport: Darnassus at 30 (Elissa Dumas, Darnassus 40.6, 82.1; the route does not go there).
  Portals at 40 (group only, ignore). Each cast needs a Rune of Teleportation (reagent vendors; remind the
  player to carry 5-10). The first Stormwind visit at level 20+ gets an `N Learn Teleport: Stormwind ...
  @ Stormwind City, 50.4, 86.0` step (and Ironforge at the first Ironforge visit at 20+).
  Every druid `N Cast Teleport: Moonglade` / `TRAIN @ Moonglade ...` / `H <town>` trip becomes
  `N Cast Teleport: Stormwind` / `TRAIN @ Stormwind City, 49.6, 85.8 | Jennea Cannon ...` / `H <town>`, IF the
  character is 20+ and has been to a Portal Trainer by then; before that, drop the trip and train at the next
  city visit. You may also replace a flight, boat or tram leg whose only purpose is to reach Stormwind or
  Ironforge with the teleport (20+), as long as no quest step, flight-path pickup or tram quest is skipped;
  say so in the header. Never build travel on Teleport: Darnassus.
- **Class quests**: 92481 and 93791 -> 93797 are done on Zephras Isle. The Stormwind mage quests (1860/1861 at
  10, 1919-1941 at 15, 1939-1942 at 26) are human/gnome-only in the data and NOT confirmed for Skyborne:
  segment 04 already tells the player to take what Jennea offers; add one more such `N` at the first training
  stop at 26+. Level 30: 1947 Journey to the Marsh (Jennea Cannon, Stormwind -> Tabetha, Dustwallow Marsh
  46.1, 57.1) is open to every mage: take it at the first Stormwind training stop at 30+ and hand it in when
  the route is next at Tabetha's hut (segment 14 if it passes her; read routes/undead-mage/13-*.route for how
  the Horde mage route handled Tabetha, 1948 Items of Power and 1952 Mage's Wand, and do the same only if the
  Alliance segment really passes the places; otherwise explain what is skipped). Level 50: 8250 Magecraft
  (Elsharin, Stormwind City 48.2, 87.2, at the mage trainers) -> Sanath Lim-yo in Azshara -> 8251 Magic Dust
  -> 8252 The Siren's Coral (Archmage Xylem); stop before 8253 (Sunken Temple). routes/undead-mage/18-*.route
  shows how it fits the Azshara loop: mirror it in segment 22, taking 8250 at the last Stormwind training stop
  at 50+ before Azshara (if there is none, add the chain's pickup as an optional `N`).
- **Mount at 40**: same as the druid (unverified, an `N` step). The druid text already says "mount" / "ride".
- **Combat hints** must suit a mage at that level: Fireball / Frostbolt, Fire Blast, Frost Nova (10) then step
  back, Polymorph (8; beasts, humanoids, critters) on the second mob, Arcane Explosion (14), Remove Lesser
  Curse (18), Blink (20), Blizzard (20), Evocation (20), Mana Shield (20), Counterspell (24) as THE interrupt,
  Cone of Cold (26), Frost Ward / Fire Ward, Ice Armor (30), conjured food and water, eat and drink between
  pulls, bandages (a mage cannot heal or cure poison/disease). Escorts: the mage cannot tank; kill attackers
  fast, Frost Nova and Polymorph extras. Skyborne racials: Walk on Air (slow fall, glide), Read Leyline.
- Segment titles that name druid things ("Cat Form") are renamed (`@segment` line only; file names stay).

## Human Mage specifics (`human-mage`, ALLIANCE)
Segments 01-04 are the human start (Northshire, Goldshire and the farms, east Elwynn, then Stormwind -> west
Elwynn -> tram -> east Dun Morogh -> Loch Modan I). Segments 05-25 are the Skyborne Mage files with the
human-only parts added; everything in "Skyborne Mage specifics" about trainers, teleports, combat hints and
the level 30 / 50 mage quests applies unchanged. Do not re-plan the quest order of 05-25, only adapt it, and
keep the hand-over state of segment 04 (ends in Thelsamar, hearthstone bound in Stormwind, flight paths
Stormwind / Ironforge / Thelsamar, carry-out 263 and 1338; segment 05 takes 2039 in Ironforge because a human
is not 12 when segment 04 passes Gnoarn).
- **No deliberate deaths.** TUGs' human files die on purpose to travel (Goldshire, Eastvale, Redridge). Walk or
  hearth instead.
- **Elite-flagged Forever quests in Elwynn**: 91752 The Big Picture and 91775 Book Return are in (TUGs does
  them solo; each step says how to leave it), 91777 Rare Books, 91740 Croaky's Head, 176 Hogger and 88
  Princess are out.
- **Unpublished things the steps describe in words** (fix them from the play log): the fishermen's chain order
  (99127 / 99143, then 99128 -> 99129 -> 99130 -> 99131), the fishing traps, the Mining Tools in the Jasperlode
  Mine, the gnoll camps with the Enchanting Supplies, the three Waterlogged items, the Mirror Lake waterfall
  (arrow is approximate), whether Earthseer Farsen gives 96392 without the Kharanos lead-in 96408, whether
  Homer Stonefield still sells Shiny Red Apples (for 91736 Applejack Still -> 91738).
- **Mage class quests a human really gets** (race mask human/gnome in the data):
  - 1: 3104 Glyphic Letter (Northshire). 10: 1860 Speak with Jennea (Zaldimar Wefhellt, Goldshire) -> 1861
    Mirror Lake (segment 04).
  - 15: 1919 Report to Jennea (Zaldimar, Goldshire) -> 1920 Investigate the Blue Recluse (Mage Quarter) -> 1921
    Gathering Materials (6 Charged Rift Gems from the Miners' League Crates in the Silver Stream Mine, Loch
    Modan, and 10 Linen Cloth) -> 1941 Manaweave Robe. In segment 06 (Goldshire, Stormwind, Loch Modan in that
    order) and the first Stormwind stop of segment 07.
  - 26: 1939 High Sorcerer Andromath -> 1938 Ur's Treatise on Shadow Magic (Tower of Ilgalar, Redridge 73.8,
    47.6, beside Lieutenant Fangore) -> 1940 Pristine Spider Silk (Carrion Recluses at the Raven Hill cemetery,
    Black Widow Hatchlings) -> 1942 Astral Knot Garment. All in segment 11.
  - 30 and 50: as in the Skyborne Mage route (1947 -> 1949 -> 1950, 8250 -> 8251 -> 8252).
- **Mount at 40**: Randal Hunter (riding) and Katie Hunter (horses), Eastvale Logging Camp, Elwynn Forest 84.3,
  64.9. ForeverChanges lists 97170 Learning to Ride and 97045 Your First Horse there (first horse free after
  training) without givers or a price, so segment 16 has one `N` step with an arrow, reached on foot from the
  Stormwind training stop and left by Hearthstone.
- Human racials are passive except Perception: no racial is named in the hints.
- The addon picks this route for a Human or Gnome mage. A race token that is not one of the eight Classic races
  is treated as Skyborne (Core.AutoRoute), so the Skyborne Mage still gets its own route.

## Gnome specifics (`gnome`, ALLIANCE, ANY CLASS)
The Gnome route is the Dwarf Shaman route (gnomes start in Coldridge Valley too) with everything shaman- or
dwarf-specific removed and every instruction written so that ANY class can follow it. The files in `routes/gnome/`
start as copies of the Dwarf Shaman files, same file names and numbers. Do not re-plan the quest order: same
quests, same order, same hearth binds, same flight paths, unless a rule below forces a change.
- **No class quests at all.** The validator profile has no class, so any class-restricted quest is an ERROR.
  Remove every step (A, C, T and helper N / G steps) of the shaman chains: Archaic Rune 98581, Call of Earth
  94373 / 94374 / 94375 (and 96243), Call of Fire 94449 / 94465 / 94466 / 94467 / 94468 / 94473, Call of Water
  94494 / 94495 / 94497 / 94499 / 94500 / 94501 / 94502 / 94503 / 94505 / 94616, Call of Air 94789. Also remove
  travel that existed ONLY for them (a walk to Bruegs Kindleborn's cave, Braldir Ashmantle's shrine, Hervdana's
  falls, Norric's house, Stendel's Pond, Veyric Thunderhame ...); keep travel that also serves other quests.
  A `C a,b,94466:1 @ ...` step keeps its other quests and loses the shaman part and the sentence about it.
- **Only quests a Gnome can take** (race bit 64). The 6387 gryphon chain (dwarves and gnomes) stays.
- **No class abilities, ever.** Never mention Ghost Wolf, Astral Recall, totems (Earthbind, Stoneclaw, Stoneskin,
  Searing, ...), shocks, Lightning Bolt / Shield, Healing Wave, Purge, weapon imbues, saptas, Stoneform (a dwarf
  racial), shaman trainers (Teo Hammerstorm, Ingrid Dunwald, Eldrun Stormbreaker) or any other class's spells.
  - "Ghost Wolf" travel: just "walk" / "run" (before 40) or "ride" (after the mount).
  - Every `N Cast Astral Recall ...` (a second hearthstone) must become real travel: a flight, a walk, or the
    Hearthstone ONLY when it has clearly not been used for an hour in that segment. If neither hearth is free,
    use the nearest flight path or walk. Say what you did in the segment's header comment.
  - Text like "Hearthstone, or cast Astral Recall" becomes just the Hearthstone.
- **Combat hints are class-neutral.** Say what the danger is and what any class can do about it: which mobs,
  their levels, pull one at a time, kill the healer / caster first ("interrupt or stun its casts if your class
  can"), enemies that run at low health ("finish it fast or slow it if you can, it brings friends"), fight at
  full health, eat / drink / bandage between pulls, where to stand, when to walk away. For escorts: "keep the
  attackers on you; you may not be able to heal him". Poison / disease: "cure it if your class can, otherwise
  bandage and eat". Pet classes (warlock, hunter) may be told once per hard fight "send your pet first" only as
  "if you have a pet". The gnome racial Escape Artist (breaks roots and snares) may be named where it helps.
- **TRAIN steps are generic and have no trainer name.** Format: `TRAIN | <town>: visit your class trainer ...`.
  Keep each training stop of the Dwarf route where it is (every gnome class has a trainer in Ironforge and in
  Stormwind; Anvilmar and Kharanos have the starting classes' trainers in the inn / main building). Drop the
  `@ Zone, x, y` of the shaman trainer: the arrow would be wrong for other classes. Where to look, for the text:
  Ironforge: warriors and hunters in the Military Ward (south-east, about 66-71, 83-90), rogues and warlocks in
  the Forlorn Cavern (north, about 50-53, 6-15), mages and priests in the Mystic Ward (north-west, about 24-27,
  6-10). Stormwind: warriors in Old Town (Command Center), rogues in Old Town (SI:7), mages in the Wizard's
  Sanctum and warlocks in the Slaughtered Lamb (both Mage Quarter), priests in the Cathedral. (Stormwind
  positions are Classic knowledge.) A trip made ONLY to train in Ironforge stays: all classes train there.
- **Class quests are the player's own business**: at the FIRST training stop at level 10+ and again at the
  first at 20+ and 30+, add one `N` step: "Your class has its own quests at about this level (your trainer
  offers them). This guide is not class-specific and does not list them: take them and fit them in where they
  suit you; the logger records what you take."
- **Mount at 40**: gnomes ride mechanostriders. Binjy Featherwhistle (riding, "Mechanostrider Pilot") and Milli
  Featherwhistle (mechanostriders) stand at Steelgrill's Depot, Dun Morogh 49.2, 48.1, just north-east of
  Kharanos (positions from the current Questie data). The Dwarf route goes to Amberstill Ranch (63.9, 50.1) for a
  ram: redirect that visit to Steelgrill's Depot (it is on the same road out of Ironforge, nearer the gate).
- **Segment titles** that name shaman things ("Fire Totem", "Call of Water", "Water Sapta", "Totems", "the
  Ram") are renamed on the `@segment` line only; file names stay so the numbering keeps its order.
- **Header comments**: rewrite the segment's header so it describes the Gnome segment ("Gnome, any class.
  From the Dwarf Shaman route's segment NN: same quests, order, binds and flights, minus the shaman quests")
  and lists what you removed or changed. Keep the "Added 2026-11-11 ..." / "Removed 2026-11-11 ..." comment
  lines and the quests they describe (97894, 161, 90, 98209, 98463, 1302, 1204 ...): they apply to gnomes too.
- **@carry / @done lines**: remove shaman quest ids from them; change nothing else in them unless your edits
  really change what is in the log at the segment's start.
- Also apply the general rule from the user: when the route walks back through a town between two loops, hand
  in what is finished there. Do not introduce new delays when you remove steps.

## Human Warlock specifics (`human-warlock`, ALLIANCE)
Segments 01-04 start as copies of the Human Mage files (Northshire, Goldshire, east Elwynn, Stormwind -> Loch
Modan I). Segments 05-25 start as copies of the class-neutral Gnome files 04-24 (same quests, order, binds and
flights as every Alliance route from level 14 on). Do not re-plan the quest order; adapt.
- **Only quests a Human Warlock can take.** Mage quests are validator errors: 3104, 1860, 1861, 1919, 1920, 1921,
  1941, 1939, 1938, 1940, 1942, 1947-1950, 8250-8252. Remove their steps and any travel made only for them.
- **No other class's abilities.** Never mention Frostbolt, Fireball, Fire Blast, Frost Nova, Polymorph, Blink,
  Counterspell, Arcane anything, Mana Shield, Evocation, conjured food / water, Teleport, portals, Runes of
  Teleportation, mage trainers (Khelden Bremen, Zaldimar Wefhellt, Jennea Cannon, Bink, Larimaine Purdue) or the
  Wizard's Sanctum. A warlock has NO teleport: where a mage file teleports, write the real travel (walk, flight,
  tram, Hearthstone if free). The Gnome-derived files 05-25 already have real travel: keep it.
- **Warlock trainers** (current Questie data): Northshire: Drusilla La Salle (Elwynn Forest 49.9, 42.7, beside
  the abbey's graveyard). Goldshire: Maximillian Crowe (Elwynn Forest 44.4, 66.2, in the basement of the Lion's
  Pride Inn). Stormwind: Demisette Cloyce / Ursula Deline / Sandahl in the Slaughtered Lamb, the tavern in the
  Mage Quarter (Stormwind City 39.2, 85.0; the trainers are in the cellar). Ironforge: Briarthorn (Ironforge 50.4,
  5.7, in the Forlorn Cavern in the north of the city). Demon trainers (pet spell books) stand beside each.
  Write `TRAIN @ Ironforge, 50.4, 5.7 | Briarthorn, the warlock trainer in the Forlorn Cavern ...` where the Gnome
  file has a generic Ironforge TRAIN step, and name the level's important spells if you are sure of them
  (Classic levels: Immolate 1, Corruption 4, Life Tap 6, Curse of Agony 8, Fear 8, Healthstone 10, Drain Soul 10,
  Health Funnel 12, Drain Life 14, Unending Breath 16, Soulstone 18, Curse of Tongues 26, Banish 28, Howl of
  Terror 40, Death Coil 42). If unsure, say "learn everything he offers". Where the route stands in Stormwind
  for other reasons anyway, the Slaughtered Lamb is an equally good trainer: do not add a city crossing just
  for it.
- **Class quests in the route** (ids and positions from the Questie data):
  - Level 1: 3105 Tainted Letter (Marshal McBride -> Drusilla La Salle), then 1598 The Stolen Tome (Drusilla; the
    book "Powers of the Void" lies in the Defias camp at the Northshire vineyard, Elwynn Forest 56.7, 44.0; the
    hand-in gives the Imp). These replace the mage's Glyphic Letter in segment 01; the tome is fetched on a
    vineyard trip that the segment already makes.
  - Level 10: 1685 Gakin's Summons (Remen Marcot, Goldshire inn basement 44.5, 66.3 -> Gakin the Darkbinder,
    Slaughtered Lamb cellar, Stormwind City 39.2, 85.2), 1688 Surena Caledon (Gakin; Surena is level 9 and stands
    with two Defias in the house at the Brackwell Pumpkin Patch, Elwynn Forest 71.0, 80.8; loot Surena's Choker;
    back to Gakin), 1689 The Binding (Gakin; use the Bloodstone Choker at the Summoning Circle in the same
    cellar, 39.1, 84.4, and defeat the Summoned Voidwalker; hand in = Voidwalker). They replace the mage's Speak
    with Jennea / Mirror Lake in segments 03-04: 1685 is taken at the end of segment 03 in Goldshire (level 10);
    segment 04 goes Stormwind (shipment, bind, flight path, Gakin) -> Goldshire -> east to the Brackwell Pumpkin
    Patch -> Hearthstone to Stormwind (just bound) -> Gakin, The Binding -> then the west Elwynn loop WITHOUT
    Mirror Lake (Applejack Still, Westbrook Garrison, gnolls) -> Stormwind -> tram. The Voidwalker is the
    leveling pet from here on.
  - Level 40: Summon Felsteed, the warlock's free mount: 4487 from Briarthorn at the level 40 training stop in
    Ironforge (segment 16) -> Strahad Farsan in Ratchet (The Barrens 62.6, 35.5), then 4490 from Strahad, handed
    in to him at once (he teaches Summon Felsteed). Segment 17 starts with the flight Theramore -> Ratchet, so
    4487 is carried one boat ride. The whole Steelgrill's Depot / mechanostrider part of the Gnome file goes
    (97046 and the riding steps): a warlock pays nothing and walks only until Ratchet. From there write "ride".
  - NOT in the route, one `N` note each at the first training stop at that level, saying it is optional and not
    routed (two continents, or a dungeon): level 20 Succubus (1716 Devourer of Souls from Gakin -> Takar the Seer
    in the southern Barrens -> Heartswood -> The Binding), level 30 Felhunter (1798 Seeking Strahad -> Tome of the
    Cabal, Ratchet / Ironforge), level 31 and 35 (Menara Voidrender's robe and orb quests in Ratchet), level 50
    (Impsy in Felwood).
- **Human, not gnome**: no Escape Artist, no mechanostrider. 2039 Find Bingles is taken in Ironforge at the
  start of segment 05 (the human is not 12 when segment 04 passes Gnoarn): segment 05 comes in with
  `@carry 263,1338`, the hearthstone bound in Stormwind, standing in Thelsamar.
- **Combat hints are written for a warlock.** Before 10: Imp out, Immolate, Corruption (4), Curse of Agony (8),
  wand or Shadow Bolt, Fear (8) on a second enemy (never near other packs: a feared mob brings friends), eat and
  drink, Life Tap (6) when health is higher than mana. From 10: send the Voidwalker first, let it hold the enemy,
  then Corruption, Curse of Agony, Immolate, wand; Fear the second mob; Drain Life (14) and Health Funnel (12) to
  stay up; Healthstone (10) for emergencies; Drain Soul the last hit when you need Soul Shards (keep 3-5: every
  demon summon and Healthstone costs one); Banish (28) for elementals and demons; Death Coil (42) and Howl of
  Terror (40) as escapes; Sacrifice (the Voidwalker's shield) when it goes wrong; Soulstone (18) on yourself
  before a hard fight; Unending Breath (16) for swims; Curse of Tongues (26) on casters (a warlock has no
  interrupt: kill casters first, or Fear them). Escorts: the Voidwalker holds the attackers. A warlock cannot
  cure poison or disease: bandage, Drain Life, eat. Replace the Gnome files' "if your class can ..." phrases with
  what a warlock really does. Only name a spell at or after its level. Mob, item, quest and place names stay
  exactly as they are, whatever words they contain.
- **Class-quest N steps of the Gnome files** ("Your class has its own quests ...") are replaced by the warlock
  notes above (the level 20 and 30 ones); delete the generic ones.
- **Header comments**: "Human Warlock. From the Gnome route's segment NN (class-neutral Alliance path) ..." or,
  for 01-04, "... from the Human Mage route's segment NN", listing what changed. Keep the dated "Added / Removed
  2026-11-11" comment lines and their quests.
- Rule from the user: when the route walks back through a town between loops, hand in what is finished, train,
  and take new quests there.

## Human Warrior specifics (`human-warrior`, ALLIANCE, GENERATED)
All 25 files are made from `routes/human/` by `tools/derive_warrior.py`. Never edit them by hand: change the
Human file (for 05-25 that means the Gnome file and `derive_anyclass.py`) or the script, then run
`python -I tools/derive_warrior.py` and rebuild `--route human-warrior`. The script stops with a list if a Human
file gains class-neutral wording that none of its rules covers, or if a step it anchors on has moved.
- **What the script changes**: every `TRAIN` step (table `TRAIN`, one entry per stop, in file order), the class
  quests (table `EDITS`), `@carry` lines for the class quests that ride along, and the class-neutral fight
  phrases ("interrupt or stun ... if your class can", "cure it if your class can", "eat and drink", pets, mana).
- **Class quests in the route** (ids, givers and positions from the baked Questie data):
  - Level 1: 3100 Simple Letter (Marshal McBride -> Llane Beshere, Northshire 50.2, 42.3).
  - Level 10, Defensive Stance: 1638 A Warrior's Training (Lyria Du Lac, Goldshire, end of segment 03) -> Harry
    Burlguard in the Pig and Whistle, Stormwind Old Town (77.1, 53.3) -> 1639 Bartleby the Drunk -> 1640 Beat
    Bartleby -> 1665 Bartleby's Mug (the stance), all at the start of segment 04. 1666 Marshal Haggard is carried
    to segment 06, which walks past Eastvale on the way to Redridge: 1667 Dead-tooth Jack (camp at Elwynn 89.4,
    79.0) is done there.
  - Level 20: 1698 Yorus Barleybrew (Kelv Sternhammer, Ironforge, segment 06) -> 1699 The Rethban Gauntlet
    (Lakeshire, timed, segment 07) -> 1702 The Shieldsmith, carried to Furen Longbeard in the Dwarven District in
    segment 11. The armor quests after it (1701 Fire Hardened Mail and on) need a Razorfen Kraul drop: `N` only.
  - Level 30: 1718 The Islander (Kelv Sternhammer, segment 12) carried to Ratchet in segment 14 -> 1719 The
    Affray on Fray Island. 1791 The Windwatcher and the Whirlwind weapon (Cyclonian, level 40 elite) are an `N`.
  - Level 50: 8417 A Troubled Spirit ends in the Sunken Temple: `N` at the first training stop after 50.
- **Trainers**: Llane Beshere (Northshire), Lyria Du Lac (Goldshire smithy 41.1, 65.8), Wu Shen (Stormwind Old
  Town 80.5, 59.9), Kelv Sternhammer (Ironforge 70.3, 90.7).
- **Ability levels** named in `TRAIN` steps come from the Forever beta spell list (build 1.60.1.70755, read
  2026-11-13 on forevercalc.com and conquestcapped.com): Charge and Rend 4, Thunder Clap 6, Hamstring 8, Bloodrage /
  Sunder Armor / Taunt 10, Overpower and Shield Bash 12, Demoralizing Shout and Revenge 14, Mocking Blow and Shield
  Block 16, Disarm 18, Victory Rush / Cleave / Slam / Retaliation 20, Intimidating Shout 22, Execute 24,
  Challenging Shout 26, Shield Wall 28, Berserker Stance / Intercept / Berserker Rage 30, Whirlwind 36, Pummel 38,
  Recklessness 50. Not checked in game. Unverified too: that the trainer (not The Affray) teaches Berserker Stance
  in Forever, the timer of The Rethban Gauntlet, and Plate Mail at 40 (Classic).
- Leftover in the Human, Dwarf and Night Elf files that the script removes for the warrior: three hints still
  name the gnome racial Escape Artist (segments 12, 13 and 16 of the Human route). Fix them in the Gnome file /
  `derive_anyclass.py` when those routes are next rebuilt.

## Any-class race routes (`dwarf`, `human`, `night-elf`, `skyborne`, ALLIANCE, ANY CLASS)
One route per Alliance race for every class that has no route of its own (the user chose this on 2026-11-12
instead of one route per race/class pair). Same rules as the Gnome route ("Gnome specifics" above): `class_bit` 0,
so ANY class-restricted quest is a validator error; no class abilities, spells, pets, forms, totems or teleports
in any step text; fight hints that work for every class ("pull one at a time", "kill the caster first", "eat and
bandage"); generic `TRAIN` steps that say where the class trainers are, never one trainer as if it were yours.
- Segments from level 14 on (Dwarf 04-24, the others 05-25) are GENERATED from the Gnome files by
  `tools/derive_anyclass.py <route>` (mount block, Find Bingles, the Skyborne-only 98021). Never edit them by
  hand: change the Gnome file or the script and run it again. The script never touches the start-zone files.
- Start-zone files are hand-written: `dwarf` 01-03 are copies of the Gnome's; `human` 01-04 come from the Human
  Warlock / Human Mage files; `skyborne` 01-04 from the Skyborne Mage / Druid files; `night-elf` 01-04 are new
  (Shadowglen, Teldrassil, Darnassus, Darkshore, then Menethil -> Loch Modan).
- **Class quests in a start zone** are not routed. Give ONE `N` step where the first one is offered (the level 1
  "letter" from the first quest giver to your class trainer) saying: your class has its own quests, take them from
  your trainer and fit them in; the logger records them. A second `N` at level 10 (most classes get a class quest
  at 10: warrior stance, hunter pet, warlock Voidwalker, druid bear form, rogue, shaman totem, priest at 5) that
  names nothing class-specific beyond "your trainer has a quest for you at level 10; it is worth doing".
- **Trainers**: name the place and list the class trainers standing there with coordinates when the data has
  them (research/json/baked_npcs.json, field 14 "Warrior Trainer" etc., field 7 spawns by zone id), e.g.
  `TRAIN | Northshire Abbey: your class trainer (warriors and paladins in the hall, mages and priests ...)`.
- **Hand-off into segment 05 (the contract; do not break it)**: segment 04 ends at level 14, standing in
  Thelsamar (Loch Modan), with the Thelsamar and Ironforge flight paths, the quest log holding 263 and 1338 and
  nothing else that segments 05-25 use, and 1339 and 237 handed in. Do NOT take 2039 Find Bingles in 01-04
  (segment 05 takes it). Model the Loch Modan I part on `routes/human-warlock/04-*.route` (same quests and
  order). No quest taken in 01-04 may be accepted again by a later file: check with the whole-route validator.
- Rule from the user: when the route walks back through a town between loops, hand in what is finished, train,
  and take new quests there. Mob, item, quest and place names stay exactly as they are.
- Auto pick in game (Core.AutoRoute): your race's route wins; within a race a route written for your class beats
  the any-class one.

## Optional dungeon runs (`routes/dungeons/*.dungeon`)
The `.route` files stay quest-only. Dungeons are described once, in `routes/dungeons/NN-name.dungeon`, and the
builder slots them into every route by itself (`tools/dungeons.py`): the run goes to the end of the hub visit
whose estimated level is closest to `@best`, each pick-up to the last time the route passes its giver before
the run, each hand-in to the first time the route passes that NPC after it. Quests whose giver is not on the
way are named in the run step as a detour instead. The file format is at the top of `tools/dungeons.py`.
- In game the steps only show with `/fr dungeons on` (or the "Dng" button). Off is the default and is exactly
  the quest-only route: the builder's dungeon steps carry `dg=<n>` and the addon leaves them out.
- The build report lists, per route, where every dungeon step landed and what was left out and why. Read it
  after changing a route or a dungeon file. `--no-dungeons` builds without them.
- Every level range, entrance, giver and hand-in in a dungeon file must come from a source, named in the
  comment at the top of the file (ForeverChanges dungeon pages in `research/fc/dungeons/`, the Questie
  install). New Forever dungeons with no published quest givers are a single `RUN` note that says so.

## Check your work
Run from the project folder:
```
python -I tools/build_route.py --route <route> --only routes/<route>/<your file>
```
It resolves coordinates and reports ERROR / WARN / INFO lines. Fix every ERROR. Review every WARN:
- "needs level X, estimated level Y": the XP estimate is rough (quest XP x1.7 for kills, measured from the play log). Within 1-2
  levels is fine. Larger gaps mean reorder, add quests, or add an `L` grind step.
- "no coordinates": add an `@ Zone, x, y` override if you can find the location (FC page pins/dots,
  digest, TUGs [G] coords), otherwise explain in the `| text` where to go.
- "accepted but never turned in": fine only if it is listed in your segment's carry-out.
The whole route (all segments in order, checking @carry/@done/levels across segments):
```
python -I tools/build_route.py --route <route> --check-only --log-at-ends
```

## Learn from the play log
After the player has played (and logged out or /reload-ed), run:
```
python -I tools/check_log.py --route <route> [--since "MM-DD HH:MM"]
```
It compares the in-game logger's events with the route: steps done in another order, quests taken that the
route does not list, route quests that were never offered, real level against the estimate, the slowest
stretches, and every Skip and /fr note. It also writes `research/observed.json` (real quest-giver / turn-in
positions and real quest XP, from every character), which `build_route.py` prefers over Questie and
ForeverChanges data on the next build. A manual `@ Zone, x, y` override still wins.
