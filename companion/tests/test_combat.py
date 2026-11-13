import unittest,time,queue,threading,socket,json
from pathlib import Path
from combat import CombatRoom,parse
from lupa.lua53 import LuaRuntime

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.r=CombatRoom();self.out=[];self.members={1:None,2:None};self.guards={1:42,2:42}
    def send(self,cid,line):self.out.append((cid,line))
    def receive(self,cid,line,now=10):self.r.receive(cid,line,1,self.members,self.guards,self.send,now)
    def start(self):
        for cid in (1,2):self.receive(cid,'COMBAT|ARM|42|enemy|player|LASER_BURST_2')
        return self.r.active['epoch']
    def test_two_matching_opt_ins_required(self):
        self.receive(1,'COMBAT|ARM|42|enemy|player|LASER_BURST_2');self.assertIsNone(self.r.active)
        self.receive(2,'COMBAT|ARM|42|different|player|LASER_BURST_2');self.assertIsNone(self.r.active)
        self.receive(2,'COMBAT|ARM|42|enemy|player|LASER_BURST_2');self.assertIsNotNone(self.r.active)
    def test_guest_shot_exactly_once_ack_replay(self):
        e=self.start();line=f'COMBAT|SHOT|{e}|1|LASER_BURST_2|35|35|10|10|90|0'
        self.receive(2,line);self.receive(2,line)
        self.assertEqual(sum(x==(1,line) for x in self.out),1)
        self.receive(1,f'COMBAT|ACK|{e}|1');self.receive(2,line,11)
        self.assertEqual(sum(x==(1,line) for x in self.out),1)
        self.assertEqual(self.out[-1],(2,f'COMBAT|ACK|{e}|1'))
    def test_retry_unacked_and_changed_identity_stops(self):
        e=self.start();line=f'COMBAT|SHOT|{e}|1|LASER_BURST_2|35|35|10|10|90|0'
        self.receive(2,line);self.receive(2,line,10.5)
        self.assertEqual(sum(x==(1,line) for x in self.out),2)
        self.receive(2,line.replace('|35|35|','|70|35|'),11);self.assertIsNone(self.r.active)
    def test_old_encounter_and_guest_state_and_unowned_weapon_rejected(self):
        e=self.start();self.out=[]
        self.receive(2,f'COMBAT|SNAP|{e}|1|0|30|0|2|')
        self.receive(2,f'COMBAT|SHOT|{e}|1|MISSILES_1|35|35|10|10|90|0')
        self.receive(2,'COMBAT|SHOT|old|1|LASER_BURST_2|35|35|10|10|90|0')
        self.assertEqual(self.out,[])
    def test_host_snapshots_monotonic(self):
        e=self.start();self.out=[];s=f'COMBAT|SNAP|{e}|2|15|30|1|2|3,2,3,2,0'
        self.receive(1,s);self.receive(1,s);self.receive(1,s.replace('|2|15|','|1|15|'))
        self.assertEqual(self.out,[(2,s)])
    def test_disconnect_stale_and_wrong_beacon_stop(self):
        for kind in ('stale','leave','beacon'):
            self.setUp();self.start()
            if kind=='leave':self.members.pop(2)
            if kind=='beacon':self.guards[2]=43
            self.r.tick(self.members,self.guards,self.send,14 if kind=='stale' else 11)
            if kind=='stale':
                self.assertIsNotNone(self.r.active)
                self.r.tick(self.members,self.guards,self.send,25)
            self.assertIsNone(self.r.active)
    def test_malformed_data_rejected(self):
        for line in ('COMBAT|SNAP|x|1|40|30|0|2|','COMBAT|SHOT|x|1|../bad|1|1|1|1|1|0','COMBAT|SHOT|x|1|LASER|nan|1|1|1|1|0','COMBAT|STOP|x\nCOMBAT|STOP|x'):
            with self.assertRaises(ValueError):parse(line)

