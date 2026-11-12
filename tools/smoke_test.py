"""Run the addon in a Lua 5.1 VM with a mocked WoW API and drive a few quest events.

Usage: python -I smoke_test.py            (Undead Mage character, plus an Orc Shaman run if that route is built)
"""
import site
import sys
from pathlib import Path

sys.path.append(site.getusersitepackages())
import lupa.lua51 as L  # noqa: E402

ADDON_DIR = Path(__file__).resolve().parent.parent / 'addon' / 'ForeverRoute'

MOCK = r'''
local unpack = unpack
timers = {}
function run_timers()
  local t = timers; timers = {}
  for _, f in ipairs(t) do f() end
end
C_Timer = { After = function(_, f) table.insert(timers, f) end,
            NewTicker = function(_, f) _G.__ticker = f; return {} end }
local function newobj()
  local o = { __shown = true, __scripts = {}, __events = {} }
  return setmetatable(o, { __index = function(t, k)
    if k == "IsShown" then return function(self) return self.__shown end end
    if k == "Show" then return function(self) self.__shown = true end end
    if k == "Hide" then return function(self) self.__shown = false end end
    if k == "SetScript" then return function(self, n, f) self.__scripts[n] = f end end
    if k == "RegisterEvent" then return function(self, e) if not rawget(self, "__reg") then rawset(self, "__reg", true); table.insert(__frames, self) end; self.__events[e] = true end end
    if k == "CreateFontString" or k == "CreateTexture" then return function() return newobj() end end
    if k == "GetStringHeight" then return function() return 12 end end
    if k == "GetLeft" or k == "GetTop" then return function() return 100 end end
    if k == "SetText" then return function(self, s) self.__text = s end end
    return function() return nil end
  end })
end
__frames = {}
function CreateFrame(_, name) local o = newobj(); if name then _G[name] = o end; return o end
UIParent = newobj()
BackdropTemplateMixin = {}
__chat = {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, m) table.insert(__chat, m) end }
SlashCmdList = {}
function time() return 1000 end
function GetBuildInfo() return '1.60.1', '70862', 'Nov 2026', 16001 end
function UnitClass() return __class[1], __class[2] end
function UnitRace() return __race[1], __race[2] end
function UnitFactionGroup() return __faction, __faction end
function GetTime() return 50 end
function UnitLevel() return __level end
function UnitName(u) return u == "player" and "Tester" or "Quest Giver" end
function UnitGUID() return "Creature-0-1-2-3-1568-00001" end
function strsplit(sep, s)
  local out = {}
  for part in string.gmatch(s, "([^" .. sep .. "]+)") do out[#out + 1] = part end
  return unpack(out)
end
function GetZoneText() return "Somewhere" end
function GetSubZoneText() return "" end
function GetBindLocation() return __bind end
function GetQuestID() return __dialogQuest or 0 end
function GetPlayerFacing() return 0 end
__level = 1
__bind = "Nowhere"
__log = {}       -- [q] = {ready=bool}
__done = {}
C_QuestLog = {
  IsOnQuest = function(q) return __log[q] ~= nil end,
  IsQuestFlaggedCompleted = function(q) return __done[q] == true end,
  IsComplete = function(q) return __log[q] ~= nil and __log[q].ready == true end,
  GetQuestObjectives = function(q) return __log[q] and { { text = "obj", finished = __log[q].ready, numFulfilled = __log[q].n or 0, numRequired = 8 } } or {} end,
  GetNumQuestLogEntries = function() local n = 0; for _ in pairs(__log) do n = n + 1 end; return n end,
  GetInfo = function(i) local k = 0; for q in pairs(__log) do k = k + 1; if k == i then return { questID = q, isHeader = false } end end end,
  GetTitleForQuestID = function(q) return "Quest " .. q end,
  GetMaxNumQuestsCanAccept = function() return 40 end,
}
function CreateVector2D(x, y) return { x = x, y = y, GetXY = function(self) return self.x, self.y end } end
C_Map = {
  GetBestMapForUnit = function() return 1420 end,
  GetPlayerMapPosition = function() return CreateVector2D(__px or 0.30, __py or 0.70) end,
  GetWorldPosFromMapPos = function(m, v) return 0, { x = (1 - v.y) * 4000, y = (1 - v.x) * 4000 } end,
  GetMapChildrenInfo = function() return {} end,
  SetUserWaypoint = function(p) __waypoint = p end,
  ClearUserWaypoint = function() __waypoint = nil end,
  CanSetUserWaypointOnMap = function() return true end,
  HasUserWaypoint = function() return __waypoint ~= nil end,
}
UiMapPoint = { CreateFromCoordinates = function(m, x, y) return { m = m, x = x, y = y } end }
C_SuperTrack = { SetSuperTrackedUserWaypoint = function() end }
Enum = { UIMapType = { Zone = 3 } }
function fire(event, ...)
  for _, f in ipairs(__frames) do
    if f.__events[event] and f.__scripts.OnEvent then f.__scripts.OnEvent(f, event, ...) end
  end
end
'''


