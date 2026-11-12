-- Forever Route: step window, waypoint arrow and native map waypoint.
local ADDON, ns = ...

local UI = {}
ns.UI = UI
local Core = ns.Core

local format, floor, sqrt, ipairs, type = string.format, math.floor, math.sqrt, ipairs, type
local atan2 = math.atan2 or atan2
local PI2 = math.pi * 2

local ICON = { A = "|cffffd100!|r", C = "|cffff8800*|r", T = "|cffffd100?|r", G = "|cff66ccff>|r", L = "|cffaaaaaaL|r",
    S = "|cff99ff99H|r", H = "|cff99ff99H|r", F = "|cff66ccffF|r", FLY = "|cff66ccffF|r", N = "|cffccccccN|r", TRAIN = "|cffcc99ffT|r" }
local VERB = { A = "Accept", C = "Do", T = "Turn in", L = "Grind to level", S = "Set hearthstone:", H = "Hearth to",
    F = "Get flight path:", FLY = "Fly to", TRAIN = "Train new spells", N = "", G = "Go to" }

local function QuestList(s)
    local parts = {}
    for k, name in ipairs(s.names or {}) do
        local obj = s.obj and s.obj[k]
        parts[#parts + 1] = "|cffffffff" .. name .. "|r" .. ((obj and obj > 0) and format(" (objective %d)", obj) or "")
    end
    return table.concat(parts, ", ")
end

function UI.StepText(s)
    local verb = VERB[s.t] or s.t
    local body
    if s.q then
        body = verb .. " " .. QuestList(s)
    elseif s.t == "L" then
        body = verb .. " " .. s.lvl
    elseif s.t == "TRAIN" then
        body = verb
    elseif s.t == "G" then
        body = verb .. " " .. (s.zone or "") .. format(" %.1f, %.1f", s.x or 0, s.y or 0)
    elseif s.t == "N" then
        body = s.arg or ""
    else
        body = verb .. " " .. (s.arg or "")
    end
    if s.text and s.text ~= "" then
        if s.t == "N" and (s.arg == nil or s.arg == "") then
            body = s.text
        else
            body = body .. "\n|cffbbbbbb" .. s.text .. "|r"
        end
    end
    if s.dg then
        local d = Core.route and Core.route.dungeons and Core.route.dungeons[s.dg]
        if not s.run then body = "|cff66ccffOptional (" .. (d and d.name or "dungeon") .. "):|r " .. body end
        return "|cff66ccffD|r " .. body
    end
    return (ICON[s.t] or "") .. " " .. body
end

---------------------------------------------------------------------------
-- Map ID resolution for zone names (needed for new Forever zones)
---------------------------------------------------------------------------
local mapByName
local function BuildMapNames()
    mapByName = {}
    if not (C_Map and C_Map.GetMapChildrenInfo) then return end
    local zoneType = Enum and Enum.UIMapType and Enum.UIMapType.Zone
    for _, root in ipairs({ 946, 947, 1414, 1415 }) do
        local ok, kids = pcall(C_Map.GetMapChildrenInfo, root, nil, true)
        if ok and type(kids) == "table" then
            for _, info in ipairs(kids) do
                local n = info.name and info.name:lower()
                if n and (not mapByName[n] or info.mapType == zoneType) then
                    mapByName[n] = info.mapID
                end
            end
        end
    end
end

local function MapFor(s)
    if s.map then return s.map end
    if not s.zone then return nil end
    if not mapByName then BuildMapNames() end
    return mapByName[s.zone:lower()]
end
UI.MapFor = MapFor

local function WorldPos(mapID, x, y)
    if not (C_Map and C_Map.GetWorldPosFromMapPos and CreateVector2D) then return nil end
    local ok, cont, wp = pcall(C_Map.GetWorldPosFromMapPos, mapID, CreateVector2D(x, y))
    if not ok or not wp then return nil end
    return cont, wp.x, wp.y
end

-- Walking path: s.path = { {x, y}, ... } are points to pass, in order, before the step's own point.
-- They are read off the zone map drawing by the builder (roads, valleys, cave entrances), so they are a
-- best guess. With s.cave the last path point is a cave entrance and the step's own point is inside.
local VIA_YARDS = 30
local viaKey, viaIdx

-- Returns the point to walk to now (x, y in 0-100) and its path number (nil = the step's own point)
local function Target(s)
    local path = s.path
    if not path or Core.opts.paths == false then return s.x, s.y, nil end
    if viaKey ~= s.key then viaKey, viaIdx = s.key, 1 end
    local tmap = MapFor(s)
    local pmap, px, py = Core.PlayerPosition()
    local pc, pwx, pwy
    if tmap and px then pc, pwx, pwy = WorldPos(pmap, px, py) end
    while pc and viaIdx <= #path do
        local p, n = path[viaIdx], path[viaIdx + 1]
        local c1, ax, ay = WorldPos(tmap, p[1] / 100, p[2] / 100)
        local c2, bx, by = WorldPos(tmap, (n and n[1] or s.x) / 100, (n and n[2] or s.y) / 100)
        if not c1 or not c2 or c1 ~= pc then break end
        local toVia = sqrt((ax - pwx) ^ 2 + (ay - pwy) ^ 2)
        local toNext = sqrt((bx - pwx) ^ 2 + (by - pwy) ^ 2)
        local viaToNext = sqrt((bx - ax) ^ 2 + (by - ay) ^ 2)
        local reached
        if s.cave and viaIdx == #path then
            -- a cave entrance: only passed by standing at it or being inside
            reached = toVia <= VIA_YARDS or (IsIndoors and IsIndoors())
        else
            -- reached it, or already further along than this point
            reached = toVia <= VIA_YARDS or toNext < viaToNext * 0.8
        end
        if not reached then break end
        viaIdx = viaIdx + 1
    end
    local p = path[viaIdx]
    if p then return p[1], p[2], viaIdx end
    return s.x, s.y, nil
end

-- Returns distance (yards) or nil, relative arrow angle or nil, false when on another continent,
-- and the path number the arrow points at (nil = the step's own point).
-- final = true ignores the path and measures to the step's own point.
local function Navigate(s, final)
    local tmap = MapFor(s)
    if not tmap or not s.x then return nil end
    local pmap, px, py = Core.PlayerPosition()
    if not px then return nil end
    local tx, ty, via = s.x, s.y, nil
    if not final then tx, ty, via = Target(s) end
    local pc, pwx, pwy = WorldPos(pmap, px, py)
    local tc, twx, twy = WorldPos(tmap, tx / 100, ty / 100)
    if not pc or not tc then return nil end
    if pc ~= tc then return nil, nil, false end
    local dx, dy = twx - pwx, twy - pwy -- world x = north, world y = west
    local dist = sqrt(dx * dx + dy * dy)
    local facing = GetPlayerFacing and GetPlayerFacing()
    local angle
    if type(facing) == "number" and not Core.Secret(facing) then
        angle = (atan2(dy, dx) - facing) % PI2
    end
    return dist, angle, true, via
end

---------------------------------------------------------------------------
-- Frames
---------------------------------------------------------------------------
local main, arrow
local lines = {}
local NUM_UPCOMING = 4

-- Always store the TOPLEFT corner so the window grows downward
local function SavePos(f, key)
    local left, top = f:GetLeft(), f:GetTop()
    if not left or not top then return end
    Core.opts[key] = { left, top }
    f:ClearAllPoints()
    f:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", left, top)
end

local function RestorePos(f, key, dp, drp, dx, dy)
    local v = Core.opts[key]
    f:ClearAllPoints()
    if v and v[1] and v[2] and type(v[1]) == "number" then
        f:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", v[1], v[2])
    else
        f:SetPoint(dp, UIParent, drp, dx, dy)
    end
end

local function MakeButton(parent, label, w, onClick)
    local b = CreateFrame("Button", nil, parent, "UIPanelButtonTemplate")
    b:SetSize(w, 18)
    b:SetText(label)
    b:SetScript("OnClick", onClick)
    return b
end

local function CreateMain()
    main = CreateFrame("Frame", "ForeverRouteFrame", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    main:SetSize(330, 210)
    main:SetFrameStrata("MEDIUM")
    main:SetMovable(true)
    main:EnableMouse(true)
    main:RegisterForDrag("LeftButton")
    main:SetClampedToScreen(true)
    main:SetScript("OnDragStart", main.StartMoving)
    main:SetScript("OnDragStop", function(f) f:StopMovingOrSizing(); SavePos(f, "mainPos") end)
    if main.SetBackdrop then
        main:SetBackdrop({ bgFile = "Interface\\Tooltips\\UI-Tooltip-Background", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true, tileSize = 16, edgeSize = 12, insets = { left = 3, right = 3, top = 3, bottom = 3 } })
        main:SetBackdropColor(0, 0, 0, 0.75)
        main:SetBackdropBorderColor(0.4, 0.4, 0.4, 1)
    end
    RestorePos(main, "mainPos", "TOPRIGHT", "TOPRIGHT", -60, -220)

    main.title = main:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    main.title:SetPoint("TOPLEFT", 8, -7)
    main.title:SetPoint("TOPRIGHT", -8, -7)
    main.title:SetJustifyH("LEFT")

    local cur = main:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    cur:SetPoint("TOPLEFT", main.title, "BOTTOMLEFT", 0, -6)
    cur:SetPoint("RIGHT", main, "RIGHT", -8, 0)
    cur:SetJustifyH("LEFT")
    cur:SetJustifyV("TOP")
    cur:SetWordWrap(true)
    main.cur = cur

    main.status = main:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    main.status:SetPoint("TOPLEFT", cur, "BOTTOMLEFT", 0, -3)
    main.status:SetPoint("RIGHT", main, "RIGHT", -8, 0)
    main.status:SetJustifyH("LEFT")

    local prev = main.status
    for i = 1, NUM_UPCOMING do
        local fs = main:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
        fs:SetPoint("TOPLEFT", prev, "BOTTOMLEFT", 0, i == 1 and -8 or -3)
        fs:SetPoint("RIGHT", main, "RIGHT", -8, 0)
        fs:SetJustifyH("LEFT")
        fs:SetWordWrap(true)
        lines[i] = fs
        prev = fs
    end

    main.done = MakeButton(main, "Done", 60, function() Core.Tick(Core.Current(), "tick") end)
    main.done:SetPoint("BOTTOMLEFT", 6, 6)
    main.skip = MakeButton(main, "Skip", 60, function() Core.Skip() end)
    main.skip:SetPoint("LEFT", main.done, "RIGHT", 4, 0)
    main.back = MakeButton(main, "Back", 60, function() Core.Back() end)
    main.back:SetPoint("LEFT", main.skip, "RIGHT", 4, 0)
    main.hide = MakeButton(main, "Hide", 50, function() UI.Toggle() end)
    main.hide:SetPoint("BOTTOMRIGHT", -6, 6)
    -- switches between the quest-only route and the one with optional dungeon runs
    main.dg = MakeButton(main, "Dng: off", 68, function()
        if not Core.HasDungeons() then return end
        Core.SetDungeons(not Core.DungeonsOn())
        Core.Print(Core.DungeonsLine())
    end)
    main.dg:SetPoint("RIGHT", main.hide, "LEFT", -4, 0)
end

local function CreateArrow()
    arrow = CreateFrame("Frame", "ForeverRouteArrow", UIParent)
    arrow:SetSize(56, 56)
    arrow:SetMovable(true)
    arrow:EnableMouse(true)
    arrow:RegisterForDrag("LeftButton")
    arrow:SetClampedToScreen(true)
    arrow:SetScript("OnDragStart", arrow.StartMoving)
    arrow:SetScript("OnDragStop", function(f) f:StopMovingOrSizing(); SavePos(f, "arrowPos") end)
    RestorePos(arrow, "arrowPos", "TOP", "TOP", 0, -140)

    arrow.tex = arrow:CreateTexture(nil, "ARTWORK")
    arrow.tex:SetAllPoints()
    arrow.tex:SetTexture("Interface\\Minimap\\MinimapArrow")
    arrow.tex:SetVertexColor(0.3, 1, 0.3)

    arrow.text = arrow:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    arrow.text:SetPoint("TOP", arrow, "BOTTOM", 0, -2)
    arrow:Hide()
end

---------------------------------------------------------------------------
-- Navigation ticker: arrow drawing and "Go to" arrival run here, independent of the arrow being shown
---------------------------------------------------------------------------
local ARRIVE_YARDS, HOLD_YARDS = 12, 30

local function ArrowVisible(want)
    if want and Core.opts.arrow and Core.opts.shown then
        if not arrow:IsShown() then arrow:Show() end
        return true
    end
    if arrow:IsShown() then arrow:Hide() end
    return false
end

local function NavTick()
    local s = Core.Current()
    if not s or not s.x then
        ArrowVisible(false)
        return
    end
    local dist, angle, same, via = Navigate(s)
    -- log walking into / out of caves and buildings, so "check my log" can confirm cave entrances
    local indoors = IsIndoors and IsIndoors() and true or false
    if UI.wasIndoors ~= nil and indoors ~= UI.wasIndoors and GetTime() - (UI.indoorsAt or 0) > 5 then
        UI.indoorsAt = GetTime()
        Core.LogEvent(indoors and "indoors" or "outdoors", { step = s.key })
    end
    UI.wasIndoors = indoors
    -- arrival for "Go to" steps (measured to the step's own point, not a path point)
    if s.t == "G" and dist then
        local fdist = via and Navigate(s, true) or dist
        if Core.holdKey == s.key then
            if fdist and fdist > HOLD_YARDS then Core.holdKey = nil end
        elseif fdist and fdist <= ARRIVE_YARDS then
            Core.Tick(s, "arrive")
            return
        end
    end
    if not ArrowVisible(true) then return end
    if same == false then
        arrow.tex:Hide()
        arrow.text:SetText("Travel to " .. (s.zone or "?"))
    elseif not dist then
        arrow.tex:Hide()
        arrow.text:SetText(s.zone and format("%s %.0f, %.0f", s.zone, s.x, s.y) or "")
    else
        if angle then
            arrow.tex:Show()
            arrow.tex:SetRotation(angle)
            arrow.tex:SetVertexColor(dist < 40 and 1 or 0.3, 1, 0.3)
        else
            arrow.tex:Hide()
        end
        local label = format("%d yd", floor(dist + 0.5))
        if via then
            if s.cave and via == #s.path then
                label = label .. "\ncave entrance"
            else
                label = label .. format("\npath %d/%d", via, #s.path)
            end
        end
        arrow.text:SetText(label)
    end
end

local function StartTicker()
    C_Timer.NewTicker(0.1, function()
        local ok = pcall(NavTick)
        if not ok and arrow then
            arrow.tex:Hide()
            arrow.text:SetText("")
        end
    end)
end

---------------------------------------------------------------------------
-- Native user waypoint (Blizzard draws its own on-screen marker)
---------------------------------------------------------------------------
local lastWaypointKey

local function ClearOwnWaypoint()
    if UI.ownWaypoint and C_Map and C_Map.ClearUserWaypoint then
        pcall(C_Map.ClearUserWaypoint)
    end
    UI.ownWaypoint = false
end

local function SetNativeWaypoint(s, force)
    if not (C_Map and C_Map.SetUserWaypoint and UiMapPoint and UiMapPoint.CreateFromCoordinates) then return end
    local opts = Core.opts
    local want = s and s.x and opts.waypoint and opts.shown
    local key = want and s.key or nil
    if key == lastWaypointKey and not force then return end
    lastWaypointKey = key
    if not key then
        ClearOwnWaypoint()
        return
    end
    local mapID = MapFor(s)
    local ok = false
    if mapID and (not C_Map.CanSetUserWaypointOnMap or C_Map.CanSetUserWaypointOnMap(mapID)) then
        ok = pcall(C_Map.SetUserWaypoint, UiMapPoint.CreateFromCoordinates(mapID, s.x / 100, s.y / 100))
    end
    if ok then
        UI.ownWaypoint = true
        if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then
            pcall(C_SuperTrack.SetSuperTrackedUserWaypoint, true)
        end
    else
        ClearOwnWaypoint() -- don't leave the previous step's pin pointing somewhere wrong
    end
end

---------------------------------------------------------------------------
-- Public
---------------------------------------------------------------------------
function UI.Update(forceWaypoint)
    if not main then return end
    main.dg:SetText(Core.DungeonsOn() and "Dng: on" or "Dng: off")
    local steps = Core.Steps
    local s = Core.Current()
    local opts = Core.opts
    if not s then
        main.title:SetText(format("Forever Route  |cffaaaaaa%d/%d|r", #steps, #steps))
        main.cur:SetText("|cff33ff99Route finished!|r")
        main.status:SetText("")
        for i = 1, NUM_UPCOMING do lines[i]:SetText("") end
        SetNativeWaypoint(nil)
        return
    end
    main.title:SetText(format("%s  |cffaaaaaa%d/%d|r", Core.Segments[s.seg] or "", s.index, #steps))
    main.cur:SetText(UI.StepText(s))
    local status = {}
    if s.t == "C" and s.q then
        for _, q in ipairs(s.q) do
            for _, o in ipairs(Core.GetObjectives(q)) do
                if o.text and o.text ~= "" then
                    status[#status + 1] = (o.finished and "|cff55ff55" or "|cffffffff") .. o.text .. "|r"
                end
            end
        end
    end
    if s.run then
        status[#status + 1] = "|cffaaaaaaDone = you ran it. Skip = not running it.|r"
    elseif s.dg and s.t == "T" then
        status[#status + 1] = "|cffaaaaaaNot finished in the dungeon? Press Skip.|r"
    elseif s.t == "A" then
        status[#status + 1] = "|cffaaaaaaNot offered? Press Skip: its later steps skip themselves.|r"
    end
    -- With dungeons on you can be ahead of the quest-only pace: say so when this quest has gone grey
    if Core.DungeonsOn() and s.q and not s.dg and (s.t == "A" or s.t == "C") then
        local qlvl = Core.route and Core.route.qlvl
        local level = UnitLevel("player")
        for _, q in ipairs(s.q) do
            if qlvl and Core.IsGrey(qlvl[q], level) and not Core.IsTurnedIn(q) then
                status[#status + 1] = "|cffaaaaaaGrey at your level (little experience): Skip it unless a later quest needs it.|r"
                break
            end
        end
    end
    if Core.IsBlocked(s) then
        status[#status + 1] = "|cffff6666You don't have this quest. Pick it up or press Skip.|r"
    end
    if s.run then
        -- its own hint is above
    elseif s.t == "G" then
        status[#status + 1] = "|cffaaaaaaTicks when you arrive, or press Done.|r"
    elseif Core.AUTO[s.t] then
        status[#status + 1] = "|cffaaaaaaTicks by itself when it happens, or press Done.|r"
    elseif Core.MANUAL[s.t] then
        status[#status + 1] = "|cffaaaaaaPress Done when finished.|r"
    end
    main.status:SetText(table.concat(status, "\n"))
    local up = Core.Upcoming(NUM_UPCOMING)
    for i = 1, NUM_UPCOMING do
        local text = up[i] and (UI.StepText(up[i]):gsub("\n.*", "")) or ""
        lines[i]:SetText(text)
    end
    local h = 40 + main.title:GetStringHeight() + main.cur:GetStringHeight() + main.status:GetStringHeight()
    for i = 1, NUM_UPCOMING do h = h + lines[i]:GetStringHeight() + 3 end
    main:SetHeight(math.max(120, h + 22))
    SetNativeWaypoint(s, forceWaypoint)
    if opts.shown then main:Show() else main:Hide() end
end

function UI.Toggle()
    local opts = Core.opts
    opts.shown = not opts.shown
    if opts.shown then main:Show() else main:Hide() end
    UI.Update(true)
end

function UI.Init()
    if main then return end
    CreateMain()
    CreateArrow()
    StartTicker()
    UI.Update(true)
end
