-- Automatic partner hull display plus optional F7 inspector.
-- Does not spawn, simulate, move or damage ships.
FleetShips17={}
local M=FleetShips17
local names={}
for _,base in ipairs({'HARD','STEALTH','MANTIS','CIRCLE','FED','JELLY','ROCK','ENERGY','CRYSTAL','ANAEROBIC'}) do
    for _,suffix in ipairs({'','_2','_3'}) do names[#names+1]='PLAYER_SHIP_'..base..suffix end
end
local lookup={};for i,n in ipairs(names)do lookup[n]=i end
local open=false
local remote=nil
local age=10000
local ticks=0
local lastError=''
local lastEnemy=''
local textures={}
local keys=Defines.SDL
local chain=Defines.Chain
local function emit(s)log('[FleetCoop7] SHIP_DIAG|'..s)end
local function number(n)return string.format('%.0f',n)end
local function active()return Hyperspace.App.world.bStartedGame and not Hyperspace.App.menu.bOpen end
local function context()
    local map=Hyperspace.App.world.starMap
    if not active() or not map.currentLoc then return nil end
    return number(Hyperspace.Global.currentSeed)..'|'..number(map.worldLevel)..'|'..number(map.currentLoc.loc.x)..'|'..number(map.currentLoc.loc.y)
end
local function hash(s)
    local h=0
    for i=1,#s do h=(h*65599+string.byte(s,i))%4294967296 end
    return h
end
local function report()
    local ctx=context();if not ctx then return end
    local ship=Hyperspace.ships.player
    if not ship then return end
    local id=lookup[ship.myBlueprint.blueprintName] or 0
    local hp=ship.ship.hullIntegrity
    if hp.first<0 or hp.second<1 or hp.second>255 or hp.first>hp.second then return end
    local interior=FleetInterior19 and FleetInterior19.capture()
    local line='SHIP|'..id..'|'..number(hp.first)..'|'..number(hp.second)..'|'..ctx..(interior and ('|'..interior) or '')..'|END'
    if not (FleetFastLink and FleetFastLink.send(line)) then log('[FleetCoop7] '..line) end
    if id==0 then
        local msg='Unsupported blueprint '..tostring(ship.myBlueprint.blueprintName)
        if msg~=lastError then emit(msg);lastError=msg end
    end
    local enemy=Hyperspace.ships.enemy
    local state='NONE'
    if enemy then state=tostring(enemy.myBlueprint.blueprintName)..'|'..number(enemy.ship.hullIntegrity.first)..'|'..number(enemy.ship.hullIntegrity.second) end
    if state~=lastEnemy then emit('LOCAL_ENEMY|'..state);lastEnemy=state end
end
function M.receive(payload,guard)
    if payload<1 or payload>2097152 then return end
    local n=payload-1
    local id=n%32;local hull=math.floor(n/32)%256;local maximum=math.floor(n/8192)%256
    local ctx=context()
    if id>30 or maximum<1 or hull>maximum or not ctx or hash(ctx)~=guard then return end
    remote={id=id,hull=hull,maximum=maximum,context=ctx};age=0
end
function M.isOpen()return open end
function M.key(key)
    if key==keys.KEY_F7 then
        if open then open=false;return chain.PREEMPT end
        if active() and not Hyperspace.App.gui.choiceBoxOpen and not (FleetPanel11 and FleetPanel11.isOpen()) then
            open=true;Hyperspace.App.gui.bPaused=true;emit('VIEW_OPEN')
        else emit('VIEW_BLOCKED|Close event/F8 first and enter a run.') end
        return chain.PREEMPT
    end
    if open then
        if key==keys.KEY_ESCAPE then open=false end
        return chain.PREEMPT
    end
    return chain.CONTINUE
end
for _,ev in ipairs({Defines.InternalEvents.ON_MOUSE_L_BUTTON_DOWN,Defines.InternalEvents.ON_MOUSE_L_BUTTON_UP,Defines.InternalEvents.ON_MOUSE_R_BUTTON_DOWN}) do
    script.on_internal_event(ev,function()return open and chain.PREEMPT or chain.CONTINUE end,300)
end
script.on_internal_event(Defines.InternalEvents.ON_TICK,function()
    ticks=ticks+1;age=age+1
    if FleetFastLink then FleetFastLink.tick() end
    if FleetInterior19 then FleetInterior19.tick() end
    if not active() then open=false;remote=nil end
    if open then Hyperspace.App.gui.bPaused=true end
    if remote and remote.context~=context() then remote=nil end
    if ticks%(FleetFastLink and FleetFastLink.ready() and 6 or 60)==0 then
        local ok,err=pcall(report)
        if not ok and tostring(err)~=lastError then lastError=tostring(err);emit('PROBE_ERROR|'..lastError) end
    end
end)
local function texture(name)
    if textures[name] then return textures[name].tex,textures[name].mini end
    local bp=Hyperspace.Blueprints:GetShipBlueprint(name,-1)
    if not bp then return nil,false end
    local stem=tostring(bp.imgFile)
    if not stem:match('^[%w_-]+$') then return nil,false end
    local path='ship/'..stem..'_base.png'
    local mini=false
    if not Hyperspace.Resources:ImageExists(path) then
        path='customizeUI/miniship_'..stem..'.png';mini=true
    end
    if not Hyperspace.Resources:ImageExists(path) then return nil,false end
    local tex=Hyperspace.Resources:GetImageId(path)
    if tex then textures[name]={tex=tex,mini=mini} end
    return tex,mini
end
local function text(x,y,s,w)FleetUI281.text(x,y,s,w or 600)end
local function image(name,y)
    local tex,mini=texture(name)
    if not tex or tex.width<=0 or tex.height<=0 then text(40,y+60,'Ship image unavailable: '..name);return end
    local scale=math.min(560/tex.width,190/tex.height)
    local w,h=tex.width*scale,tex.height*scale
    Graphics.CSurface.GL_BlitImagePartial(tex,30+(580-w)/2,y+(200-h)/2,w,h,0,1,0,1,1,Graphics.GL_Color(1,1,1,1),false)
    if mini then text(40,y+180,'Thumbnail asset (full hull unavailable)') end
end
local function draw()
    if not open or not active() then return end
    Graphics.CSurface.GL_DrawRect(10,80,630,610,Graphics.GL_Color(0.04,0.07,0.12,1))
    text(30,95,'FLEET VIEW v0.28.16 | READ-ONLY | F7 / Esc closes')
    text(30,120,'PARTNER — reported ship, not an allied combat entity')
    if remote and age<=600 and remote.context==context() then
        text(30,143,'Hull '..remote.hull..' / '..remote.maximum)
        if names[remote.id] then image(names[remote.id],165)
        else text(40,220,'Partner blueprint unsupported; see logs.') end
    else text(40,220,'Waiting for fresh partner ship data at the same beacon.') end
    text(30,380,'YOU — local ship (game paused for this view)')
    local player=Hyperspace.ships.player
    if player then
        local hp=player.ship.hullIntegrity
        text(30,403,'Hull '..number(hp.first)..' / '..number(hp.second))
        image(player.myBlueprint.blueprintName,425)
    end
    text(30,650,FleetCombat22 and FleetCombat22.status() or 'Separate battles')
    text(30,672,'Mixed ships; shared enemy effects. No boarding/drone support.')
end
-- Native scene rendering owns the stacked transform and inverse input mapping.
local function drawLive()
    if open or not active() then return end
    local gui=Hyperspace.App.gui
    if gui.choiceBoxOpen or gui.menu_pause or gui.event_pause or gui.bHideUI then return end
    if Hyperspace.App.world.starMap.bOpen then return end
    if FleetPanel11 and FleetPanel11.isOpen() then return end
    if not remote or remote.context~=context() then return end
    local name=names[remote.id]
    if not name then return end
    local tex,mini=texture(name)
    if not tex or tex.width<=0 or tex.height<=0 then return end
    -- Keep the native crew list, top resource bar, and right-side enemy clear.
    -- No frame enclosing the local ship and no replacement player rendering.
    local x,y,w,h=145,94,665,264
    FleetUI281.box(x,y,w,24)
    text(x+8,y+5,'PARTNER  |  HULL '..remote.hull..' / '..remote.maximum)
    if age>600 then text(x+365,y+5,'PARTNER UPDATE DELAYED',285)end
    if FleetScene26 then
        if not FleetScene26.available() then text(x+8,y+30,"Install the v0.28.16 DLL using Start_FTL_Coop.bat")
        else
            local shown,delayed=FleetScene26.draw()
            if not shown then text(x+8,y+30,"Waiting for partner native scene...")
            else
                local labelY=FleetScene26.localLabelY()
                FleetUI281.box(x,labelY,665,20)
                text(x+8,labelY+3,"YOUR SHIP",204)
                text(x+300,labelY+3,FleetScene26.viewLabel(),350)
                if delayed and age<=600 then text(x+365,y+5,"PARTNER UPDATE DELAYED",285)end
            end
        end
        return
    end
    if FleetFastView and FleetFastView.draw(x,y+28,w,h-28) then return end
    if FleetInterior19 and FleetInterior19.draw(x,y+28,w,h-28,not mini and tex or nil) then return end
    local scale=math.min((w-20)/tex.width,(h-32)/tex.height)
    local iw,ih=tex.width*scale,tex.height*scale
    Graphics.CSurface.GL_BlitImagePartial(tex,x+(w-iw)/2,y+28+(h-28-ih)/2,iw,ih,0,1,0,1,1,Graphics.GL_Color(1,1,1,1),false)
    if mini then text(x+8,y+h,'Thumbnail asset') end
end
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()end,function()
    local ok,err=pcall(function()
        drawLive();draw()
        if not open and active() and FleetCombat22 and FleetCombat22.notice() then
            local message=FleetCombat22.status()
            FleetUI281.box(145,70,665,24)
            text(153,75,FleetUI281.readable(message),649)
        end
    end)
    if not ok then
        open=false
        if tostring(err)~=lastError then lastError=tostring(err);emit('VIEW_ERROR|'..lastError) end
    end
end)
script.on_init(function()open=false;remote=nil;age=10000 end)
script.on_load(function()emit('V027_LOADED')end)