def boot(race, cls, saved_char=None):
    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK)
    faction = 'Alliance' if race[1] in ('Dwarf', 'Human', 'NightElf', 'Gnome', 'Skyborne') else 'Horde'
    lua.execute(f'__race = {{"{race[0]}", "{race[1]}"}}; __class = {{"{cls[0]}", "{cls[1]}"}}; __faction = "{faction}"')
    if saved_char:
        lua.execute('ForeverRouteChar = ' + saved_char)
    ns = lua.table()
    lua.globals().__ns = ns
    toc = (ADDON_DIR / 'ForeverRoute.toc').read_text(encoding='utf-8').splitlines()
    files = [ln.strip().replace('\\', '/') for ln in toc if ln.strip() and not ln.startswith('#')]
    for f in files:
        p = ADDON_DIR / f
        if not p.exists():
            print('  (toc file missing, skipped:', f, ')')
            continue
        chunk = lua.execute('return function(src, name) return assert(loadstring(src, name)) end')(
            p.read_text(encoding='utf-8'), '@' + f)
        chunk('ForeverRoute', ns)
    fire = lua.globals().fire
    run = lua.eval('run_timers')
    fire('ADDON_LOADED', 'ForeverRoute')
    fire('PLAYER_LOGIN')
    fire('PLAYER_ENTERING_WORLD')
    run(); run()
    return lua, fire, run


