FleetScene26={}
local M=FleetScene26
local n=FleetNativeScene
if n and n.version~=6 then n=nil end
local ticks=0
local view=0
local crisp=true
local names={"BALANCED", "YOUR SHIP DETAIL", "PARTNER DETAIL"}
function M.viewLabel()return "F9: "..names[view+1].." | F10: "..(crisp and "CRISP" or "SMOOTH")end
function M.localLabelY()return ({356,286,428})[view+1]end
local guard=nil
local received=0
local awaiting=false
function M.ack()awaiting=false end
local function visible()
 local a=Hyperspace.App
 return a.world.bStartedGame and not a.menu.bOpen and not a.gui.choiceBoxOpen and not a.world.starMap.bOpen and not (FleetPanel11 and FleetPanel11.isOpen())
end
function M.tick()
 ticks=ticks+1
 if not n then return end
 if not FleetFastLink or not FleetFastLink.ready() then awaiting=false end
 local g=FleetInterior19 and FleetInterior19.contextGuard()
 local on=g and visible() and FleetFastLink and FleetFastLink.ready()
 if g~=guard then n.enable(false);guard=g end
 n.enable(not not on)
 -- Target 30 Hz at 60 game ticks/sec. Native capture
 -- retains the newest frame; intermediate frames never need transmission.
 if on and not awaiting and ticks%2==0 then local data=n.poll();if data then awaiting=not not FleetFastLink.send('SCENE|'..string.format('%.0f',g)..'|'..data)end end
end
function M.receive(line)
 if not n or not visible() then return end
 local g,data=line:match('^SCENE|(%d+)|([0-9a-f]+)$')
 if g and tonumber(g)==FleetInterior19.contextGuard() then
  if n.accept(data) then
   received=received+1
   if received==1 or received%200==0 then log("[FleetCoop26] NATIVE_SCENE|RECEIVED|"..received)end
  end
 end
end
function M.draw()if n and visible() then return n.draw()end;return false end
function M.available()return n~=nil end
script.on_init(function()guard=nil;awaiting=false;view=0;if n then n.enable(false);n.setView(0);n.setCrisp(crisp)end end)
script.on_internal_event(Defines.InternalEvents.ON_KEY_DOWN,function(key)
 if key==Defines.SDL.KEY_F10 and n and visible() then
  crisp=not crisp;n.setCrisp(crisp);return Defines.Chain.PREEMPT
 end
 if key==Defines.SDL.KEY_F9 and n and visible() then
  view=(view+1)%3;n.setView(view)
  return Defines.Chain.PREEMPT
 end
 return Defines.Chain.CONTINUE
end)

script.on_load(function()log("[FleetCoop26] NATIVE_SCENE|"..(n and "AVAILABLE" or "DLL_MISSING"))end)
