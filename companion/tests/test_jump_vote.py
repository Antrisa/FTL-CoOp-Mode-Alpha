from ui_fixture import load_ui
import unittest
import test_travel
import test_combat
from jump_vote import JumpRoom,parse
from ship_view import guard
from lupa.lua53 import LuaRuntime
from pathlib import Path

class JumpTests(unittest.TestCase):
    def setUp(self):
        self.p=test_travel.players();self.r=JumpRoom();self.out=[]
        s=self.p[0]['snapshot'];self.g=guard(dict(seed=s['seed'],level=s['level'],x=s['position'][0],y=s['position'][1]))
    def send(self,cid,line):self.out.append((cid,line))
    def vote(self,cid,serial=1,target=test_travel.TARGET):
        self.r.receive(cid,f'JUMP|VOTE|{self.g}|{serial}|{target[0]}|{target[1]}',self.p,self.send,100)
    def ready(self,cid,id=1,now=101):self.r.receive(cid,f'JUMP|READY|{id}',self.p,self.send,now)
    def test_matching_votes_then_both_ready_commits_once(self):
        self.vote(1);self.assertIsNone(self.r.pending);self.vote(2)
        self.assertEqual(self.r.pending['phase'],'prepare')
        self.ready(1);self.ready(1);self.assertEqual(self.r.pending['phase'],'prepare')
        self.ready(2);self.ready(2)
        self.assertEqual(sum('|COMMIT|' in s for _,s in self.out),2)
    def test_different_votes_wait_and_changed_vote_can_match(self):
        target=next(n[:2] for n in self.p[0]['snapshot']['nodes'] if n[:2]!=test_travel.TARGET and n[:2]!=test_travel.ORIGIN and self.p[0]['snapshot']['nodes'].index(n) in next(n for n in self.p[0]['snapshot']['nodes'] if n[:2]==test_travel.ORIGIN)[3])
        self.vote(1);self.vote(2,target=target);self.assertIsNone(self.r.pending)
        self.vote(2,2);self.assertIsNotNone(self.r.pending)
    def test_no_vote_to_non_neighbor_or_wrong_context(self):
        with self.assertRaises(ValueError):self.vote(1,target=[999,999])
        self.g+=1
        with self.assertRaises(ValueError):self.vote(1)
    def test_closed_map_or_expired_prepare_cannot_commit(self):
        self.vote(1);self.vote(2);self.r.receive(1,'JUMP|CLEAR',self.p,self.send,100)
        self.ready(1);self.ready(2);self.assertFalse(any('|COMMIT|' in s for _,s in self.out))
        self.vote(1);self.vote(2);self.ready(1,id=2,now=104);self.assertIsNone(self.r.pending)
    def test_disconnect_and_partial_arrival_blocks_new_vote(self):
        self.vote(1);self.vote(2);self.ready(1);self.ready(2)
        self.p[0]['snapshot']['position']=test_travel.TARGET
        self.r.tick(self.p,self.send,102);self.assertEqual(self.r.pending['phase'],'commit')
        self.r.receive(1,'JUMP|CLEAR',self.p,self.send,102);self.assertIsNotNone(self.r.pending)
        self.p[1]['snapshot']['position']=test_travel.TARGET
        self.r.tick(self.p,self.send,103);self.assertIsNone(self.r.pending)
        self.assertIn('both_arrived',self.out[-1][1])
    def test_parser_rejects_invalid_messages(self):
        for line in ('JUMP|VOTE|1|2|nan|1','JUMP|COMMIT|1','JUMP|READY|-','JUMP|VOTE|1|2|0|99999999999'):
            with self.assertRaises(ValueError):parse(line)

class JumpLuaTests(unittest.TestCase):
    def lua(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute('''
        sent={};commits=0;valid=true;polled=false;ready=true;guard=42
        FleetNativeCombat={version=4,jumpEnable=function(v)gate=v end,jumpArrived=function()end,
         jumpPoll=function()if not polled then polled=true;return 7,43,168 end end,
         jumpCheck=function(s)return valid and s==7 end,jumpCommit=function(s)commits=commits+1;return true end}
        FleetFastLink={ready=function()return ready end,send=function(s)sent[#sent+1]=s;return true end}
        FleetInterior19={contextGuard=function()return guard end}
        Hyperspace={App={world={bStartedGame=true,starMap={bOpen=true}},menu={bOpen=false},gui={}}}
        Defines={InternalEvents={JUMP_ARRIVE='arrive'},RenderEvents={MOUSE_CONTROL=1}}
        script={on_internal_event=function(e,f)arrive=f end,on_render_event=function()end}
        ''');load_ui(l);l.execute(Path('jump_vote.lua').read_text());l.globals().FleetJump24.tick();return l
    def test_prepare_commit_duplicates_and_closed_map(self):
        l=self.lua();m=l.globals().FleetJump24
        m.receive('JUMP|COMMIT|1|42|7');self.assertEqual(l.globals().commits,0)
        m.receive('JUMP|PREPARE|1|42|7');m.receive('JUMP|COMMIT|1|42|7');m.receive('JUMP|COMMIT|1|42|7')
        self.assertEqual(l.globals().commits,1)
        l=self.lua();m=l.globals().FleetJump24;m.receive('JUMP|PREPARE|1|42|7');l.globals().valid=False;m.receive('JUMP|COMMIT|1|42|7')
        self.assertEqual(l.globals().commits,0)
    def test_old_context_refused_and_link_loss_remains_gated(self):
        l=self.lua();m=l.globals().FleetJump24;m.receive('JUMP|PREPARE|1|43|7');m.receive('JUMP|COMMIT|1|43|7')
        self.assertEqual(l.globals().commits,0)
        l.globals().ready=False;m.tick();self.assertTrue(l.globals().gate)

class AutoCombatTests(unittest.TestCase):
    def test_auto_arms_and_pauses_without_f6(self):
        l=test_combat.LuaCombatTests().lua();l.execute('for i=1,16 do FleetCombat22.tick()end')
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
        self.assertTrue(any('AUTO_ARMED' in x for x in l.globals().logs.values()))
        self.assertTrue(any('|ARM|' in x for x in l.globals().sent.values()))
    def test_event_open_does_not_auto_arm_and_unsupported_does_not_loop(self):
        l=test_combat.LuaCombatTests().lua();l.execute('Hyperspace.App.gui.choiceBoxOpen=true;FleetCombat22.tick()')
        self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
        l.execute('Hyperspace.App.gui.choiceBoxOpen=false;bp.type=9;for i=1,16 do FleetCombat22.tick()end;Hyperspace.App.gui.bPaused=false;FleetCombat22.tick()')
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)