def chat(lua):
    c = lua.eval('__chat')
    out = [c[i] for i in range(1, len(c) + 1)]
    lua.execute('__chat = {}')
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    built = [p.stem for p in (ADDON_DIR / 'Routes').glob('*.lua')]
    print('routes built:', built)

    print('\n== Undead Mage, fresh character')
    lua, fire, run = boot(('Undead', 'Scourge'), ('Mage', 'MAGE'))
    print('  ', '\n   '.join(chat(lua)))
    exercise(lua, fire, run)

    print('\n== Undead Mage with 0.1 saved progress (must be kept)')
    lua, fire, run = boot(('Undead', 'Scourge'), ('Mage', 'MAGE'),
                          '{ ticked = { ["x#1"] = "tick" }, current = 7, currentKey = "END", opts = { arrow = false } }')
    print('   migrated:', lua.eval('ForeverRouteChar.progress["undead-mage"] and ForeverRouteChar.progress["undead-mage"].currentKey'),
          '| old top-level ticked gone:', lua.eval('ForeverRouteChar.ticked == nil'),
          '| arrow option kept off:', lua.eval('ForeverRouteChar.opts.arrow == false'))

    if 'OrcShaman' in built:
        print('\n== Orc Shaman, fresh character')
        lua, fire, run = boot(('Orc', 'Orc'), ('Shaman', 'SHAMAN'))
        print('  ', '\n   '.join(chat(lua)))
        exercise(lua, fire, run)
        print('\n== Troll Shaman picks the Shaman route; /fr route switching')
        lua, fire, run = boot(('Troll', 'Troll'), ('Shaman', 'SHAMAN'))
        print('  ', '\n   '.join(chat(lua)))
        slash = lua.globals().SlashCmdList.FOREVERROUTE
        slash('route undead-mage'); print('  ', chat(lua))
        print('   saved route choice:', lua.eval('ForeverRouteChar.route'))
        slash('route auto'); print('  ', chat(lua))
        slash('route nonsense'); print('  ', chat(lua)[:2])
        lua, fire, run = boot(('Tauren', 'Tauren'), ('Shaman', 'SHAMAN'))
        key = lua.eval('__ns.Core.routeKey')
        print('   Tauren Shaman (Horde) gets:', key, '' if key == 'orc-shaman' else '  FAIL')
        if key != 'orc-shaman':
            global FAILED
            FAILED = True

    if 'DwarfShaman' in built:
        print('\n== Dwarf Shaman (Alliance), fresh character')
        lua, fire, run = boot(('Dwarf', 'Dwarf'), ('Shaman', 'SHAMAN'))
        print('  ', '\n   '.join(chat(lua)))
        key = lua.eval('__ns.Core.routeKey')
        if key != 'dwarf-shaman':
            print('   FAIL: picked', key)
            FAILED = True
        exercise(lua, fire, run)

    if 'SkyborneDruid' in built:
        print()
        print('== Skyborne Druid (Alliance), fresh character')
        # The real race token of the High Order Skyborne is not known: the route must be picked by class alone
        for token in ('Skyborne', 'SomeUnknownRaceToken'):
            lua, fire, run = boot(('Skyborne', token), ('Druid', 'DRUID'))
            lua.execute('__faction = "Alliance"')
            fire('PLAYER_LOGIN')
            key = lua.eval('__ns.Core.AutoRoute()')
            if key != 'skyborne-druid':
                print('   FAIL: race token', token, 'picked', key)
                FAILED = True
            else:
                print('   ok   race token', token, '-> skyborne-druid')
        lua, fire, run = boot(('Skyborne', 'Skyborne'), ('Druid', 'DRUID'))
        for line in chat(lua):
            print('   ' + line)
        exercise(lua, fire, run)

    if 'SkyborneMage' in built:
        print()
        print('== Skyborne Mage (Alliance), fresh character')
        # The real race token of the High Order Skyborne is not known: the route must be picked by class alone
        for token in ('Skyborne', 'SomeUnknownRaceToken'):
            lua, fire, run = boot(('Skyborne', token), ('Mage', 'MAGE'))
            lua.execute('__faction = "Alliance"')
            fire('PLAYER_LOGIN')
            key = lua.eval('__ns.Core.AutoRoute()')
            if key != 'skyborne-mage':
                print('   FAIL: race token', token, 'picked', key)
                FAILED = True
            else:
                print('   ok   race token', token, '-> skyborne-mage')
        lua, fire, run = boot(('Skyborne', 'Skyborne'), ('Mage', 'MAGE'))
        for line in chat(lua):
            print('   ' + line)
        exercise(lua, fire, run)


    if 'HumanMage' in built:
        print()
        print('== Human Mage (Alliance), fresh character')
        lua, fire, run = boot(('Human', 'Human'), ('Mage', 'MAGE'))
        for line in chat(lua):
            print('   ' + line)
        key = lua.eval('__ns.Core.routeKey')
        if key != 'human-mage':
            print('   FAIL: picked', key)
            FAILED = True
        exercise(lua, fire, run)
        # the other Alliance mages must not be pulled onto the wrong route
        for race, token, want in (('Gnome', 'Gnome', 'gnome' if 'Gnome' in built else 'human-mage'), ('Skyborne', 'SomeUnknownRaceToken', 'skyborne-mage'),
                                  ('Undead', 'Scourge', 'undead-mage')):
            lua, fire, run = boot((race, token), ('Mage', 'MAGE'))
            if token == 'SomeUnknownRaceToken':
                lua.execute('__faction = "Alliance"')
                fire('PLAYER_LOGIN')
            key = lua.eval('__ns.Core.AutoRoute()')
            ok = key == want or (want == 'skyborne-mage' and 'SkyborneMage' not in built)
            print('   ' + ('ok  ' if ok else 'FAIL'), race, 'Mage ->', key)
            if not ok:
                FAILED = True


    if 'Gnome' in built:
        print()
        print('== Gnome (Alliance, any class), fresh character')
        lua, fire, run = boot(('Gnome', 'Gnome'), ('Warlock', 'WARLOCK'))
        for line in chat(lua):
            print('   ' + line)
        exercise(lua, fire, run)
        # who gets the class-neutral route, and who must keep their own
        for race, token, cls, want in (('Gnome', 'Gnome', 'MAGE', 'gnome'), ('Gnome', 'Gnome', 'WARRIOR', 'gnome'),
                                       ('Gnome', 'Gnome', 'HUNTER', 'gnome'), ('Human', 'Human', 'MAGE', 'human-mage'),
                                       ('Dwarf', 'Dwarf', 'SHAMAN', 'dwarf-shaman'),
                                       ('Skyborne', 'SomeUnknownRaceToken', 'MAGE', 'skyborne-mage'),
                                       ('Skyborne', 'SomeUnknownRaceToken', 'DRUID', 'skyborne-druid'),
                                       ('Undead', 'Scourge', 'MAGE', 'undead-mage'), ('Orc', 'Orc', 'SHAMAN', 'orc-shaman')):
            lua, fire, run = boot((race, token), (cls.title(), cls))
            if token == 'SomeUnknownRaceToken':
                lua.execute('__faction = "Alliance"')
                fire('PLAYER_LOGIN')
            key = lua.eval('__ns.Core.AutoRoute()')
            ok = key == want
            print('   ' + ('ok  ' if ok else 'FAIL'), race, cls, '->', key)
            if not ok:
                FAILED = True


    if 'HumanWarlock' in built:
        print()
        print('== Human Warlock (Alliance), fresh character')
        lua, fire, run = boot(('Human', 'Human'), ('Warlock', 'WARLOCK'))
        for line in chat(lua):
            print('   ' + line)
        key = lua.eval('__ns.Core.routeKey')
        if key != 'human-warlock':
            print('   FAIL: picked', key)
            FAILED = True
        exercise(lua, fire, run)
        for race, token, cls, want in (('Human', 'Human', 'MAGE', 'human-mage'), ('Gnome', 'Gnome', 'WARLOCK', 'gnome'),
                                       ('Undead', 'Scourge', 'WARLOCK', 'undead-mage')):
            lua, fire, run = boot((race, token), (cls.title(), cls))
            key = lua.eval('__ns.Core.AutoRoute()')
            ok = key == want or (want == 'gnome' and 'Gnome' not in built)
            print('   ' + ('ok  ' if ok else 'FAIL'), race, cls, '->', key)
            if not ok:
                FAILED = True


    # any-class routes, one per Alliance race
    for lua_name, key, race, cls in (('Dwarf', 'dwarf', ('Dwarf', 'Dwarf'), ('Warrior', 'WARRIOR')),
                                     ('Human', 'human', ('Human', 'Human'), ('Priest', 'PRIEST')),
                                     ('NightElf', 'night-elf', ('Night Elf', 'NightElf'), ('Hunter', 'HUNTER')),
                                     ('Skyborne', 'skyborne', ('Skyborne', 'Skyborne'), ('Rogue', 'ROGUE'))):
        if lua_name not in built:
            continue
        print()
        print('==', race[0], cls[0], '(Alliance, any-class route), fresh character')
        lua, fire, run = boot(race, cls)
        for line in chat(lua):
            print('   ' + line)
        got = lua.eval('__ns.Core.routeKey')
        if got != key:
            print('   FAIL: picked', got)
            FAILED = True
        exercise(lua, fire, run)
    if all(n in built for n in ('Dwarf', 'Human', 'NightElf', 'Skyborne')):
        print()
        print('== who gets which route')
        for race, token, cls, want in (('Dwarf', 'Dwarf', 'WARRIOR', 'dwarf'), ('Dwarf', 'Dwarf', 'PALADIN', 'dwarf'),
                                       ('Dwarf', 'Dwarf', 'SHAMAN', 'dwarf-shaman'), ('Human', 'Human', 'WARRIOR', 'human'),
                                       ('Human', 'Human', 'SHAMAN', 'human'), ('Human', 'Human', 'DRUID', 'human'),
                                       ('Human', 'Human', 'MAGE', 'human-mage'), ('Human', 'Human', 'WARLOCK', 'human-warlock'),
                                       ('Night Elf', 'NightElf', 'DRUID', 'night-elf'), ('Night Elf', 'NightElf', 'MAGE', 'night-elf'),
                                       ('Night Elf', 'NightElf', 'WARLOCK', 'night-elf'), ('Gnome', 'Gnome', 'MAGE', 'gnome'),
                                       ('Gnome', 'Gnome', 'WARLOCK', 'gnome'), ('Gnome', 'Gnome', 'SHAMAN', 'gnome'),
                                       ('Skyborne', 'SomeUnknownRaceToken', 'WARRIOR', 'skyborne'),
                                       ('Skyborne', 'SomeUnknownRaceToken', 'SHAMAN', 'skyborne'),
                                       ('Skyborne', 'SomeUnknownRaceToken', 'DRUID', 'skyborne-druid'),
                                       ('Skyborne', 'SomeUnknownRaceToken', 'MAGE', 'skyborne-mage'),
                                       ('Undead', 'Scourge', 'MAGE', 'undead-mage'), ('Orc', 'Orc', 'SHAMAN', 'orc-shaman'),
                                       ('Troll', 'Troll', 'SHAMAN', 'orc-shaman')):
            lua, fire, run = boot((race, token), (cls.title(), cls))
            if token == 'SomeUnknownRaceToken':
                lua.execute('__faction = "Alliance"')
            key = lua.eval('__ns.Core.AutoRoute()')
            ok = key == want
            print('   ' + ('ok  ' if ok else 'FAIL'), race, cls, '->', key)
            if not ok:
                FAILED = True


