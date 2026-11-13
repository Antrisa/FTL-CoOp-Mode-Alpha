-- Shared-enemy laboratory. Automatically synchronizes linked supported encounters.
-- Host FTL owns enemy damage/repair/death. Each player still owns their own ship.
FleetCombat22={}
local M=FleetCombat22
local enabled=false
local epoch=nil
local role=nil
local ticks=0
local lastServer=0
local lastSnap=0
local shotId=0
local spawnId=0
local snapId=0
local remoteEffects=0
local remoteSnap=0
local remoteSpawn=0
local seen={}
local pending={}
local status='Fleet combat: automatic when linked'
local stopped=false
local networkHold=false
local signature=nil
local latest=nil
local setupStarted=0
local injected=false
local autoAttempt=nil
local stableGuard=nil
local clearTicks=0
local heartbeatCount=0
local finishing=nil
local completedEpoch=nil
local completedSeq=nil
local post=nil
local native=FleetNativeCombat
local boarding=FleetNativeBoarding
local boardingEncounter=false
-- v0.28.16: a failed or unsupported shared fight becomes a separate fight at
-- this beacon instead of ending the run. {guard=beacon guard, reason=text}
local independent=nil
local idle='Fleet combat: automatic when linked'
local C=Defines.Chain
local function logc(s)log('[FleetCoop7] COMBAT22|'..s)end
local function send(s)return FleetFastLink and FleetFastLink.send('COMBAT|'..s)end
local function fields(s)local out={};for x in (s..'|'):gmatch('(.-)|')do out[#out+1]=x end;return out end
local function pause()Hyperspace.App.gui.bPaused=true end
local function reset(quiet)
 boardingEncounter=false
 if boarding then boarding.clear()end
 post=nil
 finishing=nil
 if enabled and not quiet then send('STOP|encounter_finished')end
 autoAttempt=nil
 networkHold=false;enabled=false;epoch=nil;role=nil;pending={};seen={};signature=nil;latest=nil;stopped=false
 if native then native.setReplica(false)end
 status='Fleet combat: automatic when linked'
end
local function separate(reason,phase)
 -- Each ship keeps its own enemy copy and its own events for the rest of this
 -- beacon. Nothing is copied between ships; the guest replica flag is cleared
 -- (inside reset) so local damage applies again. Cleared when the beacon changes.
 local g=FleetInterior19 and FleetInterior19.contextGuard()
 reset(true)
 autoAttempt=g
 independent={guard=g,reason=reason}
 status='SEPARATE FIGHT: '..reason..' | each ship fights its own enemy here'
 logc('SEPARATE_FIGHT|'..phase..'|'..reason)
end
local function fail(reason)
 -- Was: freeze and tell the captain to return to the menu (a dead run).
 if not enabled then logc('FAIL_IGNORED|'..tostring(reason));return end
 local clean=tostring(reason):gsub('[^%w_.-]','_'):sub(1,90)
 local phase=epoch and 'MIDFIGHT' or 'SETUP'
 send('STOP|'..clean)
 separate(clean,phase)
end
local function guard()return FleetInterior19 and FleetInterior19.contextGuard()end
local function hash(s)local h=0;for i=1,#s do h=(h*65599+s:byte(i))%4294967296 end;return string.format('%.0f',h)end
local function geometry(ship)
 local rows={ship.myBlueprint.blueprintName,tostring(ship.ship.hullIntegrity.second)}
 for i=0,ship.ship.vRoomList:size()-1 do local r=ship.ship.vRoomList[i];local a=r.rect
  rows[#rows+1]=table.concat({r.iRoomId,a.x,a.y,a.w,a.h},',')end
 return hash(table.concat(rows,';'))
end
local function weapons(ship,allowEmpty)
 local list=ship:GetWeaponList();local names={};local added={}
 local function add(bp)
  if bp.type<0 or bp.type>4 then return 'weapon_'..bp.name..'_type_'..tostring(bp.type)end
  if not added[bp.name]then names[#names+1]=bp.name;added[bp.name]=true end
 end
 for i=0,list:size()-1 do local why=add(list[i].blueprint);if why then return nil,why end end
 if ship.artillerySystems then
  for i=0,ship.artillerySystems:size()-1 do
   local why=add(ship.artillerySystems[i].projectileFactory.blueprint);if why then return nil,why end
  end
 end
 if ship.iShipId==0 and ship:HasSystem(4)then
  local drones=ship:GetDroneList()
  for i=0,drones:size()-1 do
   local d=drones[i]
   if d.type==1 then
    local name=d.blueprint and d.blueprint.weaponBlueprint
    if not name or name=='' then return nil,'drone_weapon_missing'end
    local bp=Hyperspace.Blueprints:GetWeaponBlueprint(name)
    if not bp or bp.name~=name then return nil,'drone_weapon_unknown'end
    local why=add(bp);if why then return nil,why end
   end
  end
 end
 if #names==0 and not allowEmpty then return nil,'no_weapons'end
 return table.concat(names,',')
end
local function supported(ship,localPlayer)
 -- Enemy space drones attack/defend locally; shared enemy hull/systems remain host-owned.
 -- Friendly repair/battle/hull-repair/shield drones affect only their own ship.
 -- Enemy crew drones and boarding pods still need additional replication.
 local names={[4]='drones',[9]='teleporter',[10]='cloaking',[13]='clone_bay',[14]='mind_control',[15]='hacking'}
 local ids=localPlayer and {9,14,15} or {10,13,14}
 for _,id in ipairs(ids)do if ship:HasSystem(id)then return false,names[id]end end
 if not localPlayer and ship:HasSystem(9) and (not boarding or boarding.version~=1 or not FleetNativeEffects or FleetNativeEffects.version~=2)then return false,'teleporter_requires_v0288_DLL'end
 if ship:HasSystem(4)then
  if not ship.GetDroneList then return false,'drone_list_unavailable'end
  local drones=ship:GetDroneList()
  for i=0,drones:size()-1 do
   local d=drones[i]
   -- Native DroneType: 0 defense, 1 combat (laser or beam).
   if not (d.type==0 or d.type==1 or (localPlayer and (d.type==2 or d.type==3 or d.type==5 or d.type==7))) then
    return false,'drone_'..tostring(d.blueprint and d.blueprint.name or 'unknown')..'_type_'..tostring(d.type)
   end
  end
 end
 -- Snapshot keys are system IDs: duplicate artillery systems need per-instance IDs.
 if not localPlayer and ship.artillerySystems and ship.artillerySystems:size()>1 then return false,'multiple_artillery'end
 return true
end
local function enemy()return Hyperspace.ships.enemy end
-- Each game rolls an enemy's surrender and escape thresholds on its own, so one
-- captain could be offered a surrender the other never sees. A textless custom
-- event (see build_mod.py) zeroes both thresholds on this game's enemy.
local function lockOutcome()
 local ok,err=pcall(function()
  Hyperspace.CustomEventsParser.GetInstance():LoadEvent(Hyperspace.App.world,'FLEET_COOP_COMBAT_SYNC',false,-1)
 end)
 logc('OUTCOME_LOCK|'..(ok and 'OK' or 'FAILED')..'|box='..tostring(Hyperspace.App.gui.choiceBoxOpen)..(ok and '' or ('|'..tostring(err):gsub('[\r\n|]',' '))))
end
local function encounterReady()
 local a=Hyperspace.App;local g=a.gui;local e=enemy()
 -- choiceBox.bOpen precedes choiceBoxOpen during arrival in the supplied logs.
 if g.choiceBoxOpen or g.event_pause or g.menu_pause or (g.choiceBox and g.choiceBox.bOpen) then return false end
 if a.world.starMap and a.world.starMap.bOpen then return false end
 if not e or not e._targetable or not e._targetable.hostile then return false end
 local p=Hyperspace.ships.player
 return not e.bJumping and not (p and p.bJumping)
end
local function arm()
 local e=enemy();local p=Hyperspace.ships.player;local g=guard()
 if not e or not p or not g or e.bDestroyed or e.ship.hullIntegrity.first<=0 then fail('no_live_enemy');return end
 local playerOk,playerWhy=supported(p,true);local enemyOk,enemyWhy=supported(e)
 if not playerOk then fail('player_system_'..playerWhy);return end
 if not enemyOk then fail('enemy_system_'..enemyWhy);return end
 local w,why=weapons(p,true);local ew,enemyWhy=weapons(e,e:HasSystem(4))
 if not w or not ew then fail(why or ('enemy_'..tostring(enemyWhy)));return end
 local sig=geometry(e)
 if signature and signature~=sig then fail('enemy_changed');return end
 signature=sig
 send('ARM|'..string.format('%.0f',g)..'|'..sig..'|'..geometry(p)..'|'..w)
end
local function snapshot(kind,outcome)
 kind=kind or "SNAP"
 local e=enemy();if not e then return end
 snapId=snapId+1
 local hp=e.ship.hullIntegrity;local shield=e:GetShieldPower();local rows={}
 for i=0,e.vSystemList:size()-1 do local s=e.vSystemList[i]
  rows[#rows+1]=table.concat({s.iSystemType,s.healthState.first,s.healthState.second,s.powerState.first,math.max(0,s.iLockCount)},',')end
 local line=kind..'|'..epoch..'|'..snapId..'|'..(kind=='FINISH' and outcome~='crew' and 0 or math.max(0,hp.first))..'|'..hp.second..'|'..shield.first..'|'..shield.second..'|'..table.concat(rows,';')..'|'..tostring(shield.super and shield.super.first or 0)..'|'..tostring(shield.super and shield.super.second or 0)
 if kind=='FINISH' and boardingEncounter then
  local data=FleetNativeEffects.capture();if not data then fail('boarding_final_capture_failed');return nil end
  line=line..'|'..(outcome or 'hull')..'|'..data
 end
 send(line)
 if kind=='SNAP' and FleetNativeEffects and hp.first>0 then local data=FleetNativeEffects.capture();if data then send('EFFECT|'..epoch..'|'..snapId..'|'..data)end end
 return line
end
local function applySnapshot(p)
 local e=enemy();if not e or geometry(e)~=signature then fail('enemy_mismatch');return end
 local hp,maxhp=tonumber(p[5]),tonumber(p[6]);if not hp or not maxhp or hp<0 or hp>maxhp or maxhp~=e.ship.hullIntegrity.second then fail('invalid_state');return end
 local super=tonumber(p[10] or '0')
 if not super or super<0 or super>255 or super~=math.floor(super) then fail('invalid_super_shield');return end
 local superMax=tonumber(p[11] or p[10] or '0')
 if not superMax or superMax<super or superMax>255 or superMax~=math.floor(superMax) then fail('invalid_super_shield');return end
 local changes={}
 for row in p[9]:gmatch('[^;]+')do
  local a={};for x in row:gmatch('[^,]+')do a[#a+1]=tonumber(x)end
  local sys=e:GetSystem(a[1]);if not sys or #a~=5 or a[3]~=sys.healthState.second or a[2]<0 or a[2]>a[3] then fail('system_mismatch');return end
  changes[#changes+1]={s=sys,a=a}
 end
 e.ship.hullIntegrity.first=hp
 if e.shieldSystem then e.shieldSystem.shields.power.first=tonumber(p[7]);e.shieldSystem.shields.power.second=tonumber(p[8]);e.shieldSystem.shields.power.super.first=super;e.shieldSystem.shields.power.super.second=superMax end
 -- Each enemy AI owns its reactor allocation and individual weapon power flags.
 -- Copying powerState alone breaks that invariant: guest DepowerShip can loop
 -- forever in DecreasePower while attempting to depower an already-zero system.
 -- Host power remains in the wire snapshot for diagnostics, never assigned here.
 for _,v in ipairs(changes)do
  v.s.healthState.first=v.a[2]
  if v.s.iLockCount~=v.a[5] then v.s:LockSystem(v.a[5])end
 end
 -- Leave bDestroyed and the death animation to FTL's normal lifecycle.
 -- SetDestroyed here bypassed the guest's native combat-end transition.
 if hp==0 then status='Enemy hull zero; waiting for native post-combat event' end
end
-- Carry the fired projectile's damage: chain-ion boosts and flak debris differ
-- from the blueprint. IDs are assigned locally, never copied across games.
local damageNumbers={'iDamage','iShieldPiercing','fireChance','breachChance','stunChance','iIonDamage','iSystemDamage','iPersDamage','iStun'}
local damageBools={'bHullBuster','bLockdown','crystalShard','bFriendlyFire'}
local function encodeDamage(d)
 local a={};for _,k in ipairs(damageNumbers)do a[#a+1]=string.format('%d',d[k])end
 for _,k in ipairs(damageBools)do a[#a+1]=d[k] and '1' or '0'end
 return table.concat(a,',')
end
local function applyDamage(proj,s)
 local a={};for x in s:gmatch('[^,]+')do a[#a+1]=tonumber(x)end
 if #a~=13 then error('invalid_damage')end
 for i,k in ipairs(damageNumbers)do proj.damage[k]=a[i]end
 for i,k in ipairs(damageBools)do proj.damage[k]=a[i+9]==1 end
end
local function spawn(p)
 local bp=Hyperspace.Blueprints:GetWeaponBlueprint(p[5])
 if not bp or bp.type<0 or bp.type>4 then fail('unsupported_projectile');return nil end
 local own=tonumber(p[11]);local target=tonumber(p[12]) or (1-own)
 local kind=tonumber(p[13]) or bp.type
 if kind~=bp.type or (#p~=20 and bp.type>1)then fail('weapon_payload_mismatch');return nil end
 local dst=Hyperspace.ships[target==1 and 'enemy' or 'player']
 local tx,ty=tonumber(p[6]),tonumber(p[7])
 -- Flak scatter and beam endpoints can legitimately fall outside rooms.
 if not dst or not tx or not ty or tx< -2048 or tx>4096 or ty< -2048 or ty>4096 then fail('invalid_target');return nil end
 local pos=Hyperspace.Pointf(tonumber(p[8]),tonumber(p[9]));local aim=Hyperspace.Pointf(tx,ty)
 local heading=tonumber(p[10]);local origin=tonumber(p[20]) or own;local space=Hyperspace.App.world.space
 logc('SPAWN_BEGIN|'..bp.name..'|'..p[4])
 injected=true
 local ok,result=pcall(function()
  local q
  if bp.type==1 then q=space:CreateMissile(bp,pos,origin,own,aim,target,heading)
  elseif bp.type==2 then
   q=space:CreateBeam(bp,pos,origin,own,aim,Hyperspace.Pointf(tonumber(p[14]),tonumber(p[15])),target,tonumber(p[16]),heading)
  elseif bp.type==3 then q=space:CreateBomb(bp,own,aim,target)
  elseif bp.type==4 then
   local found=false
   for i=0,bp.miniProjectiles:size()-1 do local m=bp.miniProjectiles[i]
    if m.image==p[17] and m.fake==(p[18]=='1')then found=true;break end
   end
   if not found then error('unknown_flak_fragment')end
   q=space:CreateBurstProjectile(bp,p[17],p[18]=='1',pos,origin,own,aim,target,heading)
  else q=space:CreateLaserBlast(bp,pos,origin,own,aim,target,heading)end
  if q and #p==20 then applyDamage(q,p[19])end
  return q
 end)
 injected=false
 if not ok or not result then fail('spawn_failed');logc(tostring(result));return nil end
 logc('SPAWN_DONE|'..bp.name..'|'..p[4])
 return result
end
local function wireShot(proj,bp,kind,id)
 local aim=proj.target;local endx,endy,length=0,0,0
 local image='none';local fake=false
 if bp.type==2 then aim=proj.target1;endx=proj.target2.x;endy=proj.target2.y;length=math.floor((tonumber(proj.length) or bp.length)+0.5) end
 if bp.type==4 then image=proj.flight_animation.animName;fake=proj.damage.ownerId==-1 end
 -- Bombs may use INT_MIN as a sentinel source position: no flight origin is sent.
 local sx,sy=proj.position.x,proj.position.y
 if bp.type==3 then sx=0;sy=0 end
 return table.concat({kind,epoch,id,bp.name,string.format('%.2f',aim.x),string.format('%.2f',aim.y),string.format('%.2f',sx),string.format('%.2f',sy),string.format('%.2f',proj.heading),string.format('%d',proj.ownerId),string.format('%d',proj.targetId),string.format('%d',bp.type),string.format('%.2f',endx),string.format('%.2f',endy),string.format('%d',length),image,fake and 1 or 0,encodeDamage(proj.damage),string.format('%d',proj.currentSpace)},'|')
end
local function receive(line)
 local p=fields(line)
 if p[2]=='POST_RELEASE' then
  if post and post.ready and p[3]==post.epoch and p[4]==post.seq then
   post=nil;status='Both ships finished combat. Fleet jump ready.';logc('POST_COMBAT_RELEASED|'..p[3])
  end
  return
 end
 if p[2]=='FINISH' then
  if p[3]==completedEpoch and p[4]==completedSeq then send('FINISH_ACK|'..p[3]..'|'..p[4]);return end
  if not enabled or stopped or role~='G' or p[3]~=epoch or (tonumber(p[5])~=0 and p[12]~='crew') then return end
  if boardingEncounter then
   if not p[13] or not FleetNativeEffects.apply(p[13]) then fail('boarding_final_state_invalid');return end
  end
  applySnapshot(p)
  if stopped then return end
  completedEpoch=p[3];completedSeq=p[4]
  reset(true);autoAttempt=guard();post={epoch=p[3],seq=p[4],clear=0,wait=0,guard=autoAttempt,sawEvent=Hyperspace.App.gui.choiceBoxOpen==true};status='Finish the post-combat event on both ships.'
  send('FINISH_ACK|'..p[3]..'|'..p[4]);logc('COMPLETED_GUEST|'..p[3]);return
 end
 if p[2]=='FINISH_ACK' then
  if finishing and role=='H' and p[3]==epoch and tonumber(p[4])==snapId then
   local saw=finishing.sawEvent or Hyperspace.App.gui.choiceBoxOpen==true
   reset(true);autoAttempt=guard();post={epoch=p[3],seq=p[4],clear=0,wait=0,guard=autoAttempt,sawEvent=saw};status='Finish the post-combat event on both ships.';logc('COMPLETED_HOST|'..p[3])
  end
  return
 end
 if p[2]=='STOP' then
  if p[3]=='encounter_finished' and (not enemy() or enemy().bDestroyed or enemy().ship.hullIntegrity.first<=0)then reset()
  elseif enabled then fail(p[3])
  elseif p[3]=='manual_split' and not independent and guard() then separate('manual_split','PEER')end;return end
 if not enabled or stopped then return end
 if p[2]=='WAIT' then pause();status='Waiting: '..tostring(p[3]);return end
 if p[2]=='START' then
  if tonumber(p[4])~=guard() or not signature or (p[5]~='H' and p[5]~='G')then logc('START_REJECTED|received_guard='..tostring(p[4])..'|local_guard='..tostring(guard())..'|signature='..tostring(signature));return end
  if epoch and epoch~=p[3]then fail('session_changed');return end
  lastServer=ticks;heartbeatCount=heartbeatCount+1
  if heartbeatCount==1 or heartbeatCount%20==0 then logc('HEARTBEAT|'..heartbeatCount)end
  if epoch then return end
  independent=nil -- both captains re-armed (F6): shared combat resumes from the host state
  epoch=p[3];role=p[5];shotId=0;spawnId=0;snapId=0;remoteSnap=0;remoteEffects=0;remoteSpawn=0;lastSnap=ticks
  boardingEncounter=enemy():HasSystem(9)
  if boardingEncounter then
   if not boarding or not boarding.begin()then fail('boarding_roster_unavailable');return end
   logc('BOARDING_TARGET|HOST_ONLY|'..role)
  end
  lockOutcome()
  native.setReplica(role=='G');pause();status='SHARED ENEMY '..(role=='H' and 'HOST' or 'GUEST')..' | both resume to test'
  if enemy():HasSystem(4)then
   local ds=enemy():GetDroneList();for i=0,ds:size()-1 do logc('ENEMY_DRONE_LOCAL|'..role..'|'..tostring(ds[i].blueprint and ds[i].blueprint.name)..'|type='..tostring(ds[i].type))end
  end
  if enemy():HasSystem(15)then logc('ENEMY_HACKING_LOCAL|'..role)end
  if boardingEncounter then status='Shared enemy | Boarding parties target HOST only' end
  logc('ACTIVE|'..role..'|'..epoch);return
 end
 if not epoch or p[3]~=epoch then return end
 if p[2]=='HOLD' then for _,shot in pairs(pending)do shot.first=ticks end;networkHold=true;lastServer=ticks;lastSnap=ticks;pause();status='Fleet link delayed - combat held; waiting for fresh reports';return end
 if p[2]=='SYNC' then networkHold=false;lastServer=ticks;lastSnap=ticks;status='Fleet link restored - both press Space when ready';if role=='H' then snapshot()end;return end
 -- Valid traffic for this encounter also proves the relay is alive.
 if p[2]=='SNAP' or p[2]=='ACK' or p[2]=='SHOT' or p[2]=='SPAWN' or p[2]=='EFFECT' then lastServer=ticks end
 if p[2]=='SHOT' and role=='H' then
  local id=tonumber(p[4]);if not id then return end
  if not seen[id]then
   local proj=spawn(p);if not proj then return end
   seen[id]=true;spawnId=spawnId+1
   local q={};for i,v in ipairs(p)do q[i]=v end;q[2]='SPAWN';q[4]=tostring(spawnId)
   send(table.concat(q,'|',2));logc('REMOTE_SHOT_APPLIED|'..id)
  end
  send('ACK|'..epoch..'|'..id)
 elseif p[2]=='ACK' and role=='G' then pending[tonumber(p[4])]=nil
 elseif p[2]=='SPAWN' and role=='G' then
  local seq=tonumber(p[4]);if seq and seq>remoteSpawn then
   remoteSpawn=seq
   if tonumber(p[11])==0 then spawn(p)end -- enemy fires locally, never replay an enemy beam
  end
 elseif p[2]=='EFFECT' and role=='G' then
  local seq=tonumber(p[4]);if seq and seq>remoteEffects then
   if not FleetNativeEffects or not FleetNativeEffects.apply(p[5]) then fail('enemy_effects_mismatch');return end
   remoteEffects=seq
  end
 elseif p[2]=='SNAP' and role=='G' then
  local seq=tonumber(p[4]);if seq and seq>remoteSnap then remoteSnap=seq;lastSnap=ticks;latest=p;applySnapshot(p)end
 end
end
function M.receive(line)local ok,err=pcall(receive,line);if not ok then fail('receive_error');logc(tostring(err))end end
local function tick()
 ticks=ticks+1
 if not Hyperspace.App.world.bStartedGame or Hyperspace.App.menu.bOpen then independent=nil;if enabled then reset()end;return end
 if independent and guard()~=independent.guard then independent=nil;if not enabled and not post then status=idle end;logc('SEPARATE_FIGHT_ENDED')end
 -- v0.28.16: the reward barrier belongs to one beacon. A sector-exit jump is not
 -- gated by the fleet jump vote, so both ships could leave before POST_RELEASE
 -- arrived; the barrier then blocked every later jump. Drop it once we have left.
 if post and guard()~=post.guard then logc('POST_ABANDONED|'..post.epoch..'|left_beacon');post=nil;status=idle end
 if post then
  local g=Hyperspace.App.gui
  -- Some outcomes show no reward screen. Do not wait for one forever.
  if not post.sawEvent and not g.bPaused then
   post.wait=post.wait+1
   if post.wait>=900 then post.sawEvent=true;logc('POST_EVENT_ASSUMED|'..post.epoch)end
  end
  -- FTL owns each ship's native rewards. Never add/copy resources here.
  -- Allow destruction/reward simulation to advance; require a quiet interval
  -- after event screens close before declaring this captain ready to travel.
  if g.choiceBoxOpen and not post.sawEvent then post.sawEvent=true;logc('POST_EVENT_SEEN|'..post.epoch)end
  if not post.sawEvent then status='Waiting for local reward event; fleet jump blocked';return end
  if g.choiceBoxOpen or g.event_pause or g.menu_pause or g.bPaused or Hyperspace.App.world.starMap.bOpen then post.clear=0
  else post.clear=post.clear+1 end
  if boarding and boarding.boarders()>0 then post.clear=0;status='Defeat remaining boarders on the host ship; fleet jump blocked';return end
  if post.clear>=60 and ticks%30==0 then post.ready=true;send('POST_READY|'..post.epoch..'|'..post.seq)end
  return
 end
 if not enabled then
  local current=guard()
  if current~=stableGuard or not encounterReady() then clearTicks=0;stableGuard=current else clearTicks=clearTicks+1 end
  local e=enemy();local g=guard();local gui=Hyperspace.App.gui
  if e and not e.bDestroyed and e.ship.hullIntegrity.first>0 and g and autoAttempt~=g and
     clearTicks>=15 and encounterReady() and native and native.version==4 and FleetFastLink and FleetFastLink.ready()then
   autoAttempt=g;enabled=true;setupStarted=ticks;pause();status='Synchronizing fleet combat automatically';logc('AUTO_ARMED');arm()
  end
  if not enabled then return end
 end
 if stopped then pause();return end
 if finishing then
  if Hyperspace.App.gui.choiceBoxOpen then finishing.sawEvent=true end
  if ticks-finishing.first>600 then fail('completion_unconfirmed');finishing=nil;return end
  if ticks-finishing.last>=30 then send(finishing.line);finishing.last=ticks end
  return
 end
 if epoch and enemy() and enemy().bJumping then fail('enemy_escape_not_synchronized');return end
 local crewDefeat=boardingEncounter and role=='H' and boarding.defeated() and enemy() and enemy().ship.hullIntegrity.first>0
 if epoch and enemy() and (enemy().bDestroyed or enemy().ship.hullIntegrity.first<=0 or crewDefeat)then
  if role=='H' then
   local terminal=snapshot('FINISH',crewDefeat and 'crew' or 'hull')
   if not terminal then return end
   finishing={line=terminal,first=ticks,last=ticks,sawEvent=Hyperspace.App.gui.choiceBoxOpen==true};status='Confirming shared enemy destruction';logc('FINISH_SENT|'..epoch)
  else status='Waiting for host combat completion' end
  return
 end
 if stopped then pause();return end
 if networkHold then pause()end
 if not FleetFastLink or not FleetFastLink.ready() then fail('native_link_unavailable');return end
 if epoch and ticks-lastServer>180 then logc('TIMEOUT_DIAG|server_age='..(ticks-lastServer)..'|snap_age='..(ticks-lastSnap)..'|heartbeats='..heartbeatCount);fail('peer_timeout');return end
 if epoch and role=='G' and ticks-lastSnap>180 then fail('state_timeout');return end
 if not epoch and ticks-setupStarted>900 then fail('setup_timeout_check_both_mods');return end
 if ticks%30==0 then arm()end
 if not enabled then return end
 if not epoch then pause();return end
 if role=='H' and ticks%6==0 then snapshot()end
 for _,p in pairs(pending)do
  if ticks-p.first>180 then fail('shot_unconfirmed');return end
  if ticks-p.last>=30 then send(p.line);p.last=ticks end
 end
end
function M.tick()local ok,err=pcall(tick);if not ok and enabled then fail('tick_error');logc(tostring(err))end end
function M.pauseBlock()if finishing then return 'setup' end;if networkHold then return 'link' end;if stopped then return 'combat' end;if enabled and not epoch then return 'setup' end;return nil end
function M.rewardPending()
 return post~=nil and not stopped and Hyperspace.App.world.bStartedGame and not Hyperspace.App.menu.bOpen
end
function M.canJump()return not enabled and not stopped and not post end
function M.status()return status end
function M.isActive()return enabled and epoch~=nil and not stopped and not finishing and not post end
function M.separate()return independent~=nil end
function M.notice()return independent~=nil or post~=nil or enabled or stopped or status:sub(1,18)=='Combat unavailable' or status:sub(1,12)=='Combat setup' end
script.on_internal_event(Defines.InternalEvents.ON_KEY_DOWN,function(key)
 if key~=Defines.SDL.KEY_F6 then return C.CONTINUE end
 -- Escape hatch: F6 while an event screen is open splits this beacon, so a
 -- screen the partner never received can no longer lock both games.
 if Hyperspace.App.gui.choiceBoxOpen and not independent and guard() then
  if enabled then fail('manual_split') else send('STOP|manual_split');separate('manual_split','MANUAL')end
  return C.PREEMPT
 end
 if stopped then pause();return C.PREEMPT end
 if enabled then
  if not epoch then
   pause();status='Co-op setup blocked; return to menu to reset';logc('SETUP_HELD')
  else pause()end
  return C.PREEMPT
 end
 if not native or native.version~=4 then status='Custom co-op DLL required for combat';logc(status);return C.PREEMPT end
 if not guard() or not FleetFastLink or not FleetFastLink.ready() then status='Connect both games before F6';return C.PREEMPT end
 if not encounterReady() then status='Finish the event and choose a hostile encounter first';return C.PREEMPT end
 enabled=true;autoAttempt=guard();setupStarted=ticks;pause();status='Co-op setup requested; waiting for partner. F6 holds setup.';logc('ARMED');return C.PREEMPT
end,400)
script.on_internal_event(Defines.InternalEvents.PROJECTILE_FIRE,function(proj,weapon)
 if not enabled or injected then return end
 local ok,err=pcall(function()
  if finishing then return end
  if stopped or not epoch then proj:Kill();pause();return end
  -- Self-targeted friendly bombs stay on that captain's own ship.
  if proj.ownerId==0 and proj.targetId==0 then return end
  if proj.ownerId==1 then logc('LOCAL_ENEMY_FIRE|'..role..'|'..weapon.blueprint.name);return end -- independent local targeting
  if role=='G' then
   shotId=shotId+1;local line=wireShot(proj,weapon.blueprint,'SHOT',shotId)
   pending[shotId]={line=line,first=ticks,last=ticks};proj:Kill();send(line)
  else
   spawnId=spawnId+1;send(wireShot(proj,weapon.blueprint,'SPAWN',spawnId))
  end
 end)
 if not ok then proj:Kill();fail('fire_error');logc(tostring(err))end
end)
-- DRONE_FIRE is a chain event: PREEMPT makes Hyperspace delete the not-yet-
-- inserted projectile. Never Kill/delete it ourselves or retain its userdata.
-- Enemy drones and friendly defensive/local support drones keep native behavior.
script.on_internal_event(Defines.InternalEvents.DRONE_FIRE,function(proj,drone)
 if not enabled or injected or proj.ownerId~=0 or drone.type~=1 then return C.CONTINUE end
 if stopped or not epoch or finishing then return C.PREEMPT end
 local ok,result=pcall(function()
  if proj.targetId~=1 then error('drone_target_not_enemy')end
  local bp=drone.weaponBlueprint
  if not bp or bp.type<0 or bp.type>4 then error('unsupported_drone_weapon')end
  if role=='G' then
   shotId=shotId+1;local line=wireShot(proj,bp,'SHOT',shotId)
   pending[shotId]={line=line,first=ticks,last=ticks};send(line)
   if shotId<=8 or shotId%100==0 then logc('FRIENDLY_DRONE_SHOT|G|'..bp.name..'|'..shotId)end
   return C.PREEMPT
  end
  spawnId=spawnId+1;send(wireShot(proj,bp,'SPAWN',spawnId))
  if spawnId<=8 or spawnId%100==0 then logc('FRIENDLY_DRONE_SHOT|H|'..bp.name..'|'..spawnId)end
  return C.CONTINUE
 end)
 if not ok then fail('drone_fire_error');logc(tostring(result));return C.PREEMPT end
 return result
end)
-- Replica enemy collisions may animate, but never roll a second enemy damage outcome.
script.on_internal_event(Defines.InternalEvents.DAMAGE_AREA,function(ship,proj,pos,dmg,force,friendly)
 if enabled and role=='G' and ship.iShipId==1 then return C.PREEMPT,force,friendly end
 return C.CONTINUE,force,friendly
end,1000)
script.on_internal_event(Defines.InternalEvents.DAMAGE_BEAM,function(ship,proj,pos,dmg,newTile,hitType)
 if enabled and role=='G' and ship.iShipId==1 then return C.PREEMPT,hitType end
 return C.CONTINUE,hitType
end,1000)
script.on_internal_event(Defines.InternalEvents.SHIELD_COLLISION_PRE,function(ship,proj,dmg,response)
 if enabled and role=='G' and ship.iShipId==1 then
  -- Visual projectile consumed at the replica shield; shield count comes from host.
  if proj and proj:GetType()~=5 then proj:Kill()end
  return C.PREEMPT
 end
 return C.CONTINUE
end,1000)
script.on_internal_event(Defines.InternalEvents.JUMP_LEAVE,function(ship)
 if enabled and ship.iShipId==0 then
  local e=enemy();if not e or e.bDestroyed or e.ship.hullIntegrity.first<=0 then reset()else fail('jump_during_combat_test')end
 end
end)
script.on_init(function(newGame)independent=nil;reset()end)
script.on_load(function()logc('LOADED|'..(native and 'NATIVE' or 'NATIVE_MISSING'))end)
script.on_internal_event(Defines.InternalEvents.MAIN_MENU,function()reset()end)
