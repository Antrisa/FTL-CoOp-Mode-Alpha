import copy
import json
import queue
import threading
import time
import unittest
from travel import Travel
from fleet_link import Room, RelayServer, RelayClient
from shared_map import parse_line
from pathlib import Path

A=parse_line(Path(__file__).with_name('real_snapshots.txt').read_text().splitlines()[0])
ORIGIN=[82,261]
TARGET=[43,168]

def players(now=100):
    return [dict(id=i,name=str(i),snapshot=copy.deepcopy(A),seen=now) for i in [1,2]]

class TravelTests(unittest.TestCase):
    def setUp(self): self.t=Travel();self.p=players()
    def propose(self): self.t.propose(1,1,self.p,TARGET,100)
    def go(self):
        self.propose();i=self.t.plan['id']
        self.t.ready(1,i,self.p,100); self.t.ready(2,i,self.p,100)
    def test_full_trip(self):
        self.go(); self.assertEqual(self.t.plan['phase'],'go')
        self.p[0]['snapshot']['position']=TARGET
        self.t.tick(self.p,101);self.assertEqual(self.t.plan['arrived'],[1])
        self.p[1]['snapshot']['position']=TARGET
        self.t.tick(self.p,102);self.assertEqual(self.t.plan['phase'],'done')
    def test_host_and_adjacency_required(self):
        with self.assertRaises(ValueError):self.t.propose(2,1,self.p,TARGET,100)
        for target in [ORIGIN,[621,405],None,[1.5,3]]:
            with self.assertRaises(ValueError): self.t.propose(1,1,self.p,target,100)
    def test_both_fresh_matching_and_same_position(self):
        for mutation in ['stale','seed','level','layout','position']:
            p=players()
            if mutation=='stale':p[1]['seen']=0
            elif mutation=='layout':p[1]['snapshot']['nodes'][0][2]=1
            elif mutation=='position':p[1]['snapshot']['position']=TARGET
            else:p[1]['snapshot'][mutation]=42
            with self.assertRaises(ValueError):self.t.propose(1,1,p,TARGET,100)
    def test_duplicate_ready_not_two_votes(self):
        self.propose();i=self.t.plan['id']
        self.t.ready(1,i,self.p,100);self.t.ready(1,i,self.p,100)
        self.assertEqual(self.t.plan['phase'],'ready')
        self.assertEqual(self.t.plan['ready'],[1])
    def test_reproposal_invalidates_old_votes(self):
        self.propose();i=self.t.plan['id'];self.t.ready(1,i,self.p,100)
        self.propose();self.assertEqual(self.t.plan['ready'],[])
        with self.assertRaises(ValueError):self.t.ready(2,i,self.p,100)
    def test_cannot_replace_released_trip(self):
        self.go()
        with self.assertRaises(ValueError):self.propose()
    def test_early_jump_cancels(self):
        self.propose();self.p[0]['snapshot']['position']=TARGET
        self.t.tick(self.p,101);self.assertIsNone(self.t.plan)
    def test_wrong_destination_cancels(self):
        self.go();self.p[0]['snapshot']['position']=[43,353]
        self.t.tick(self.p,101);self.assertIsNone(self.t.plan)
    def test_stale_disconnect_sector_change_timeout_cancel(self):
        for reason in ['stale','disconnect','sector','timeout']:
            self.t=Travel();self.p=players();self.go()
            now=101
            if reason=='stale':now=121
            if reason=='disconnect':self.p.pop()
            if reason=='sector':self.p[0]['snapshot']['level']=1
            if reason=='timeout':
                now=281
                for p in self.p:p['seen']=281
            self.t.tick(self.p,now);self.assertIsNone(self.t.plan,reason)
    def test_menu_cancels_room_plan(self):
        class Sink:
            def send(self,x):pass
        room=Room();a=room.join(Sink(),'host',True);b=room.join(Sink(),'guest')
        room.snapshot(a,A);room.snapshot(b,A)
        room.action(a,{'action':'propose','target':TARGET})
        self.assertIsNotNone(room.travel.plan)
        room.report(b,'MAIN_MENU');self.assertIsNone(room.travel.plan)
    def test_real_tcp_host_votes_and_arrivals(self):
        srv=RelayServer('127.0.0.1',port=0)
        threading.Thread(target=srv.serve_forever,daemon=True).start()
        a=b=None
        def state_until(q,predicate):
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try:kind,d=q.get(timeout=.1)
                except queue.Empty:continue
                if kind=='network' and d.get('type')=='state' and predicate(d):return d
            self.fail('Expected state not received')
        try:
            q1,q2=queue.Queue(),queue.Queue()
            # Guest connects first: host authority must NOT depend on join order.
            b=RelayClient('127.0.0.1','guest',q2,port=srv.server_address[1])
            a=RelayClient('127.0.0.1','host',q1,port=srv.server_address[1],host_token=srv.host_token)
            a.send({'type':'snapshot','snapshot':A});b.send({'type':'snapshot','snapshot':A})
            d=state_until(q1,lambda d:len(d['players'])==2 and all(p['snapshot'] for p in d['players']))
            host=next(p for p in d['players'] if p['name']=='host')['id']
            self.assertEqual(d['host_id'],host)
            a.send({'type':'travel','action':'propose','target':TARGET})
            d=state_until(q1,lambda d:d['travel']['plan'] is not None)
            i=d['travel']['plan']['id']
            for c in [a,b]:c.send({'type':'travel','action':'ready','plan_id':i})
            state_until(q1,lambda d:d['travel']['plan'] and d['travel']['plan']['phase']=='go')
            moved=copy.deepcopy(A);moved['position']=TARGET
            for c in [a,b]:c.send({'type':'snapshot','snapshot':moved})
            state_until(q1,lambda d:d['travel']['plan'] and d['travel']['plan']['phase']=='done')
        finally:
            if a:a.close()
            if b:b.close()
            srv.shutdown();srv.server_close()