def exercise(lua, fire, run):
    g = lua.globals()
    lua.execute('__key = nil; for k in pairs(ForeverRouteChar.progress) do __key = k end')
    key = lua.eval('__key')
    prog = lambda: lua.eval('ForeverRouteChar.progress[__key].current')  # noqa: E731
    title = lambda: lua.eval('ForeverRouteFrame and ForeverRouteFrame.title and ForeverRouteFrame.title.__text')  # noqa: E731
    print('   route key', key, '| start step', prog(), '|', title())
    qid = first_quest(lua)
    lua.execute(f'__dialogQuest = {qid}'); fire('QUEST_DETAIL')
    lua.execute(f'__log[{qid}] = {{ready=true}}'); fire('QUEST_ACCEPTED', qid); run(); run()
    print(f'   after accept {qid} -> step', prog(), '|', title())
    lua.execute(f'__dialogQuest = {qid}'); fire('QUEST_COMPLETE')
    lua.execute(f'__log[{qid}] = nil; __done[{qid}] = true'); fire('QUEST_REMOVED', qid); run(); run()
    fire('QUEST_TURNED_IN', qid, 40, 0); run()
    print(f'   after turn-in {qid} -> step', prog(), '|', title())
    lua.execute('__ticker()')
    print('   arrow text:', lua.eval('ForeverRouteArrow.text.__text'))
    g.SlashCmdList.FOREVERROUTE('skip'); run()
    print('   after skip ->', prog())
    g.SlashCmdList.FOREVERROUTE('back'); run()
    print('   after back ->', prog())
    chat(lua)
    ev = lua.eval('ForeverRouteLog.events')
    kinds = [ev[i].e for i in range(1, len(ev) + 1)]
    print('   logged events:', kinds, '| login route:', ev[1].route, ev[1].steps)
    print('   waypoint', lua.eval('__waypoint and (__waypoint.m .. " " .. __waypoint.x .. " " .. __waypoint.y)'))
    features(lua, fire, run)
    paths(lua)
    auto(lua)
    jump(lua)


