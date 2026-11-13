-- Display-only remote pointer. Never moves the OS mouse or invokes clicks.
FleetCursor14={}
local M=FleetCursor14
local ev=Defines.InternalEvents
local keys=Defines.SDL
local x,y=0,0
local moved=false
local frame=0
local remote=nil
local age=1000
local diagnostic=0
local disabled=false
local function panel() return FleetPanel11 and FleetPanel11.isOpen() and 1 or 0 end
local function context()
    local app=Hyperspace.App
    if app.menu.bOpen then
        if app.menu.shipBuilder and app.menu.shipBuilder.bOpen then return -1 end
        return 0
    end
    local e=FleetCoop10.safeCapture()
    return e and e.token or -1
end
script.on_internal_event(ev.ON_MOUSE_MOVE,function(mx,my)
    if mx>=0 and mx<1280 and my>=0 and my<720 then x=math.floor(mx);y=math.floor(my);moved=true end
    return Defines.Chain.CONTINUE
end)
function M.receive(payload,guard)
    if payload<1 or payload>4194304 then return end
    local n=payload-1
    local rx=n%2048;local ry=math.floor(n/2048)%1024;local rp=math.floor(n/2097152)%2
    if rx>=1280 or ry>=720 or guard~=context() or rp~=panel() then remote=nil;return end
    remote={x=rx,y=ry,token=guard,panel=rp};age=0
    if diagnostic<=0 then
        log('[FleetCoop7] CURSOR_DIAG|RECEIVED|'..rx..','..ry)
        diagnostic=180
    end
end
script.on_internal_event(ev.ON_TICK,function()
    frame=frame+1;age=age+1;diagnostic=diagnostic-1
    if age>180 then remote=nil end
    if not disabled and moved and frame%30==0 then
        log('[FleetCoop7] CURSOR|'..x..'|'..y..'|'..panel()..'|'..string.format('%.0f',context()))
    end
end)
local function draw()
    if not remote or age>180 or remote.token~=context() or remote.panel~=panel() then return end
    local color=Graphics.GL_Color(0.2,1,0.9,1)
    local px,py=remote.x,remote.y
    Graphics.CSurface.GL_DrawRect(px-6,py-1,13,3,color)
    Graphics.CSurface.GL_DrawRect(px-1,py-6,3,13,color)
    Graphics.freetype.easy_print(5,math.min(px+10,1190),math.min(py+10,695),'Partner')
end
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()end,function()
    if disabled then return end
    local ok,err=pcall(draw)
    if not ok then disabled=true;remote=nil;log('[FleetCoop7] ERROR|Cursor disabled: '..tostring(err)) end
end)
script.on_init(function()remote=nil;age=1000;moved=false end)
script.on_load(function()log('[FleetCoop7] CURSOR_DIAG|V014_LOADED')end)
