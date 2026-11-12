-- Forever Route: step tracking, quest API wrappers and the quest logger.
local ADDON, ns = ...

local Core = {}
ns.Core = Core

local CQ = C_QuestLog
local floor, format, tostring, type, pairs, ipairs = math.floor, string.format, tostring, type, pairs, ipairs

-- Retail-engine clients can hand back "secret" values that error on use; treat them as unknown.
local function Secret(v)
    return issecretvalue ~= nil and v ~= nil and issecretvalue(v)
end
Core.Secret = Secret

---------------------------------------------------------------------------
-- Quest API wrappers (Forever uses the modern C_QuestLog; older globals are fallbacks)
---------------------------------------------------------------------------
local function LogIndexFor(q)
    if CQ and CQ.GetLogIndexForQuestID then
        return CQ.GetLogIndexForQuestID(q)
    elseif GetQuestLogIndexByID then
        local i = GetQuestLogIndexByID(q)
        if i and i > 0 then return i end
    end
    return nil
end

function Core.IsOnQuest(q)
    if CQ and CQ.IsOnQuest then
        return CQ.IsOnQuest(q) and true or false
    end
    return LogIndexFor(q) ~= nil
end

function Core.IsTurnedIn(q)
    if CQ and CQ.IsQuestFlaggedCompleted then
        return CQ.IsQuestFlaggedCompleted(q) and true or false
    elseif IsQuestFlaggedCompleted then
        return IsQuestFlaggedCompleted(q) and true or false
    end
    return false
end

-- Objectives finished (ready to hand in)
function Core.IsReady(q)
    if CQ and CQ.IsComplete then
        return CQ.IsComplete(q) and true or false
    end
    local i = LogIndexFor(q)
    if i and GetQuestLogTitle then
        -- Classic tuple: title, level, suggestedGroup, isHeader, isCollapsed, isComplete, ...
        local isComplete = select(6, GetQuestLogTitle(i))
        return isComplete == 1
    end
    return false
end

function Core.GetObjectives(q)
    if CQ and CQ.GetQuestObjectives then
        return CQ.GetQuestObjectives(q) or {}
    end
    return {}
end

local function ObjectiveDone(q, idx)
    local o = Core.GetObjectives(q)[idx]
    if not o then return Core.IsReady(q) end
    return o.finished and true or false
end