PATHS = r'''
-- walking paths: the arrow goes through s.path first, a cave entrance is only passed by standing at it
local C = __ns.Core
local idx
for i, s in ipairs(C.Steps) do if s.cave and s.path and #s.path >= 2 then idx = i break end end
if not idx then return "no cave step with a path in this route" end
local s = C.Steps[idx]
ForeverRouteChar.progress[__key].current = idx
ForeverRouteChar.opts.arrow, ForeverRouteChar.opts.shown = true, true
local out = {}
local function at(x, y) __px, __py = x / 100, y / 100; __ticker(); return ForeverRouteArrow.text.__text or "" end
local n = #s.path
local t1 = at(s.path[1][1] + 3, s.path[1][2] + 3)          -- well before the first path point
out[#out + 1] = (t1:find("path 1/" .. n, 1, true) and "ok  " or "FAIL") .. " arrow starts on path point 1 of " .. n
local t2
for i = 1, n - 1 do t2 = at(s.path[i][1], s.path[i][2]) end -- walk the path points up to the cave
out[#out + 1] = (t2:find("cave entrance", 1, true) and "ok  " or "FAIL") .. " last path point is shown as the cave entrance"
local t3 = at(s.path[n][1], s.path[n][2])                   -- stand at the entrance
out[#out + 1] = ((not t3:find("cave", 1, true) and not t3:find("path", 1, true)) and "ok  " or "FAIL") .. " at the entrance the arrow switches to the step's own point"
ForeverRouteChar.opts.paths = false
local t4 = at(s.path[1][1] + 3, s.path[1][2] + 3)
out[#out + 1] = ((not t4:find("path", 1, true) and not t4:find("cave", 1, true)) and "ok  " or "FAIL") .. " /fr paths off points straight at the target"
ForeverRouteChar.opts.paths = nil
return table.concat(out, "\n")
'''


AUTOQ = r"""
-- auto accept / hand in: only quests the route wants now, any finished quest, never a reward choice
local C = __ns.Core
local out = {}
local function check(name, ok) out[#out + 1] = (ok and "ok   " or "FAIL ") .. name end
local calls
local function reset() calls = {}; fire("GOSSIP_CLOSED"); run_timers() end
local function called(name, arg)
  for _, c in ipairs(calls) do if c[1] == name and (arg == nil or c[2] == arg) then return true end end
  return false
end
local function rec(name) return function(a) calls[#calls + 1] = { name, a } end end
AcceptQuest, CompleteQuest, GetQuestReward = rec("accept"), rec("complete"), rec("reward")
SelectActiveQuest, SelectAvailableQuest = rec("selActive"), rec("selAvail")
local shift, choices, completable = false, 0, true
function IsShiftKeyDown() return shift end
function GetNumQuestChoices() return choices end
function IsQuestCompletable() return completable end
local gActive, gAvail = {}, {}
C_GossipInfo = { GetActiveQuests = function() return gActive end, GetAvailableQuests = function() return gAvail end,
                 SelectActiveQuest = rec("gActive"), SelectAvailableQuest = rec("gAvail") }
local savedLog, savedDone = __log, __done
__log, __done = {}, {}

local near, nearName, far
for i, s in ipairs(C.Steps) do
  if s.t == "A" and not s.dg then
    if not near then near, nearName = s.q[1], s.names and s.names[1]; C.char.current = i; C.char.currentKey = s.key end
    far = s.q[1]
  end
end
local opts = ForeverRouteChar.opts
check("auto is on by default", opts.auto == true)

reset(); __dialogQuest = near; fire("QUEST_DETAIL")
check("the quest of the current step is accepted", called("accept"))
reset(); __dialogQuest = 999999; fire("QUEST_DETAIL")
check("a quest the route does not use is left alone", not called("accept"))
reset(); __dialogQuest = far; fire("QUEST_DETAIL")
check("a quest the route takes much later is left alone", not called("accept"))
reset(); shift = true; __dialogQuest = near; fire("QUEST_DETAIL")
check("holding Shift does nothing", not called("accept")); shift = false
reset(); __log[near] = {}; __dialogQuest = near; fire("QUEST_DETAIL")
check("a quest already in the log is not accepted again", not called("accept")); __log[near] = nil

reset(); gActive = { { questID = 555, isComplete = false }, { questID = 556, isComplete = true } }
gAvail = { { questID = 999999 }, { questID = near } }
fire("GOSSIP_SHOW")
check("gossip: the finished quest is opened first", called("gActive", 556) and not called("gAvail"))
gActive = {}; fire("GOSSIP_SHOW")
check("gossip: then the route's quest, not the other one", called("gAvail", near) and not called("gAvail", 999999))
calls = {}; fire("GOSSIP_SHOW")
check("gossip: the same quest is not opened twice in one talk", #calls == 0)
reset(); gAvail = { { questID = 999999 } }; fire("GOSSIP_SHOW")
check("gossip: nothing is picked when the NPC only has other quests", #calls == 0)
gAvail = {}

function GetNumActiveQuests() return 1 end
function GetActiveTitle() return "Some quest", true end
function GetNumAvailableQuests() return 2 end
function GetAvailableTitle(i) return i == 2 and nearName or "Other quest" end
reset(); fire("QUEST_GREETING")
check("quest list: the finished quest is opened", called("selActive", 1))
function GetNumActiveQuests() return 0 end
reset(); fire("QUEST_GREETING")
check("quest list: the route's quest is found by its name", nearName == nil or called("selAvail", 2))
function GetAvailableQuestInfo(i) return false, 0, false, false, i == 1 and near or 999999 end
reset(); fire("QUEST_GREETING")
check("quest list: the quest ID is used when the game gives one", called("selAvail", 1) and not called("selAvail", 2))

reset(); fire("QUEST_PROGRESS")
check("progress window: Continue is pressed when the quest can be completed", called("complete"))
reset(); completable = false; fire("QUEST_PROGRESS")
check("progress window: left alone when items are missing", not called("complete")); completable = true
reset(); choices = 0; __dialogQuest = near; fire("QUEST_COMPLETE")
check("reward window: completed when there is nothing to choose", called("reward"))
reset(); choices = 3; fire("QUEST_COMPLETE")
check("reward window: a choice of rewards is left to the player", not called("reward")); choices = 0

SlashCmdList.FOREVERROUTE("auto off")
reset(); __dialogQuest = near; fire("QUEST_DETAIL"); fire("QUEST_COMPLETE"); fire("QUEST_PROGRESS")
check("/fr auto off stops all of it", #calls == 0 and opts.auto == false)
SlashCmdList.FOREVERROUTE("auto on")
check("/fr auto on turns it back on", opts.auto == true)

__log, __done = savedLog, savedDone
__dialogQuest = nil
AcceptQuest, CompleteQuest, GetQuestReward, C_GossipInfo = nil, nil, nil, nil
return table.concat(out, "\n")
"""


