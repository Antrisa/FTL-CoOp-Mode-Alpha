import queue
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from fleet_link import parse_event, RelayServer, RelayClient, LogTail

class Tests(unittest.TestCase):
    def test_parse_real_lines(self):
        self.assertEqual(parse_event('[Lua]: [FleetCoop] RUN_NEW   '),'RUN_NEW')
        self.assertEqual(parse_event('[Lua]: [FleetCoop] JUMP_ARRIVE   '),'JUMP_ARRIVE')
        self.assertEqual(parse_event('[Lua]: [FleetCoop] V0_5_MOD_LOADED   '),'V0_5_MOD_LOADED')
        self.assertIsNone(parse_event('Loading Lua file: data/mv_scripts/core.lua'))
    def test_room_local(self):
        srv=RelayServer('127.0.0.1')
        thr=threading.Thread(target=srv.serve_forever,daemon=True)
        thr.start()
        out1,out2=queue.Queue(),queue.Queue()
        a=b=None
        try:
            a=RelayClient('127.0.0.1','Alpha',out1)
            b=RelayClient('127.0.0.1','Beta',out2)
            a.send({'type':'event','event':'RUN_NEW'})
            b.send({'type':'event','event':'JUMP_ARRIVE'})
            deadline=time.monotonic()+3
            observed=[]
            while time.monotonic()<deadline:
                try:
                    kind,payload=out1.get(timeout=.15)
                except queue.Empty:
                    continue
                if kind=='network' and payload.get('type')=='state':
                    observed=[(x['captain'],x['event']) for x in payload['events']]
                    if len(observed)>=2:
                        break
            self.assertIn(('Alpha','RUN_NEW'),observed)
            self.assertIn(('Beta','JUMP_ARRIVE'),observed)
        finally:
            if a:a.close()
            if b:b.close()
            srv.shutdown()
            srv.server_close()
    def test_new_line_tail(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'FTL_HS.log'
            path.write_text('[Lua]: [FleetCoop] RUN_NEW\n',encoding='utf-8')
            got=[]
            tail=LogTail(path, got.append)
            tail.start()
            try:
                time.sleep(.5)
                self.assertEqual(got,[]) # ignore stale lines
                with path.open('a',encoding='utf-8') as f:
                    f.write('[Lua]: [FleetCoop] JUMP_LEAVE   \n')
                deadline=time.monotonic()+3
                while not got and time.monotonic()<deadline:
                    time.sleep(.1)
                self.assertEqual(got,['JUMP_LEAVE'])
            finally:
                tail.stop()

if __name__=='__main__':unittest.main()
