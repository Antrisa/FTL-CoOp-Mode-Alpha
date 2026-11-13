-- Experimental local overlay. Network state remains in the background utility.
FleetPanel11={status='Connect utility and enable bridge before voting.'}
local M=FleetPanel11
local opened=false
local failed=false
local rendered=nil
local cached=nil
local remote=nil
local remoteAge=10000
local held=false
local ev=Defines.InternalEvents
local chain=Defines.Chain
local function inRun()
    return Hyperspace.App.world.bStartedGame and not Hyperspace.App.menu.bOpen
end
local function active() return inRun() or Hyperspace.App.menu.bOpen end
local function hostControls()
    return inRun() and remote~=nil and remoteAge<=900 and remote.host
end
local function inside(x,y,l,t,w,h) return x>=l and x<l+w and y>=t and y<t+h end
local function emit(s) log('[FleetCoop7] '..s) end
local function rect(x,y,w,h,r,g,b)
    Graphics.CSurface.GL_DrawRect(x,y,w,h,Graphics.GL_Color(r,g,b,1))
end
local function label(x,y,text,width)
    FleetUI281.text(x,y,text,width or 470)
end
local function refresh()
    local state=FleetCoop10.safeCapture()
    cached=nil
    if state then
        local labels={}
        for i=1,state.count do labels[i]=tostring(state.box:GetChoices()[i-1].text) end
        cached={token=state.token,count=state.count,labels=labels}
    end
end
function M.receiveStatus(payload,token)
    if payload<1 or payload>1048576 then return end
    local n=payload-1
    local own=n%16;local peer=math.floor(n/16)%16;local agreed=math.floor(n/256)%16
    if own>9 or peer>9 or agreed>9 then return end
    remote={own=own,peer=peer,agreed=agreed,token=token,command=math.floor(n/262144)%4,
        captains=math.floor(n/4096)%4,enabled=math.floor(n/16384)%4,
        host=math.floor(n/65536)%2==1,matched=math.floor(n/131072)%2==1}
    remoteAge=0
end
script.on_internal_event(ev.ON_TICK,function()
    remoteAge=remoteAge+1
    if opened and inRun() then refresh() else cached=nil end
end)
local function displayStatus(state)
    if not remote or remoteAge>900 then
        return 'Link status unavailable / stale. Check utility.','Votes unconfirmed. Keep utility and bridge enabled.'
    end
    local link=(remote.host and 'HOST' or 'GUEST')..' | Captains '..remote.captains..'/2 | Game link '..remote.enabled..'/2'
    if not state or state.token~=remote.token or not remote.matched then
        return link,'Waiting for matching events / current ballot.'
    end
    local function vote(n) return n==0 and '-' or tostring(n) end
    return link,'Votes: You '..vote(remote.own)..' | Partner '..vote(remote.peer)..' | Agreed '..vote(remote.agreed)
end
local function draw()
    if failed or not active() then rendered=nil;return end
    if Hyperspace.App.menu.bOpen then
        FleetUI281.box(680,350,250,40)
        label(692,362,'CO-OP LOBBY',216)
    else
        FleetUI281.box(1100,680,160,30)
        label(1108,686,'CO-OP [F8]',144)
    end
    if not opened then return end
    local state=cached
    FleetUI281.box(20,100,520,545)
    label(32,112,'FLEET CO-OP 0.28.16  |  F8 TO CLOSE')
    if not inRun() then
        label(32,138,'CO-OP CONNECTION STATUS')
        label(32,185,'1. Open the v0.28.16 companion on both PCs.')
        label(32,220,'2. Host / Join there; enable both game links.')
        label(32,255,'3. Check Captains 2/2 and Game link 2/2.')
        label(32,290,'4. Close this panel, then start or continue FTL.')
        label(32,340,'Events: vote in FTL. Missile sales: choose locally.')
        label(32,385,'Utility must stay running in the background.')
        label(32,420,'Host / Join is managed in the companion.')
        label(32,455,'Shared combat / pause / map votes: experimental.')
        local link=displayStatus(nil)
        label(32,560,link,490)
        label(32,590,'F9: view layout   F10: crisp / smooth textures.',490)
        label(32,616,'F8 or CO-OP closes this panel.',490)
        rendered=nil
        return
    end
    if not state then
        label(32,170,'PLAY TOGETHER IN FTL')
        label(32,210,'Events: both click an option to vote.')
        label(32,245,'Map: both click the same beacon to jump.')
        label(32,280,'Space: pause / ready; both ready resumes play.')
        label(32,330,'F7: ship inspector (pauses)')
        label(32,365,'F9: view layout - never enables solo play')
        label(32,400,'F10: crisp / smooth friendly-ship textures')
        label(32,445,'F6: on a stuck event, split this beacon (separate play until next jump).')
        local link=displayStatus(nil);label(32,560,link,490)
        label(32,600,'Keep the companion running. F8 closes this panel.')
        rendered=nil;return
    end
    if FleetNative15 and (FleetNative15.localReward(FleetCoop10.safeCapture()) or FleetNative15.localNotice(FleetCoop10.safeCapture()))then
        label(32,180,'LOCAL CONFIRMATION - close F8 and click Continue.')
        label(32,220,'No partner vote needed for this confirmation.')
        label(32,260,'Finish both screens, then resume together.')
        rendered=nil;return
    end
    if FleetTrade2812 and FleetTrade2812.localEvent(FleetCoop10.safeCapture())then
        label(32,180,'PERSONAL TRADE - each captain chooses separately.')
        label(32,220,'Close F8 and sell or decline in the normal event.')
        label(32,260,'Finish both trades before resuming or jumping.')
        rendered=nil;return
    end
    label(32,138,'Click a row to VOTE; it does not choose immediately.')
    label(32,162,'Read full options in FTL. Panel labels may be shortened.')
    if state then
        for i=1,state.count do
            local y=190+(i-1)*35
            rect(30,y,500,31,0.10,0.20,0.27)
            if remote and remoteAge<=900 and remote.matched and remote.token==state.token then
                if remote.own==i then rect(30,y,4,31,0.1,0.35,0.6)end
                if remote.peer==i then rect(526,y,4,31,0.6,0.35,0.05)end
            end
            label(38,y+7,tostring(i)..'. '..state.labels[i],482)
        end
    else label(32,210,'Open the same event in both games to vote.') end
    if hostControls() then
        rect(30,515,245,32,0.18,0.22,0.30)
        rect(285,515,245,32,0.18,0.22,0.30)
        label(38,523,'HOST: use my vote',228)
        label(293,523,remote.command==1 and 'COMMAND PENDING' or 'HOST: apply choice',228)
    else
        label(32,523,remote and remoteAge<=900 and 'Vote above. The host applies the agreed choice.' or 'Waiting for role confirmation. Host controls hidden.',490)
    end
    local status=M.status
    if remote and remoteAge<=900 then
        if remote.command==1 then status='Command pending: waiting for both games.'
        elseif remote.command==3 then status='Last command failed / timed out. Check both games.' end
    end
    label(32,560,status,490)
    local link,votes=displayStatus(state)
    label(32,590,link,490)
    label(32,616,votes,490)
    rendered=state -- immutable snapshot actually drawn
