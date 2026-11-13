-- Native event clicks become votes; only the existing guarded bridge applies choices.
FleetNative15={}
local M=FleetNative15
local enabled=true
local held=false
local own=nil
local ownToken=nil
local message='Click an event option to vote.'
local lastState=''
local ev=Defines.InternalEvents
local chain=Defines.Chain
local keys=Defines.SDL
local function capture() return FleetCoop10.safeCapture() end
local function emit(s) log('[FleetCoop7] '..s) end
local function overlay() return FleetPanel11 and FleetPanel11.isOpen() end
-- Only the observed informational warning bypasses voting. No generic
-- single-choice bypass: Continue can otherwise award resources or branch events.
function M.localNotice(state)
    if not state or state.count~=1 or not FleetCombat22 or not FleetCombat22.isActive()then return false end
    if tostring(state.box.mainText)~="The enemy ship appears to be powering up its FTL. It's trying to escape!" then return false end
    local c=state.box:GetChoices()[0]
    return c and c.type==0 and tostring(c.text)=='Continue...'
end
-- Confirm only this captain's single Continue during the acknowledged
-- post-combat phase. The shared POST_READY barrier still gates travel.
function M.localReward(state)
    if not state or state.count~=1 or not FleetCombat22 or not FleetCombat22.rewardPending or not FleetCombat22.rewardPending() then return false end
    local c=state.box:GetChoices()[0]
    return c and c.type==0 and tostring(c.text)=='Continue...'
end
-- v0.28.16: after a shared fight fell back to separate fights, every event at
-- that beacon (surrender, rewards, follow-ups) belongs to this captain alone.
-- The partner may never see the same screen, so a vote could not complete.
function M.localSeparate(state)
    return state~=nil and FleetCombat22~=nil and FleetCombat22.separate~=nil and FleetCombat22.separate()==true
end
local function localContinue(state)return (FleetTrade2812 and FleetTrade2812.localEvent(state)) or M.localNotice(state) or M.localReward(state) or M.localSeparate(state)end
local function vote(state,index)
    if not state or index<1 or index>state.count then return end
    emit('EVENT|'..string.format('%.0f',state.token)..'|'..state.content)
    emit('NATIVE_VOTE|'..string.format('%.0f',state.token)..'|'..string.format('%.0f',index))
    own=index;ownToken=state.token
    message='Vote '..index..' requested. Waiting for both captains.'
end
function M.key(key)
    local state=enabled and capture() or nil
    if not state or localContinue(state)then return chain.CONTINUE end
    if key>=keys.KEY_1 and key<=keys.KEY_9 then vote(state,key-keys.KEY_1+1);return chain.PREEMPT end
    if key==keys.KEY_RETURN or key==keys.KEY_SPACE or key==keys.KEY_KP_ENTER then return chain.PREEMPT end
    return chain.CONTINUE
end
script.on_internal_event(ev.ON_MOUSE_L_BUTTON_DOWN,function(x,y)
    if not enabled or overlay() then return chain.CONTINUE end
    local state=capture()
    if not state or localContinue(state)then return chain.CONTINUE end
    held=true
    local index=tonumber(state.box.potentialChoice)
    if index and index>=0 and index<state.count then vote(state,index+1)
    else message='Point at an event option, then click to vote.' end
    return chain.PREEMPT -- also consumes empty-area clicks while event is open
end,200)
script.on_internal_event(ev.ON_MOUSE_L_BUTTON_UP,function()
    if held then held=false;return chain.PREEMPT end
    return chain.CONTINUE
end,200)
script.on_internal_event(ev.ON_MOUSE_R_BUTTON_DOWN,function()
    if enabled and capture() then return chain.PREEMPT end
    return chain.CONTINUE
end,200)
script.on_internal_event(ev.ON_TICK,function()
    local state=capture()
    if FleetTrade2812 then FleetTrade2812.localEvent(state)end
    local app=Hyperspace.App
    local diag=state and ('OPEN|'..state.token) or ('CLOSED|run='..tostring(app.world.bStartedGame)..'|menu='..tostring(app.menu.bOpen)..'|gui='..tostring(app.gui.choiceBoxOpen)..'|box='..tostring(app.gui.choiceBox.bOpen))
    if diag~=lastState then emit('NATIVE_DIAG|EVENT_STATE|'..diag);lastState=diag end
    if not state or state.token~=ownToken then own=nil;ownToken=nil end
end)
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()end,function()
    local state=capture()
    if not state or overlay() then return end
    if FleetTrade2812 and FleetTrade2812.localEvent(state)then
        FleetUI281.box(210,570,850,46)
        FleetUI281.text(220,576,'PERSONAL TRADE - sell or decline for your own ship',830)
        FleetUI281.text(220,598,'Finish your trade, then resume together. No event vote needed.',830)
        return
    end
    if M.localSeparate(state)then
        FleetUI281.box(210,570,850,46)
        FleetUI281.text(220,576,'SEPARATE FIGHT - this event is yours alone: choose normally',830)
        FleetUI281.text(220,598,'No partner vote here. Shared voting returns at the next beacon.',830)
        return
    end
    if M.localReward(state)then
        FleetUI281.box(210,570,850,46)
        FleetUI281.text(220,576,'YOUR COMBAT REWARD - click Continue on this screen',830)
        FleetUI281.text(220,598,'Then both press SPACE if paused. Travel waits for both reward sequences.',830)
        return
    end
    if M.localNotice(state)then
        FleetUI281.box(210,570,850,46)
        FleetUI281.text(220,576,'ENEMY FTL WARNING - click Continue on this screen',830)
        FleetUI281.text(220,598,'Informational notice: no partner vote needed. Resume together.',830)
        return
    end
    local text=message
    local remote,age=FleetPanel11.nativeStatus()
    if enabled and remote and age<=900 and remote.token==state.token and remote.matched then
        text='Votes: You '..remote.own..' | Partner '..remote.peer..' | Agreed '..remote.agreed..' (0 = waiting)'
        if remote.command==1 then text='Applying choice: keep FTL focused.' end
        if remote.command==3 then text='Last command failed. Inspect both games; see utility log.' end
    end
    local fresh=enabled and remote and age<=900 and remote.token==state.token and remote.matched
    local you=fresh and remote.own or 0
    local peer=fresh and remote.peer or 0
    for i=1,state.count do
        local x=155+(i-1)*108
        Graphics.CSurface.GL_DrawRect(x,540,102,24,Graphics.GL_Color(0.08,0.12,0.18,1))
        if you==i then Graphics.CSurface.GL_DrawRect(x,540,51,24,Graphics.GL_Color(0.1,0.35,0.6,1)) end
        if peer==i then Graphics.CSurface.GL_DrawRect(x+51,540,51,24,Graphics.GL_Color(0.6,0.35,0.05,1)) end
        FleetUI281.text(x+5,545,tostring(i)..(you==i and peer==i and ' BOTH' or you==i and ' YOU' or peer==i and ' PARTNER' or ' -'),92)
    end
    FleetUI281.box(210,570,850,46)
    while #text>0 and Graphics.freetype.easy_measureWidth(12,text)>830 do text=text:sub(1,-2) end
    FleetUI281.text(220,576,text,830)
    FleetUI281.text(220,598,'BLUE: you | AMBER: partner | Matching votes continue',830)
end)
