-- Fleet Co-op v0.7. Seeded map experiment for Hyperspace 1.20.0.
-- Installed identically on both PCs. No network/file APIs are needed.
local SHARED_SEED = 7062026
local function emit(s) log('[FleetCoop7] ' .. s) end
local ev = Defines.InternalEvents
local active = false
local ticks = 0
local lastError = nil
local function point(p)
    return string.format('%.0f,%.0f', p.x, p.y)
end
local function snapshot()
    local world = Hyperspace.App.world
    if not world.bStartedGame then return end
    local map = world.starMap
    local locations = map.locations
    local count = locations:size()
    if count == 0 or not map.currentLoc then return end
    if count > 128 then error('Map has more than 128 beacons') end
    local indices = {}
    for i = 0, count - 1 do indices[point(locations[i].loc)] = i end
    local nodes = {}
    for i = 0, count - 1 do
        local location = locations[i]
        local links = {}
        for j = 0, location.connectedLocations:size() - 1 do
            local index = indices[point(location.connectedLocations[j].loc)]
            if index == nil then error('Unknown connected beacon') end
            links[#links + 1] = tostring(index)
        end
        table.sort(links)
        nodes[#nodes + 1] = point(location.loc) .. ',' .. (location.nebula and '1' or '0') .. ':' .. table.concat(links, ',')
    end
    emit('SNAP|' .. tostring(Hyperspace.Global.currentSeed) .. '|' .. tostring(map.worldLevel) .. '|' .. point(map.currentLoc.loc) .. '|' .. table.concat(nodes, ';'))
end
local function safeSnapshot()
    local ok, err = pcall(snapshot)
    if not ok then
        local message = tostring(err):gsub('[\r\n|]', ' ')
        if message ~= lastError then emit('ERROR|' .. message); lastError = message end
    else lastError = nil end
end
script.on_load(function() emit('V0_7_MOD_LOADED') end)
if ev.GET_RUN_SEED then
    script.on_internal_event(ev.GET_RUN_SEED, function(custom, seed)
        emit('SEED_FORCED|' .. tostring(SHARED_SEED))
        return true, SHARED_SEED
    end)
else
    emit('ERROR|GET_RUN_SEED unavailable; shared seed cannot be enforced')
end
script.on_init(function(newGame)
    active = true
    ticks = 119
    emit(newGame and 'RUN_NEW' or 'RUN_LOADED')
end)
if ev.MAIN_MENU then
    script.on_internal_event(ev.MAIN_MENU, function()
        active = false
        emit('MAIN_MENU')
    end)
end
script.on_internal_event(ev.ON_TICK, function()
    if not active then return end
    ticks = ticks + 1
    if ticks >= 120 then ticks = 0; safeSnapshot() end
end)
for _, name in ipairs({'JUMP_LEAVE', 'JUMP_ARRIVE'}) do
    local label = name
    if ev[label] then
        script.on_internal_event(ev[label], function(ship)
            if ship and ship.iShipId == 0 then
                emit(label)
                ticks = 119 -- snapshot next tick, after the game updates its map
            end
        end)
    end
end
