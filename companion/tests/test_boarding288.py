import unittest
from pathlib import Path
import test_combat
from combat import parse
from enemy_effects import validate

ALIVE='E28 1 0 1 C 0 human 0 0 100 100 -1 0 0 END'
DEAD='E28 1 0 1 C 0 human 0 0 0 100 -1 1 0 END'
class BoardingTests(unittest.TestCase):
 def game(self,role):
  h=test_combat.LuaCombatTests();l=h.lua()
  l.execute('''boarderCount=0;crewDefeated=false;begins=0;clears=0;effectsApplied=0
  FleetNativeBoarding={version=1,begin=function()begins=begins+1;return true end,clear=function()clears=clears+1 end,boarders=function()return boarderCount end,defeated=function()return crewDefeated end}
  FleetNativeEffects={version=2,capture=function()return effectPayload end,apply=function(s)effectsApplied=effectsApplied+1;lastEffect=s;return true end}
  Hyperspace.ships.enemy.HasSystem=function(self,id)return id==9 end
  ''')
  l.globals().effectPayload=ALIVE
  l.execute(Path('combat.lua').read_text());h.start(l,role);return l
 def test_teleporter_requires_new_native_api(self):
  h=test_combat.LuaCombatTests();l=h.lua()
  l.execute('Hyperspace.ships.enemy.HasSystem=function(self,id)return id==9 end')
  h.start(l,'H');self.assertIn('teleporter_requires_v0288_DLL',l.globals().FleetCombat22.status())
 def test_one_roster_per_encounter_not_per_heartbeat(self):
  l=self.game('H');self.assertEqual(l.globals().begins,1)
  l.globals().FleetCombat22.receive('COMBAT|START|testepoch|42|H')
  self.assertEqual(l.globals().begins,1)
  self.assertTrue(any('BOARDING_TARGET|HOST_ONLY|H' in x for x in l.globals().logs.values()))
 def test_finish_embeds_final_crew_state_and_preserves_hull_for_crew_victory(self):
  l=self.game('H');l.globals().effectPayload=DEAD
  l.execute('crewDefeated=true;Hyperspace.ships.enemy.ship.hullIntegrity.first=17;FleetCombat22.tick()')
  line=next(x for x in l.globals().sent.values() if '|FINISH|' in x)
  p=parse(line);self.assertEqual(p[4],'17');self.assertEqual(p[11],'crew');self.assertEqual(p[12],DEAD)
  guest=self.game('G');guest.globals().FleetCombat22.receive(line)
  self.assertEqual(guest.globals().effectsApplied,1)
  self.assertEqual(guest.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,17)
  guest.globals().FleetCombat22.receive(line);self.assertEqual(guest.globals().effectsApplied,1)
 def test_hull_finish_has_roster_and_zero_hull(self):
  l=self.game('H');l.execute('Hyperspace.ships.enemy.ship.hullIntegrity.first=0;FleetCombat22.tick()')
  line=next(x for x in l.globals().sent.values() if '|FINISH|' in x)
  self.assertEqual(parse(line)[11:13],['hull',ALIVE])
 def test_missing_final_roster_keeps_combat_held(self):
  l=self.game('G');l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0||0|0')
  self.assertIn('boarding_final_state_invalid',l.globals().FleetCombat22.status())
  self.assertFalse(any('FINISH_ACK' in x for x in l.globals().sent.values()))
 def test_remaining_boarders_block_post_ready_and_jump(self):
  l=self.game('G');l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0||0|0|hull|'+ALIVE)
  l.execute('boarderCount=2;Hyperspace.App.gui.choiceBoxOpen=true;FleetCombat22.tick();Hyperspace.App.gui.choiceBoxOpen=false;Hyperspace.App.gui.bPaused=false;for i=1,120 do FleetCombat22.tick()end')
  self.assertFalse(any('POST_READY' in x for x in l.globals().sent.values()))
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.execute('boarderCount=0;for i=1,90 do FleetCombat22.tick()end')
  self.assertTrue(any('POST_READY' in x for x in l.globals().sent.values()))
 def test_roomless_boarders_allowed_but_bad_locations_rejected(self):
  for loc in ('-1','0'):
   validate(ALIVE.replace('-1 0 0 END','-1 0 '+loc+' END'))
  for data in (ALIVE.replace('-1 0 0 END','-1 0 1 END'),ALIVE.replace('-1 0 0 END','0 0 0 END'),ALIVE.replace('-1 0 0 END','-1 0 2 END')):
   with self.assertRaises(ValueError):validate(data)
 def test_terminal_roster_forwarded_and_retried_without_duplicate_release(self):
  h=test_combat.ProtocolTests();h.setUp();e=h.start()
  line=f'COMBAT|FINISH|{e}|2|17|30|0|0||0|0|crew|'+DEAD
  h.out=[];h.receive(1,line);self.assertEqual(h.out,[(2,line)])
  h.receive(2,f'COMBAT|FINISH_ACK|{e}|2');self.assertIsNone(h.r.active)
  h.out=[];h.receive(1,line);self.assertEqual(h.out,[(1,f'COMBAT|FINISH_ACK|{e}|2')])
