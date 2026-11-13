-- v0.10: 64-bit packet assembled as two exact 32-bit words.
-- Event choices use an ARMED handshake before the utility sends a digit.
local ev=Defines.InternalEvents
local keys=Defines.SDL
local chain=Defines.Chain
local value=nil
local count=0
local header=0
local age=0
local heartbeat=0
local seen={}
local order={}
local armed=nil
local queued=nil
local function emit(s) log('[FleetCoop7] '..s) end
local function answer(nonce,name,status,cache)
    local result='BRIDGE_ACK|'..string.format('%.0f',nonce)..'|'..name..'|'..status
    if cache then
        seen[cache]=result;order[#order+1]=cache
        if #order>128 then seen[table.remove(order,1)]=nil end
    end
    if FleetPanel11 then FleetPanel11.status=name..": "..status.." (this PC)" end
    emit(result)
end
local function current() return FleetCoop10 and FleetCoop10.safeCapture() end
local function receive(packet,guard)
    local op=math.floor(packet/16777216)
    local nonce=packet%16777216
    if op>=50 and op<=52 then
        if FleetInterior19 then FleetInterior19.receive(op,nonce,guard) end
        return
    end
    if op==42 then
        if FleetShips17 then FleetShips17.receive(nonce,guard) end
        return
    end
    if op==41 then
        if FleetCursor14 then FleetCursor14.receive(nonce,guard) end
        return
    end
    if op==40 then
        if FleetPanel11 and FleetPanel11.receiveStatus then FleetPanel11.receiveStatus(nonce,guard) end
        return -- display-only, never ACK or execute an action
    end
    if nonce<1 or not (op>=1 and op<=3 or op>=17 and op<=25) then return end
    local cache=tostring(op)..':'..tostring(nonce)
    if seen[cache] then emit(seen[cache]);return end
    local names={[1]='PING',[2]='PAUSE',[3]='RESUME'}
    local name=names[op] or ('CHOICE_'..tostring(op-16))
    if op>=17 then
        local state=current()
        if not state or state.token~=guard or state.count<op-16 then answer(nonce,name,'FAILED',cache);return end
        armed={nonce=nonce,name=name,index=op-16,guard=guard,cache=cache,age=0}
        answer(nonce,name,'ARMED',nil)
        return
    end
    local ok,err=pcall(function()
        if op~=1 then
            if not Hyperspace.App.world.bStartedGame or Hyperspace.App.menu.bOpen then error('NOT_IN_RUN') end
            if FleetPause27 and FleetPause27.active() then
                if op==2 then FleetPause27.hold() else error("USE_SPACE_FOR_FLEET_READY") end
                -- ACK confirms request receipt; the on-screen fleet barrier owns resume.
            else
                Hyperspace.App.gui.bPaused=(op==2)
                if Hyperspace.App.gui.bPaused~=(op==2) then error('PAUSE_STATE_NOT_APPLIED') end
            end
        end
    end)
    answer(nonce,name,ok and 'OK' or 'FAILED',cache)
    if not ok then emit('ERROR|Bridge '..tostring(err):gsub('[\r\n|]',' ')) end
end
script.on_load(function()emit('V0_10_BRIDGE_LOADED')end)
script.on_internal_event(ev.ON_KEY_DOWN,function(key)
    if key==keys.KEY_F13 then value=0;header=0;count=0;age=0;return chain.PREEMPT end
    if key==keys.KEY_F14 or key==keys.KEY_F15 then
        if value~=nil then
            value=value*2+(key==keys.KEY_F15 and 1 or 0);count=count+1;age=0
            if count==32 then header=value;value=0 end
            if count==64 then local guard=value;value=nil;receive(header,guard) end
        end
        return chain.PREEMPT
    end
    if armed and key>=keys.KEY_1 and key<=keys.KEY_9 then
        local a=armed;armed=nil
        local state=current()
        if key~=keys.KEY_1+a.index-1 or not state or state.token~=a.guard then
            answer(a.nonce,a.name,'FAILED',a.cache)
            return chain.PREEMPT
        end
        a.age=0;queued=a
        emit('CHOICE_INPUT|'..string.format('%.0f',a.nonce)..'|'..a.name)
        return chain.CONTINUE -- vanilla handles availability and input timing
    end
    if FleetShips17 and FleetShips17.key(key)==chain.PREEMPT then return chain.PREEMPT end
    if FleetNative15 then return FleetNative15.key(key) end
    return chain.CONTINUE
end)
script.on_internal_event(ev.ON_TICK,function()
    heartbeat=heartbeat+1
    if heartbeat>=120 then heartbeat=0;emit('BRIDGE10_READY') end
    if value~=nil then age=age+1;if age>600 then value=nil end end
    if armed then
        armed.age=armed.age+1
        -- Keep a tombstone rather than clearing: a delayed digit must be consumed
        -- and rejected even after expiry. New requests replace it.
        if armed.age>1800 then armed.guard=-1 end
    end
    if queued then
        local q=queued;q.age=q.age+1
        local state=current()
        local closed=not Hyperspace.App.gui.choiceBoxOpen
        if closed or (state and state.token~=q.guard) then
            answer(q.nonce,q.name,'OK',q.cache);queued=nil
        elseif q.age>120 then
            answer(q.nonce,q.name,'FAILED',q.cache);queued=nil
            emit('ERROR|Choice did not advance; it may be unavailable or hotkeys may be disabled')
        end
    end
end)
