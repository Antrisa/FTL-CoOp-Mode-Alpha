import copy
import queue
import threading
import time
import unittest
from shared_map import parse_line, validate_snapshot, fingerprint, compare
from fleet_link import Room, RelayServer, RelayClient, wire

LINE = '[Lua]: [FleetCoop7] SNAP|7062026|0|10,20|10,20,0:1;30,40,1:0\n'

def snap(): return parse_line(LINE)
def players(a=None,b=None):
    return [{'snapshot':a or snap(),'seen':100},{'snapshot':b or snap(),'seen':100}]

class SharedMapTests(unittest.TestCase):
    def test_real_format(self):
        s=snap()
        self.assertEqual(s['position'],[10,20])
        self.assertEqual(s['nodes'][1],[30,40,1,[0]])
        self.assertEqual(parse_line('[FleetCoop7] RUN_NEW'),'RUN_NEW')
        self.assertIsNone(parse_line('[FleetCoop7] SNAP|nope'))
    def test_layout_not_seed_only(self):
        b=snap(); b['nodes'][1][2]=0
        self.assertIn('MAP MISMATCH',compare(players(b=b),100))
        b=snap(); b['nodes'][0][3]=[]
        self.assertIn('MAP MISMATCH',compare(players(b=b),100))
    def test_order_independent(self):
        b=snap(); b['nodes']=[[30,40,1,[1]],[10,20,0,[0]]]
        self.assertEqual(fingerprint(snap()),fingerprint(b))
    def test_positions_sectors_seeds_and_staleness(self):
        self.assertIn('SAME BEACON',compare(players(),100))
        b=snap(); b['position']=[30,40]
        self.assertIn('different beacons',compare(players(b=b),100))
        b['level']=1
        self.assertIn('DIFFERENT SECTORS',compare(players(b=b),100))
        b['seed']=42
        self.assertIn('SEED MISMATCH',compare(players(b=b),100))
        a=snap(); a['seed']=42
        self.assertIn('WRONG SEED',compare(players(a=a,b=b),100))
        self.assertIn('STALE',compare(players(),121))
        self.assertIn('WAITING',compare([],100))
    def test_malformed_snapshot_rejected(self):
        for key,value in [('seed',True),('nodes',[]),('position',[9,9]),('level',-1)]:
            b=snap(); b[key]=value
            with self.assertRaises(ValueError): validate_snapshot(b)
        b=snap();b['nodes'][0][3]=[2]
        with self.assertRaises(ValueError): validate_snapshot(b)
        b=snap();b['nodes'][1][:2]=[10,20]
        with self.assertRaises(ValueError): validate_snapshot(b)
    def test_new_run_menu_and_disconnect_clear_map(self):
        class Sink:
            def send(self,data): pass
        room=Room(); i=room.join(Sink(),'Captain')
        for event in ['RUN_NEW','RUN_LOADED','MAIN_MENU','ERROR|Failed']:
            room.snapshot(i,snap()); self.assertIn(i,room.snapshots)
            room.report(i,event); self.assertNotIn(i,room.snapshots)
        room.snapshot(i,snap()); room.leave(i)
        self.assertNotIn(i,room.snapshots)
    def test_snapshot_roundtrip_over_tcp(self):
        srv=RelayServer('127.0.0.1',port=0)
        threading.Thread(target=srv.serve_forever,daemon=True).start()
        a=b=None
        try:
            q1,q2=queue.Queue(),queue.Queue()
            a=RelayClient('127.0.0.1','Alpha',q1,port=srv.server_address[1])
            b=RelayClient('127.0.0.1','Beta',q2,port=srv.server_address[1])
            a.send({'type':'snapshot','snapshot':snap()})
            b.send({'type':'snapshot','snapshot':snap()})
            deadline=time.monotonic()+3
            found=False
            while time.monotonic()<deadline:
                try: kind,state=q1.get(timeout=.1)
                except queue.Empty: continue
                if kind=='network' and 'SAME BEACON' in compare(state.get('players',[])):
                    found=True;break
            self.assertTrue(found)
        finally:
            if a:a.close()
            if b:b.close()
            srv.shutdown();srv.server_close()
    def test_version_mismatch(self):
        import socket
        srv=RelayServer('127.0.0.1',port=0)
        threading.Thread(target=srv.serve_forever,daemon=True).start()
        try:
            with socket.create_connection(srv.server_address,timeout=2) as s:
                s.sendall(wire({'type':'join','name':'v6'}))
                self.assertIn(b'Both players must use',s.recv(1024))
            self.assertEqual(srv.room.members,{})
        finally: srv.shutdown();srv.server_close()
