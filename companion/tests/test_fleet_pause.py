from ui_fixture import load_ui
import unittest,time,socket,queue,threading
from pathlib import Path
from fleet_pause import PauseRoom,parse
from lupa.lua53 import LuaRuntime

def lua():
    l=LuaRuntime(unpack_returned_tuples=True)
    l.execute('''
      messages={};callbacks={};connection=true;g=42
      Hyperspace={App={world={bStartedGame=true,starMap={bOpen=false}},menu={bOpen=false},gui={bPaused=false}}}
      FleetInterior19={contextGuard=function()return g end}
      FleetFastLink={ready=function()return connection end,send=function(s)messages[#messages+1]=s;return connection end}
      Defines={SDL={KEY_SPACE=32},Chain={CONTINUE=0,PREEMPT=1},InternalEvents={ON_KEY_DOWN='down',ON_KEY_UP='up'},RenderEvents={MOUSE_CONTROL='mouse'}}
      script={on_internal_event=function(e,f)callbacks[e]=f end,on_render_event=function()end,on_init=function(f)init=f end}
    ''')
    load_ui(l);l.execute(Path('fleet_pause.lua').read_text());return l

class Pair:
    def __init__(self):
        self.r=PauseRoom();self.games={1:lua(),2:lua()};self.ids={1:None,2:None};self.enabled={1,2};self.builds={1:(2816,10),2:(2816,10)};self.out=[];self.now=10
    def send(self,c,s):self.out.append((c,s))
    def pump(self):
        for _ in range(25):
            changed=False
            for c,l in self.games.items():
                lines=list(l.globals().messages.values());l.execute('messages={}')
                for line in lines:
                    changed=True;self.r.receive(c,line,self.ids,self.enabled,self.builds,self.send,self.now)
            pending=self.out;self.out=[]
            for c,s in pending:
                changed=True
                if c in self.games:self.games[c].globals().FleetPause27.receive(s)
            if not changed:return
        raise AssertionError('pause protocol did not settle')
    def tick(self,n=1):
        for _ in range(n):
            for l in self.games.values():l.globals().FleetPause27.tick()
            self.r.update(self.ids,self.enabled,self.builds,self.send,self.now);self.pump()
    def press(self,c):
        self.games[c].execute('callbacks.down(32);callbacks.up(32)');self.pump()
    def start(self):
        self.tick(7);self.press(1);self.press(2);self.tick();assert self.r.running
    def paused(self,c):return self.games[c].globals().Hyperspace.App.gui.bPaused