def auto(lua):
    global FAILED
    res = lua.execute(AUTOQ)
    for line in str(res).split('\n'):
        print('  ', line)
        if line.startswith('FAIL'):
            FAILED = True
    chat(lua)


JUMP = r"""
-- a leveled character using the guide for the first time is offered the segment for its level
local C = __ns.Core
local out = {}
local function check(name, ok) out[#out + 1] = (ok and "ok   " or "FAIL ") .. name end
local prog = ForeverRouteChar.progress[__key]
local savedTicked, savedCur, savedKey, savedLevel = prog.ticked, prog.current, prog.currentKey, __level
local shown
StaticPopupDialogs = {}
function StaticPopup_Show(name) shown = name end
local function fresh(level) prog.ticked = {}; prog.jumpAsked = nil; prog.current = 1; prog.currentKey = C.Steps[1].key; __level = level; shown = nil end

fresh(1)
check("level 1: no offer", C.OfferJump(true) == false and shown == nil)
local want
for i, name in ipairs(C.Segments) do if tonumber(name:match("^(%d+)")) <= 23 then want = i end end
check("segment for level 23 is found from the segment names", C.SegmentForLevel(23) == want and want > 1)
fresh(23)
check("level 23, unused guide: the offer is shown", C.OfferJump(true) == true and shown == "FOREVERROUTE_JUMP")
StaticPopupDialogs.FOREVERROUTE_JUMP.OnAccept()
local cur = C.Steps[prog.current]
check("accepting starts in that segment", cur ~= nil and cur.seg == want)
shown = nil
check("it is only offered once", C.OfferJump(true) == false and shown == nil)
fresh(23); prog.ticked = { x = true }
check("a guide already in use is left alone", C.OfferJump(true) == false and shown == nil)
fresh(23); StaticPopup_Show = nil
check("without the popup API it prints the command instead", C.OfferJump(true) == true)
fresh(40)
SlashCmdList.FOREVERROUTE("seg auto")
cur = C.Steps[prog.current]
check("/fr seg auto jumps to the segment for the level", cur ~= nil and cur.seg == C.SegmentForLevel(40))

prog.ticked, prog.current, prog.currentKey, prog.jumpAsked, __level = savedTicked, savedCur, savedKey, nil, savedLevel
StaticPopupDialogs = nil
return table.concat(out, "\n")
"""


def jump(lua):
    global FAILED
    res = lua.execute(JUMP)
    for line in str(res).split('\n'):
        print('  ', line)
        if line.startswith('FAIL'):
            FAILED = True
    chat(lua)


def paths(lua):
    global FAILED
    res = lua.execute(PATHS)
    for line in str(res).split('\n'):
        print('  ', line)
        if line.startswith('FAIL'):
            FAILED = True


