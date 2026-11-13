import unittest
from input_bridge import target_status,transmit,packet_keys

def state(exe=r'C:\FTL\FTLGame.exe',held=None,hwnd=1,pid=2):
    return dict(exe=exe,held=held or [],hwnd=hwnd,pid=pid)

class FocusTests(unittest.TestCase):
    def test_explicit_target_and_default(self):
        self.assertEqual(target_status(state()),'')
        self.assertTrue(target_status(state(r'C:\FTL\FTL.exe')))
        self.assertEqual(target_status(state(r'C:\FTL\FTL.exe'),r'c:\ftl\FTL.EXE'),'')
        self.assertTrue(target_status(state(r'D:\FTL\FTL.exe'),r'C:\FTL\FTL.exe'))
    def test_modifier_and_api_errors_are_distinct(self):
        self.assertIn('Ctrl',target_status(state(held=['Ctrl'])))
        self.assertEqual(target_status({'error':'OpenProcess error 5'}),'OpenProcess error 5')
    def run_transport(self,states,allowed=lambda:True,timeout=.3):
        class Backend:
            def __init__(self):self.i=0;self.sent=[]
            def inspect(self):
                s=states[min(self.i,len(states)-1)];self.i+=1;return s
            def send_key_pair(self,vk):self.sent.append(vk)
        b=Backend();now=[0];logs=[]
        def sleep(t):now[0]+=t
        try:transmit(b,packet_keys('PING',1),allowed,report=logs.append,clock=lambda:now[0],sleep=sleep,timeout=timeout)
        except RuntimeError as e:return b,logs,str(e)
        return b,logs,None
    def test_no_input_to_wrong_process(self):
        b,logs,error=self.run_transport([state(r'C:\Tools\Other.exe')])
        self.assertEqual(b.sent,[]);self.assertIn('Other.exe',error)
    def test_wait_for_ftl_then_deliver(self):
        b,logs,error=self.run_transport([state(r'C:\Other.exe'),state()])
        self.assertIsNone(error);self.assertEqual(b.sent,packet_keys('PING',1))
        self.assertIn('TARGET ACCEPTED',logs[-1])
    def test_cancel_or_focus_change_stops_delivery(self):
        b,logs,error=self.run_transport([state()],allowed=lambda:False)
        self.assertFalse(b.sent);self.assertIn('cancelled',error)
        b,logs,error=self.run_transport([state(),state(),state(hwnd=8,pid=9)])
        self.assertEqual(len(b.sent),1);self.assertIn('changed',error)
