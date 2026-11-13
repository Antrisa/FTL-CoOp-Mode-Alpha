import unittest,socket,time,queue
from pathlib import Path
from fast_local import LocalCompanion
import test_interior
from ship_view import guard

class FastTests(unittest.TestCase):
    def setUp(self):
        self.q=queue.Queue();self.server=LocalCompanion(self.q.put,port=0);self.server.start()
        self.client=socket.create_connection(('127.0.0.1',self.server.port));self.client.settimeout(1)
    def tearDown(self):self.client.close();self.server.stop()
    def test_local_hello_capture_and_state(self):
        self.client.sendall(b'HELLO|1\n');self.assertEqual(self.client.recv(1024),b'HELLO|1\n')
        self.client.sendall(b'SHIP|1|28|30|7062026|0|43|168|END\n')
        ship=self.q.get(timeout=1);self.assertEqual(ship['hull'],28)
        self.server.set_snapshot(ship,guard(ship))
        response=self.client.recv(4096).decode()
        self.assertTrue(response.startswith('STATE|1|28|30|'))
        self.assertTrue(self.server.ready)
    def test_only_display_reports_accepted(self):
        self.client.sendall(b'HELLO|1\n');self.client.recv(1024)
        self.client.sendall(b'DAMAGE|enemy|100\n')
        self.assertEqual(self.client.recv(1024),b'')
        self.assertTrue(self.q.empty())
    def test_native_lua_absent_preserves_fallback(self):
        l=test_interior.InteriorTests().lua()
        l.execute(Path('fast_link.lua').read_text());l.globals().FleetFastLink.tick()
        self.assertFalse(l.globals().FleetFastLink.ready())
    def test_native_lua_snapshot_validates_and_draws(self):
        fixture=test_interior.InteriorTests();l=fixture.lua();hexdata=l.globals().FleetInterior19.capture()
        l.execute("incoming={};sent={};FleetNativeTransport={version=1,connect=function()return true end,connected=function()return true end,close=function()end,poll=function()local a=incoming;incoming={};return a end,send=function(s)sent[#sent+1]=s;return true end}")
        l.execute(Path('fast_link.lua').read_text())
        l.globals().incoming=l.table_from(['HELLO|1',f'STATE|1|28|30|{fixture.g()}|{hexdata}'])
        l.globals().FleetFastLink.tick()
        self.assertTrue(l.globals().FleetFastLink.ready())
        self.assertTrue(l.globals().FleetInterior19.draw(0,0,440,124))
        l.execute('Hyperspace.App.world.starMap.currentLoc.loc.x=99')
        self.assertFalse(l.globals().FleetInterior19.draw(0,0,440,124))
    def test_fast_capture_wrong_guard_and_corruption_rejected(self):
        fixture=test_interior.InteriorTests();l=fixture.lua();data=l.globals().FleetInterior19.capture()
        self.assertFalse(l.globals().FleetInterior19.receiveRaw(data,99))
        self.assertFalse(l.globals().FleetInterior19.receiveRaw('zz',fixture.g()))
        self.assertFalse(l.globals().FleetInterior19.receiveRaw('01000000',fixture.g()))
        self.assertFalse(l.globals().FleetInterior19.draw(0,0,440,124))
    def test_frame_validation_and_local_forward(self):
        from view_frame import validate_frame,frame_line
        frame=dict(guard=1,width=2,height=1,data='02ff0000')
        self.assertEqual(validate_frame(frame),frame)
        for bad in ['00ff0000','03ff0000','zzff0000','01ff0000']:
            with self.assertRaises(ValueError):validate_frame(dict(frame,data=bad))
        self.client.sendall(b'HELLO|1\n');self.client.recv(1024)
        self.server.set_frame(frame)
        self.assertEqual(self.client.recv(1024).decode(),frame_line(frame))
    def test_rendered_frame_routes_only_to_matching_peer(self):
        from fleet_link import Room
        from ship_view import guard
        import json,time
        class Peer:
            def __init__(self):self.messages=[]
            def send(self,raw):self.messages.append(json.loads(raw))
        a,b=Peer(),Peer();r=Room();r.members={1:(a,'a'),2:(b,'b')}
        report=dict(id=1,hull=30,maximum=30,seed=1,level=0,x=1,y=2,seen=time.time())
        r.ships={1:dict(report),2:dict(report)}
        frame=dict(guard=guard(report),width=1,height=1,data='01ff0000')
        r.view_frame(1,frame);self.assertEqual(len(b.messages),1);self.assertEqual(a.messages,[])
        r.ships[2]['x']=9;r.view_frame(1,frame);self.assertEqual(len(b.messages),1)
    def test_video_lua_receives_only_current_context(self):
        fixture=test_interior.InteriorTests();l=fixture.lua()
        l.execute("FleetNativeVideo={clear=function()end,accept=function(w,h,data)accepted={w,h,data};return true end,draw=function()return true end}")
        l.execute(Path('fast_view.lua').read_text())
        l.globals().FleetFastView.receive('VIEW|99|1|1|01ff0000')
        self.assertIsNone(l.globals().accepted)
        l.globals().FleetFastView.receive(f'VIEW|{fixture.g()}|1|1|01ff0000')
        self.assertEqual(l.globals().accepted[1],1)
        self.assertTrue(l.globals().FleetFastView.draw(0,0,440,124))
        l.execute('Hyperspace.App.world.starMap.currentLoc.loc.x=99;FleetFastView.tick()')
        self.assertFalse(l.globals().FleetFastView.draw(0,0,440,124))
    def test_two_real_relay_clients_forward_rendered_frame(self):
        from fleet_link import RelayServer,RelayClient
        from ship_view import guard
        import threading
        server=RelayServer('127.0.0.1',port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        qa,qb=queue.Queue(),queue.Queue();a=b=None
        try:
            port=server.server_address[1]
            a=RelayClient('127.0.0.1','a',qa,port=port);b=RelayClient('127.0.0.1','b',qb,port=port)
            ship=dict(id=1,hull=30,maximum=30,seed=1,level=0,x=1,y=2)
            a.send(dict(type='ship_view',ship=ship));b.send(dict(type='ship_view',ship=ship))
            end=time.monotonic()+2
            while len(server.room.ships)<2 and time.monotonic()<end:time.sleep(.01)
            self.assertEqual(len(server.room.ships),2)
            frame=dict(guard=guard(ship),width=1,height=1,data='0100ff00')
            a.send(dict(type='view_frame',frame=frame))
            got=None;end=time.monotonic()+2
            while time.monotonic()<end:
                kind,message=qb.get(timeout=1)
                if message.get('type')=='view_frame':got=message['frame'];break
            self.assertEqual(got,frame)
        finally:
            if a:a.close()
            if b:b.close()
            server.shutdown();server.server_close()

class ViewCaptureTests(unittest.TestCase):
    def test_capture_failure_recovery_and_four_hz_budget(self):
        l=test_interior.InteriorTests().lua()
        l.execute('''
        captures=0;videoSent={};works=false
        script.on_render_event=function(ev,before,after)captureFrame=before end
        Hyperspace.App.gui.shipPosition={x=100,y=100}
        Hyperspace.ships.player.ship.shipImage={x=0,y=0,w=400,h=200}
        Hyperspace.ShipGraph={GetShipInfo=function()return {shipBox={x=0,y=0}}end}
        FleetFastLink={ready=function()return true end,send=function(s)videoSent[#videoSent+1]=s end}
        FleetNativeVideo={clear=function()end,capture=function(x,y,w,h)
          assert(x>=0 and y>=80 and x+w<=1280 and y+h<=660)
          captures=captures+1
          if works then return 1,1,'01ffffff' else return nil,'No OpenGL viewport' end
        end}
        ''')
        l.execute(Path('fast_view.lua').read_text())
        l.execute('captureFrame();works=true;for i=1,60 do FleetFastView.tick();captureFrame()end')
        self.assertEqual(l.globals().captures,5);self.assertEqual(len(list(l.globals().videoSent.values())),4)
        self.assertTrue(any('VIDEO_CAPTURE_RECOVERED' in s for s in l.globals().logs.values()))
        l.execute('Hyperspace.App.gui.choiceBoxOpen=true;for i=1,30 do FleetFastView.tick();captureFrame()end')
        self.assertEqual(l.globals().captures,5)

class CompressionTests(unittest.TestCase):
    def test_compressed_roundtrip_reduces_repetitive_frame(self):
        from view_frame import pack_frame,unpack_frame
        from fleet_link import wire,decode_message
        f=dict(guard=1,width=100,height=100,data='01ffaa33'*10000)
        packed=pack_frame(f);self.assertLess(len(packed['z']),len(f['data'])//5)
        self.assertEqual(unpack_frame(packed),f)
        self.assertEqual(decode_message(wire(dict(type='view_frame',frame=f)))['frame'],f)
    def test_bomb_trailing_stream_and_invalid_encoding_refused(self):
        from view_frame import unpack_frame
        import zlib,base64
        for raw in (zlib.compress(b'a'*300000),zlib.compress(b'\x01\xff\xff\xff')+b'extra',b'notzlib'):
            f=dict(guard=1,width=1,height=1,z=base64.b64encode(raw).decode())
            with self.assertRaises(ValueError):unpack_frame(f)
