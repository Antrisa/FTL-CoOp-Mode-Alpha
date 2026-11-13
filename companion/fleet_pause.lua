-- General ON_TICK continues while paused; never depend on SHIP_LOOP for delivery.
FleetPause27={}
local M=FleetPause27
local token='none'
local rev=0
local mode='HOLD'
local readyRev=nil
local ticks=0
local lastState=-10000
local seq=0
local keyDown=false
local count=0
local reason='waiting_for_both'
local lastGuard=nil
local lastBlocked=nil
local pending=nil
local latched=false
local rejected=nil
local pendingSeq=0
local C=Defines.Chain
local function gui()return Hyperspace.App.gui end
local function inRun()return Hyperspace.App.world.bStartedGame and not Hyperspace.App.menu.bOpen end
local function guard()return FleetInterior19 and FleetInterior19.contextGuard()end
local function linked()return FleetFastLink and FleetFastLink.ready()end
local function send(s)return FleetFastLink and FleetFastLink.send('PAUSE|'..s)end
local function blocked()
 local a=Hyperspace.App;local g=gui()
 if not inRun() then return 'lobby' end
 if g.choiceBoxOpen or g.event_pause then return 'event' end
 if a.world.starMap.bOpen then return 'map' end
 if g.menu_pause then return 'menu' end
 if (FleetPanel11 and FleetPanel11.isOpen()) or (FleetShips17 and FleetShips17.isOpen and FleetShips17.isOpen()) then return 'inspector' end
 if FleetCombat22 and FleetCombat22.pauseBlock then local b=FleetCombat22.pauseBlock();if b then return b end end
 return 'clear'
end
local function freeze()if inRun() then gui().bPaused=true end end
local function report()
 send('REPORT|'..string.format('%.0f',guard() or -1)..'|'..blocked()..'|'..token..'|'..rev)
end
local function request(kind)
 if rev<1 or token=='none' then freeze();return end
 if kind=='HOLD' and pending and pending:sub(1,5)=='HOLD|' then return end
 seq=seq+1;pendingSeq=seq;pending=kind..'|'..token..'|'..rev..'|'..seq;send(pending)
end
function M.hold(origin)
 if not inRun() then return end
 if log then log('[FleetCoop7] PAUSE27|LOCAL_HOLD|'..tostring(origin or 'player')..'|auto='..tostring(gui().bAutoPaused))end
 mode='HOLD';readyRev=nil;reason='captain_paused';freeze();report();request('HOLD')
end
function M.ready()
 -- Replayed utility READY must not pause an already running fleet.
 if mode=='RUN' then return end
 if not inRun() or not linked() or blocked()~='clear' or rev<1 or ticks-lastState>90 then freeze();return end
 if readyRev==rev then M.hold();return end
 freeze();report();readyRev=rev;request('READY')
