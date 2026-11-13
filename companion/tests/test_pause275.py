import unittest
from test_fleet_pause import Pair
class PauseRecoveryTests(unittest.TestCase):
 def test_duplicate_ready_does_not_pause_running_game(self):
  p=Pair();p.start()
  for l in p.games.values():l.globals().FleetPause27.receive('PAUSE|LOCAL_READY')
  p.tick(8);self.assertTrue(p.r.running)
  for c in (1,2):self.assertFalse(p.paused(c))
 def test_earlier_hold_ack_cannot_undo_same_revision_run(self):
  p=Pair();p.start()
  for l in p.games.values():l.globals().FleetPause27.receive(f'PAUSE|STATE|{p.r.token}|{p.r.rev}|HOLD|both_press_space|1|1')
  p.tick(8);self.assertTrue(p.r.running)
  for c in (1,2):self.assertFalse(p.paused(c))
 def test_native_auto_pause_requires_both_and_clears_on_resume(self):
  p=Pair();p.start()
  p.games[1].execute('Hyperspace.App.gui.bPaused=true;Hyperspace.App.gui.bAutoPaused=true')
  p.tick();self.assertFalse(p.r.running)
  p.press(1);self.assertFalse(p.r.running);p.press(2);p.tick(8)
  self.assertTrue(p.r.running)
  for c in (1,2):self.assertFalse(p.paused(c))
