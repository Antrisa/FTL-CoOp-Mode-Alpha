import unittest
from pathlib import Path
from interior import decode,frames,checksum
from ship_view import guard,parse_ship
import test_ships

class InteriorTests(unittest.TestCase):
    def lua(self):
        l=test_ships.ShipTests().lua()
        l.execute(Path('interior.lua').read_text())
        l.execute('''
        function vec(t,n)t.size=function()return n end;return t end
        player.iShipId=0
        player.ship.vRoomList=vec({[0]={iRoomId=0,rect={x=0,y=0,w=70,h=35}},[1]={iRoomId=1,rect={x=70,y=0,w=35,h=70}}},2)
        player.vCrewList=vec({[0]={x=21,y=14,health={first=80,second=100},bDead=false,currentShipId=0,intruder=false},[1]={x=84,y=21,health={first=50,second=100},currentShipId=0,intruder=true}},2)
        player.vSystemList=vec({[0]={roomId=0,iSystemType=3,healthState={first=2,second=4},powerState={first=1}}},1)
        ''')
        return l
    def g(self):return guard(dict(seed=7062026,level=0,x=43,y=168))
    def deliver(self,l,blocks):
        for keys in blocks:
            header=word=0
            for k in keys[1:33]:header=header*2+(k==0x7e)
            for k in keys[33:]:word=word*2+(k==0x7e)
            l.globals().FleetInterior19.receive(header>>24,header&0xffffff,word)
    def applied(self,l):return [x for x in l.globals().logs.values() if 'INTERIOR|APPLIED' in x]
    def test_capture_python_validation_and_atomic_receive(self):
        l=self.lua();value=l.globals().FleetInterior19.capture()
        rooms,crew,systems=decode(value)
        self.assertEqual(len(rooms),2);self.assertEqual(crew[0],(67,66,80,0));self.assertEqual(systems[0],(0,3,2,4,1))
        blocks=frames(value,1,self.g());self.deliver(l,blocks[:-1])
        self.assertEqual(self.applied(l),[])
        self.deliver(l,blocks[-1:]);self.assertEqual(len(self.applied(l)),1)
        self.assertTrue(l.globals().FleetInterior19.draw(145,124,440,124))
        self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
    def test_missing_reordered_corrupt_and_wrong_context_rejected(self):
        for case in ('missing','reordered','corrupt','context','sequence'):
            with self.subTest(case=case):
                l=self.lua();blocks=frames(l.globals().FleetInterior19.capture(),3,self.g())
                if case=='missing':blocks.pop(1)
                if case=='reordered':blocks[1],blocks[2]=blocks[2],blocks[1]
                if case=='corrupt':blocks[1][25]=0x7e if blocks[1][25]==0x7d else 0x7d
                if case=='context':l.execute('Hyperspace.App.world.starMap.currentLoc.loc.x=99')
                if case=='sequence':blocks[-1]=frames(l.globals().FleetInterior19.capture(),4,self.g())[-1]
                self.deliver(l,blocks);self.assertEqual(self.applied(l),[])
    def test_delayed_snapshot_persists_but_jump_clears(self):
        l=self.lua();blocks=frames(l.globals().FleetInterior19.capture(),2,self.g())
        self.deliver(l,blocks);l.execute('for i=1,901 do FleetInterior19.tick()end')
        self.assertTrue(l.globals().FleetInterior19.draw(0,0,440,124))
        self.assertIn('INTERIOR UPDATE DELAYED',list(l.globals().texts.values()))
        self.deliver(l,blocks);self.assertTrue(l.globals().FleetInterior19.draw(0,0,440,124))
        l.execute('Hyperspace.App.world.starMap.currentLoc.loc.x=99;FleetInterior19.tick()')
        self.assertFalse(l.globals().FleetInterior19.draw(0,0,440,124))
    def test_parser_and_malformed_report(self):
        value=self.lua().globals().FleetInterior19.capture()
        self.assertEqual(parse_ship('SHIP|1|28|30|7062026|0|43|168|'+value+'|END')['ship']['interior'],value)
        self.assertIsNone(parse_ship('SHIP|1|28|30|7062026|0|43|168|01000000|END'))
        for data in ('','zz','01010101','00'*600):
            with self.assertRaises(ValueError):decode(data)
    def test_capture_failure_keeps_hull_fallback(self):
        l=self.lua();l.execute('player.ship.vRoomList=nil')
        self.assertIsNone(l.globals().FleetInterior19.capture())
        l.execute('for i=1,60 do callbacks[4]()end')
        self.assertTrue(any('SHIP|1|27|30|' in x for x in l.globals().logs.values()))
    def test_bridge_dispatch_end_to_end(self):
        import test_event_vote
        t=test_event_vote.EventLuaTests();t.setUp()
        t.l.execute('script.on_init=function(f)end')
        t.l.execute(Path('interior.lua').read_text())
        # The bridge harness has an active run; supply ship context for display guard.
        t.l.execute('Hyperspace.Global={currentSeed=7062026};Hyperspace.App.world.starMap={worldLevel=0,currentLoc={loc={x=43,y=168}}}')
        value=self.lua().globals().FleetInterior19.capture()
        for keys in frames(value,7,self.g()):
            for k in keys:t.l.globals().callbacks.key(k)
        self.assertEqual(len(self.applied(t.l)),1)
        self.assertFalse(any('BRIDGE_ACK' in x for x in t.logs()))

    def test_hull_geometry_capture_and_composite_render(self):
        l=self.lua()
        l.execute("player.ship.shipImage={x=-21,y=-14,w=140,h=98};Hyperspace.ShipGraph={GetShipInfo=function(id)return {shipBox={x=7,y=7}}end}")
        value=l.globals().FleetInterior19.capture()
        self.assertEqual(bytes.fromhex(value)[:8],bytes([2,2,2,1,62,63,20,14]))
        self.assertEqual(len(decode(value)[0]),2)
        self.deliver(l,frames(value,9,self.g()))
        l.execute("FleetInterior19.draw(145,124,440,124,{path='partner-hull'})")
        self.assertEqual(list(l.globals().images.values()),['partner-hull'])
    def test_bad_hull_geometry_rejected_and_capture_falls_back(self):
        l=self.lua();value=l.globals().FleetInterior19.capture()
        raw=bytes.fromhex(value)
        bad=(bytes([2])+raw[1:4]+bytes([64,64,0,20])+raw[4:]).hex()
        with self.assertRaises(ValueError):decode(bad)
        l.execute("player.ship.shipImage={w=0,h=0}")
        self.assertEqual(bytes.fromhex(l.globals().FleetInterior19.capture())[0],1)
    def test_normal_ship_view_keeps_interior_when_hull_update_delayed(self):
        l=self.lua();value=l.globals().FleetInterior19.capture()
        l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),self.g())
        self.deliver(l,frames(value,10,self.g()))
        l.execute('for i=1,901 do callbacks[4]()end;render()')
        self.assertIn('INTERIOR UPDATE DELAYED',list(l.globals().texts.values()))
        self.assertTrue(any('PARTNER' in t and 'UPDATE DELAYED' in t for t in l.globals().texts.values()))
        l.execute('Hyperspace.App.world.starMap.currentLoc.loc.x=99;callbacks[4]()')
        self.assertFalse(l.globals().FleetInterior19.draw(0,0,440,124))
