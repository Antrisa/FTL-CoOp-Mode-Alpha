import unittest
from pathlib import Path
from bridge_room import Bridge
from input_bridge import packet_keys
from fleet_link import Room
try:
    from lupa.lua53 import LuaRuntime
except ImportError:LuaRuntime=None

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.b=Bridge();self.b.enabled={1,2};self.b.loaded={1:100,2:100}
    def test_requires_host_enabled_and_recent_game(self):
        with self.assertRaises(ValueError):self.b.command(2,1,[1,2],'PING',100)
        self.b.enabled={1}
        with self.assertRaises(ValueError):self.b.command(1,1,[1,2],'PING',100)
        self.b.enabled={1,2}
        with self.assertRaises(ValueError):self.b.command(1,1,[1,2],'PING',131)
    def test_acknowledgment_required_from_both_games(self):
        self.b.command(1,1,[1,2],'PAUSE',100);n=self.b.pending['nonce']
        self.b.ack(1,f'BRIDGE_ACK|{n}|PAUSE|OK')
        self.assertEqual(self.b.pending['status'],'waiting')
        self.b.ack(2,f'BRIDGE_ACK|{n}|PAUSE|OK')
        self.assertEqual(self.b.pending['status'],'confirmed')
    def test_wrong_ack_and_duplicate_vote_not_success(self):
        self.b.command(1,1,[1,2],'PAUSE',100);n=self.b.pending['nonce']
        for s in [f'BRIDGE_ACK|{n+1}|PAUSE|OK',f'BRIDGE_ACK|{n}|RESUME|OK']:
            self.b.ack(2,s)
        self.b.ack(1,f'BRIDGE_ACK|{n}|PAUSE|OK');self.b.ack(1,f'BRIDGE_ACK|{n}|PAUSE|OK')
        self.assertEqual(self.b.pending['status'],'waiting')
    def test_timeout_and_disconnect(self):
        self.b.command(1,1,[1,2],'PING',100);self.b.tick([1,2],161)
        self.assertEqual(self.b.pending['status'],'unconfirmed')
        self.b.command(1,1,[1,2],'PING',101);self.b.tick([1],102)
        self.assertEqual(self.b.pending['status'],'cancelled')
    def test_reject_unsupported_command_and_nonce(self):
        for op,n in [('JUMP',1),('PING',0),('PING',True),('PING',2**24)]:
            with self.assertRaises(ValueError):packet_keys(op,n)
    def test_room_delivers_ack_status(self):
        class Sink:
            def send(self,data):pass
        r=Room();a=r.join(Sink(),'A',True);b=r.join(Sink(),'B')
        for i in [a,b]:
            r.report(i,'BRIDGE10_READY');r.bridge_action(i,{'action':'enable','enabled':True})
        r.bridge_action(a,{'action':'command','op':'PING'})
        n=r.bridge.pending['nonce']
        for i in [a,b]:r.report(i,f'BRIDGE_ACK|{n}|PING|OK')
        self.assertEqual(r.state()['bridge']['pending']['status'],'confirmed')

@unittest.skipUnless(LuaRuntime,'Lua harness requires lupa')
class LuaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.l=LuaRuntime(unpack_returned_tuples=True)
        self.l.execute('''
        callbacks={};logs={}
        function log(s) logs[#logs+1]=s end
        script={on_load=function(f) callbacks.load=f end,on_internal_event=function(e,f) callbacks[e]=f end}
        Defines={InternalEvents={ON_KEY_DOWN='key',ON_TICK='tick'},SDL={KEY_F13=124,KEY_F14=125,KEY_F15=126},Chain={PREEMPT=1,CONTINUE=0}}
        Hyperspace={App={world={bStartedGame=true},menu={bOpen=false},gui={bPaused=false}}}
        ''')
        self.l.execute((Path(__file__).resolve().parents[1]/'bridge.lua').read_text())
    def send(self,op,n):
        for key in packet_keys(op,n):self.l.globals().callbacks.key(key)
    def test_real_encoded_packets_pause_resume_and_ack(self):
        self.send('PAUSE',123456)
        self.assertTrue(self.l.eval('Hyperspace.App.gui.bPaused'))
        self.assertIn('BRIDGE_ACK|123456|PAUSE|OK',list(self.l.globals().logs.values())[-1])
        self.send('RESUME',123457)
        self.assertFalse(self.l.eval('Hyperspace.App.gui.bPaused'))
    def test_replay_is_idempotent(self):
        self.send('PAUSE',2)
        self.l.execute('Hyperspace.App.gui.bPaused=false')
        self.send('PAUSE',2)
        self.assertFalse(self.l.eval('Hyperspace.App.gui.bPaused'))
    def test_menu_rejects_pause_but_ping_works(self):
        self.l.execute('Hyperspace.App.menu.bOpen=true')
        self.send('PAUSE',5)
        self.assertFalse(self.l.eval('Hyperspace.App.gui.bPaused'))
        self.assertTrue(any('PAUSE|FAILED' in s for s in self.l.globals().logs.values()))
        self.send('PING',6)
        self.assertIn('PING|OK',list(self.l.globals().logs.values())[-1])
    def test_partial_packet_does_nothing_and_start_resets(self):
        for key in packet_keys('PAUSE',8)[:12]:self.l.globals().callbacks.key(key)
        self.assertFalse(self.l.eval('Hyperspace.App.gui.bPaused'))
        self.send('PING',9)
        self.assertIn('BRIDGE_ACK|9|PING|OK',list(self.l.globals().logs.values())[-1])
