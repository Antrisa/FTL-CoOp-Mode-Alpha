import unittest
import test_combat
from combat import parse
class ShieldHackingTests(unittest.TestCase):
 def test_super_shield_depletion_and_stale_snapshot(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
  l.execute('Hyperspace.ships.enemy.shieldSystem={shields={power={first=1,second=2,super={first=5,second=5}}}}')
  for seq,ss in [(1,3),(2,0),(1,5)]:
   l.globals().FleetCombat22.receive(f'COMBAT|SNAP|testepoch|{seq}|30|30|1|2||{ss}|5')
  self.assertEqual(l.globals().Hyperspace.ships.enemy.shieldSystem.shields.power.super.first,0)
  self.assertEqual(l.globals().Hyperspace.ships.enemy.shieldSystem.shields.power.first,1)
 def test_host_serializes_and_relay_forwards_super_shield(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'H')
  l.execute('Hyperspace.ships.enemy.GetShieldPower=function()return {first=1,second=2,super={first=4,second=5}}end;for i=1,6 do FleetCombat22.tick()end')
  line=next(s for s in l.globals().sent.values() if '|SNAP|' in s)
  self.assertEqual(parse(line)[9:11],['4','5'])
  r=test_combat.ProtocolTests();r.setUp();epoch=r.start();line=line.replace('testepoch',epoch);r.out=[]
  r.receive(1,line);self.assertEqual(r.out,[(2,line)])
 def test_invalid_super_shields_rejected(self):
  for ss in ('-1','256','1.5','nan'):
   with self.assertRaises(ValueError):parse('COMBAT|SNAP|e|1|30|30|1|2||'+ss)
 def test_enemy_hack_allowed_and_player_hack_still_blocked(self):
  for who in ('enemy','player'):
   l=test_combat.LuaCombatTests().lua()
   l.execute(f"Hyperspace.ships.{who}.HasSystem=function(self,id)return id==15 end;Hyperspace.ships.{who}.hackingSystem={{currentSystem='local-target',effectTimer=7}};for i=1,16 do FleetCombat22.tick()end")
   armed=any('|ARM|' in s for s in l.globals().sent.values())
   self.assertEqual(armed,who=='enemy')
   if who=='enemy':
    l.globals().FleetCombat22.receive('COMBAT|START|testepoch|42|G')
    l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|1|25|30|0|0||0')
    self.assertEqual(l.globals().Hyperspace.ships.enemy.hackingSystem.currentSystem,'local-target')
    self.assertEqual(l.globals().Hyperspace.ships.enemy.hackingSystem.effectTimer,7)
 def test_native_pair_cannot_be_replaced_and_finish_roundtrip(self):
  h=test_combat.LuaCombatTests();host=h.lua();h.start(host,'H')
  host.execute('Hyperspace.ships.enemy.GetShieldPower=function()return {first=1,second=2,super={first=3,second=5}}end;for i=1,6 do FleetCombat22.tick()end')
  line=next(s for s in host.globals().sent.values() if '|SNAP|' in s)
  guest=h.lua();h.start(guest,'G')
  guest.execute('''nativeSuper={first=5,second=5};Hyperspace.ships.enemy.shieldSystem={shields={power=setmetatable({first=1,second=2},{__index=function(_,k)if k=='super' then return nativeSuper end end,__newindex=function(_,k,v)error('Cannot replace native shield field '..k)end})}}''')
  guest.globals().FleetCombat22.receive(line)
  self.assertEqual(guest.globals().nativeSuper.first,3)
  self.assertEqual(guest.globals().nativeSuper.second,5)
  terminal=line.replace('|SNAP|','|FINISH|').split('|');terminal[3]='2';terminal[4]='0';terminal[9]='0'
  terminal='|'.join(terminal);parse(terminal)
  guest.globals().FleetCombat22.receive(terminal)
  self.assertEqual(guest.globals().nativeSuper.first,0)
  self.assertEqual(guest.globals().nativeSuper.second,5)
 def test_bad_capacity_rejected_before_mutation(self):
  for maximum in ('2','-1','256','nan','4.5'):
   line='COMBAT|SNAP|testepoch|1|20|30|0|0||3|'+maximum
   with self.assertRaises(ValueError):parse(line)
   h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
   l.globals().FleetCombat22.receive(line)
   self.assertEqual(l.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,30)
