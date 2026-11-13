import unittest,time
from unittest.mock import patch
from lupa.lua53 import LuaRuntime
from pathlib import Path
from cursor_sync import validate_cursor,parse_cursor,partner_cursor
from input_bridge import cursor_packet_keys,send_cursor,INPUT_LOCK
import test_event_vote

class CursorTests(unittest.TestCase):
    def players(self):
        return [dict(id=i,event=test_event_vote.event(i+10),event_seen=100,cursor=dict(x=100*i,y=200,panel=0,token=i+10,seen=100)) for i in (1,2)]
    def test_matching_events_maps_to_receiver_token(self):
        self.assertEqual(partner_cursor(self.players(),1,100),(200,200,0,11))
    def test_mismatch_stale_and_panels_hide(self):
        for kind in ['screen','stale','panel','token','event_stale']:
            p=self.players()
            if kind=='screen':p[1]['event']['text']='Different'
            if kind=='stale':p[1]['cursor']['seen']=90
            if kind=='panel':p[1]['cursor']['panel']=1
            if kind=='token':p[1]['cursor']['token']=999
            if kind=='event_stale':p[1]['event_seen']=70
            self.assertIsNone(partner_cursor(p,1,100))
    def test_menu_and_bounds(self):
        p=self.players()
        for a in p:a['cursor']['token']=0;a['event']=None
        self.assertEqual(partner_cursor(p,1,100),(200,200,0,0))
        for s in ['CURSOR|1280|0|0|0','CURSOR|-1|0|0|0','CURSOR|1|720|0|0','CURSOR|1|1|2|0']:
            self.assertIsNone(parse_cursor(s))
        self.assertIsNotNone(parse_cursor('CURSOR|1279|719|1|4294967295'))
    def test_display_packet_does_not_ack_or_act(self):
        t=test_event_vote.EventLuaTests();t.setUp()
        t.l.execute('FleetCursor14={receive=function(n,g)received={n,g}end}')
        for k in cursor_packet_keys(1279,719,1,4294967295):t.l.globals().callbacks.key(k)
        self.assertEqual(t.l.globals().received[1],1+1279+(719<<11)+(1<<21))
        self.assertEqual(t.l.globals().received[2],4294967295)
        self.assertEqual(t.logs(),[])
    def test_cursor_yields_to_input_lock(self):
        with INPUT_LOCK:
            with patch('input_bridge.WindowsInput') as backend:
                self.assertFalse(send_cursor(1,2,0,0,lambda:True));backend.assert_not_called()
    def lua(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute('''callbacks={};logs={};draws=0
        Defines={InternalEvents={ON_MOUSE_MOVE=1,ON_TICK=2},RenderEvents={MOUSE_CONTROL=1},Chain={CONTINUE=0},SDL={}}
        script={on_internal_event=function(k,f)callbacks[k]=f end,on_render_event=function(k,b,a)render=a end,on_init=function(f)end,on_load=function(f)f()end}
        log=function(s)table.insert(logs,s)end
        Hyperspace={App={menu={bOpen=false}}}
        state={token=11};FleetCoop10={safeCapture=function()return state end}
        panelOpen=false;FleetPanel11={isOpen=function()return panelOpen end}
        Graphics={GL_Color=function(...)return {}end,CSurface={GL_DrawRect=function(...)draws=draws+1 end},freetype={easy_print=function(...)end}}
        ''')
        l.execute(Path('cursor.lua').read_text());return l
    def test_receiver_context_and_expiry(self):
        l=self.lua();l.globals().FleetCursor14.receive(1+100+(200<<11),11);l.execute('render()')
        self.assertEqual(l.eval('draws'),2)
        l.execute('for i=1,181 do callbacks[2]() end;render()');self.assertEqual(l.eval('draws'),2)
        l.globals().FleetCursor14.receive(1,999);l.execute('render()');self.assertEqual(l.eval('draws'),2)
        l.globals().FleetCursor14.receive(1+(1<<21),11);l.execute('render()');self.assertEqual(l.eval('draws'),2)
    def test_local_mouse_is_only_observed(self):
        l=self.lua();self.assertEqual(l.globals().callbacks[1](500,300),0)
        l.execute('for i=1,30 do callbacks[2]() end')
        self.assertIn('CURSOR|500|300|0|11',l.eval('logs[#logs]'))
