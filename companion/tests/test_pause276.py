import unittest
from test_fleet_pause import Pair

class PauseHandshakeTests(unittest.TestCase):
 def test_readonly_native_autopause_does_not_break_resume(self):
  p=Pair()
  for l in p.games.values():
   l.execute('''local backing=Hyperspace.App.gui;backing.bAutoPaused=true
    Hyperspace.App.gui=setmetatable({}, {__index=backing,__newindex=function(_,k,v)
     if k=='bAutoPaused' then error('read-only bAutoPaused') end;backing[k]=v end})''')
  p.start()
  for c in (1,2):self.assertFalse(p.paused(c))

 def test_rejected_run_does_not_generate_feedback_storm(self):
  p=Pair();p.tick(7)
  l=p.games[1];l.execute('messages={}')
  line=f'PAUSE|STATE|{p.r.token}|{p.r.rev}|RUN|running|2|1|0'
  for _ in range(100):l.globals().FleetPause27.receive(line)
  messages=list(l.globals().messages.values())
  self.assertLessEqual(len(messages),2)
  self.assertTrue(p.paused(1))
  p.pump()  # The relay/client exchange must settle without a busy loop.

 def test_stale_ready_ack_does_not_swallow_cancel_retry(self):
  p=Pair();p.tick(7);p.press(1)
  l=p.games[1];l.execute('callbacks.down(32);callbacks.up(32);messages={}') # lose cancellation
  # Earlier acknowledgement for READY arrives after the local cancellation.
  l.globals().FleetPause27.receive(f'PAUSE|STATE|{p.r.token}|{p.r.rev}|HOLD|both_press_space|1|1|{p.r.seq[1]}')
  for _ in range(15):l.globals().FleetPause27.tick()
  self.assertTrue(any(s.startswith('PAUSE|HOLD|') for s in l.globals().messages.values()))
  p.pump();self.assertFalse(p.r.running);self.assertEqual(p.r.ready,set())

 def test_reports_do_not_force_unlimited_state_echoes(self):
  p=Pair();p.start();p.out=[]
  line=f'PAUSE|REPORT|42|clear|{p.r.token}|{p.r.rev}'
  for _ in range(100):p.r.receive(1,line,p.ids,p.enabled,p.builds,p.send,p.now)
  self.assertEqual(p.out,[])
  p.now+=.21;p.r.update(p.ids,p.enabled,p.builds,p.send,p.now)
  self.assertEqual(len(p.out),2)

 def test_delayed_ready_and_cancel_require_fresh_both_votes(self):
  p=Pair();p.tick(7);p.press(1)
  l=p.games[1];l.execute('callbacks.down(32);callbacks.up(32)')
  # Other captain readies before cancellation reaches the host.
  other=p.games[2];other.execute('callbacks.down(32);callbacks.up(32)')
  lines=list(other.globals().messages.values());other.execute('messages={}')
  for line in lines:p.r.receive(2,line,p.ids,p.enabled,p.builds,p.send,p.now)
  p.pump();self.assertFalse(p.r.running)
  self.assertTrue(p.paused(1));self.assertTrue(p.paused(2))
  p.tick(7);p.press(1);self.assertFalse(p.r.running);p.press(2)
  self.assertTrue(p.r.running)