class PauseTests(unittest.TestCase):
    def test_initial_run_requires_both_ready(self):
        p=Pair();p.tick(7);self.assertTrue(p.paused(1));self.assertTrue(p.paused(2));p.press(1)
        self.assertFalse(p.r.running);p.press(2);self.assertTrue(p.r.running);self.assertFalse(p.paused(1));self.assertFalse(p.paused(2))
    def test_either_player_pauses_and_new_votes_required(self):
        for c in (1,2):
            p=Pair();p.start();p.press(c);self.assertFalse(p.r.running);self.assertTrue(p.paused(1));self.assertTrue(p.paused(2))
            p.tick(7);p.press(1);self.assertFalse(p.r.running);p.press(2);self.assertTrue(p.r.running)
    def test_repeated_space_does_not_ready_then_cancel(self):
        p=Pair();p.tick(7);p.games[1].execute('callbacks.down(32);callbacks.down(32);callbacks.down(32)');p.pump();self.assertEqual(p.r.ready,{1})
    def test_second_press_cancels_readiness(self):
        p=Pair();p.tick(7);p.press(1);p.press(1);self.assertEqual(p.r.ready,set());self.assertFalse(p.r.running)
    def test_event_map_and_menu_clear_old_votes(self):
        for field in ('Hyperspace.App.gui.choiceBoxOpen','Hyperspace.App.gui.menu_pause','Hyperspace.App.world.starMap.bOpen'):
            p=Pair();p.start();p.games[2].execute(field+'=true');p.tick();self.assertFalse(p.r.running);self.assertTrue(p.paused(1))
            p.press(1);p.press(2);self.assertFalse(p.r.running)
            p.games[2].execute(field+'=false');p.tick(7);self.assertFalse(p.r.running);p.press(1);p.press(2);self.assertTrue(p.r.running)
    def test_manual_pause_not_overwritten_by_queued_run(self):
        p=Pair();p.start();p.games[1].execute('Hyperspace.App.gui.bPaused=true')
        p.games[1].globals().FleetPause27.receive(f'PAUSE|STATE|{p.r.token}|{p.r.rev}|RUN|running|2|1');p.pump()
        self.assertFalse(p.r.running);self.assertTrue(p.paused(2))
    def test_local_socket_loss_and_stale_run_fail_closed(self):
        p=Pair();p.start();old=f'PAUSE|STATE|{p.r.token}|{p.r.rev}|RUN|running|2|1'
        p.games[1].execute('connection=false');p.games[1].globals().FleetPause27.tick();self.assertTrue(p.paused(1))
        p.games[1].execute('connection=true');p.games[1].globals().FleetPause27.receive(old);self.assertTrue(p.paused(1));p.pump();self.assertFalse(p.r.running)
    def test_timeout_stale_epoch_readiness_and_disabled_bridge(self):
        p=Pair();p.start();p.now=12;p.r.update(p.ids,p.enabled,p.builds,p.send,p.now);p.pump();self.assertFalse(p.r.running);self.assertTrue(p.paused(1))
        oldrev=p.r.rev;p.enabled.remove(2);p.r.update(p.ids,p.enabled,p.builds,p.send,p.now);p.pump()
        p.r.receive(1,f'PAUSE|READY|{p.r.token}|{oldrev}|999',p.ids,p.enabled,p.builds,p.send,p.now);self.assertFalse(p.r.running)
    def test_different_beacons_and_game_restart_hold(self):
        p=Pair();p.start();p.games[2].execute('g=43');p.tick();self.assertFalse(p.r.running)
        p.games[2].execute('g=42');p.tick(7);self.assertFalse(p.r.running)
        p.r.game_reconnected(2);p.r.update(p.ids,p.enabled,p.builds,p.send,p.now);p.pump();self.assertFalse(p.r.running)
    def test_general_tick_reports_while_bpaused(self):
        l=lua();l.execute('Hyperspace.App.gui.bPaused=true;for i=1,60 do FleetPause27.tick()end')
        self.assertGreaterEqual(len(list(l.globals().messages.values())),10)
    def test_invalid_protocol(self):
        for bad in ('PAUSE|REPORT|nan|clear|none|0','PAUSE|READY|token|0|1','PAUSE|HOLD|x|1|-1','PAUSE|REPORT|42|unknown|x|1','PAUSE|REPORT|42|clear|x|1\n'):
            with self.assertRaises(ValueError):parse(bad)
    def test_local_companion_routes_pause_while_paused(self):
        from fast_local import LocalCompanion
        received=queue.Queue();c=LocalCompanion(lambda s:None,port=0,on_pause=received.put);c.start()
        try:
            with socket.create_connection(('127.0.0.1',c.port)) as s:
                s.settimeout(2);f=s.makefile('rb');s.sendall(b'HELLO|1\n');self.assertEqual(f.readline(),b'HELLO|1\n')
                s.sendall(b'PAUSE|REPORT|42|clear|none|0\n');self.assertEqual(received.get(timeout=1),'PAUSE|REPORT|42|clear|none|0')
                c.send_combat('PAUSE|STATE|abc|1|HOLD|waiting_for_both|0|0');self.assertEqual(f.readline(),b'PAUSE|STATE|abc|1|HOLD|waiting_for_both|0|0\n')
        finally:c.stop()

    def test_utility_ready_is_only_local_vote(self):
        p=Pair();p.tick(7)
        p.games[1].globals().FleetPause27.receive('PAUSE|LOCAL_READY');p.pump()
        self.assertEqual(p.r.ready,{1});self.assertFalse(p.r.running)
        p.games[2].globals().FleetPause27.receive('PAUSE|LOCAL_READY');p.pump()
        self.assertTrue(p.r.running)
        p.games[2].globals().FleetPause27.receive('PAUSE|LOCAL_HOLD');p.pump()
        self.assertFalse(p.r.running);self.assertTrue(p.paused(1))

    def test_real_relay_routes_reports_and_utility_only_to_sender(self):
        from fleet_link import RelayServer,RelayClient
        server=RelayServer('127.0.0.1',port=0)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        qa,qb=queue.Queue(),queue.Queue();a=b=None
        def wait(q,kind,sub=''):
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                _,m=q.get(timeout=3)
                if m.get('type')==kind and sub in m.get('line',''):return m
            self.fail('missing relay message')
        try:
            port=server.server_address[1]
            a=RelayClient('127.0.0.1','a',qa,port,server.host_token)
            b=RelayClient('127.0.0.1','b',qb,port)
            wait(qa,'welcome');wait(qb,'welcome')
            for c in (a,b):c.send(dict(type='pause',line='PAUSE|REPORT|42|clear|none|0'))
            wait(qa,'pause','|STATE|');wait(qb,'pause','|STATE|')
            a.send(dict(type='bridge',action='command',op='RESUME'))
            wait(qa,'pause','PAUSE|LOCAL_READY')
            deadline=time.monotonic()+.2
            while time.monotonic()<deadline:
                try:_,m=qb.get(timeout=.02)
                except queue.Empty:continue
                self.assertNotEqual(m.get('line'),'PAUSE|LOCAL_READY')
            self.assertFalse(server.room.pause.running)
        finally:
            if a:a.close()
            if b:b.close()
            server.shutdown();server.server_close()
