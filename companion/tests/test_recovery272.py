import unittest,time
import test_combat
from combat import CombatRoom
from fleet_link import Room
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.r=CombatRoom();self.out=[];self.members={1:None,2:None};self.guards={1:42,2:42}
        for cid in self.members:self.arm(cid,10)
        self.epoch=self.r.active['epoch'];self.out=[]
    def send(self,cid,line):self.out.append((cid,line))
    def arm(self,cid,now):self.r.receive(cid,'COMBAT|ARM|42|enemy|player|LASER_BURST_2',1,self.members,self.guards,self.send,now)
    def test_stale_display_uses_fresh_general_heartbeat(self):
        r=Room();r.members=self.members
        r.pause.reports={1:dict(guard=42,seen=time.monotonic()),2:dict(guard=42,seen=time.monotonic())}
        self.assertEqual(r.combat_guards(),self.guards)
        r.pause.reports[2]['seen']-=2
        self.assertNotIn(2,r.combat_guards())
    def test_real_beacon_change_not_masked_by_old_ship_report(self):
        r=Room();r.members=self.members;r.pause.reports={1:dict(guard=43,seen=time.monotonic())}
        r.ships={1:dict(seed=1,level=0,x=1,y=2,seen=time.time())}
        self.assertEqual(r.combat_guards()[1],43)
        r.pause.reports[1]['guard']=-1;self.assertNotIn(1,r.combat_guards())
    def test_short_loss_holds_then_resyncs_same_encounter(self):
        self.r.tick(self.members,{},self.send,12)
        self.assertTrue(any('|HOLD|' in x for _,x in self.out));self.assertIsNotNone(self.r.active)
        self.arm(1,13);self.arm(2,13);self.r.tick(self.members,self.guards,self.send,13)
        self.assertEqual(self.r.active['epoch'],self.epoch)
        self.assertEqual(sum('|SYNC|' in x for _,x in self.out),2)
    def test_hold_drops_mutations_until_reports_return(self):
        self.r.tick(self.members,{},self.send,12);self.out=[]
        self.arm(1,12);self.arm(2,12);self.out=[]
        self.r.receive(1,f'COMBAT|SNAP|{self.epoch}|1|15|30|0|0|',1,self.members,self.guards,self.send,12)
        self.assertEqual(self.out,[])
    def test_permanent_loss_and_changed_beacon_still_stop(self):
        self.r.tick(self.members,{},self.send,12);self.r.tick(self.members,{},self.send,23);self.assertIsNone(self.r.active)
        self.setUp();self.r.tick(self.members,{1:42,2:43},self.send,11);self.assertIsNone(self.r.active)
    def test_guest_hold_recovers_without_disabling_replica(self):
        h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'G')
        l.execute("for i=1,600 do if i%10==0 then FleetCombat22.receive('COMBAT|HOLD|testepoch|waiting_for_peer')end;FleetCombat22.tick()end")
        self.assertTrue(l.globals().replica);self.assertEqual(l.globals().FleetCombat22.pauseBlock(),'link')
        l.globals().FleetCombat22.receive('COMBAT|SYNC|other');self.assertEqual(l.globals().FleetCombat22.pauseBlock(),'link')
        l.globals().FleetCombat22.receive('COMBAT|SYNC|testepoch');self.assertIsNone(l.globals().FleetCombat22.pauseBlock())
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
