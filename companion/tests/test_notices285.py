import unittest
import test_native,test_combat
class NoticesTests(unittest.TestCase):
 def notice(self):
  l=test_native.NativeLuaTests().lua()
  l.execute("""FleetCombat22={isActive=function()return true end};state.count=1
  box.mainText="The enemy ship appears to be powering up its FTL. It's trying to escape!"
  choice={type=0,text='Continue...'};box.GetChoices=function()return {[0]=choice}end
  """)
  return l
 def test_exact_live_warning_click_passes_to_native_without_vote(self):
  l=self.notice()
  self.assertTrue(l.globals().FleetNative15.localNotice(l.globals().state))
  self.assertEqual(l.eval('callbacks[1](20,30)'),0)
  self.assertEqual(l.eval('FleetNative15.key(49)'),0)
  self.assertFalse(any('NATIVE_VOTE|' in s for s in l.globals().logs.values()))
 def test_other_single_choices_and_inactive_combat_still_vote(self):
  for change in ["box.mainText='Accept this reward.'","choice.text='Accept surrender'","choice.type=1","FleetCombat22.isActive=function()return false end"]:
   l=self.notice();l.execute(change)
   self.assertFalse(l.globals().FleetNative15.localNotice(l.globals().state))
   self.assertEqual(l.eval('FleetNative15.key(49)'),1)
 def test_enemy_escape_blocks_further_combat_and_travel(self):
  h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
  l.execute('Hyperspace.ships.enemy.bJumping=true;FleetCombat22.tick()')
  self.assertEqual(l.globals().FleetCombat22.pauseBlock(),'combat')
  self.assertFalse(l.globals().FleetCombat22.canJump())
  self.assertIn('enemy_escape_not_synchronized',l.globals().FleetCombat22.status())
