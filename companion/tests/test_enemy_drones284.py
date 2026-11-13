import unittest
import test_combat
class EnemyDroneTests(unittest.TestCase):
 def game(self,kind):
  l=test_combat.LuaCombatTests().lua()
  l.execute("Hyperspace.ships.enemy.HasSystem=function(self,id)return id==4 end;drone={type="+str(kind)+",blueprint={name='TEST_DRONE'}};Hyperspace.ships.enemy.GetDroneList=function()return vec({[0]=drone},1)end")
  return l
 def test_defense_laser_and_beam_combat_types_can_arm(self):
  for kind in (0,1):
   l=self.game(kind);l.execute('for i=1,16 do FleetCombat22.tick()end')
   self.assertTrue(any('|ARM|' in s for s in l.globals().sent.values()))
   l.globals().FleetCombat22.receive('COMBAT|START|testepoch|42|G')
   self.assertTrue(l.globals().replica)
 def test_drone_only_enemy_can_arm(self):
  l=self.game(1);l.execute('Hyperspace.ships.enemy.GetWeaponList=function()return vec({},0)end;for i=1,16 do FleetCombat22.tick()end')
  self.assertTrue(any('|ARM|' in s for s in l.globals().sent.values()))
 def test_crew_boarding_and_shield_drone_types_remain_blocked(self):
  for kind in (2,3,4,5,6,7,99):
   l=self.game(kind);l.execute('for i=1,16 do FleetCombat22.tick()end')
   self.assertEqual(l.globals().FleetCombat22.pauseBlock(),'combat')
   self.assertFalse(l.globals().FleetCombat22.canJump())
 def test_enemy_fire_stays_local_and_friendly_damage_is_not_suppressed(self):
  for role in ('H','G'):
   l=self.game(1);l.execute('for i=1,16 do FleetCombat22.tick()end')
   l.globals().FleetCombat22.receive('COMBAT|START|testepoch|42|'+role)
   l.execute("sent={};callbacks.fire({ownerId=1},{blueprint={name='DRONE_LASER'}})")
   self.assertFalse(any('|SHOT|' in s or '|SPAWN|' in s for s in l.globals().sent.values()))
   self.assertEqual(l.eval('callbacks.damage(Hyperspace.ships.player,nil,nil,nil,0,true)')[0],0)
