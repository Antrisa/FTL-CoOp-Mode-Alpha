import unittest,struct,base64,zlib,socket,time
import scene,enemy_effects
from combat import CombatRoom,parse
from fast_local import LocalCompanion
from fleet_link import wire,decode_message

def sample(guard=42):
    name=b'ship/kestral_base.png'
    v=struct.pack('<8f',0,0,0,0,1,1,1,1)
    raw=struct.pack('<4s4fI',b'FS26',0,0,600,300,1)+struct.pack('<I',len(name))+name+struct.pack('<I',3)+v*3
    return dict(guard=guard,data=raw.hex())
E='E26 1 1 2 C 0 human 35 70 60 100 1 0 F 0 1 50 B 0 20 O 0 80 O 1 50 R 3 20 0 1 1 END'
class SceneTests(unittest.TestCase):
    def test_wire_roundtrip(self):
        s=sample();self.assertEqual(scene.parse(scene.line(s).strip()),s)
        self.assertEqual(decode_message(wire(dict(type='scene',scene=s)))['scene'],s)
    def test_bad_and_truncated_data(self):
        s=sample()
        for value in (s['data'][:-2],s['data']+'00','ff','zz'):
            with self.assertRaises(ValueError):scene.validate(dict(guard=42,data=value))
        raw=bytearray.fromhex(s['data']);raw[4:8]=struct.pack('<f',float('nan'))
        with self.assertRaises(ValueError):scene.validate(dict(guard=42,data=raw.hex()))
    def test_assets_cannot_escape(self):
        s=sample();s['data']=s['data'].replace(b'ship/kestral_base.png'.hex(),b'../p/kestral_base.png'.hex())
        with self.assertRaises(ValueError):scene.validate(s)
    def test_decompression_bounded(self):
        z=base64.b64encode(zlib.compress(b'0'*(scene.MAX_BYTES+1))).decode()
        with self.assertRaises(ValueError):scene.unpack(dict(guard=42,z=z))
    def test_loopback_scene_and_priority_command(self):
        incoming=[];c=LocalCompanion(lambda s:None,port=0,on_scene=incoming.append);c.start()
        try:
            with socket.create_connection(('127.0.0.1',c.port)) as sock:
                sock.settimeout(2);f=sock.makefile('rb');sock.sendall(b'HELLO|1\n');self.assertEqual(f.readline(),b'HELLO|1\n')
                sock.sendall(scene.line(sample()).encode());end=time.monotonic()+1
                while not incoming and time.monotonic()<end:time.sleep(.01)
                self.assertEqual(incoming,[sample()]);self.assertEqual(f.readline(),b'SCENE_ACK\n');c.send_combat('COMBAT|STOP|test');c.set_scene(sample())
                got=[f.readline().decode().strip(),f.readline().decode().strip()]
                self.assertEqual(got[0],'COMBAT|STOP|test');self.assertEqual(scene.parse(got[1]),sample())
        finally:c.stop()
    def test_lua_context_gate_clears_scene_and_wrong_guard_is_ignored(self):
        from test_interior import InteriorTests
        from pathlib import Path
        fixture=InteriorTests();l=fixture.lua();l.execute("Defines.InternalEvents.ON_KEY_DOWN=10;Defines.SDL.KEY_F9=290")
        l.execute("enables={};accepted={};FleetNativeScene={version=6,setCrisp=function(v)end,setView=function(v)end,enable=function(v)table.insert(enables,v)end,poll=function()return nil end,accept=function(v)table.insert(accepted,v)end,draw=function()return true end};FleetFastLink={ready=function()return true end};")
        l.execute(Path('scene.lua').read_text());l.globals().FleetScene26.tick()
        l.globals().FleetScene26.receive('SCENE|99|00');self.assertEqual(len(l.globals().accepted),0)
        l.globals().FleetScene26.receive(f'SCENE|{fixture.g()}|00');self.assertEqual(len(l.globals().accepted),1)
        l.execute('Hyperspace.App.world.starMap.bOpen=true;FleetScene26.tick()')
        self.assertFalse(list(l.globals().enables.values())[-1])
    def test_real_relay_only_sends_scene_to_matching_beacon(self):
        from fleet_link import RelayServer,RelayClient
        from ship_view import guard
        import threading,queue
        server=RelayServer('127.0.0.1',port=0);threading.Thread(target=server.serve_forever,daemon=True).start()
        qa,qb=queue.Queue(),queue.Queue();a=b=None
        try:
            port=server.server_address[1];a=RelayClient('127.0.0.1','a',qa,port=port);b=RelayClient('127.0.0.1','b',qb,port=port)
            ship=dict(id=1,hull=30,maximum=30,seed=1,level=0,x=1,y=2)
            for c in (a,b):c.send(dict(type='ship_view',ship=ship))
            end=time.monotonic()+2
            while len(server.room.ships)<2 and time.monotonic()<end:time.sleep(.01)
            self.assertEqual(len(server.room.ships),2);frame=sample(guard(ship));a.send(dict(type='scene',scene=frame))
            got=None;end=time.monotonic()+2
            while time.monotonic()<end:
                kind,msg=qb.get(timeout=1)
                if msg.get('type')=='scene':got=msg['scene'];break
            self.assertEqual(got,frame)
            # The server rejects a sender scene whose beacon guard is wrong.
            before=dict(server.room.scene_seen);server.room.scene(1,sample(999));self.assertEqual(server.room.scene_seen,before)
        finally:
            if a:a.close()
            if b:b.close()
            server.shutdown();server.server_close()
class EffectsTests(unittest.TestCase):
    def test_parse(self):self.assertEqual(parse('COMBAT|EFFECT|epoch|1|'+E)[4],E)
    def test_incomplete_duplicate_and_invalid(self):
        for bad in (E.replace('C 0 human 35 70 60 100 1 0 ',''),E.replace(' END',' B 0 5 END'),E.replace('60 100','101 100'),E.replace('F 0 1 50','F 0 1 nan'),E+' END'):
            with self.assertRaises(ValueError):enemy_effects.validate(bad)
    def test_only_host_can_change_enemy_effects_and_replays_drop(self):
        r=CombatRoom();out=[];send=lambda c,s:out.append((c,s));members={1:None,2:None};guards={1:42,2:42}
        for c in members:r.receive(c,'COMBAT|ARM|42|enemy|friendly|LASER',1,members,guards,send,10)
        epoch=r.active['epoch'];out.clear();line='COMBAT|EFFECT|'+epoch+'|1|'+E
        r.receive(2,line,1,members,guards,send,10);self.assertEqual(out,[])
        r.receive(1,line,1,members,guards,send,10);self.assertEqual(out,[(2,line)])
        r.receive(1,line,1,members,guards,send,10);self.assertEqual(len(out),1)
        r.receive(1,line.replace(epoch,'other'),1,members,guards,send,10);self.assertEqual(len(out),1)
    def test_guest_lua_uses_native_effects_with_epoch_and_sequence(self):
        from test_combat import LuaCombatTests
        l=LuaCombatTests().lua();l.execute('applied={};FleetNativeEffects={apply=function(s)table.insert(applied,s);return true end}')
        l.execute('for i=1,16 do FleetCombat22.tick()end');l.globals().FleetCombat22.receive('COMBAT|START|testepoch|42|G')
        for line in ('COMBAT|EFFECT|other|1|'+E,'COMBAT|EFFECT|testepoch|1|'+E,'COMBAT|EFFECT|testepoch|1|'+E):l.globals().FleetCombat22.receive(line)
        self.assertEqual(list(l.globals().applied.values()),[E])
