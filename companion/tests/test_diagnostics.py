import subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DiagnosticsTests(unittest.TestCase):
    def test_errors_and_stacks_written_without_console(self):
        with tempfile.TemporaryDirectory() as folder:
            code='''import diagnostics as d,sys,threading
d.start(sys.argv[1])
def fail():raise RuntimeError('worker_test_failure')
t=threading.Thread(target=fail,name='test-worker');t.start();t.join()
try:raise ValueError('callback_test_failure')
except ValueError:d.tk_error(*sys.exc_info())
d.mark('testing');d.dump('snapshot_test')
from async_sender import AsyncSender
class BadSocket:
 def sendall(self,data):raise OSError('socket_test_failure')
 def shutdown(self,how):pass
w=AsyncSender(BadSocket());w.send(b'test');w.thread.join(2)
assert not w.thread.is_alive()
d.stop()
'''
            p=subprocess.run([sys.executable,'-c',code,folder],cwd=ROOT,capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            log=(Path(folder)/'fleet_diagnostics.txt').read_text()
            for value in ('START v0.28.16','worker_test_failure','callback_test_failure','snapshot_test','stage=testing','socket_test_failure','Socket writer failed'):self.assertIn(value,log)
            self.assertTrue((Path(folder)/'fleet_faults.txt').exists())
    def test_watchdog_detects_stall_and_periodic_dump(self):
        import diagnostics as d
        from unittest.mock import patch
        calls=[]
        class Stop:
            count=0
            def wait(self,n):self.count+=1;return self.count>1
        with patch.object(d,'_stop',Stop()),patch.object(d,'_last_tick',0),patch.object(d.time,'monotonic',side_effect=[0,40,40,40]),patch.object(d,'dump',side_effect=calls.append):d._watch()
        self.assertTrue(any('heartbeat missing' in x for x in calls))
        self.assertTrue(any('Periodic snapshot' in x for x in calls))
