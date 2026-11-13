from ui_fixture import load_ui
import unittest,time
from pathlib import Path
from lupa.lua53 import LuaRuntime
from fleet_link import Room
from shared_map import parse_line
from test_event_vote import event

class PanelTests(unittest.TestCase):
    def test_server_guard_and_host_authority(self):
        class Sink:
            def __init__(self):self.messages=[]
            def send(self,x):self.messages.append(x)
        r=Room();a=r.join(Sink(),'host',True);b=r.join(Sink(),'guest')
        for i in [a,b]:
            r.report(i,'BRIDGE10_READY');r.bridge_action(i,{'action':'enable','enabled':True});r.event_state(i,event(i+10))
        r.report(a,'PANEL_ACTION|999|vote|1')
        self.assertEqual(r.event_vote.ballot['votes'],{})
        for i in [a,b]:r.report(i,f'PANEL_ACTION|{i+10}|vote|1')
        self.assertEqual(r.event_vote.ballot['agreed'],1)
        r.report(b,f'PANEL_ACTION|{b+10}|apply|0');self.assertIsNone(r.bridge.pending)
        r.report(a,f'PANEL_ACTION|{a+10}|apply|0');self.assertEqual(r.bridge.pending['op'],'CHOICE_1')
    def lua(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
        callbacks={};logs={};renders={}
        Defines={InternalEvents={ON_TICK=4,ON_KEY_DOWN=1,ON_MOUSE_L_BUTTON_DOWN=2,ON_MOUSE_L_BUTTON_UP=3},Chain={PREEMPT=1,CONTINUE=0},SDL={KEY_F8=8},RenderEvents={MOUSE_CONTROL=1,MAIN_MENU=2}}
        script={on_internal_event=function(k,f)callbacks[k]=f end,on_render_event=function(k,f,g)renders[k]=function(...)f(...);g(...)end end,on_init=function(f)end,on_load=function(f)f()end}
        log=function(s)table.insert(logs,s)end
        Hyperspace={App={world={bStartedGame=true},menu={bOpen=false}}}
        Graphics={GL_Color=function(...)return {}end,CSurface={GL_DrawRect=function(...)end},freetype={easy_measureWidth=function(font,s)return #s*8 end,easy_print=function(...)end}}
        choices={[0]={text='Continue'},[1]={text='Leave'}}
        state={token=123,count=2,content='data',box={GetChoices=function()return choices end}}
        FleetCoop10={safeCapture=function()return state end}
        ''')
        load_ui(lua);lua.execute(Path('panel.lua').read_text());return lua
    def test_click_vote_consumes_down_up_and_preserves_native_keys(self):
        l=self.lua();l.execute('callbacks[1](8);renders[1]()')
        self.assertEqual(l.eval('callbacks[2](40,200)'),1)
        self.assertEqual(l.eval('logs[#logs]'),'[FleetCoop7] PANEL_ACTION|123|vote|1')
        self.assertEqual(l.eval('callbacks[3](40,200)'),1)
        self.assertEqual(l.eval('callbacks[1](49)'),0)
        self.assertEqual(l.eval('callbacks[2](800,600)'),1)
    def test_stale_render_does_not_vote(self):
        l=self.lua();l.execute('callbacks[1](8);renders[1]();state={token=124,count=2};callbacks[2](40,200)')
        self.assertEqual(l.eval('#logs'),2)
        self.assertIn('changed',l.eval('FleetPanel11.status'))
    def test_render_failure_disables_interception(self):
        l=self.lua();l.execute('Graphics.CSurface.GL_DrawRect=function()error("test")end;renders[1]()')
        self.assertEqual(l.eval('callbacks[2](1110,690)'),0)
        self.assertIn('Panel render disabled',l.eval('logs[#logs]'))
    def test_labels_are_measured_and_clipped(self):
        l=self.lua();l.execute("printed={};Graphics.freetype.easy_print=function(font,x,y,s)table.insert(printed,{x=x,y=y,text=s})end;choices[0].text=string.rep('Wide label ',100);callbacks[1](8);renders[1]()")
        for item in l.globals().printed.values():
            width=228 if item['y']==523 and item['x'] in (38,293) else 482 if item['y']==197 else 490
            self.assertLessEqual(len(item['text'].encode())*8,width)
        self.assertTrue(any(item['text'].endswith('...') for item in l.globals().printed.values()))

    def test_log_route(self):
        self.assertEqual(parse_line('[Lua]: [FleetCoop7] PANEL_ACTION|123|vote|2  '),'PANEL_ACTION|123|vote|2')

if __name__=='__main__':unittest.main()
