import unittest
import test_combat
from realtime_bridge import forward
class PostCombatTests(unittest.TestCase):
 def test_separate_inventory_preserved_during_replayed_completion(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
  l.execute('Hyperspace.ships.player.scrap_count=41;Hyperspace.ships.player.fuel_count=7;rewardCalls=0;Hyperspace.ships.enemy.SetDestroyed=function(self)self.bDestroyed=true;rewardCalls=rewardCalls+1;Hyperspace.ships.player.scrap_count=Hyperspace.ships.player.scrap_count+12 end')
  for _ in range(4):l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0|')
  self.assertEqual(l.globals().rewardCalls,0) # No synthetic death/reward call.
  self.assertEqual(l.globals().Hyperspace.ships.player.scrap_count,41)
  self.assertEqual(l.globals().Hyperspace.ships.player.fuel_count,7)
 def test_post_event_blocks_ready_then_release_enables_jump(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
  l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0|')
  l.execute('Hyperspace.App.gui.choiceBoxOpen=true;for i=1,120 do FleetCombat22.tick()end')
  self.assertFalse(any('POST_READY' in x for x in l.globals().sent.values()))
  l.execute('Hyperspace.App.gui.choiceBoxOpen=false;Hyperspace.App.gui.bPaused=false;for i=1,90 do FleetCombat22.tick()end')
  self.assertIn('COMBAT|POST_READY|testepoch|2',list(l.globals().sent.values()))
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.globals().FleetCombat22.receive('COMBAT|POST_RELEASE|old|2');self.assertFalse(l.globals().FleetCombat22.canJump())
  l.globals().FleetCombat22.receive('COMBAT|POST_RELEASE|testepoch|2');self.assertTrue(l.globals().FleetCombat22.canJump())
 def test_two_fights_require_both_post_ready_and_use_new_epoch(self):
  h=test_combat.ProtocolTests();h.setUp();e=h.start()
  h.receive(1,f'COMBAT|FINISH|{e}|2|0|30|0|0|');h.receive(2,f'COMBAT|FINISH_ACK|{e}|2')
  h.out=[];h.receive(1,f'COMBAT|POST_READY|{e}|2');self.assertEqual(h.out,[])
  for c in (1,2):h.receive(c,'COMBAT|ARM|42|enemy|player|LASER_BURST_2')
  self.assertIsNone(h.r.active)
  h.receive(2,f'COMBAT|POST_READY|{e}|2');self.assertEqual(len(h.out),2)
  new=h.start();self.assertNotEqual(new,e)
  h.receive(1,f'COMBAT|SPAWN|{e}|1|LASER_BURST_2|35|35|10|10|90|0')
  h.out=[];h.receive(2,f'COMBAT|SHOT|{new}|1|LASER_BURST_2|35|35|10|10|90|0')
  self.assertEqual(len(h.out),1);self.assertIn(new,h.out[0][1])
 def test_release_can_be_retried_after_lost_reply(self):
  h=test_combat.ProtocolTests();h.setUp();e=h.start()
  h.receive(1,f'COMBAT|FINISH|{e}|2|0|30|0|0|');h.receive(2,f'COMBAT|FINISH_ACK|{e}|2')
  for c in (1,2):h.receive(c,f'COMBAT|POST_READY|{e}|2')
  h.out=[];h.receive(2,f'COMBAT|POST_READY|{e}|2');self.assertEqual(len(h.out),2)
 def test_realtime_control_bypasses_ui_and_disabled_bridge_blocks_combat(self):
  class Local:
   def __init__(self):self.lines=[];self.scenes=[]
   def send_combat(self,s):self.lines.append(s)
   def set_scene(self,s):self.scenes.append(s)
  l=Local();logs=[]
  self.assertTrue(forward({'type':'combat','line':'COMBAT|ACK|e|1'},l,True,logs.append))
  self.assertEqual(l.lines,['COMBAT|ACK|e|1'])
  forward({'type':'combat','line':'COMBAT|SHOT|e|2'},l,False,logs.append)
  self.assertEqual(len(l.lines),1)
  self.assertFalse(forward({'type':'state'},l,True,logs.append))
