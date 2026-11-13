import copy
import unittest
from pathlib import Path
from event_vote import EventVote,parse_event_state,validate_event
from input_bridge import packet_keys
from fleet_link import Room
try:from lupa.lua53 import LuaRuntime
except ImportError:LuaRuntime=None

def event(token=10):return dict(token=token,seed=7062026,level=0,position=[43,73],text='A quiet beacon.',choices=[{'type':0,'text':'Continue'},{'type':0,'text':'Wait'}])
def players():return [dict(id=i,event=event(i+10),event_seen=100) for i in [1,2]]

class EventTests(unittest.TestCase):
    def test_parser_roundtrip_unicode(self):
        s='EVENT|12|7062026|0|43,73|'+('Hello\n船|'.encode().hex())+'|0,'+('Continue;'.encode().hex())
        e=parse_event_state(s)['event'];self.assertEqual(e['text'],'Hello\n船|');self.assertEqual(e['choices'][0]['text'],'Continue;')
        self.assertIsNone(parse_event_state('EVENT|garbage'))
    def test_agreement_requires_two_distinct_votes(self):
        v=EventVote();v.sync(players(),100);r=v.round
        v.vote(1,r,1);v.vote(1,r,1);self.assertIsNone(v.ballot['agreed'])
        v.vote(2,r,1);self.assertEqual(v.prepare(1,1,r)[0],'CHOICE_1')
    def test_tie_host_only_and_event_change_resets(self):
        v=EventVote();p=players();v.sync(p,100);r=v.round
        v.vote(1,r,1);v.vote(2,r,2)
        with self.assertRaises(ValueError):v.prepare(1,1,r)
        with self.assertRaises(ValueError):v.break_tie(2,1,r)
        v.break_tie(1,1,r);self.assertEqual(v.ballot['agreed'],1)
        p[1]['event']['token']=99;v.sync(p,101)
        self.assertEqual(v.ballot['votes'],{})
        with self.assertRaises(ValueError):v.vote(1,r,1)
    def test_mismatch_stale_or_missing_disables(self):
        for kind in ['text','choices','stale','none']:
            p=players();v=EventVote()
            if kind=='text':p[1]['event']['text']='Different'
            if kind=='choices':p[1]['event']['choices'][0]['type']=2
            if kind=='stale':p[1]['event_seen']=0
            if kind=='none':p[1]['event']=None
            v.sync(p,100);self.assertIsNone(v.ballot)
    def test_room_vote_apply_uses_individual_tokens(self):
        class Sink:
            def send(self,x):pass
        r=Room();a=r.join(Sink(),'host',True);b=r.join(Sink(),'guest')
        for i in [a,b]:
            r.report(i,'BRIDGE10_READY');r.bridge_action(i,{'action':'enable','enabled':True});r.event_state(i,event(i+10))
        round_id=r.event_vote.round
        for i in [a,b]:r.event_action(i,{'action':'vote','round':round_id,'index':1})
        r.event_action(a,{'action':'apply','round':round_id})
        self.assertEqual(r.bridge.pending['op'],'CHOICE_1')
        self.assertEqual(r.bridge.pending['guards'],{str(a):a+10,str(b):b+10})
        self.assertTrue(r.event_vote.ballot['applied'])

@unittest.skipUnless(LuaRuntime,'Requires lupa')
class EventLuaTests(unittest.TestCase):
    def setUp(self):
        self.l=LuaRuntime(unpack_returned_tuples=True)
        self.l.execute('''
        callbacks={};logs={}
        function log(s) logs[#logs+1]=s end
        script={on_load=function(f) callbacks.load=f end,on_internal_event=function(e,f) callbacks[e]=f end}
        Defines={InternalEvents={ON_KEY_DOWN='key',ON_TICK='tick'},SDL={KEY_F13=124,KEY_F14=125,KEY_F15=126,KEY_1=49,KEY_9=57},Chain={PREEMPT=1,CONTINUE=0}}
        box={selectedChoice=-1}
        snapshot={token=42,count=2,box=box}
        FleetCoop10={safeCapture=function()return snapshot end}
        Hyperspace={App={world={bStartedGame=true},menu={bOpen=false},gui={bPaused=false,choiceBoxOpen=true}}}
        ''')
        self.l.execute((Path(__file__).resolve().parents[1]/'bridge.lua').read_text())
    def send(self,op,n,guard=0):
        for k in packet_keys(op,n,guard):self.l.globals().callbacks.key(k)
    def logs(self):return list(self.l.globals().logs.values())
    def test_armed_before_digit_then_transition_ack(self):
        self.send('CHOICE_1',123,42)
        self.assertIn('CHOICE_1|ARMED',self.logs()[-1])
        self.assertEqual(self.l.globals().callbacks.key(49),0)
        self.assertFalse(any('CHOICE_1|OK' in s for s in self.logs()))
        self.l.execute('snapshot.token=43;callbacks.tick()')
        self.assertIn('CHOICE_1|OK',self.logs()[-1])
    def test_stale_at_arm_or_commit_rejected(self):
        self.send('CHOICE_1',1,99)
        self.assertIn('FAILED',self.logs()[-1])
        self.send('CHOICE_1',2,42)
        self.l.execute('snapshot.token=99')
        self.assertEqual(self.l.globals().callbacks.key(49),1)
        self.assertIn('FAILED',self.logs()[-1])
    def test_unavailable_normal_choice_not_falsely_confirmed(self):
        self.send('CHOICE_2',3,42);self.l.globals().callbacks.key(50)
        self.l.execute('for i=1,121 do callbacks.tick() end')
        self.assertTrue(any('CHOICE_2|FAILED' in s for s in self.logs()))
        self.assertFalse(any('CHOICE_2|OK' in s for s in self.logs()))
    def test_capture_error_does_not_confirm_choice(self):
        self.send('CHOICE_1',4,42);self.l.globals().callbacks.key(49)
        self.l.execute('snapshot=nil;callbacks.tick()')
        self.assertFalse(any('CHOICE_1|OK' in s for s in self.logs()))

