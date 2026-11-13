import unittest
from unittest.mock import patch
from panel_status import encode_status
from input_bridge import status_packet_keys,INPUT_LOCK,send_status
import test_panel
import test_event_vote

class StatusTests(unittest.TestCase):
    def test_encode_and_game_display_expire_and_guard(self):
        players=[{'id':1,'event':{'token':123}},{'id':2,'event':{'token':999}}]
        b={'guards':{'1':123,'2':999},'votes':{'1':2,'2':2},'agreed':2}
        value,token=encode_status(1,1,players,{'enabled':[1,2]},{'ballot':b})
        l=test_panel.PanelTests().lua()
        l.execute('printed={};Graphics.freetype.easy_print=function(font,x,y,s)printed[y]=s end;callbacks[1](8)')
        l.globals().FleetPanel11.receiveStatus(value,token);l.execute('renders[1]()')
        self.assertIn('Captains 2/2',l.globals().printed[590])
        self.assertIn('You 2 | Partner 2 | Agreed 2',l.globals().printed[616])
        l.execute('state.token=124;callbacks[4]();renders[1]()')
        self.assertIn('Waiting for matching',l.globals().printed[616])
        l.execute('for i=1,901 do callbacks[4]() end;renders[1]()')
        self.assertIn('stale',l.globals().printed[590])
    def test_status_wire_is_display_only(self):
        t=test_event_vote.EventLuaTests();t.setUp();t.l.execute('FleetPanel11={receiveStatus=function(n,g)received={n,g}end}')
        for k in status_packet_keys(12345,42):t.l.globals().callbacks.key(k)
        self.assertEqual(t.l.globals().received[1],12345)
        self.assertEqual(t.l.globals().received[2],42)
        self.assertEqual(t.logs(),[])
        self.assertFalse(t.l.globals().Hyperspace.App.gui.bPaused)
    def test_low_priority_status_does_not_interleave(self):
        with INPUT_LOCK:
            with patch('input_bridge.WindowsInput') as backend:
                self.assertFalse(send_status(1,0,lambda:True));backend.assert_not_called()
    def test_status_validation_and_no_ballot(self):
        value,token=encode_status(2,1,[{'id':2}],{'enabled':[]},{})
        self.assertEqual(token,0)
        self.assertEqual((value-1)&4095,0)
        with self.assertRaises(ValueError):status_packet_keys(0,0)
        with self.assertRaises(ValueError):status_packet_keys(1,-1)
