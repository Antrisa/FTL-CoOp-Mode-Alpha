import unittest
import test_combat
from combat import parse
from priority_updates import UpdateQueue,line_key
class CompletionTests(unittest.TestCase):
 def game(self,role):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,role);return l
 def test_finish_before_queued_snapshot_applies_and_clears(self):
  l=self.game('G');q=UpdateQueue(key=line_key)
  q.put('COMBAT|SNAP|testepoch|1|10|30|0|0|')
  q.put('COMBAT|FINISH|testepoch|2|0|30|0|0|')
  l.globals().FleetCombat22.receive(q.get_nowait())
  self.assertEqual(l.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,0)
  self.assertFalse(l.globals().replica);self.assertFalse(l.globals().FleetCombat22.canJump())
  l.globals().FleetCombat22.receive(q.get_nowait())
  self.assertEqual(l.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,0)
  self.assertIn('COMBAT|FINISH_ACK|testepoch|2',list(l.globals().sent.values()))
 def test_replayed_finish_does_not_destroy_twice(self):
  l=self.game('G');l.execute('deaths=0;Hyperspace.ships.enemy.SetDestroyed=function(self)deaths=deaths+1;self.bDestroyed=true end')
  for _ in range(3):l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0|')
  self.assertEqual(l.globals().deaths,0) # FTL owns destruction; Lua only supplies terminal hull.
  self.assertEqual(list(l.globals().sent.values()).count('COMBAT|FINISH_ACK|testepoch|2'),3)
 def test_wrong_epoch_finish_ignored(self):
  l=self.game('G');l.globals().FleetCombat22.receive('COMBAT|FINISH|old|2|0|30|0|0|')
  self.assertEqual(l.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,30)
 def test_host_retries_until_matching_ack_and_then_can_jump(self):
  l=self.game('H');l.execute('Hyperspace.ships.enemy.ship.hullIntegrity.first=0;FleetCombat22.tick()')
  lines=[x for x in l.globals().sent.values() if x.startswith('COMBAT|FINISH|')];self.assertEqual(len(lines),1)
  seq=lines[0].split('|')[3]
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.execute('for i=1,30 do FleetCombat22.tick()end')
  self.assertEqual(list(l.globals().sent.values()).count(lines[0]),2)
  l.globals().FleetCombat22.receive('COMBAT|FINISH_ACK|old|'+seq)
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.globals().FleetCombat22.receive('COMBAT|FINISH_ACK|testepoch|'+seq)
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.execute('Hyperspace.App.gui.choiceBoxOpen=true;FleetCombat22.tick();Hyperspace.App.gui.choiceBoxOpen=false;Hyperspace.App.gui.bPaused=false;for i=1,90 do FleetCombat22.tick()end')
  l.globals().FleetCombat22.receive('COMBAT|POST_RELEASE|testepoch|'+seq)
  self.assertTrue(l.globals().FleetCombat22.canJump())
  self.assertNotIn('COMBAT|STOP|encounter_finished',list(l.globals().sent.values()))
 def test_relay_finish_host_only_and_ack_replay(self):
  h=test_combat.ProtocolTests();h.setUp();e=h.start();h.out=[]
  line=f'COMBAT|FINISH|{e}|2|0|30|0|0|'
  h.receive(2,line);self.assertEqual(h.out,[])
  h.receive(1,line);self.assertEqual(h.out,[(2,line)])
  h.receive(2,f'COMBAT|FINISH_ACK|{e}|3');self.assertIsNotNone(h.r.active)
  h.receive(2,f'COMBAT|FINISH_ACK|{e}|2');self.assertIsNone(h.r.active)
  h.receive(1,line);self.assertEqual(h.out[-1],(1,f'COMBAT|FINISH_ACK|{e}|2'))
  self.assertFalse(any('|STOP|' in x for _,x in h.out))
 def test_nonzero_finish_invalid(self):
  with self.assertRaises(ValueError):parse('COMBAT|FINISH|e|2|1|30|0|0|')