@unittest.skipUnless(LuaRuntime,'Requires lupa')
class EventCaptureTests(unittest.TestCase):
    def test_capture_encoding_epoch_and_close(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute('''
        callbacks={};logs={}
        function log(s)logs[#logs+1]=s end
        script={on_init=function(f)callbacks.init=f end,on_internal_event=function(e,f)callbacks[e]=f end}
        Defines={InternalEvents={POST_CREATE_CHOICEBOX='create',ON_TICK='tick'}}
        choices={[0]={type=0,text='Continue'},size=function()return 1 end}
        box={bOpen=true,mainText='Quiet beacon',GetChoices=function()return choices end}
        Hyperspace={Global={currentSeed=7062026.0},App={menu={bOpen=false},world={bStartedGame=true,starMap={worldLevel=0,currentLoc={loc={x=43,y=73}}}},gui={choiceBoxOpen=true,choiceBox=box}}}
        ''')
        l.execute((Path(__file__).resolve().parents[1]/'events.lua').read_text())
        l.execute('for i=1,60 do callbacks.tick() end')
        first=parse_event_state(list(l.globals().logs.values())[-1].split('[FleetCoop7] ')[1])['event']
        self.assertEqual(first['text'],'Quiet beacon')
        self.assertEqual(first['choices'][0]['text'],'Continue')
        l.execute('callbacks.create();for i=1,60 do callbacks.tick() end')
        second=parse_event_state(list(l.globals().logs.values())[-1].split('[FleetCoop7] ')[1])['event']
        self.assertNotEqual(first['token'],second['token'])
        l.execute('Hyperspace.App.gui.choiceBoxOpen=false;for i=1,60 do callbacks.tick() end')
        self.assertIn('EVENT_NONE',list(l.globals().logs.values())[-1])

class EventNetworkTests(unittest.TestCase):
    def test_tcp_votes_dispatch_and_acknowledgments(self):
        import queue,threading,time
        from fleet_link import RelayServer,RelayClient
        srv=RelayServer('127.0.0.1',port=0)
        threading.Thread(target=srv.serve_forever,daemon=True).start()
        a=b=None;q=queue.Queue()
        def wait_for(pred):
            end=time.monotonic()+3
            while time.monotonic()<end:
                try:kind,d=q.get(timeout=.1)
                except queue.Empty:continue
                if kind=='network' and d.get('type')=='state' and pred(d):return d
            self.fail('No expected state received')
        try:
            a=RelayClient('127.0.0.1','Host',q,port=srv.server_address[1],host_token=srv.host_token)
            b=RelayClient('127.0.0.1','Guest',queue.Queue(),port=srv.server_address[1])
            for i,c in enumerate([a,b],1):
                c.send({'type':'event','event':'BRIDGE10_READY'})
                c.send({'type':'bridge','action':'enable','enabled':True})
                c.send({'type':'event_state','event':event(i+40)})
            d=wait_for(lambda d:d['event_vote']['ballot'] is not None and len(d['bridge']['enabled'])==2)
            r=d['event_vote']['ballot']['round']
            for c in [a,b]:c.send({'type':'event_vote','action':'vote','round':r,'index':1})
            wait_for(lambda d:d['event_vote']['ballot']['agreed']==1)
            a.send({'type':'event_vote','action':'apply','round':r})
            d=wait_for(lambda d:d['bridge']['pending'] is not None)
            n=d['bridge']['pending']['nonce']
            for c in [a,b]:c.send({'type':'event','event':f'BRIDGE_ACK|{n}|CHOICE_1|ARMED'})
            wait_for(lambda d:len(d['bridge']['pending']['armed'])==2)
            for c in [a,b]:c.send({'type':'event','event':f'BRIDGE_ACK|{n}|CHOICE_1|OK'})
            wait_for(lambda d:d['bridge']['pending']['status']=='confirmed')
        finally:
            if a:a.close()
            if b:b.close()
            srv.shutdown();srv.server_close()
