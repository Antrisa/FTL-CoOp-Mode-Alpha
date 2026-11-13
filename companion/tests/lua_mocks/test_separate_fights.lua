-- Mock test for v0.28.14 combat fallback. NOT an in-game test.
local DIR=(os.getenv('FLEET_COMPANION') or 'companion')..'/'
logs={};sent={};handlers={};loaded={}
function log(s)logs[#logs+1]=s end
local function vec(t)t=t or {};local n=#t;local v={};for i=1,n do v[i-1]=t[i]end;v.size=function()return n end;return v end
script={on_internal_event=function(e,f)handlers[e]=f end,on_init=function(f)handlers.init=f end,on_load=function(f)end,on_render_event=function()end}
Defines={Chain={CONTINUE=0,PREEMPT=1},SDL={KEY_F6=6,KEY_1=49,KEY_9=57,KEY_RETURN=13,KEY_SPACE=32,KEY_KP_ENTER=271},
 InternalEvents=setmetatable({},{__index=function(t,k)return k end}),RenderEvents={MOUSE_CONTROL=1}}
local systems={}
local function ship(id,name)
 return {iShipId=id,bDestroyed=false,bJumping=false,_targetable={hostile=true},myBlueprint={blueprintName=name},
  ship={hullIntegrity={first=10,second=10},vRoomList=vec{{iRoomId=0,rect={x=0,y=0,w=2,h=2}}}},
  HasSystem=function(self,i)return id==1 and systems[i]==true end,
  GetWeaponList=function()return vec{{blueprint={type=0,name='LASER_BURST_1'}}}end,
  GetDroneList=function()return vec{}end,vSystemList=vec{},GetShieldPower=function()return {first=0,second=0}end}
end
local box={bOpen=false}
Hyperspace={App={world={bStartedGame=true,starMap={bOpen=false}},menu={bOpen=false},
  gui={choiceBoxOpen=false,event_pause=false,menu_pause=false,bPaused=false,choiceBox=box}},
 ships={player=ship(0,'PLAYER_SHIP_HARD'),enemy=ship(1,'REBEL_FAT')},
 CustomEventsParser={GetInstance=function()return {LoadEvent=function(self,world,name,uniq,seed)loaded[#loaded+1]=name end}end},
 Blueprints={},Pointf=function(x,y)return {x=x,y=y}end}
beacon=111
FleetInterior19={contextGuard=function()return beacon end}
FleetFastLink={ready=function()return true end,send=function(s)sent[#sent+1]=s;return true end}
FleetNativeCombat={version=4,setReplica=function(v)replica=v end}
dofile(DIR..'combat.lua')
local M=FleetCombat22
local function ticks(n)for i=1,n do M.tick()end end
local function has(t,pat)for _,s in ipairs(t)do if s:find(pat,1,true)then return true end end return false end
local function check(c,msg)if not c then error('FAILED: '..msg,2)end;print('pass: '..msg)end

-- 1. Unsupported enemy (cloaking) no longer dead-ends the run
systems[10]=true
ticks(40)
check(M.separate(),'cloaking enemy -> separate fight')
check(has(logs,'SEPARATE_FIGHT|SETUP|enemy_system_cloaking'),'logged setup fallback')
check(has(sent,'COMBAT|STOP|enemy_system_cloaking'),'partner told the reason')
check(M.canJump() and M.pauseBlock()==nil and not M.isActive(),'no lock: can pause, resume and jump')
check(Hyperspace.App.gui.bPaused==true,'(setup pause happened once; captain resumes with Space)')
Hyperspace.App.gui.bPaused=false;ticks(200)
check(Hyperspace.App.gui.bPaused==false,'separate fight is never re-paused by combat code')
check(not has(sent,'COMBAT|ARM|') or #sent<4,'no re-arm at the same beacon')
beacon=222;systems[10]=nil;Hyperspace.ships.enemy=nil;ticks(2)
check(not M.separate(),'cleared after leaving the beacon')

-- 2. Supported enemy: START locks surrender/escape; mid-fight STOP falls back
Hyperspace.ships.enemy=ship(1,'REBEL_FAT');sent={};ticks(40)
check(has(sent,'COMBAT|ARM|222|'),'auto-armed at the new beacon')
M.receive('COMBAT|START|abcd|222|G')
check(M.isActive() and replica==true,'shared combat active as guest replica')
check(#loaded==1 and loaded[1]=='FLEET_COOP_COMBAT_SYNC','surrender/escape lock event loaded once')
check(has(logs,'OUTCOME_LOCK|OK'),'lock logged')
M.receive('COMBAT|STOP|peer_unavailable_after_hold')
check(M.separate() and replica==false and not M.isActive(),'link loss mid-fight -> separate fight, replica off')
check(has(logs,'SEPARATE_FIGHT|MIDFIGHT|peer_unavailable_after_hold'),'logged mid-fight fallback')
-- events are personal while separate
FleetCoop10=nil;FleetPanel11=nil;FleetUI281={}
dofile(DIR..'native_vote.lua')
check(FleetNative15.localSeparate({count=2})==true,'event screens are personal during a separate fight')
beacon=333;Hyperspace.ships.enemy=nil;ticks(2)
check(FleetNative15.localSeparate({count=2})==false,'shared voting returns at the next beacon')

-- 3. F6 escape hatch on a stuck event (not in combat)
sent={};Hyperspace.App.gui.choiceBoxOpen=true
local r=handlers.ON_KEY_DOWN(Defines.SDL.KEY_F6)
check(r==Defines.Chain.PREEMPT and M.separate(),'F6 with an event open splits the beacon')
check(has(sent,'COMBAT|STOP|manual_split'),'partner notified of the split')
-- partner side
beacon=444;ticks(1);check(not M.separate(),'reset for partner scenario')
M.receive('COMBAT|STOP|manual_split')
check(M.separate(),'partner receiving the split also separates')
-- 4. F6 without an event keeps its old meaning
beacon=555;Hyperspace.App.gui.choiceBoxOpen=false;ticks(1)
handlers.ON_KEY_DOWN(Defines.SDL.KEY_F6);check(not M.separate(),'F6 without an event does not split')

-- 5. v0.28.15: the reward barrier must not survive leaving its beacon
beacon=600;Hyperspace.App.gui.choiceBoxOpen=false;Hyperspace.ships.enemy=ship(1,'AUTO_ASSAULT');sent={};ticks(40)
M.receive('COMBAT|START|ef01|600|G')
check(M.isActive(),'shared fight at the exit beacon')
Hyperspace.ships.enemy.ship.hullIntegrity.first=0
M.receive('COMBAT|FINISH|ef01|5|0|10|0|0||0|0')
check(has(logs,'COMPLETED_GUEST|ef01') and M.rewardPending() and not M.canJump(),'reward barrier holds at the beacon')
check(has(sent,'COMBAT|FINISH_ACK|ef01|5'),'finish acknowledged')
beacon=700;Hyperspace.ships.enemy=nil;ticks(2)
check(has(logs,'POST_ABANDONED|ef01|left_beacon'),'barrier dropped after leaving (sector jump before release)')
check(M.canJump() and not M.rewardPending(),'jumping is possible again in the new sector')
-- 6. no reward screen ever appears: stop waiting after 15 s of running time
beacon=800;Hyperspace.ships.enemy=ship(1,'AUTO_ASSAULT');sent={};ticks(40)
M.receive('COMBAT|START|ef02|800|G');Hyperspace.ships.enemy.ship.hullIntegrity.first=0
M.receive('COMBAT|FINISH|ef02|7|0|10|0|0||0|0');Hyperspace.App.gui.bPaused=false
ticks(1000)
check(has(logs,'POST_EVENT_ASSUMED|ef02') and has(sent,'COMBAT|POST_READY|ef02|7'),'missing reward screen no longer blocks POST_READY')
print('ALL MOCK CHECKS PASSED')
