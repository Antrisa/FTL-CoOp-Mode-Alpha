import unittest
import test_combat
class EncounterGuardsTests(unittest.TestCase):
 def test_missing_reward_event_never_releases_travel(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
  l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0|')
  l.execute('Hyperspace.App.gui.bPaused=false;for i=1,1200 do FleetCombat22.tick()end')
  self.assertFalse(any('POST_READY' in x for x in l.globals().sent.values()))
  l.globals().FleetCombat22.receive('COMBAT|POST_RELEASE|testepoch|2')
  self.assertFalse(l.globals().FleetCombat22.canJump())
 def test_host_remembers_event_seen_before_guest_ack(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'H')
  l.execute('Hyperspace.ships.enemy.ship.hullIntegrity.first=0;Hyperspace.App.gui.choiceBoxOpen=true;FleetCombat22.tick()')
  line=next(x for x in l.globals().sent.values() if '|FINISH|' in x);seq=line.split('|')[3]
  l.execute('Hyperspace.App.gui.choiceBoxOpen=false')
  l.globals().FleetCombat22.receive('COMBAT|FINISH_ACK|testepoch|'+seq)
  l.execute('Hyperspace.App.gui.bPaused=false;for i=1,90 do FleetCombat22.tick()end')
  self.assertIn('COMBAT|POST_READY|testepoch|'+seq,list(l.globals().sent.values()))
 def test_rejected_encounter_cannot_unpause_jump_or_toggle_to_solo(self):
  h=test_combat.LuaCombatTests();l=h.lua()
  l.execute("bp.type=9;callbacks.key(6);for i=1,30 do FleetCombat22.tick()end;callbacks.key(6);Hyperspace.App.gui.bPaused=false;FleetCombat22.tick()")
  self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
  self.assertEqual(l.globals().FleetCombat22.pauseBlock(),'combat')
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.execute('callbacks.menu()')
  self.assertIsNone(l.globals().FleetCombat22.pauseBlock())
