import unittest
import test_combat, test_weapons
from combat import CombatRoom, parse

class FriendlyDroneTests(unittest.TestCase):
 def loadout(self,kind=1,no_guns=False):
  l=test_combat.LuaCombatTests().lua()
  l.globals().dtype=kind;l.globals().no_guns=no_guns
  l.execute('''dronebp={name='DRONE_LASER',type=0}
  Hyperspace.Blueprints.GetWeaponBlueprint=function(self,name)if name=='DRONE_LASER'then return dronebp else return bp end end
  drone={type=dtype,blueprint={name='DRONE_BLUEPRINT',weaponBlueprint='DRONE_LASER'}}
  Hyperspace.ships.player.HasSystem=function(self,id)return id==4 end
  Hyperspace.ships.player.GetDroneList=function()return vec({[0]=drone},1)end
  if no_guns then Hyperspace.ships.player.GetWeaponList=function()return vec({},0)end end
  ''')
  return l
 def arm(self,l):
  l.execute('for i=1,30 do FleetCombat22.tick()end')
  return [x for x in l.globals().sent.values() if '|ARM|' in x]
 def test_combat_and_local_support_drone_loadouts_arm(self):
  for kind in (0,1,2,3,5,7):
   l=self.loadout(kind);arms=self.arm(l);self.assertTrue(arms)
   payload=parse(arms[-1])[5].split(',')
   self.assertEqual('DRONE_LASER' in payload,kind==1)
 def test_drone_only_and_unarmed_support_ship_can_join(self):
  for kind in (0,1,2,3,5,7):
   l=self.loadout(kind,True);arms=self.arm(l);self.assertTrue(arms)
   self.assertEqual(parse(arms[-1])[5],'DRONE_LASER' if kind==1 else '')
 def test_boarding_unknown_and_missing_drone_weapon_stay_blocked(self):
  for kind in (4,6,99):self.assertEqual(self.arm(self.loadout(kind)),[])
  l=self.loadout();l.execute("drone.blueprint.weaponBlueprint='' ")
  self.assertEqual(self.arm(l),[])
  self.assertIn('drone_weapon_missing',l.globals().FleetCombat22.status())
 def fire(self,kind=0,role='G'):
  l=test_weapons.WeaponTests().setup_lua(kind,role)
  l.execute('sent={};p=projectile();p.currentSpace=1;p.length=46;result=callbacks.drone_fire(p,{type=1,weaponBlueprint=bp})')
  return l
 def test_guest_laser_and_beam_preempt_native_and_host_applies_once(self):
  for kind in (0,2):
   g=self.fire(kind);self.assertEqual(g.globals().result,1)
   self.assertIsNone(g.globals().p.killed) # PREEMPT transfers deletion to Hyperspace
   line=next(x for x in g.globals().sent.values() if '|SHOT|' in x)
   self.assertEqual(parse(line)[19],'1') # enemy-space origin, not partner ship geometry
   h=test_weapons.WeaponTests().setup_lua(kind,'H')
   for _ in range(3):h.globals().FleetCombat22.receive(line)
   self.assertEqual(h.globals().spawned,1)
   if kind==2:self.assertEqual(h.globals().calls[1].args[8],46)
   self.assertIn('COMBAT|ACK|testepoch|1',list(h.globals().sent.values()))
 def test_host_retains_native_drone_and_forwards_visual(self):
  h=self.fire(role='H');self.assertEqual(h.globals().result,0)
  self.assertIsNone(h.globals().p.killed)
  line=next(x for x in h.globals().sent.values() if '|SPAWN|' in x)
  g=test_weapons.WeaponTests().setup_lua(0)
  for _ in range(3):g.globals().FleetCombat22.receive(line)
  self.assertEqual(g.globals().spawned,1)
  self.assertEqual(g.eval('callbacks.damage(Hyperspace.ships.enemy,nil,nil,nil,0,true)')[0],1)
 def test_weapons_and_drones_share_unique_shot_ids(self):
  for role,kind in [('G','SHOT'),('H','SPAWN')]:
   l=self.fire(role=role)
   l.execute('callbacks.fire(projectile(),{blueprint=bp});callbacks.drone_fire(projectile(),{type=1,weaponBlueprint=bp})')
   lines=[x for x in l.globals().sent.values() if '|'+kind+'|' in x]
   self.assertEqual([parse(x)[3] for x in lines],['1','2','3'])
 def test_enemy_and_friendly_defense_fire_are_local(self):
  l=self.fire();l.execute('sent={} ')
  for owner,kind in [(1,1),(1,0),(0,0),(0,5),(0,7)]:
   l.globals().owner=owner;l.globals().kind=kind
   l.execute('p=projectile();p.ownerId=owner;result=callbacks.drone_fire(p,{type=kind})')
   self.assertEqual(l.globals().result,0);self.assertIsNone(l.globals().p.killed)
  self.assertEqual(len(l.globals().sent),0)
 def test_bad_drone_callback_blocks_once_without_killing_userdata(self):
  l=test_weapons.WeaponTests().setup_lua(0,'G');l.execute('sent={};p=projectile();result=callbacks.drone_fire(p,{type=1})')
  self.assertEqual(l.globals().result,1);self.assertIsNone(l.globals().p.killed)
  self.assertIn('drone_fire_error',l.globals().FleetCombat22.status())
  l.execute('for i=1,20 do callbacks.drone_fire(p,{type=1})end')
  self.assertEqual(sum('|STOP|' in x for x in l.globals().sent.values()),1)
 def test_mixed_gun_ship_and_drone_ship_authorize_only_their_own_weapons(self):
  g=self.loadout(no_guns=True);g.execute("Hyperspace.ships.player.myBlueprint.blueprintName='PLAYER_SHIP_CIRCLE';Hyperspace.ships.player.ship.hullIntegrity.second=40")
  h=test_combat.LuaCombatTests().lua()
  arms=[self.arm(h)[-1],self.arm(g)[-1]]
  self.assertNotEqual(parse(arms[0])[4],parse(arms[1])[4])
  r=CombatRoom();out=[];send=lambda c,s:out.append((c,s));members={1:None,2:None};guards={1:42,2:42}
  for cid,line in enumerate(arms,1):r.receive(cid,line,1,members,guards,send,10)
  self.assertIsNotNone(r.active);e=r.active['epoch'];out.clear()
  line=f'COMBAT|SHOT|{e}|1|DRONE_LASER|35|35|10|10|90|0'
  r.receive(2,line,1,members,guards,send,10);self.assertEqual(out,[(1,line)])
  out.clear();r.receive(2,line.replace('DRONE_LASER','LASER_BURST_2').replace('|1|LASER','|2|LASER'),1,members,guards,send,10)
  self.assertEqual(out,[])
 def test_setup_failure_reaches_waiting_captain_and_lua_does_not_spam(self):
  r=CombatRoom();out=[];send=lambda c,s:out.append((c,s));members={1:None,2:None};guards={1:42,2:42}
  r.receive(1,'COMBAT|ARM|42|enemy|player|LASER',1,members,guards,send,10)
  r.receive(2,'COMBAT|STOP|player_system_teleporter',1,members,guards,send,10)
  self.assertEqual(out,[(1,'COMBAT|STOP|player_system_teleporter')]);self.assertEqual(r.arms,{})
  l=self.loadout(4);self.arm(l)
  l.execute("for i=1,25 do FleetCombat22.receive('COMBAT|STOP|bridge_disabled')end")
  self.assertEqual(sum('|STOP|' in x for x in l.globals().sent.values()),1)
 def test_loadout_bound_expanded_for_drone_and_artillery_blueprints(self):
  parse('COMBAT|ARM|42|enemy|player|'+','.join('WEAPON_'+str(i) for i in range(16)))
  with self.assertRaises(ValueError):parse('COMBAT|ARM|42|enemy|player|'+','.join('WEAPON_'+str(i) for i in range(17)))
 def test_mixed_ship_snapshot_never_copies_partner_inventory_or_local_drone_state(self):
  l=test_weapons.WeaponTests().setup_lua(0,'G')
  l.execute('Hyperspace.ships.player.scrap_count=37;Hyperspace.ships.player.drone_count=4;Hyperspace.ships.player.hull_repairs=2;Hyperspace.ships.player.shieldSystem={shields={power={super={first=5,second=5}}}}')
  l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|1|12|30|0|0|')
  self.assertEqual(l.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,12)
  self.assertEqual(l.globals().Hyperspace.ships.player.scrap_count,37)
  self.assertEqual(l.globals().Hyperspace.ships.player.drone_count,4)
  self.assertEqual(l.globals().Hyperspace.ships.player.shieldSystem.shields.power.super.first,5)
 def test_new_utility_rejects_old_game_build(self):
  import json,time
  from fleet_link import Room
  from ship_view import guard
  class Peer:
   def __init__(self):self.messages=[]
   def send(self,s):self.messages.append(json.loads(s))
  r=Room();a,b=Peer(),Peer();r.members={1:(a,'a'),2:(b,'b')};r.host_id=1
  ship=dict(id=1,hull=30,maximum=30,seed=1,level=0,x=1,y=2,seen=time.time())
  r.ships={1:ship,2:dict(ship)};r.game_build(1,2816);r.game_build(2,288)
  r.combat_line(1,f'COMBAT|ARM|{guard(ship)}|enemy|player|LASER')
  self.assertIsNone(r.combat.active)
  self.assertIn('both_need_mod_v0.28.16',a.messages[-1]['line'])
