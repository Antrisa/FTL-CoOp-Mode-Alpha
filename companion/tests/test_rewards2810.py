import unittest
from pathlib import Path
import test_native, test_combat

class RewardContinuationTests(unittest.TestCase):
 def view(self):
  l=test_native.NativeLuaTests().lua()
  l.execute("""pending=true;FleetCombat22={isActive=function()return false end,rewardPending=function()return pending end}
  state.count=1;choice={type=0,text='Continue...'};box.GetChoices=function()return {[0]=choice}end
  box.mainText='The ship explodes, leaving behind scrap.';box.potentialChoice=0""")
  return l
 def test_local_reward_with_no_partner_event_passes_click_and_number(self):
  l=self.view();l.execute('FleetPanel11.nativeStatus=function()return nil,9999 end')
  self.assertTrue(l.globals().FleetNative15.localReward(l.globals().state))
  self.assertEqual(l.globals().callbacks[1](20,30),0)
  self.assertEqual(l.globals().FleetNative15.key(49),0)
  self.assertFalse(any('NATIVE_VOTE|' in x for x in l.globals().logs.values()))
 def test_multi_choice_non_continue_and_nonterminal_events_still_vote(self):
  for change in ['state.count=2','pending=false',"choice.text='Accept surrender'",'choice.type=1']:
   l=self.view();l.execute(change)
   self.assertFalse(l.globals().FleetNative15.localReward(l.globals().state))
   self.assertEqual(l.globals().FleetNative15.key(49),1)
 def test_f9_cannot_leave_next_event_in_solo_mode(self):
  l=self.view();l.globals().FleetNative15.key(290)
  self.assertEqual(l.globals().callbacks[1](20,30),0)
  l.execute('pending=false;state.token=43;state.count=2')
  self.assertEqual(l.globals().callbacks[1](20,30),1)
  self.assertIn('NATIVE_VOTE|43|1',list(l.globals().logs.values())[-1])
 def test_real_combat_gate_requires_finish_and_retains_jump_barrier(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
  self.assertFalse(l.globals().FleetCombat22.rewardPending())
  l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0|')
  self.assertTrue(l.globals().FleetCombat22.rewardPending())
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.execute('for i=1,180 do FleetCombat22.tick()end')
  self.assertFalse(any('POST_READY' in x for x in l.globals().sent.values()))
  l.execute('Hyperspace.App.gui.choiceBoxOpen=true;FleetCombat22.tick();Hyperspace.App.gui.choiceBoxOpen=false;Hyperspace.App.gui.bPaused=false;for i=1,100 do FleetCombat22.tick()end')
  self.assertFalse(l.globals().FleetCombat22.canJump())
  l.globals().FleetCombat22.receive('COMBAT|POST_RELEASE|testepoch|2')
  self.assertTrue(l.globals().FleetCombat22.canJump())
  self.assertFalse(l.globals().FleetCombat22.rewardPending())
