# Forever Route

A free 1-60 leveling guide addon for **WoW: Forever** (client 1.60.1). It shows the next step, points an arrow at it, and ticks steps off by itself as you take, finish and hand in quests.

## Install

1. Download `ForeverRoute-x.y.z.zip` from the [latest release](../../releases/latest).
2. Unzip it into `World of Warcraft\_forever_\Interface\AddOns\` so you end up with `AddOns\ForeverRoute\ForeverRoute.toc`.
3. Start the game (a full restart, not `/reload`, when you add or update the addon).

No other addon is needed. Questie works well next to it; leave Questie's own auto-accept option off.

## Guides

The addon picks a guide from your race and class when you log in.

| Guide | For |
|---|---|
| Human, Dwarf, Gnome, Night Elf, Skyborne (any class) | every Alliance character |
| Human Mage, Human Warlock, Human Warrior, Dwarf Shaman, Skyborne Druid, Skyborne Mage | these combos get their class quests, named trainers and class fight tips |
| Undead Mage, Orc Shaman | Horde (Trolls get the Orc Shaman guide) |

Already leveled? On first login the addon offers to start at the segment for your level; quests you already did are skipped. `/fr seg auto` does the same at any time.

The guides are quest-only. Optional dungeon runs can be switched on with `/fr dungeons on`.

## Commands

| Command | What it does |
|---|---|
| `/fr` | show or hide the window |
| `/fr skip`, `/fr back` | move one step forward or back |
| `/fr seg [n]` | list the segments, or jump to one (`/fr seg auto` picks the one for your level) |
| `/fr route [name]` | list the guides, or switch to one (`/fr route auto` picks from race and class) |
| `/fr auto` | auto accept and hand in on or off (on by default; hold Shift at an NPC to do it by hand) |
| `/fr dungeons on\|off\|list` | optional dungeon runs |
| `/fr arrow`, `/fr paths`, `/fr waypoint` | arrow, road-following paths, map waypoint on or off |
| `/fr note <text>` | save a note in the play log |

Auto accept only takes quests the guide wants at the current step or the next few steps. It hands in any finished quest and leaves reward choices to you.

## State of the guides

The Undead Mage guide has been played the furthest. Most of the others were written from quest data and have not been played end to end, so expect wrong spots and awkward orders here and there. Steps that rest on unchecked facts say so in their text.

## Building from source

`routes/<guide>/*.route` are the guide sources (format and rules in `routes/AUTHORING.md`); `tools/build_route.py` compiles them into `addon/ForeverRoute/Routes/*.lua`. The builder reads quest and NPC data from a `research/` folder that is not in this repository (exports of the Questie database and saved ForeverChanges pages), so the repository is enough to read and install the guides but not to rebuild them as it stands.

## Credits

Quest and NPC positions come from the Questie database for Forever and from foreverchanges.pro. The quest order was informed by TUGs' Guidelime guides and RestedXP's free Forever guides; all step text is written from scratch.
