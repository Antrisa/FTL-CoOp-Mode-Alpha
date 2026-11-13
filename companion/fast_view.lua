-- Optional live image of the partner's actual FTL ship region. Read-only.
FleetFastView={}
local M=FleetFastView
local ticks=0
local lastCapture=-100
local lastSeen=-10000
local remoteContext=nil
local native=FleetNativeVideo
local captureWarning=false
local received=0
local function guard()
 if not FleetInterior19 then return nil end
 return FleetInterior19.contextGuard()
end
function M.tick()
 ticks=ticks+1
 if ticks%300==0 and received>0 then
  log('[FleetCoop7] SHIP_DIAG|FAST|VIDEO_FRAMES_LAST_300_TICKS|'..received);received=0
 end
 if remoteContext and remoteContext~=guard() then remoteContext=nil;if native then native.clear()end end
end
function M.receive(line)
 if not native then return end
 local g,w,h,data=line:match('^VIEW|(%d+)|(%d+)|(%d+)|([%x]+)$')
 if not g then return end
 g=tonumber(g);w=tonumber(w);h=tonumber(h)
 if g~=guard() or w<1 or w>320 or h<1 or h>180 or #data>460800 then return end
 if native.accept(w,h,data) then
  if remoteContext~=g then log('[FleetCoop7] SHIP_DIAG|FAST|VIDEO_ACTIVE')end
  remoteContext=g;lastSeen=ticks;received=received+1
 end
end
function M.draw(x,y,w,h)
 if not native or not remoteContext or remoteContext~=guard() then return false end
 local shown=native.draw(x,y,w,h)
 if shown and ticks-lastSeen>180 then Graphics.freetype.easy_print(5,x+4,y+h-12,'LIVE VIEW UPDATE DELAYED')end
 return shown
end
local function capture()
 if not native or not FleetFastLink or not FleetFastLink.ready() or ticks-lastCapture<15 then return end
 local g=guard();if not g then return end
 local gui=Hyperspace.App.gui
 if gui.choiceBoxOpen or gui.menu_pause or gui.event_pause or gui.bHideUI or Hyperspace.App.world.starMap.bOpen then return end
 if FleetPanel11 and FleetPanel11.isOpen() then return end
 local s=Hyperspace.ships.player;local a=s.ship.shipImage
 local box=Hyperspace.ShipGraph.GetShipInfo(s.iShipId).shipBox
 local x=math.max(0,gui.shipPosition.x+box.x+a.x-28)
 local y=math.max(80,gui.shipPosition.y+box.y+a.y-28)
 local w=math.min(a.w+56,1280-x);local h=math.min(a.h+56,660-y)
 if w<16 or h<16 then return end
 lastCapture=ticks
 local ow,oh,data=native.capture(x,y,w,h)
 if data then
  if captureWarning then log('[FleetCoop7] SHIP_DIAG|FAST|VIDEO_CAPTURE_RECOVERED');captureWarning=false end
  FleetFastLink.send('VIEW|'..string.format('%.0f',g)..'|'..ow..'|'..oh..'|'..data)
 elseif not captureWarning then
  captureWarning=true;log('[FleetCoop7] SHIP_DIAG|FAST|VIDEO_CAPTURE_UNAVAILABLE|'..tostring(oh)..'|Use Start_FTL_Coop.bat (OpenGL)')
 end
end
local failed=false
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()
 local ok,err=pcall(capture)
 if not ok and not failed then failed=true;log('[FleetCoop7] SHIP_DIAG|FAST|VIDEO_ERROR|'..tostring(err))end
end,function()end)
script.on_init(function()remoteContext=nil;lastSeen=-10000;failed=false;captureWarning=false;if native then native.clear()end end)
