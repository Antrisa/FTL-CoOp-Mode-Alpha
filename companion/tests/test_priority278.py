import unittest,json,queue
from priority_updates import UpdateQueue,ui_key,wire_key
from async_sender import AsyncSender
from test_async_sender import BlockedSocket
from fast_local import LocalCompanion

class PriorityTests(unittest.TestCase):
 def test_ui_display_flood_keeps_latest_and_control_fifo(self):
  q=UpdateQueue(key=ui_key)
  for i in range(10000):q.put(('network',dict(type='scene',scene=i)))
  controls=[('network',dict(type='combat',line='COMBAT|SHOT|e|1')),('network',dict(type='pause',line='PAUSE|STATE|e|1|HOLD|test|0|0|0'))]
  for x in controls:q.put(x)
  self.assertEqual(q.qsize(),3)
  for x in controls:self.assertEqual(q.get_nowait(),x)
  self.assertEqual(q.get_nowait()[1]['scene'],9999)
 def test_writer_prioritizes_shots_after_inflight_frame(self):
  sock=BlockedSocket();w=AsyncSender(sock)
  first=b'{"type":"scene_z","scene":0}'
  w.send(first);self.assertTrue(sock.started.wait(1))
  for i in range(1000):w.send(json.dumps(dict(type='scene_z',scene=i)).encode())
  shot=b'{"type":"combat","line":"COMBAT|SHOT|e|1"}'
  ack=b'{"type":"combat","line":"COMBAT|ACK|e|1"}'
  w.send(shot);w.send(ack);sock.release.set();w.finish()
  self.assertEqual(sock.received[:3],[first,shot,ack])
  self.assertEqual(json.loads(sock.received[-1])['scene'],999)
  self.assertEqual(len(sock.received),4)
 def test_local_snapshot_flood_does_not_displace_commands(self):
  c=LocalCompanion(lambda s:None)
  for i in range(10000):c.send_combat(f'COMBAT|SNAP|epoch|{i}|20|30|0|1|')
  for line in ['COMBAT|SHOT|epoch|1','COMBAT|ACK|epoch|1','COMBAT|STOP|test']:c.send_combat(line)
  self.assertEqual(c.commands.qsize(),4)
  self.assertTrue(c.commands.get_nowait().startswith(b'COMBAT|SHOT|'))
  self.assertTrue(c.commands.get_nowait().startswith(b'COMBAT|ACK|'))
  self.assertTrue(c.commands.get_nowait().startswith(b'COMBAT|STOP|'))
  self.assertIn(b'|9999|',c.commands.get_nowait())
 def test_report_and_ready_transitions_never_coalesced(self):
  q=UpdateQueue(key=ui_key)
  xs=[('fast_pause','PAUSE|REPORT|42|map|e|2'),('fast_pause','PAUSE|REPORT|42|clear|e|2'),('fast_pause','PAUSE|READY|e|2|1')]
  for x in xs:q.put(x)
  self.assertEqual([q.get_nowait() for _ in xs],xs)
 def test_control_overflow_explicit(self):
  q=UpdateQueue(1,key=wire_key);q.put(b'one')
  with self.assertRaises(queue.Full):q.put(b'two')
 def test_timeout_empty_queue(self):
  with self.assertRaises(queue.Empty):UpdateQueue().get(timeout=.001)
