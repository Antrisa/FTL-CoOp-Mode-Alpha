import unittest
import test_panel
from bridge_room import Bridge
from panel_status import encode_status

class LobbyTests(unittest.TestCase):
    def lua(self,host=False,command=None):
        l=test_panel.PanelTests().lua()
        val,token=encode_status(1,1 if host else 2,[{'id':1,'event':{'token':123}},{'id':2}],{'enabled':[1,2],'pending':{'status':command}},{})
        l.globals().FleetPanel11.receiveStatus(val,token)
        l.execute('printed={};Graphics.freetype.easy_print=function(font,x,y,s)printed[y]=s end;callbacks[1](8);renders[1]()')
        return l
    def test_guest_cannot_see_or_click_host_buttons(self):
        l=self.lua();self.assertIn('host applies',l.globals().printed[523])
        before=l.eval('#logs');l.execute('callbacks[2](300,525);callbacks[2](40,525)')
        self.assertEqual(l.eval('#logs'),before)
    def test_host_buttons_and_stale_role(self):
        l=self.lua(True);self.assertIn('HOST: apply',l.globals().printed[523])
        l.execute('callbacks[2](300,525)');self.assertIn('|apply|',l.eval('logs[#logs]'))
        l.execute('for i=1,901 do callbacks[4]() end;renders[1]()')
        self.assertIn('hidden',l.globals().printed[523])
    def test_pending_shows_blocked_apply(self):
        l=self.lua(True,'waiting');self.assertIn('COMMAND PENDING',l.globals().printed[523])
        self.assertIn('waiting for both',l.globals().printed[560])
        before=l.eval('#logs');l.execute('callbacks[2](300,525)');self.assertEqual(l.eval('#logs'),before)
    def test_main_menu_button_opens_lobby_without_event_actions(self):
        l=test_panel.PanelTests().lua()
        l.execute('Hyperspace.App.menu.bOpen=true;Hyperspace.App.world.bStartedGame=false;state=nil;printed={};Graphics.freetype.easy_print=function(font,x,y,s)printed[y]=s end;renders[2]()')
        self.assertIn('CO-OP',l.globals().printed[362])
        l.execute('callbacks[2](700,365);renders[2]()')
        self.assertIn('CONNECTION STATUS',l.globals().printed[138])
        before=l.eval('#logs');l.execute('callbacks[2](40,200);callbacks[2](300,525)')
        self.assertEqual(l.eval('#logs'),before)

class FailureTests(unittest.TestCase):
    def bridge(self):
        b=Bridge();b.enabled={1,2};b.loaded={1:100,2:100};b.command(1,1,[1,2],'PING',100);return b
    def test_interrupted_ping_releases_busy_command(self):
        b=self.bridge();n=b.pending['nonce'];b.ack(1,f'BRIDGE_ACK|{n}|PING|OK')
        b.delivery_failed(2,n,'PING');self.assertEqual(b.pending['status'],'failed')
        b.command(1,1,[1,2],'PING',101);self.assertEqual(b.pending['status'],'waiting')
    def test_stale_wrong_and_already_confirmed_reports_ignored(self):
        for sender,n_delta,op in [(3,0,'PING'),(2,1,'PING'),(2,0,'PAUSE')]:
            b=self.bridge();b.delivery_failed(sender,b.pending['nonce']+n_delta,op)
            self.assertEqual(b.pending['status'],'waiting')
        b=self.bridge();n=b.pending['nonce'];b.ack(1,f'BRIDGE_ACK|{n}|PING|OK');b.delivery_failed(1,n,'PING')
        self.assertEqual(b.pending['status'],'waiting')
