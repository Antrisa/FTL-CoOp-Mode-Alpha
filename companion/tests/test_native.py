from ui_fixture import load_ui
import unittest
from pathlib import Path
from unittest.mock import patch
from lupa.lua53 import LuaRuntime
from fleet_link import Room
import test_event_vote

class NativeRoomTests(unittest.TestCase):
    def room(self):
        class Sink:
            def send(self,x):pass
        r=Room();a=r.join(Sink(),'host',True);b=r.join(Sink(),'peer')
        for i in [a,b]:
            r.report(i,'BRIDGE10_READY');r.bridge_action(i,{'action':'enable','enabled':True});r.event_state(i,test_event_vote.event(i+10))
        return r,a,b
    def test_matching_native_votes_apply_once(self):
        r,a,b=self.room();r.report(a,f'NATIVE_VOTE|{a+10}|1');self.assertIsNone(r.bridge.pending)
        r.report(b,f'NATIVE_VOTE|{b+10}|1');self.assertEqual(r.bridge.pending['op'],'CHOICE_1')
        n=r.bridge.pending['nonce'];r.auto_native();r.report(a,f'NATIVE_VOTE|{a+10}|1')
        self.assertEqual(r.bridge.pending['nonce'],n)
    def test_decimal_mouse_votes_from_live_logs(self):
        r,a,b=self.room()
        r.report(a,f'NATIVE_VOTE|{a+10}|1.0')
        self.assertEqual(r.event_vote.ballot['votes'][str(a)],1)
        r.report(b,f'NATIVE_VOTE|{b+10}|1.0')
        self.assertEqual(r.bridge.pending['op'],'CHOICE_1')
    def test_fractional_and_invalid_mouse_votes_rejected(self):
        for value in ['1.5','nan','inf','10','0','1e0']:
            r,a,b=self.room();r.report(a,f'NATIVE_VOTE|{a+10}|{value}')
            self.assertEqual(r.event_vote.ballot['votes'],{})
            self.assertIsNone(r.bridge.pending)

    def test_tie_is_chosen_once_from_submitted_options(self):
        r,a,b=self.room()
        with patch('fleet_link.secrets.choice',return_value=2) as choose:
            r.report(a,f'NATIVE_VOTE|{a+10}|1');r.report(b,f'NATIVE_VOTE|{b+10}|2');r.auto_native()
            choose.assert_called_once();self.assertEqual(set(choose.call_args.args[0]),{1,2})
        self.assertEqual(r.bridge.pending['op'],'CHOICE_2')
    def test_mismatch_or_one_native_vote_cannot_auto_apply(self):
        r,a,b=self.room();r.report(a,f'NATIVE_VOTE|{a+10}|1')
        r.event_action(b,dict(action='vote',round=r.event_vote.round,index=1));r.auto_native();self.assertIsNone(r.bridge.pending)
        r.report(b,'NATIVE_VOTE|999|1');self.assertIsNone(r.bridge.pending)

class NativeLuaTests(unittest.TestCase):
    def lua(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute('''callbacks={};logs={};render={};rectdraws=0
        Defines={InternalEvents={ON_MOUSE_L_BUTTON_DOWN=1,ON_MOUSE_L_BUTTON_UP=2,ON_MOUSE_R_BUTTON_DOWN=3,ON_TICK=4},Chain={CONTINUE=0,PREEMPT=1},SDL={KEY_F9=290,KEY_1=49,KEY_9=57,KEY_RETURN=13,KEY_SPACE=32},RenderEvents={CHOICE_BOX=1,MOUSE_CONTROL=2}}
        script={on_internal_event=function(k,f)callbacks[k]=f end,on_render_event=function(k,b,a)render[k]=a end}
        log=function(s)table.insert(logs,s)end
        box={potentialChoice=1,bOpen=true,choiceBoxes={[0]={x=10,y=20,w=100,h=30},[1]={x=10,y=60,w=100,h=30},size=function()return 2 end}}
        state={token=42,count=2,content='test',box=box}
        FleetCoop10={safeCapture=function()return state end}
        FleetPanel11={isOpen=function()return false end,nativeStatus=function()return {token=42,matched=true,own=1,peer=2,agreed=0,command=0},0 end}
        Hyperspace={App={world={bStartedGame=true},menu={bOpen=false},gui={choiceBoxOpen=true,choiceBox=box}}}
        Graphics={GL_Color=function(...)return {}end,CSurface={GL_DrawRect=function(...)rectdraws=rectdraws+1 end},freetype={easy_print=function(...)end,easy_measureWidth=function(f,s)return #s*8 end}}
        ''')
        load_ui(l);l.execute(Path('native_vote.lua').read_text());return l
    def test_mouse_vote_consumes_click_and_release(self):
        l=self.lua();self.assertEqual(l.globals().callbacks[1](100,100),1)
        self.assertIn('NATIVE_VOTE|42|2',l.eval('logs[#logs]'))
        self.assertEqual(l.globals().callbacks[2](),1)
    def test_float_hover_is_formatted_as_integer_and_opaque_rects_ignored(self):
        l=self.lua();l.execute('box.potentialChoice=1.0;box.choiceBoxes=io.stdout')
        l.globals().callbacks[1](100,100)
        self.assertEqual(l.eval('logs[#logs]'),'[FleetCoop7] NATIVE_VOTE|42|2')
        l.execute('render[2]()')
        self.assertEqual(l.eval('rectdraws'),6)

    def test_unhovered_click_and_keyboard_do_not_execute_locally(self):
        l=self.lua();l.execute('box.potentialChoice=-1')
        self.assertEqual(l.globals().callbacks[1](0,0),1);self.assertEqual(l.eval('#logs'),0)
        self.assertEqual(l.globals().FleetNative15.key(49),1)
        self.assertIn('NATIVE_VOTE|42|1',l.eval('logs[#logs]'))
        self.assertEqual(l.globals().FleetNative15.key(13),1)
    def test_f9_does_not_disable_voting(self):
        l=self.lua();l.execute('render[2]()');self.assertEqual(l.eval('rectdraws'),6)
        self.assertEqual(l.globals().FleetNative15.key(290),0)
        self.assertEqual(l.globals().callbacks[1](100,100),1)
    def test_bridge_commit_bypasses_vote_interceptor(self):
        t=test_event_vote.EventLuaTests();t.setUp()
        t.l.execute('FleetNative15={key=function(k)error("must not intercept guarded commit")end}')
        t.send('CHOICE_1',123,42)
        self.assertEqual(t.l.globals().callbacks.key(49),0)
