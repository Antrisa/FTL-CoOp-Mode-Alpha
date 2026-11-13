FleetJump24={}
local M=FleetJump24
local native=FleetNativeCombat
local gated=false
local vote=nil
local prepared=nil
local committed=0
local voteYou=nil
local votePeer=nil
local message='Click a neighboring beacon to vote. Both votes must match.'
local function send(s)return FleetFastLink and FleetFastLink.send('JUMP|'..s)end
local function guard()return FleetInterior19 and FleetInterior19.contextGuard()end
local function fmt(x)return string.format('%.0f',x)end
local function clear()
 if vote or prepared then send('CLEAR')end
 vote=nil;prepared=nil;voteYou=nil;votePeer=nil
end
function M.tick()
 if not native or native.version<2 then return end
 if not Hyperspace.App.world.bStartedGame or Hyperspace.App.menu.bOpen then
  clear();gated=false;native.jumpEnable(false);native.jumpArrived();return
 end
 if FleetFastLink and FleetFastLink.ready()then gated=true end
 -- Once connected, fail closed if the link drops; only menu resets to solo.
 native.jumpEnable(gated)
 if not gated then return end
 if Hyperspace.App.gui.choiceBoxOpen or Hyperspace.App.gui.event_pause then clear();message='Finish your event before fleet jumping';return end
 local serial,x,y=native.jumpPoll()
 if serial then
  vote=serial;prepared=nil
  if FleetCombat22 and not FleetCombat22.canJump()then clear();message='Finish shared combat before fleet jumping';return end
  if guard() and FleetFastLink.ready() then
   send('VOTE|'..fmt(guard())..'|'..fmt(serial)..'|'..fmt(x)..'|'..fmt(y))
   message='Your vote: '..fmt(x)..','..fmt(y)..' - waiting for partner'
  else message='Link unavailable. Return to menu to reset co-op.'end
 end
 if vote and not native.jumpCheck(vote) then clear();message='Vote cancelled: reopen the map and choose again.'end
end
function M.receive(line)
 local p={};for x in (line..'|'):gmatch('(.-)|')do p[#p+1]=x end
 if p[2]=='STATUS' then
  message=p[3]
  voteYou,votePeer=message:match('^You ([%d,%-]+) / Partner ([%d,%-]+)$')
  if not voteYou then
   voteYou=message:match('^You ([%d,%-]+) / Partner waiting$')
   votePeer=message:match('^You waiting / Partner ([%d,%-]+)$')
  end
  return
 end
 if p[2]=='CANCEL' then
  if p[3]~='both_arrived' and committed>0 then Hyperspace.App.gui.bPaused=true end
  vote=nil;prepared=nil;voteYou=nil;votePeer=nil;message=p[3];if p[3]=='both_arrived' then committed=0 end;return
 end
 if p[2]~='PREPARE' and p[2]~='COMMIT' then return end
 local id,g,serial=tonumber(p[3]),tonumber(p[4]),tonumber(p[5])
 if not id or not native or native.version<2 then return end
 if p[2]=='COMMIT' and id==committed then send('ACK|'..fmt(id));return end
 if Hyperspace.App.gui.choiceBoxOpen or Hyperspace.App.gui.event_pause or (FleetCombat22 and not FleetCombat22.canJump()) or g~=guard() or serial~=vote or not native.jumpCheck(serial) then clear();return end
 if p[2]=='PREPARE' then prepared=id;send('READY|'..fmt(id));message='Votes match - confirming both ships'
 elseif prepared==id then
  if native.jumpCommit(serial)then committed=id;vote=nil;prepared=nil;send('ACK|'..fmt(id));message='Fleet jump committed'
  else clear();message='Jump refused locally - check both ships'end
 end
end
script.on_internal_event(Defines.InternalEvents.JUMP_ARRIVE,function(ship)
 if ship.iShipId==0 and native and native.version>=2 then native.jumpArrived()end
end)
script.on_render_event(Defines.RenderEvents.MOUSE_CONTROL,function()end,function()
 if gated and Hyperspace.App.world.starMap.bOpen then
  if Hyperspace.App.world.starMap.bChoosingNewSector then
   FleetUI281.box(180,665,900,40)
   FleetUI281.text(190,676,'SECTOR CHOICE: select the same sector manually on both PCs',880)
   return
  end
  if voteYou or votePeer then
   Graphics.CSurface.GL_DrawRect(180,633,440,28,Graphics.GL_Color(.1,.25,.4,1))
   Graphics.CSurface.GL_DrawRect(630,633,450,28,Graphics.GL_Color(.4,.25,.05,1))
   FleetUI281.text(190,639,'YOU: '..(voteYou or 'waiting'),420)
   FleetUI281.text(640,639,'PARTNER: '..(votePeer or 'waiting'),430)
  end
  FleetUI281.box(180,665,900,40)
  FleetUI281.text(190,676,'FLEET JUMP: '..FleetUI281.readable(message),880)
 end
end)