class LuaCombatTests(unittest.TestCase):
    def lua(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute('''
        logs={};sent={};callbacks={};spawned=0;replica=false
        function log(s)logs[#logs+1]=s end
        function vec(t,n)t.size=function()return n end;return t end
        local room={iRoomId=0,rect={x=0,y=0,w=70,h=70}}
        bp={name='LASER_BURST_2',type=0}
        function ship(id)
          local s={_targetable={hostile=true},iShipId=id,myBlueprint={blueprintName=id==0 and 'PLAYER_SHIP_HARD' or 'ENEMY'},ship={hullIntegrity={first=30,second=30},vRoomList=vec({[0]=room},1),GetSelectedRoomId=function(self,x,y,flag)if x>=0 and x<70 and y>=0 and y<70 then return 0 else return -1 end end},vSystemList=vec({},0)}
          s.GetWeaponList=function()return vec({[0]={blueprint=bp}},1)end
          s.HasSystem=function()return false end
          s.GetShieldPower=function()return {first=0,second=0}end
          s.SetDestroyed=function()s.bDestroyed=true end
          return s
        end
        Hyperspace={ships={player=ship(0),enemy=ship(1)},App={world={bStartedGame=true,space={},starMap={bOpen=false}},menu={bOpen=false},gui={bPaused=false}},Blueprints={GetWeaponBlueprint=function(self,name) return bp end},Pointf=function(x,y)return {x=x,y=y}end}
        function create()spawned=spawned+1;return {}end
        Hyperspace.App.world.space.CreateLaserBlast=create;Hyperspace.App.world.space.CreateMissile=create
        FleetNativeCombat={version=4,setReplica=function(v)replica=v end}
        FleetFastLink={ready=function()return true end,send=function(s)sent[#sent+1]=s;return true end}
        FleetInterior19={contextGuard=function()return 42 end}
        Defines={Chain={CONTINUE=0,PREEMPT=1},SDL={KEY_F6=6},InternalEvents={ON_KEY_DOWN='key',PROJECTILE_FIRE='fire',DRONE_FIRE='drone_fire',DAMAGE_AREA='damage',DAMAGE_BEAM='beam',SHIELD_COLLISION_PRE='shield',JUMP_LEAVE='leave',MAIN_MENU='menu'}}
        script={on_internal_event=function(e,f)if e=='menu' then assert(debug.getinfo(f,'u').nparams==0,'MAIN_MENU requires zero parameters')end;callbacks[e]=f end,on_init=function(f)init=f end,on_load=function(f)load=f end}
        ''')
        l.execute(Path('combat.lua').read_text());return l
    def start(self,l,role):
        l.execute('callbacks.key(6);for i=1,30 do FleetCombat22.tick()end')
        l.globals().FleetCombat22.receive('COMBAT|START|testepoch|42|'+role)
    def test_unlinked_does_not_auto_start(self):
        l=self.lua();l.execute('FleetFastLink.ready=function()return false end;FleetCombat22.tick()');self.assertFalse(l.globals().replica);self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
    def test_host_duplicate_shots_spawn_only_once(self):
        l=self.lua();self.start(l,'H')
        line='COMBAT|SHOT|testepoch|1|LASER_BURST_2|35|35|10|10|90|0'
        for _ in range(2):l.globals().FleetCombat22.receive(line)
        self.assertEqual(l.globals().spawned,1)
        self.assertEqual(list(l.globals().sent.values()).count('COMBAT|ACK|testepoch|1'),2)
    def test_guest_fire_is_forwarded_not_locally_applied(self):
        l=self.lua();self.start(l,'G');self.assertTrue(l.globals().replica)
        l.execute("p={target={x=35,y=35},position={x=10,y=10},heading=90,ownerId=0,targetId=1,currentSpace=0,damage={iDamage=1,iShieldPiercing=0,fireChance=0,breachChance=0,stunChance=0,iIonDamage=0,iSystemDamage=0,iPersDamage=0,iStun=0},Kill=function()killed=true end};callbacks.fire(p,{blueprint=bp})")
        self.assertTrue(l.globals().killed);self.assertTrue(any('|SHOT|' in x for x in l.globals().sent.values()))
        self.assertEqual(l.globals().spawned,0)
        self.assertEqual(l.eval('callbacks.damage(Hyperspace.ships.enemy,nil,nil,nil,0,true)')[0],1)
    def test_guest_state_monotonic_and_wrong_epoch_ignored(self):
        l=self.lua();self.start(l,'G')
        for line in ['COMBAT|SNAP|old|1|5|30|0|0|','COMBAT|SNAP|testepoch|2|20|30|0|0|','COMBAT|SNAP|testepoch|1|29|30|0|0|']:
            l.globals().FleetCombat22.receive(line)
        self.assertEqual(l.globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,20)
    def test_timeout_pauses_and_keeps_replica_frozen_until_menu(self):
        l=self.lua();self.start(l,'G');l.execute('Hyperspace.App.gui.bPaused=false;for i=1,181 do FleetCombat22.tick()end')
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused);self.assertTrue(l.globals().replica)
        l.execute('callbacks.menu()');self.assertFalse(l.globals().replica)
    def test_waiting_setup_cannot_fall_back_to_solo_with_f6(self):
        l=self.lua();l.execute('callbacks.key(6);FleetCombat22.tick();callbacks.key(6);Hyperspace.App.gui.bPaused=false;FleetCombat22.tick()')
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
        self.assertFalse(l.globals().replica)
        self.assertIn('blocked',l.globals().FleetCombat22.status())
    def test_unsupported_setup_remains_held_until_menu(self):
        l=self.lua();l.execute("bp.type=9;bp.name='UNKNOWN';callbacks.key(6);for i=1,30 do FleetCombat22.tick()end;Hyperspace.App.gui.bPaused=false;FleetCombat22.tick()")
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
        self.assertFalse(l.globals().replica)
        self.assertIn('UNKNOWN',l.globals().FleetCombat22.status())
    def test_mod_mismatch_blocks_room_activation(self):
        from fleet_link import Room
        from ship_view import guard
        class Peer:
            def __init__(self):self.msg=[]
            def send(self,raw):self.msg.append(json.loads(raw))
        r=Room();a,b=Peer(),Peer();r.members={1:(a,'a'),2:(b,'b')};r.host_id=1
        ship=dict(id=1,hull=30,maximum=30,seed=1,level=0,x=1,y=2,seen=time.time())
        r.ships={1:ship,2:dict(ship)};r.game_build(1,2816)
        r.combat_line(1,f'COMBAT|ARM|{guard(ship)}|enemy|player|LASER_BURST_2')
        self.assertIsNone(r.combat.active);self.assertIn('both_need_mod',a.msg[-1]['line'])

    def test_spawn_failure_not_acknowledged(self):
        l=self.lua();self.start(l,'H');l.execute("Hyperspace.App.world.space.CreateLaserBlast=function()error('engine unavailable')end")
        l.globals().FleetCombat22.receive('COMBAT|SHOT|testepoch|1|LASER_BURST_2|35|35|10|10|90|0')
        self.assertNotIn('COMBAT|ACK|testepoch|1',list(l.globals().sent.values()))
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)