FEATURES = r'''
local C = __ns.Core
local out = {}
local function check(name, ok) out[#out + 1] = (ok and "ok   " or "FAIL ") .. name; if not ok then __failed = true end end
local function goto_step(i) C.char.current = i; C.char.currentKey = C.Steps[i].key end
local function first(kind, from)
  for i = from or 1, #C.Steps do if C.Steps[i].t == kind then return i end end
end

-- 1. Skip on an Accept step: the quest's later Do / Turn-in steps skip themselves
local ai, ti, q
for i = 40, #C.Steps do
  local s = C.Steps[i]
  if s.t == "A" and #s.q == 1 then
    for j = i + 1, math.min(i + 60, #C.Steps) do
      local t = C.Steps[j]
      if t.t == "T" and #t.q == 1 and t.q[1] == s.q[1] then ai, ti, q = i, j, s.q[1] break end
    end
  end
  if ai then break end
end
check("turn-in waits while the quest is merely not taken", not C.IsDone(C.Steps[ti]) and C.IsBlocked(C.Steps[ti]))
goto_step(ai); C.Skip()
check("skipped accept: its turn-in is done and not blocked", C.IsDone(C.Steps[ti]) and not C.IsBlocked(C.Steps[ti]))
__log[q] = { ready = false }
check("taking the quest after all brings the turn-in back", not C.IsDone(C.Steps[ti]))
__log[q] = nil
goto_step(ai + 1); C.Back()
check("Back on the skipped accept forgets the decline", C.char.current == ai and not C.IsDone(C.Steps[ti]))

-- 2. Get flight path: only at the flight master the step names
local fi = first("F")
local arg = C.Steps[fi].arg
function NumTaxiNodes() return 2 end
function TaxiNodeGetType(i) return i == 2 and "CURRENT" or "REACHABLE" end
function TaxiNodeName(i) return __node end
goto_step(fi); __node = "Elsewhere, Nowhere"; fire("TAXIMAP_OPENED")
check("F step stays at another flight master", C.char.ticked[C.Steps[fi].key] == nil)
__node = arg .. ", Some Zone"; fire("TAXIMAP_OPENED")
check("F step ticks at its own flight master (" .. arg .. ")", C.char.ticked[C.Steps[fi].key] == "auto")

-- 3. Fly to: a taxi ride that ends in the named place
local li = first("FLY")
local dest = C.Steps[li].arg
__taxi = true
function UnitOnTaxi() return __taxi end
goto_step(li); __sub = "Not There"
fire("PLAYER_CONTROL_LOST"); run_timers(); __taxi = false; fire("PLAYER_CONTROL_GAINED"); run_timers()
check("FLY step stays after landing somewhere else", C.char.ticked[C.Steps[li].key] == nil)
__taxi = true; __sub = "The " .. dest
fire("PLAYER_CONTROL_LOST"); run_timers(); __taxi = false; fire("PLAYER_CONTROL_GAINED"); run_timers()
check("FLY step ticks after landing at " .. dest, C.char.ticked[C.Steps[li].key] == "auto")
goto_step(li); C.char.ticked[C.Steps[li].key] = nil
fire("PLAYER_CONTROL_GAINED"); run_timers()
check("losing control without a flight (stun, fear) does not tick FLY", C.char.ticked[C.Steps[li].key] == nil)

-- 4. Hearth
local hi = first("H")
goto_step(hi); fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast", 133); run_timers()
check("another spell does not tick H", C.char.ticked[C.Steps[hi].key] == nil)
fire("UNIT_SPELLCAST_SUCCEEDED", "player", "cast", 8690); run_timers()
check("Hearthstone ticks H", C.char.ticked[C.Steps[hi].key] == "auto")

-- 5. Train
local tr = first("TRAIN")
function IsTradeskillTrainer() return __trade end
goto_step(tr); __trade = true; fire("TRAINER_SHOW"); fire("TRAINER_CLOSED")
check("profession trainer does not tick TRAIN", C.char.ticked[C.Steps[tr].key] == nil)
__trade = false; fire("TRAINER_SHOW"); fire("TRAINER_CLOSED")
check("class trainer ticks TRAIN", C.char.ticked[C.Steps[tr].key] == "auto")
return table.concat(out, "; ")
'''