end
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()
    if failed or Hyperspace.App.menu.bOpen then return end
    local ok,err=pcall(draw)
    if not ok then
        failed=true;opened=false;rendered=nil
        emit('ERROR|Panel render disabled: '..tostring(err):gsub('[\r\n|]',' '))
    end
end,function()end)
script.on_internal_event(ev.ON_KEY_DOWN,function(key)
    if key==Defines.SDL.KEY_F8 and active() and not failed then
        opened=not opened;rendered=nil;refresh();return chain.PREEMPT
    end
    return chain.CONTINUE
end)
script.on_internal_event(ev.ON_MOUSE_L_BUTTON_DOWN,function(x,y)
    if failed or not active() then return chain.CONTINUE end
    if (Hyperspace.App.menu.bOpen and inside(x,y,680,350,250,40)) or (inRun() and inside(x,y,1100,680,160,30)) then
        opened=not opened;rendered=nil;refresh();held=true;return chain.PREEMPT
    end
    if not opened then return chain.CONTINUE end
    if not inside(x,y,20,100,520,545) then held=true;return chain.PREEMPT end
    held=true
    if not inRun() then return chain.PREEMPT end
    local action=nil
    local index=0
    if inside(x,y,30,190,500,315) then
        index=math.floor((y-190)/35)+1
        if (y-190)%35<31 then action='vote' end
    elseif hostControls() and inside(x,y,30,515,245,32) then action='tie'
    elseif hostControls() and remote.command~=1 and inside(x,y,285,515,245,32) then action='apply' end
    local state=FleetCoop10.safeCapture()
    if action and state and rendered and state.token==rendered.token and (action~='vote' or index<=state.count) then
        -- Snapshot precedes request so the server validates the exact local screen.
        emit('EVENT|'..string.format('%.0f',state.token)..'|'..state.content)
        emit('PANEL_ACTION|'..string.format('%.0f',state.token)..'|'..action..'|'..index)
        M.status=action=='vote' and ('Vote '..index..' requested; awaiting host apply.') or (action..' requested; check game result.')
    elseif action then
        M.status=not state and 'No event open on this PC. Open an event first.' or (action=='vote' and index>state.count and 'No option in that row.' or 'Event changed. Review options and click again.')
        emit('PANEL_REJECT|'..M.status..' live='..tostring(state and state.token)..' drawn='..tostring(rendered and rendered.token))
    end
    return chain.PREEMPT
end,100)
script.on_internal_event(ev.ON_MOUSE_L_BUTTON_UP,function(x,y)
    if held then held=false;return chain.PREEMPT end
    return chain.CONTINUE
end,100)
script.on_init(function()opened=false;rendered=nil;cached=nil;remote=nil;remoteAge=10000;held=false end)
script.on_load(function()emit('PANEL17_LOADED')end)

function M.isOpen() return opened end

function M.nativeStatus() return remote,remoteAge end
script.on_render_event(Defines.RenderEvents.MAIN_MENU,function()end,function()
    if failed then return end
    local ok,err=pcall(draw)
    if not ok then log('[FleetCoop7] ERROR|Menu panel: '..tostring(err)) end
end)