-- Quest IDs currently in the log
local function QuestLogIDs()
    local ids = {}
    if CQ and CQ.GetNumQuestLogEntries and CQ.GetInfo then
        local n = CQ.GetNumQuestLogEntries()
        for i = 1, n do
            local info = CQ.GetInfo(i)
            if info and not info.isHeader and info.questID and info.questID > 0 then
                ids[#ids + 1] = info.questID
            end
        end
    elseif GetNumQuestLogEntries and GetQuestLogTitle then
        local n = GetNumQuestLogEntries()
        for i = 1, n do
            local _, _, _, isHeader, _, _, _, questID = GetQuestLogTitle(i)
            if not isHeader and questID and questID > 0 then ids[#ids + 1] = questID end
        end
    end
    return ids
end
Core.QuestLogIDs = QuestLogIDs

---------------------------------------------------------------------------
-- Player position
---------------------------------------------------------------------------
function Core.PlayerPosition()
    if not (C_Map and C_Map.GetBestMapForUnit) then return nil end
    local mapID = C_Map.GetBestMapForUnit("player")
    if not mapID or Secret(mapID) then return nil end
    local pos = C_Map.GetPlayerMapPosition(mapID, "player")
    if not pos then return mapID end
    local x, y = pos:GetXY()
    if Secret(x) or Secret(y) then return mapID end
    return mapID, x, y
end

local function Snapshot()
    local mapID, x, y = Core.PlayerPosition()
    return {
        map = mapID,
        x = x and floor(x * 1000 + 0.5) / 10 or nil,
        y = y and floor(y * 1000 + 0.5) / 10 or nil,
        zone = GetZoneText and GetZoneText() or nil,
        sub = GetSubZoneText and GetSubZoneText() or nil,
        lvl = UnitLevel("player"),
        time = time(),
    }
end

---------------------------------------------------------------------------
-- Steps
---------------------------------------------------------------------------
-- The active route (ns.Routes[key], one per race/class, generated into Routes/*.lua)
local Steps, Segments = {}, {}
Core.Steps, Core.Segments = Steps, Segments

local MANUAL = { N = true, H = true, F = true, FLY = true, TRAIN = true, G = true }
Core.MANUAL = MANUAL

-- Content-based keys so ticks and the saved position survive route regeneration.
-- A route file holds every step; steps with dg = <dungeon number> belong to an optional dungeon run and are
-- only followed when the "dungeons" option is on. With it off the list is exactly the quest-only route.
local keyIndex = {}  -- key -> position in the list being followed
local allKeys = {}   -- key -> position in the full list (dungeon steps included)
local function IndexSteps(all, withDungeons)
    keyIndex, allKeys = {}, {}
    local seen, active = {}, {}
    for i, s in ipairs(all) do
        local what = s.q and table.concat(s.q, ",") or tostring(s.arg or s.lvl or "")
        local where = s.x and format("%.1f,%.1f", s.x, s.y) or ""
        local body = table.concat({ Segments[s.seg] or "", s.t, what, where, s.text or "" }, "|")
        if s.dg then body = "dg" .. s.dg .. "|" .. body end -- never shifts the numbering of quest-only steps
        seen[body] = (seen[body] or 0) + 1
        s.key = body .. "#" .. seen[body]
        allKeys[s.key] = i
        s.index = nil
        if withDungeons or not s.dg then
            active[#active + 1] = s
            s.index = #active
            keyIndex[s.key] = #active
        end
    end
    return active
end

local saved -- ForeverRouteChar: { opts = {}, route = key or nil (auto), progress = { [key] = {...} } }
local char  -- progress on the active route: { ticked = {}, current = n, currentKey = key }
local routeQuests -- quest IDs used by the active route (built on demand)
local acceptAt, acceptByName -- auto accept: [quest] = index of its Accept step, [title] = { quests }

local function Ticked(s)
    return char and char.ticked[s.key]
end

-- Loose place-name match: "Crossroads" fits "The Crossroads" and "Crossroads, The Barrens"
local function TextMatches(have, want)
    if type(have) ~= "string" or type(want) ~= "string" or Secret(have) then return false end
    if have == "" or want == "" then return false end
    have, want = have:lower(), want:lower()
    return have:find(want, 1, true) ~= nil or want:find(have, 1, true) ~= nil
end

local function BindMatches(arg)
    if not GetBindLocation then return false end
    return TextMatches(GetBindLocation(), arg)
end

-- A quest you pressed Done / Skip on at its Accept step without taking it. Its later "Do" and
-- "Turn in" steps then skip themselves; taking the quest after all brings them back.
local function Declined(q)
    return char and char.declined and char.declined[q]
        and not Core.IsOnQuest(q) and not Core.IsTurnedIn(q) and true or false
end
Core.Declined = Declined

-- You pressed Skip on the "run" step of a dungeon: every step of that dungeon counts as done
local function DungeonSkipped(s)
    return s.dg and char and char.dgSkip and char.dgSkip[s.dg] and true or false
end

-- Optional dungeon steps never hold the route up:
--   a step chained to an earlier quest (req) waits out of sight until that quest is taken or handed in;
--   a hand-in for a quest you are not carrying (never took it, or it starts inside the dungeon) is passed over.
local function DungeonStepDone(s)
    if DungeonSkipped(s) then return true end
    local req = s.req
    if req and req ~= (s.q and s.q[1]) and not (Core.IsOnQuest(req) or Core.IsTurnedIn(req)) then return true end
    if s.t == "T" then
        for _, q in ipairs(s.q) do
            if Core.IsOnQuest(q) then return false end
        end
        return true
    end
    return nil -- decided by the normal rules
end

function Core.IsDone(s)
    if Ticked(s) then return true end
    local t = s.t
    if s.dg then
        local done = DungeonStepDone(s)
        if done ~= nil then return done end
    end
    if t == "A" then
        for _, q in ipairs(s.q) do
            if not (Core.IsOnQuest(q) or Core.IsTurnedIn(q)) then return false end
        end
        return true
    elseif t == "C" then
        for k, q in ipairs(s.q) do
            if not Core.IsTurnedIn(q) and not Declined(q) then
                if not Core.IsOnQuest(q) then return false end
                local obj = s.obj and s.obj[k]
                if obj and obj > 0 then
                    if not ObjectiveDone(q, obj) then return false end
                elseif not Core.IsReady(q) then
                    return false
                end
            end
        end
        return true
    elseif t == "T" then
        for _, q in ipairs(s.q) do
            if not Core.IsTurnedIn(q) and not Declined(q) then return false end
        end
        return true
    elseif t == "L" then
        return (UnitLevel("player") or 1) >= s.lvl
    elseif t == "S" then
        return BindMatches(s.arg)
    end
    return false
end

-- A "C"/"T" step for a quest you are not on (abandoned / never got) cannot finish by itself
function Core.IsBlocked(s)
    if s.dg then return false end
    if s.t == "C" or s.t == "T" then
        for _, q in ipairs(s.q) do
            if not Core.IsTurnedIn(q) and not Core.IsOnQuest(q) and not Declined(q) then return true end
        end
    end
    return false
end

local function SetCurrent(i)
    if i < 1 then i = 1 end
    if i > #Steps + 1 then i = #Steps + 1 end
    char.current = i
    char.currentKey = Steps[i] and Steps[i].key or "END"
end

-- Advance the pointer past finished steps. Never moves backwards on its own.
function Core.Refresh()
    if not char then return end
    local i = char.current or 1
    while i <= #Steps and Core.IsDone(Steps[i]) do
        i = i + 1
    end
    SetCurrent(i)
    if ns.UI and ns.UI.Update then ns.UI.Update() end
end

function Core.Current()
    return char and Steps[char.current]
end

-- Upcoming steps after the current one that are not already done
function Core.Upcoming(count)
    local out = {}
    if not char then return out end
    local i = char.current + 1
    while i <= #Steps and #out < count do
        if not Core.IsDone(Steps[i]) then out[#out + 1] = Steps[i] end
        i = i + 1
    end
    return out
end

function Core.Tick(s, how)
    if not s or not char then return end
    char.ticked[s.key] = how or "tick"
    if s.t == "A" then -- Done / Skip without the quest: remember it so its later steps do not block
        for _, q in ipairs(s.q) do
            if not Core.IsOnQuest(q) and not Core.IsTurnedIn(q) then char.declined[q] = true end
        end
    end
    if s.run and how == "skip" then char.dgSkip[s.dg] = true end -- not running this dungeon
    Core.LogEvent(how or "tick", { step = s.index, key = s.key, t = s.t, q = s.q and s.q[1], dg = s.dg })
    Core.Refresh()
end

function Core.Skip()
    Core.Tick(Core.Current(), "skip")
end

-- Undo the most recent manual tick/skip before the current step
function Core.Back()
    if not char then return end
    for i = math.min(char.current, #Steps + 1) - 1, 1, -1 do
        local s = Steps[i]
        if char.ticked[s.key] then
            char.ticked[s.key] = nil
            if s.t == "A" then
                for _, q in ipairs(s.q) do char.declined[q] = nil end
            end
            if s.run then char.dgSkip[s.dg] = nil end
            SetCurrent(i)
            Core.holdKey = s.key -- don't instantly re-tick a "Go to" step you are standing on
            if ns.UI and ns.UI.Update then ns.UI.Update() end
            return true
        end
    end
    Core.Print("nothing to undo: earlier steps were completed by quest progress")
    return false
end

function Core.JumpToSegment(n)
    if not char then return false end
    for i, s in ipairs(Steps) do
        if s.seg == n then
            SetCurrent(i)
            Core.Refresh()
            return true
        end
    end
    return false
end

-- A character that is already leveled when the addon is first used: offer to start at the segment for its level
-- (segment names begin with their level range, "20-22 Redridge II & Duskwood I").
function Core.SegmentForLevel(level)
    local best
    for i, name in ipairs(Segments) do
        local from = type(name) == "string" and tonumber(name:match("^(%d+)"))
        if from and from <= level then best = i end
    end
    return best
end

local jumpOffered = false
function Core.OfferJump(again)
    if (jumpOffered and not again) or not char or char.jumpAsked then return false end
    jumpOffered = true
    if next(char.ticked) ~= nil then return false end -- the guide is already in use on this character
    local level = UnitLevel("player") or 1
    local seg = Core.SegmentForLevel(level)
    local cur = Steps[char.current or 1]
    if not seg or seg <= 1 or not cur or cur.seg >= seg then return false end
    char.jumpAsked = true
    local name = Segments[seg] or tostring(seg)
    local function jump()
        if Core.JumpToSegment(seg) then
            Core.Print("started at segment " .. seg .. " (" .. name .. "). Quests you already did are skipped. Press Skip on a step for a quest you never took. /fr seg lists the segments if this one does not fit.")
        end
    end
    if StaticPopupDialogs and StaticPopup_Show then
        StaticPopupDialogs.FOREVERROUTE_JUMP = {
            text = "Forever Route\n\nYou are level " .. level .. ". Start the guide at segment " .. seg .. ", \"" .. name
                .. "\"?\n\nQuests you already did are skipped. You can change this later with /fr seg.",
            button1 = "Start there",
            button2 = "Start at step 1",
            OnAccept = jump,
            timeout = 0,
            whileDead = true,
            hideOnEscape = true,
            preferredIndex = 3,
        }
        StaticPopup_Show("FOREVERROUTE_JUMP")
    else
        Core.Print("you are level " .. level .. ": type /fr seg " .. seg .. " to start the guide at \"" .. name .. "\".")
    end
    return true
end

-- Optional dungeon runs: off = the quest-only route, on = the same route with dungeon steps added
function Core.DungeonsOn()
    return saved and saved.opts and saved.opts.dungeons and true or false
end

function Core.HasDungeons()
    return Core.route and Core.route.dungeons and #Core.route.dungeons > 0 or false
end

function Core.SetDungeons(on)
    if not saved then return end
    saved.opts.dungeons = on and true or false
    if Core.routeKey then
        Core.SelectRoute(Core.routeKey)
        Core.Refresh()
    end
    Core.LogEvent("dungeons", { on = saved.opts.dungeons })
    if ns.UI and ns.UI.Update then ns.UI.Update(true) end
end

function Core.DungeonsLine()
    if not Core.HasDungeons() then return "this route has no dungeon steps" end
    if Core.DungeonsOn() then
        return "optional dungeon runs are ON (" .. #Core.route.dungeons .. " dungeons). /fr dungeons off for the quest-only route."
    end
    return "quest-only, no dungeons. /fr dungeons on adds optional dungeon runs."
end

-- Has a quest gone grey (no longer worth its experience) at this player level?
-- Asks the game for its own range when it offers one; otherwise the Classic grey-level table.
function Core.IsGrey(questLevel, playerLevel)
    if not questLevel or questLevel <= 0 or not playerLevel then return false end
    local range = (GetQuestGreenRange and GetQuestGreenRange())
        or (UnitQuestTrivialLevelRange and UnitQuestTrivialLevelRange("player"))
    if type(range) == "number" and not Secret(range) and range > 0 then
        return playerLevel - questLevel > range
    end
    local grey
    if playerLevel <= 5 then grey = 0
    elseif playerLevel <= 39 then grey = playerLevel - 5 - floor(playerLevel / 10)
    elseif playerLevel <= 59 then grey = playerLevel - 1 - floor(playerLevel / 5)
    else grey = playerLevel - 9 end
    return questLevel <= grey
end

-- Best route for this character: class match counts double, race match once
local CLASSIC_RACES = { Human = true, Dwarf = true, NightElf = true, Gnome = true, Orc = true, Scourge = true, Tauren = true, Troll = true }
function Core.AutoRoute()
    local _, race = UnitRace("player")
    local _, class = UnitClass("player")
    local faction = UnitFactionGroup and UnitFactionGroup("player")
    -- The Skyborne race token is not known. Every Classic race is, so anything else is taken to be Skyborne
    -- (otherwise a Skyborne Mage would tie with the Human Mage route and get the wrong one).
    if race and not CLASSIC_RACES[race] then race = "Skyborne" end
    local best, bestScore
    for key, r in pairs(ns.Routes or {}) do
        local score = 0
        -- a route for the other faction is never the automatic pick while one for yours exists
        if r.faction and faction and r.faction ~= faction then score = -10 end
        -- your race's route first (its start zone is the one you are standing in); within a race the route written
        -- for your class beats the any-class one (no classes listed), which beats one written for another class
        for _, x in ipairs(r.races or {}) do if x == race then score = score + 4 end end
        local classes = r.classes or {}
        if #classes > 0 then
            local mine = false
            for _, c in ipairs(classes) do if c == class then mine = true end end
            score = score + (mine and 2 or -1)
        end
        if not bestScore or score > bestScore or (score == bestScore and key < best) then
            best, bestScore = key, score
        end
    end
    return best
end

function Core.SelectRoute(key)
    local r = key and ns.Routes and ns.Routes[key]
    if not r or not saved then return false end
    Core.routeKey, Core.route = key, r
    Segments = r.segments
    Steps = IndexSteps(r.steps, Core.DungeonsOn())
    Core.Steps, Core.Segments = Steps, Segments
    routeQuests = nil
    acceptAt = nil
    saved.progress[key] = saved.progress[key] or {}
    char = saved.progress[key]
    char.ticked = char.ticked or {}
    char.declined = char.declined or {}
    char.dgSkip = char.dgSkip or {}
    -- Restore the pointer by step key; fall back to the start (finished steps auto-skip)
    local i = char.currentKey and keyIndex[char.currentKey]
    if not i and char.currentKey and allKeys[char.currentKey] then
        -- the saved step is a dungeon step and dungeons are now off: carry on with the next quest-only step
        for j = allKeys[char.currentKey], #r.steps do
            if r.steps[j].index then i = r.steps[j].index break end
        end
        i = i or #Steps + 1
    end
    if char.currentKey == "END" then i = #Steps + 1 end
    if not i and char.currentKey and type(char.current) == "number" then
        -- The saved step is gone (its text or position changed in a new build). Going back to step 1 would
        -- stall on the first re-worded manual step, so stay where the saved step number was: finished
        -- steps from there on still skip themselves.
        i = math.max(1, math.min(char.current, #Steps + 1))
        Core.resumedByNumber = true
    end
    SetCurrent(i or 1)
    -- forget ticks for steps that no longer exist (dungeon steps are kept while dungeons are off)
    for k in pairs(char.ticked) do
        if not allKeys[k] then char.ticked[k] = nil end
    end
    Core.char = char
    return true
end

---------------------------------------------------------------------------
-- Logger: records what really happens in game so the route can be corrected
---------------------------------------------------------------------------
local LOG_MAX = 20000
local OBJ_SAMPLES = 15

local function NpcFromUnit(unit)
    local name = UnitName(unit)
    local guid = UnitGUID(unit)
    if Secret(name) then name = nil end
    if not guid or Secret(guid) then return name, nil end
    local kind, _, _, _, _, id = strsplit("-", guid)
    if kind == "Creature" or kind == "GameObject" then
        return name, tonumber(id)
    end
    return name, nil
end

function Core.LogEvent(kind, data, snap)
    if not ForeverRouteLog then return end
    local ev = data or {}
    ev.e = kind
    for k, v in pairs(snap or Snapshot()) do
        if ev[k] == nil then ev[k] = v end
    end
    ev.char = UnitName("player")
    local events = ForeverRouteLog.events
    events[#events + 1] = ev
    if #events > LOG_MAX then table.remove(events, 1) end
    return ev
end

-- Dialog snapshots keyed by quest ID: who and where, captured while the dialog is open
local dialogAccept, dialogTurnin = {}, {}
local loggedTurnin = {}

local function DialogQuestID()
    local id = GetQuestID and GetQuestID()
    if id and not Secret(id) and id > 0 then return id end
    return nil
end

local function CaptureDialog(store)
    local id = DialogQuestID()
    if not id then return end
    local name, npcId = NpcFromUnit("npc")
    store[id] = { npc = name, npcId = npcId, snap = Snapshot(), t = GetTime() }
end

local function TakeDialog(store, q)
    local d = store[q]
    store[q] = nil
    if d and GetTime() - d.t < 300 then return d end
    return nil
end

-- Objective progress: log only real increases over the best value seen this session
local objBest = {}    -- ["q:i"] = highest numFulfilled seen
local objSamples = {} -- ["q:i"] = events logged
local objFresh = {}   -- [q] = true when accepted this session, so its counts start from 0
local loading = true  -- suppress during login / loading screens

local function ScanObjectives()
    if loading then return end
    for _, q in ipairs(QuestLogIDs()) do
        for i, o in ipairs(Core.GetObjectives(q)) do
            local k = q .. ":" .. i
            local n = o.numFulfilled
            if Secret(n) then n = nil end
            n = n or (o.finished and 1 or 0)
            local best = objBest[k]
            if best == nil and objFresh[q] then best = 0 end
            if best == nil then
                objBest[k] = n -- first sighting: baseline only
            elseif n > best then
                objBest[k] = n
                objSamples[k] = (objSamples[k] or 0) + 1
                if objSamples[k] <= OBJ_SAMPLES or o.finished then
                    Core.LogEvent("objective", { q = q, i = i, n = n, need = o.numRequired, text = o.text, done = o.finished or nil })
                end
            end
        end
    end
end

local function RouteHasQuest(q)
    if not routeQuests then
        routeQuests = {}
        for _, s in ipairs(Steps) do
            if s.q then
                for _, id in ipairs(s.q) do routeQuests[id] = true end
            end
        end
    end
    return routeQuests[q] or false
end

local function LogTurnin(q, extra)
    if loggedTurnin[q] then return loggedTurnin[q].ev end
    local d = TakeDialog(dialogTurnin, q) or {}
    local data = { q = q, npc = d.npc, npcId = d.npcId, offroute = (not RouteHasQuest(q)) or nil }
    for k, v in pairs(extra or {}) do data[k] = v end
    local ev = Core.LogEvent("turnin", data, d.snap)
    loggedTurnin[q] = { ev = ev, t = GetTime() }
    return ev
end

---------------------------------------------------------------------------
-- Auto accept / hand in (option "auto", /fr auto). Hold Shift while talking to do it by hand.
--   Accept: only quests the route takes at the current step or within the next AUTO_AHEAD steps, so an
--           NPC never hands you a quest the guide skips, or an escort the guide starts later.
--   Hand in: any finished quest. A reward with more than one choice is left for you to pick.
---------------------------------------------------------------------------
local AUTO_AHEAD = 12
local tried = {}             -- picked once in this conversation: never loop on a dialog that did not go through

local function AutoOn()
    return char and Core.opts and Core.opts.auto and not (IsShiftKeyDown and IsShiftKeyDown()) and true or false
end

local function BuildAccepts()
    acceptAt, acceptByName = {}, {}
    for i, s in ipairs(Steps) do
        if s.t == "A" and s.q then
            for k, q in ipairs(s.q) do
                if not acceptAt[q] then
                    acceptAt[q] = i
                    local name = s.names and s.names[k]
                    if name then
                        acceptByName[name] = acceptByName[name] or {}
                        table.insert(acceptByName[name], q)
                    end
                end
            end
        end
    end
end

-- The route wants this quest taken now
local function WantsNow(q)
    if type(q) ~= "number" or q <= 0 then return false end
    if not acceptAt then BuildAccepts() end
    local at = acceptAt[q]
    if not at or at > (char.current or 1) + AUTO_AHEAD then return false end
    if Core.IsOnQuest(q) or Core.IsTurnedIn(q) or Declined(q) then return false end
    local s = Steps[at]
    if s.dg and DungeonSkipped(s) then return false end
    return true
end
Core.WantsNow = WantsNow

local function WantedByTitle(title)
    if type(title) ~= "string" or Secret(title) then return nil end
    if not acceptAt then BuildAccepts() end
    for _, q in ipairs(acceptByName[title] or {}) do
        if WantsNow(q) then return q end
    end
    return nil
end

local function Num(v)
    if type(v) == "number" and not Secret(v) and v > 0 then return v end
    return nil
end

local function TalkEnded()
    C_Timer.After(0.5, function()
        if (GossipFrame and GossipFrame:IsVisible()) or (QuestFrame and QuestFrame:IsVisible()) then return end
        for k in pairs(tried) do tried[k] = nil end
    end)
end

-- NPC with a gossip window: quest IDs are in the list
local function AutoGossip()
    local G = C_GossipInfo
    if not (AutoOn() and G and G.GetActiveQuests and G.GetAvailableQuests) then return end
    for _, quest in ipairs(G.GetActiveQuests() or {}) do
        local q = Num(quest.questID)
        if q and not tried["T" .. q] and (quest.isComplete == true or Core.IsReady(q)) then
            tried["T" .. q] = true
            G.SelectActiveQuest(q)
            return
        end
    end
    for _, quest in ipairs(G.GetAvailableQuests() or {}) do
        local q = Num(quest.questID)
        if q and not tried["A" .. q] and WantsNow(q) then
            tried["A" .. q] = true
            G.SelectAvailableQuest(q)
            return
        end
    end
end

-- NPC with the plain quest list
local function AutoGreeting()
    if not (AutoOn() and GetNumActiveQuests and GetNumAvailableQuests) then return end
    for i = 1, GetNumActiveQuests() or 0 do
        local title, done = GetActiveTitle(i)
        local q = GetActiveQuestID and Num(GetActiveQuestID(i))
        local k = "T" .. tostring(q or (not Secret(title) and title) or i)
        if not tried[k] and ((not Secret(done) and done) or (q and Core.IsReady(q))) then
            tried[k] = true
            SelectActiveQuest(i)
            return
        end
    end
    for i = 1, GetNumAvailableQuests() or 0 do
        local q = GetAvailableQuestInfo and Num((select(5, GetAvailableQuestInfo(i))))
        if q then
            if not WantsNow(q) then q = nil end
        else
            q = WantedByTitle(GetAvailableTitle and GetAvailableTitle(i))
        end
        if q and not tried["A" .. q] then
            tried["A" .. q] = true
            SelectAvailableQuest(i)
            return
        end
    end
end

local function AutoAccept()
    if not (AutoOn() and AcceptQuest) then return end
    local guid = UnitGUID("questnpc")
    if type(guid) == "string" and not Secret(guid) and guid:find("^Player") then return end -- shared by a player
    if WantsNow(DialogQuestID()) then AcceptQuest() end
end

local function AutoProgress()
    if AutoOn() and CompleteQuest and IsQuestCompletable and IsQuestCompletable() then CompleteQuest() end
end

local function AutoReward()
    if not (AutoOn() and GetQuestReward and GetNumQuestChoices) then return end
    local n = GetNumQuestChoices()
    if Secret(n) or (n or 0) > 1 then return end
    GetQuestReward(1)
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------
local frame = CreateFrame("Frame")
local refreshQueued = false

local function QueueRefresh()
    if refreshQueued then return end
    refreshQueued = true
    C_Timer.After(0.3, function()
        refreshQueued = false
        Core.Refresh()
    end)
end
Core.QueueRefresh = QueueRefresh

local handlers = {}

function handlers.ADDON_LOADED(name)
    if name ~= ADDON then return end
    ForeverRouteLog = ForeverRouteLog or {}
    ForeverRouteLog.version = 1
    ForeverRouteLog.events = ForeverRouteLog.events or {}
    ForeverRouteChar = ForeverRouteChar or {}
    saved = ForeverRouteChar
    saved.opts = saved.opts or {}
    saved.progress = saved.progress or {}
    if saved.ticked then -- 0.1 kept one route's progress at the top level (Undead Mage)
        saved.progress["undead-mage"] = saved.progress["undead-mage"]
            or { ticked = saved.ticked, current = saved.current, currentKey = saved.currentKey }
        saved.ticked, saved.current, saved.currentKey = nil, nil, nil
    end
    local opts = saved.opts
    if opts.arrow == nil then opts.arrow = true end
    if opts.waypoint == nil then opts.waypoint = true end
    if opts.shown == nil then opts.shown = true end
    if opts.dungeons == nil then opts.dungeons = false end -- quest-only unless you turn dungeons on
    if opts.auto == nil then opts.auto = true end
    Core.opts = opts
    local key = saved.route
    if not (key and ns.Routes and ns.Routes[key]) then key = Core.AutoRoute() end
    Core.SelectRoute(key)
end

function handlers.PLAYER_LOGIN()
    if saved and not saved.route then -- race/class are certain by now
        local key = Core.AutoRoute()
        if key and key ~= Core.routeKey then Core.SelectRoute(key) end
    end
    local maxQuests = CQ and CQ.GetMaxNumQuestsCanAccept and CQ.GetMaxNumQuestsCanAccept() or nil
    if Secret(maxQuests) then maxQuests = nil end
    local build = select(1, GetBuildInfo())
    Core.LogEvent("login", { route = Core.routeKey, steps = #Steps, dungeons = Core.DungeonsOn() or nil, maxQuests = maxQuests, build = build, class = select(2, UnitClass("player")), race = select(2, UnitRace("player")) })
    if ns.UI and ns.UI.Init then ns.UI.Init() end
    if Core.route then
        Core.Print("following the " .. Core.route.title .. " route. /fr route to change it.")
        if Core.resumedByNumber then
            Core.resumedByNumber = nil
            Core.Print("the route was rebuilt and your saved step changed: resumed at the same step number. If that is off, use Back / Skip or /fr seg <number>.")
        end
        if Core.HasDungeons() then Core.Print(Core.DungeonsLine()) end
    end
end

function handlers.PLAYER_ENTERING_WORLD()
    loading = true
    C_Timer.After(3, function()
        loading = false
        ScanObjectives()
        Core.Refresh()
        Core.OfferJump()
    end)
end

function handlers.LOADING_SCREEN_ENABLED()
    loading = true
end

function handlers.QUEST_DETAIL()
    CaptureDialog(dialogAccept)
    AutoAccept()
end

function handlers.QUEST_COMPLETE()
    CaptureDialog(dialogTurnin)
    AutoReward()
end

function handlers.QUEST_PROGRESS()
    AutoProgress()
end

function handlers.GOSSIP_SHOW()
    AutoGossip()
end

function handlers.QUEST_GREETING()
    AutoGreeting()
end

function handlers.GOSSIP_CLOSED()
    TalkEnded()
end

function handlers.QUEST_FINISHED()
    TalkEnded()
end

function handlers.QUEST_ACCEPTED(a, b)
    local q = b or a
    if type(q) ~= "number" then return end
    local d = TakeDialog(dialogAccept, q) or {}
    local title = CQ and CQ.GetTitleForQuestID and CQ.GetTitleForQuestID(q) or nil
    Core.LogEvent("accept", { q = q, name = title, npc = d.npc, npcId = d.npcId, offroute = (not RouteHasQuest(q)) or nil }, d.snap)
    loggedTurnin[q] = nil
    for k in pairs(objBest) do
        if k:match("^" .. q .. ":") then objBest[k] = nil end
    end
    objFresh[q] = true
    QueueRefresh()
end

-- Forever can send QUEST_TURNED_IN late (or never), so whichever of the two events comes first logs it
function handlers.QUEST_TURNED_IN(q, xp, money)
    if type(q) ~= "number" then return end
    local entry = loggedTurnin[q]
    if entry and GetTime() - entry.t < 180 then
        entry.ev.xpGain = xp
        entry.ev.money = money
    else
        loggedTurnin[q] = nil
        LogTurnin(q, { xpGain = xp, money = money })
    end
    QueueRefresh()
end

function handlers.QUEST_REMOVED(q)
    if type(q) == "number" then
        local snap = Snapshot()
        C_Timer.After(1, function()
            if Core.IsTurnedIn(q) then
                if not loggedTurnin[q] then
                    local d = dialogTurnin[q]
                    if d then d.snap = d.snap or snap else dialogTurnin[q] = { snap = snap, t = GetTime() } end
                    LogTurnin(q)
                end
            elseif not Core.IsOnQuest(q) then
                Core.LogEvent("abandon", { q = q }, snap)
            end
            QueueRefresh()
        end)
    end
    QueueRefresh()
end

function handlers.QUEST_LOG_UPDATE()
    ScanObjectives()
    QueueRefresh()
end

function handlers.PLAYER_LEVEL_UP(level)
    Core.LogEvent("level", { newLevel = level })
    QueueRefresh()
end

function handlers.HEARTHSTONE_BOUND()
    Core.LogEvent("bind", { bind = GetBindLocation and GetBindLocation() or nil })
    QueueRefresh()
end

-- Manual steps that tick themselves when the game shows they happened. Only ever the current step.
local AUTO = { F = true, FLY = true, H = true, TRAIN = true }
Core.AUTO = AUTO

local function AutoTick(kind, check)
    local s = Core.Current()
    if s and s.t == kind and not Ticked(s) and (not check or check(s)) then
        Core.Tick(s, "auto")
        return true
    end
    return false
end

local function Here(arg)
    return TextMatches(GetSubZoneText and GetSubZoneText(), arg)
        or TextMatches(GetZoneText and GetZoneText(), arg)
        or TextMatches(GetMinimapZoneText and GetMinimapZoneText(), arg)
end

-- "Get flight path": the flight map is open at the flight master the step names
function handlers.TAXIMAP_OPENED()
    local node
    if NumTaxiNodes and TaxiNodeGetType and TaxiNodeName then
        for i = 1, NumTaxiNodes() or 0 do
            if TaxiNodeGetType(i) == "CURRENT" then
                node = TaxiNodeName(i)
                break
            end
        end
    end
    if Secret(node) then node = nil end
    Core.LogEvent("flightmaster", { node = node })
    AutoTick("F", function(s) return TextMatches(node, s.arg) end)
end

-- "Fly to": a flight just ended in the place the step names
local onTaxi = false
function handlers.PLAYER_CONTROL_LOST()
    C_Timer.After(1, function()
        if UnitOnTaxi and UnitOnTaxi("player") then onTaxi = true end
    end)
end

function handlers.PLAYER_CONTROL_GAINED()
    if not onTaxi then return end
    onTaxi = false
    C_Timer.After(1.5, function()
        AutoTick("FLY", function(s) return Here(s.arg) end)
    end)
end

-- "Hearth to": Hearthstone (8690) or Astral Recall (556) went off
function handlers.UNIT_SPELLCAST_SUCCEEDED(unit, _, spellID)
    if unit ~= "player" or Secret(spellID) then return end
    if spellID == 8690 or spellID == 556 then
        C_Timer.After(1, function() AutoTick("H") end)
    end
end

-- "Train": a class trainer window was open and is closed again
local atClassTrainer = false
function handlers.TRAINER_SHOW()
    atClassTrainer = not (IsTradeskillTrainer and IsTradeskillTrainer())
end

function handlers.TRAINER_CLOSED()
    if atClassTrainer then
        atClassTrainer = false
        AutoTick("TRAIN")
    end
end

function handlers.ZONE_CHANGED_NEW_AREA()
    QueueRefresh()
end

frame:SetScript("OnEvent", function(_, event, ...)
    local h = handlers[event]
    if h then
        local ok, err = pcall(h, ...)
        if not ok and geterrorhandler then geterrorhandler()(err) end
    end
end)
for event in pairs(handlers) do
    pcall(frame.RegisterEvent, frame, event)
end

---------------------------------------------------------------------------
-- Slash commands
---------------------------------------------------------------------------
local function Print(msg)
    DEFAULT_CHAT_FRAME:AddMessage("|cff33ff99Forever Route|r: " .. tostring(msg))
end
Core.Print = Print

SLASH_FOREVERROUTE1 = "/fr"
SLASH_FOREVERROUTE2 = "/foreverroute"
SlashCmdList.FOREVERROUTE = function(msg)
    if not char then return end
    local cmd, rest = (msg or ""):match("^%s*(%S*)%s*(.-)%s*$")
    cmd = (cmd or ""):lower()
    if cmd == "" or cmd == "toggle" then
        if ns.UI then ns.UI.Toggle() end
    elseif cmd == "skip" then
        Core.Skip()
    elseif cmd == "back" then
        Core.Back()
    elseif cmd == "arrow" then
        Core.opts.arrow = not Core.opts.arrow
        Print("arrow " .. (Core.opts.arrow and "on" or "off"))
        if ns.UI then ns.UI.Update() end
    elseif cmd == "paths" then
        Core.opts.paths = Core.opts.paths == false
        Print("walking paths " .. (Core.opts.paths and "on (the arrow follows roads and cave entrances read from the map)" or "off (the arrow points straight at the target)"))
    elseif cmd == "auto" then
        local want = rest:lower()
        if want == "on" or want == "off" then Core.opts.auto = want == "on" else Core.opts.auto = not Core.opts.auto end
        Print("auto accept and hand in " .. (Core.opts.auto
            and "on: quests the guide wants are taken and finished ones handed in when you talk to the NPC. Hold Shift to do it by hand. Rewards with a choice are left to you."
            or "off"))
    elseif cmd == "waypoint" then
        Core.opts.waypoint = not Core.opts.waypoint
        Print("map waypoint " .. (Core.opts.waypoint and "on" or "off"))
        if ns.UI then ns.UI.Update(true) end
    elseif cmd == "route" then
        local want = rest:lower()
        local pick
        if want == "auto" then
            saved.route = nil
            pick = Core.AutoRoute()
        elseif want ~= "" and ns.Routes and ns.Routes[want] then
            saved.route = want
            pick = want
        end
        if pick and Core.SelectRoute(pick) then
            Core.Refresh()
            if ns.UI then ns.UI.Update(true) end
            Print("now following " .. Core.route.title .. (saved.route and "" or " (picked from your race and class)"))
        else
            if want ~= "" then Print("no route called " .. rest) end
            Print("current route: " .. (Core.route and Core.route.title or "none") .. (saved.route and "" or " (picked from your race and class)"))
            local keys = {}
            for key in pairs(ns.Routes or {}) do keys[#keys + 1] = key end
            table.sort(keys)
            for _, key in ipairs(keys) do Print("  /fr route " .. key .. "  - " .. ns.Routes[key].title) end
            Print("  /fr route auto  - pick from race and class")
            Print("  " .. Core.DungeonsLine())
        end
    elseif cmd == "dungeons" or cmd == "dungeon" or cmd == "dg" then
        local want = rest:lower()
        if not Core.HasDungeons() then
            Print("this route has no dungeon steps")
        elseif want == "on" or want == "off" or want == "" then
            if want == "" then want = Core.DungeonsOn() and "off" or "on" end
            Core.SetDungeons(want == "on")
            Print(Core.DungeonsLine())
            if Core.DungeonsOn() then
                Print("Dungeon steps are marked Optional. Skip on a dungeon run step hides the rest of that dungeon.")
            end
        elseif want == "list" then
            for i, d in ipairs(Core.route.dungeons) do
                Print(format("%d. %s (levels %s)%s", i, d.name, d.levels, char.dgSkip[i] and " - skipped" or ""))
            end
        else
            Print("/fr dungeons on | off | list")
        end
    elseif cmd == "seg" or cmd == "segment" then
        local n = tonumber(rest)
        if rest:lower() == "auto" then n = Core.SegmentForLevel(UnitLevel("player") or 1) end
        if n and Core.JumpToSegment(n) then
            Print("jumped to " .. (Segments[n] or n))
        else
            for i, name in ipairs(Segments) do Print(i .. ". " .. name) end
            Print("use /fr seg <number>, or /fr seg auto for the one that fits your level")
        end
    elseif cmd == "reset" then
        char.ticked = {}
        char.declined = {}
        char.dgSkip = {}
        SetCurrent(1)
        Core.Refresh()
        Print("progress on this route reset (completed quests are still detected)")
    elseif cmd == "log" then
        Print(format("%d events logged. They are saved when you log out or /reload.", #ForeverRouteLog.events))
    elseif cmd == "note" then
        Core.LogEvent("note", { text = rest, step = char.current })
        Print("note saved: " .. rest)
    else
        Print("/fr - show or hide | /fr skip | /fr back | /fr seg [n] | /fr route [name] | /fr dungeons [on|off|list] | /fr auto | /fr arrow | /fr paths | /fr waypoint | /fr note <text> | /fr log | /fr reset")
    end
end