DUNGEONS = r'''
local C = __ns.Core
local slash = SlashCmdList.FOREVERROUTE
local out = {}
local function check(name, ok) out[#out + 1] = (ok and "ok   " or "FAIL ") .. name; if not ok then __failed = true end end
local all = C.route.steps
local nBase, nDg = 0, 0
for _, s in ipairs(all) do if s.dg then nDg = nDg + 1 else nBase = nBase + 1 end end
check("route file has dungeon steps (" .. nDg .. ")", nDg > 0 and C.HasDungeons())

-- 1. Off by default: exactly the quest-only route, with the keys the 0.3 addon gave its steps
local clean = not C.DungeonsOn() and #C.Steps == nBase
for _, s in ipairs(C.Steps) do if s.dg then clean = false end end
check("dungeons are off by default and no dungeon step is followed", clean)
local seen, same, k = {}, true, 0
for _, s in ipairs(all) do
  if not s.dg then
    k = k + 1
    local what = s.q and table.concat(s.q, ",") or tostring(s.arg or s.lvl or "")
    local where = s.x and string.format("%.1f,%.1f", s.x, s.y) or ""
    local body = table.concat({ C.Segments[s.seg] or "", s.t, what, where, s.text or "" }, "|")
    seen[body] = (seen[body] or 0) + 1
    if s.key ~= body .. "#" .. seen[body] or s.index ~= k then same = false end
  end
end
check("quest-only steps keep the keys and numbering of version 0.3 (saved progress carries over)", same)

-- 2. Turning dungeons on keeps your place and adds the steps
C.char.dgSkip = {}
local firstRun
for i, s in ipairs(all) do if s.run then firstRun = i break end end
local before
for i = firstRun, 1, -1 do if not all[i].dg then before = all[i] break end end
C.char.current = before.index; C.char.currentKey = before.key
slash("dungeons on")
check("/fr dungeons on adds the dungeon steps", C.DungeonsOn() and #C.Steps == nBase + nDg)
check("turning dungeons on keeps your place", C.Steps[C.char.current].key == before.key)
local keysSame = true
for _, s in ipairs(all) do if not s.dg and C.Steps[s.index] ~= s then keysSame = false end end
check("every quest-only step is still there, in the same order", keysSame)

-- 3. Skip on the run step hides the rest of that dungeon; Back brings it back
local run = all[firstRun]
local dg = run.dg
local laterT
for i = firstRun + 1, #all do if all[i].dg == dg and all[i].t == "T" and not all[i].req then laterT = all[i] break end end
__log[laterT.q[1]] = { ready = true }
check("a dungeon hand-in shows while you carry its quest", not C.IsDone(laterT) and not C.IsBlocked(laterT))
C.char.current = run.index; C.char.currentKey = run.key
C.Skip()
check("Skip on the run step hides that dungeon's hand-ins", C.IsDone(laterT) and C.char.dgSkip[dg] == true)
C.char.current = run.index + 1; C.Back()
check("Back on the run step brings them back", not C.IsDone(laterT) and C.char.dgSkip[dg] == nil)
__log[laterT.q[1]] = nil
check("a dungeon hand-in for a quest you do not carry is passed over, not blocking", C.IsDone(laterT) and not C.IsBlocked(laterT))

-- 4. Chained steps wait for the step before them
local chained
for _, s in ipairs(all) do if s.dg and s.req and s.t == "A" and s.q[1] ~= s.req then chained = s break end end
if chained then
  check("a chained pick-up stays hidden until the quest before it is done", C.IsDone(chained))
  __done[chained.req] = true
  check("... and shows once that quest is handed in", not C.IsDone(chained))
  __done[chained.req] = nil
end

-- 5. Turning dungeons off while standing on a dungeon step moves to the next quest-only step
local nextBase
for i = firstRun + 1, #all do if not all[i].dg then nextBase = all[i] break end end
C.char.ticked[run.key] = "tick"
C.char.current = run.index; C.char.currentKey = run.key
slash("dungeons off")
check("/fr dungeons off returns to the quest-only route", not C.DungeonsOn() and #C.Steps == nBase)
check("... and carries on at the next quest-only step", C.char.current <= nextBase.index and not C.Steps[C.char.current].dg)
check("ticks on dungeon steps are kept while dungeons are off", C.char.ticked[run.key] == "tick")
C.char.ticked[run.key] = nil

-- 6. Grey quest rule. Classic table: level 20 -> grey at 13 and below; level 48 -> grey at 38 and below
check("grey rule (Classic table)", C.IsGrey(13, 20) and not C.IsGrey(14, 20) and C.IsGrey(38, 48) and not C.IsGrey(39, 48) and not C.IsGrey(nil, 30))
GetQuestGreenRange = function() return 9 end
check("grey rule uses the game's own range when it has one", C.IsGrey(10, 20) and not C.IsGrey(11, 20))
GetQuestGreenRange = nil

-- 7. Step text marks dungeon steps as optional
slash("dungeons on")
local txt = __ns.UI.StepText(laterT)
check("dungeon steps are labelled Optional with the dungeon's name", txt:find("Optional %(") ~= nil and txt:find(C.route.dungeons[dg].name, 1, true) ~= nil)
check("the run step names the dungeon and its levels", (run.arg or ""):find("Optional dungeon: ", 1, true) == 1)
slash("dungeons list")
slash("dungeons off")
return table.concat(out, "; ")
'''


def features(lua, fire, run):
    lua.execute('function GetSubZoneText() return __sub or "" end')
    for line in lua.execute(FEATURES).split('; '):
        print('   ' + line)
    print('   -- optional dungeons')
    for line in lua.execute(DUNGEONS).split('; '):
        print('   ' + line)
    print('   ', chat(lua)[-3:])
    if lua.eval('__failed'):
        global FAILED
        FAILED = True


def first_quest(lua):
    """First quest id of the active route's first A step (read from the generated Lua file)."""
    import re
    key = lua.eval('__key')
    name = {'undead-mage': 'UndeadMage', 'orc-shaman': 'OrcShaman', 'dwarf-shaman': 'DwarfShaman',
            'skyborne-druid': 'SkyborneDruid', 'skyborne-mage': 'SkyborneMage', 'human-mage': 'HumanMage', 'gnome': 'Gnome', 'human-warlock': 'HumanWarlock',
            'dwarf': 'Dwarf', 'human': 'Human', 'night-elf': 'NightElf', 'skyborne': 'Skyborne'}[key]
    text = (ADDON_DIR / 'Routes' / f'{name}.lua').read_text(encoding='utf-8')
    m = re.search(r'\{t="A", seg=\d+, q=\{(\d+)', text)
    return int(m.group(1))


FAILED = False

if __name__ == '__main__':
    main()
    sys.exit(1 if FAILED else 0)