class JumpTransportTests(unittest.TestCase):
    def test_two_real_relay_clients_vote_prepare_commit(self):
        import queue,socket,threading,time
        from fleet_link import RelayServer,RelayClient
        server=RelayServer('127.0.0.1',port=0);threading.Thread(target=server.serve_forever,daemon=True).start()
        qa,qb=queue.Queue(),queue.Queue();a=b=None
        def wait(q,kind,sub=''):
            end=time.monotonic()+3
            while time.monotonic()<end:
                _,m=q.get(timeout=3)
                if m.get('type')==kind and sub in m.get('line',''):return m
            raise AssertionError('message missing')
        try:
            port=server.server_address[1];a=RelayClient('127.0.0.1','a',qa,port,server.host_token);b=RelayClient('127.0.0.1','b',qb,port)
            wait(qa,'welcome');wait(qb,'welcome')
            for c in (a,b):c.send(dict(type='game_build',version=2816));c.send(dict(type='snapshot',snapshot=test_travel.A))
            end=time.monotonic()+3
            while (len(server.room.mod_builds)<2 or len(server.room.snapshots)<2) and time.monotonic()<end:time.sleep(.01)
            self.assertEqual(len(server.room.mod_builds),2)
            s=test_travel.A;g=guard(dict(seed=s['seed'],level=s['level'],x=s['position'][0],y=s['position'][1]));x,y=test_travel.TARGET
            for c in (a,b):c.send(dict(type='jump',line=f'JUMP|VOTE|{g}|1|{x}|{y}'))
            h=wait(qa,'jump','|PREPARE|');k=wait(qb,'jump','|PREPARE|');self.assertEqual(h['line'],k['line'])
            id=h['line'].split('|')[2]
            for c in (a,b):c.send(dict(type='jump',line=f'JUMP|READY|{id}'))
            self.assertEqual(wait(qa,'jump','|COMMIT|')['line'],wait(qb,'jump','|COMMIT|')['line'])
        finally:
            if a:a.close()
            if b:b.close()
            server.shutdown();server.server_close()
    def test_local_jump_lines_reach_native_queue(self):
        import queue,socket
        from fast_local import LocalCompanion
        q=queue.Queue();s=LocalCompanion(lambda x:None,port=0,on_jump=q.put);s.start()
        c=socket.create_connection(('127.0.0.1',s.port));c.settimeout(2)
        try:
            c.sendall(b'HELLO|1\n');self.assertEqual(c.recv(1024),b'HELLO|1\n')
            c.sendall(b'JUMP|VOTE|42|1|43|168\n');self.assertEqual(q.get(timeout=2),'JUMP|VOTE|42|1|43|168')
            s.send_combat('JUMP|PREPARE|1|42|1');self.assertEqual(c.recv(1024),b'JUMP|PREPARE|1|42|1\n')
        finally:c.close();s.stop()

class VictoryTests(unittest.TestCase):
    def test_enemy_death_releases_replica_and_allows_travel(self):
        harness=test_combat.LuaCombatTests();l=harness.lua();harness.start(l,'G')
        l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|1|0|30|0|0|')
        l.globals().FleetCombat22.tick()
        self.assertTrue(l.globals().replica);self.assertFalse(l.globals().FleetCombat22.canJump())
        l.globals().FleetCombat22.receive('COMBAT|FINISH|testepoch|2|0|30|0|0|')
        self.assertFalse(l.globals().replica);self.assertFalse(l.globals().FleetCombat22.canJump())
        l.execute('Hyperspace.App.gui.choiceBoxOpen=true;FleetCombat22.tick();Hyperspace.App.gui.choiceBoxOpen=false;Hyperspace.App.gui.bPaused=false;for i=1,90 do FleetCombat22.tick()end')
        l.globals().FleetCombat22.receive('COMBAT|POST_RELEASE|testepoch|2')
        self.assertTrue(l.globals().FleetCombat22.canJump())
    def test_active_combat_blocks_jump_prepare(self):
        l=JumpLuaTests().lua();l.execute('FleetCombat22={canJump=function()return false end}')
        l.globals().FleetJump24.receive('JUMP|PREPARE|1|42|7');l.globals().FleetJump24.receive('JUMP|COMMIT|1|42|7')
        self.assertEqual(l.globals().commits,0)