end
function M.active()return latched and inRun()end
function M.receive(line)
 if line=='PAUSE|LOCAL_HOLD' then M.hold();return end
 if line=='PAUSE|LOCAL_READY' then M.ready();return end
 local state,ack=line:match('^(PAUSE|STATE|.*)|(%d+)$')
 -- v276 states carry the last processed request sequence.
 if state and select(2,state:gsub('|',''))==7 then line=state else ack=nil end
 ack=tonumber(ack) or 0
 local t,r,m,why,n,me=line:match('^PAUSE|STATE|([%w_-]+)|(%d+)|(HOLD)|([%w_]+)|([012])|([01])$')
 if not t then t,r,m,why,n,me=line:match('^PAUSE|STATE|([%w_-]+)|(%d+)|(RUN)|([%w_]+)|([012])|([01])$')end
 r=tonumber(r);if not t or not r or r<1 or r>2147483647 then return end
 if t==token and r<rev then return end
 -- Server HOLD -> RUN is monotonic within a revision. A later pause gets a new revision.
 if t==token and r==rev and mode=='RUN' and m=='HOLD' then return end
 local changed=t~=token or r~=rev
 if log and (changed or m~=mode or why~=reason) then log('[FleetCoop7] PAUSE27|'..m..'|'..why..'|rev='..r)end
 if changed then readyRev=nil;pending=nil;rejected=nil;mode='HOLD' end
 token=t;rev=r;lastState=ticks;count=tonumber(n);reason=why
 if m=='RUN' then
  if mode=='RUN' and inRun() and gui().bPaused then M.hold('game_pause_on_state');return end
  -- A stale RUN cannot undo a local pause or a newly opened modal screen.
  if not changed and (mode=='RUN' or readyRev==rev) and blocked()=='clear' and linked() then
   local resumed=mode~='RUN'
   gui().bPaused=false;mode='RUN';pending=nil
   if resumed and log then log('[FleetCoop7] PAUSE27|APPLIED_RUN|rev='..rev)end
  else
   mode='HOLD';readyRev=nil;freeze()
   if rejected~=rev then
    rejected=rev
    if log then log('[FleetCoop7] PAUSE27|REJECT_RUN|rev='..rev..'|blocked='..blocked()..'|linked='..tostring(linked()))end
    report();request('HOLD')
   end
  end
 else
  mode='HOLD';freeze()
  -- A stale state must not acknowledge a newer cancellation request.
  if pending and ack>=pendingSeq then pending=nil end
 end
end
function M.tick()
 ticks=ticks+1
 if inRun() then latched=true end
 local b=blocked();local g=guard()
 if g~=lastGuard or b~=lastBlocked then
  if mode=='RUN' or readyRev then mode='HOLD';readyRev=nil;pending=nil;freeze();request('HOLD')end
  lastGuard=g;lastBlocked=b;report()
 end
 if not inRun() then keyDown=false;readyRev=nil;mode='HOLD';pending=nil end
 if not linked() or ticks-lastState>90 then
  if mode=='RUN' or readyRev then mode='HOLD';readyRev=nil;pending=nil;request('HOLD')end
  reason='connection_wait';freeze()
 elseif inRun() and mode=='RUN' and gui().bPaused then M.hold('game_pause_on_tick') end
 if mode~='RUN' or b~='clear' then freeze()end
 if ticks%6==0 then report()end
 if pending and ticks%15==0 then send(pending)end
end
script.on_internal_event(Defines.InternalEvents.ON_KEY_DOWN,function(key)
 if key~=Defines.SDL.KEY_SPACE or not inRun() then return C.CONTINUE end
 if keyDown then return C.PREEMPT end;keyDown=true
 if mode=='RUN' then M.hold() else M.ready()end
 return C.PREEMPT
end,2000)
script.on_internal_event(Defines.InternalEvents.ON_KEY_UP,function(key)
 if key==Defines.SDL.KEY_SPACE then keyDown=false end
 return C.CONTINUE
end,2000)
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()end,function()
 if not inRun() or mode=='RUN' then return end
 local g=Hyperspace.App.gui
 if g.choiceBoxOpen or g.menu_pause or Hyperspace.App.world.starMap.bOpen or (FleetPanel11 and FleetPanel11.isOpen())then return end
 FleetUI281.box(145,580,665,26)
 local b=blocked()
 local display=b~='clear' and ('blocked_'..b) or (reason=='running' and 'waiting_for_resume_confirmation' or reason)
 local message='FLEET PAUSED | '..display:gsub('_',' ')..' | Ready '..count..'/2'
 if blocked()=='clear' then message=message..(readyRev==rev and ' | Space cancels ready' or ' | Space = ready')end
 FleetUI281.text(153,586,'PAUSED: '..display:gsub('_',' '),300)
 local action=blocked()=='clear' and (readyRev==rev and ' | SPACE: cancel ready' or ' | SPACE: ready') or ''
 FleetUI281.text(465,586,'Ready '..count..'/2'..action,337)
end)
script.on_init(function()mode='HOLD';readyRev=nil;pending=nil;lastGuard=nil;lastBlocked=nil;keyDown=false;lastState=-10000;rejected=nil end)