class TransportTests(unittest.TestCase):
    def test_local_commands_priority_and_heartbeat_without_partner(self):
        from fast_local import LocalCompanion
        q=queue.Queue();s=LocalCompanion(lambda x:None,port=0,on_combat=q.put);s.start()
        c=socket.create_connection(('127.0.0.1',s.port));c.settimeout(2)
        try:
            c.sendall(b'HELLO|1\n');self.assertEqual(c.recv(1024),b'HELLO|1\n')
            c.sendall(b'PING\n');self.assertEqual(c.recv(1024),b'PONG\n')
            self.assertEqual(q.get(timeout=2),'COMBAT|STOP|game_reconnected')
            c.sendall(b'COMBAT|ARM|42|enemy|player|LASER_BURST_2\n')
            self.assertEqual(q.get(timeout=2),'COMBAT|ARM|42|enemy|player|LASER_BURST_2')
            s.send_combat('COMBAT|START|epoch|42|H')
            self.assertEqual(c.recv(1024),b'COMBAT|START|epoch|42|H\n')
        finally:c.close();s.stop()
    def test_real_relay_two_clients_shot_and_authority(self):
        from fleet_link import RelayServer,RelayClient
        from ship_view import guard
        server=RelayServer('127.0.0.1',port=0);threading.Thread(target=server.serve_forever,daemon=True).start()
        qa,qb=queue.Queue(),queue.Queue();a=b=None
        def wait(q,kind):
            end=time.monotonic()+2
            while time.monotonic()<end:
                _,m=q.get(timeout=2)
                if m.get('type')==kind:return m
            raise AssertionError('missing '+kind)
        try:
            port=server.server_address[1]
            a=RelayClient('127.0.0.1','host',qa,port,server.host_token);b=RelayClient('127.0.0.1','guest',qb,port)
            wait(qa,'welcome');wait(qb,'welcome')
            ship=dict(id=1,hull=30,maximum=30,seed=1,level=0,x=1,y=2)
            for c in (a,b):c.send(dict(type='ship_view',ship=ship))
            end=time.monotonic()+2
            while len(server.room.ships)<2 and time.monotonic()<end:time.sleep(.01)
            for c in (a,b):c.send(dict(type='game_build',version=2816))
            end=time.monotonic()+2
            while len(server.room.mod_builds)<2 and time.monotonic()<end:time.sleep(.01)
            self.assertEqual(len(server.room.mod_builds),2)
            for c,hull in ((a,'kestrel_layout'),(b,'rock_layout')):c.send(dict(type='combat',line=f'COMBAT|ARM|{guard(ship)}|enemy|{hull}|LASER_BURST_2'))
            h=wait(qa,'combat')['line'];g=wait(qb,'combat')['line']
            self.assertTrue(h.endswith('|H'));self.assertTrue(g.endswith('|G'));e=h.split('|')[2]
            shot=f'COMBAT|SHOT|{e}|1|LASER_BURST_2|35|35|10|10|90|0'
            b.send(dict(type='combat',line=shot));self.assertEqual(wait(qa,'combat')['line'],shot)
            ack=f'COMBAT|ACK|{e}|1';a.send(dict(type='combat',line=ack));self.assertEqual(wait(qb,'combat')['line'],ack)
            snap=f'COMBAT|SNAP|{e}|1|12|30|1|2|';a.send(dict(type='combat',line=snap));self.assertEqual(wait(qb,'combat')['line'],snap)
            b.close();b=None
            self.assertIn('|STOP|',wait(qa,'combat')['line'])
        finally:
            if a:a.close()
            if b:b.close()
            server.shutdown();server.server_close()
