"""Optional native local channel. No input injection; read-only ship state only."""
import diagnostics as diag
import select,socket,threading,time
from collections import deque
import queue
from priority_updates import UpdateQueue,line_key
from ship_view import parse_ship

# v0.28.16: v0.28.13 set one 5 ms socket timeout for reads AND writes. A 70-80 KB
# scene frame that the game did not drain within 5 ms raised TimeoutError, the
# link was dropped and every shared fight in progress split. Reads now poll with
# select; writes may block this long before the link is declared dead.
SEND_TIMEOUT=10

class LocalCompanion:
    def __init__(self,on_ship,port=38474,on_frame=lambda frame:None,on_combat=lambda line:None,on_build=lambda version:None,on_jump=lambda line:None,on_scene=lambda scene:None,on_pause=lambda line:None):
        self.on_pause=on_pause;self.on_scene=on_scene;self.scene=None;self.on_jump=on_jump;self.on_build=on_build;self.on_combat=on_combat;self.commands=UpdateQueue(128,key=lambda data:line_key(data.decode("ascii").strip()))
        self.on_ship=on_ship;self.on_frame=on_frame;self.port=port;self.running=False
        self.server=None;self.peer=None;self.lock=threading.Lock();self.latest=None;self.frame=None
        self.last_seen=0;self.error=''
    @property
    def ready(self):return self.running and time.monotonic()-self.last_seen<3
    def start(self):
        self.server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            self.server.bind(('127.0.0.1',self.port));self.server.listen(1);self.server.settimeout(.2)
        except OSError:
            self.server.close();self.server=None;raise
        self.port=self.server.getsockname()[1];self.running=True
        threading.Thread(target=self._run,daemon=True).start()
    def send_combat(self,line):
        if not isinstance(line,str) or not line.startswith(("COMBAT|","JUMP|","PAUSE|")) or len(line)>60000 or "\n" in line:raise ValueError("combat line")
        try:self.commands.put_nowait((line+"\n").encode("ascii"))
        except queue.Full:
            self.commands.clear()
            self.commands.put_nowait(b"COMBAT|STOP|local_queue_full\n")
            diag.record('Local control queue overflow')
    def set_snapshot(self,ship,guard):
        # Source is already validated by the fleet server; validate again at local boundary.
        if ship is None:
            with self.lock:self.latest=None
            return
        from ship_view import validate_ship
        clean=validate_ship(ship)
        if type(guard)is not int or not 0<=guard<2**32:raise ValueError('guard')
        line=f"STATE|{clean['id']}|{clean['hull']}|{clean['maximum']}|{guard}|{clean.get('interior','')}\n"
        with self.lock:self.latest=(time.monotonic(),line.encode('ascii'))
    def set_scene(self,scene):
        from scene import line
        with self.lock:self.scene=(time.monotonic(),line(scene).encode("ascii"))
    def set_frame(self,frame):
        from view_frame import frame_line
        with self.lock:self.frame=(time.monotonic(),frame_line(frame).encode('ascii'))
    def stop(self):
        self.running=False;self.last_seen=0
        for sock in (self.peer,self.server):
            if sock:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                sock.close()
    def _run(self):
        while self.running:
            try:peer,_=self.server.accept()
            except socket.timeout:continue
            except OSError:break
            diag.record('Local game connected')
            self.peer=peer;peer.settimeout(SEND_TIMEOUT)
            # Bound what can queue in the OS behind a stalled game, so control
            # messages are never stuck behind megabytes of stale snapshots.
            try:peer.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,65536)
            except OSError:pass
            peer.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);buffer=b'';hello=False;last_send=0;last_report=0;scene_pending=False
            try:
                while self.running:
                    # Wait briefly for input without putting a deadline on sends.
                    data=peer.recv(65536) if select.select([peer],[],[],.005)[0] else None
                    if data==b'':
                        diag.record('Local game EOF');break
                    if data is not None:buffer+=data
                    if len(buffer)>524288:raise ValueError('local message too long')
                    while b'\n' in buffer:
                        raw,buffer=buffer.split(b'\n',1)
                        line=raw.decode('ascii')
                        if not hello:
                            if line!='HELLO|1':raise ValueError('local version mismatch')
                            with self.lock:self.commands.clear()
                            self.on_combat('COMBAT|STOP|game_reconnected')
                            hello=True;peer.sendall(b'HELLO|1\n')
                        elif line=='BUILD|2816':self.on_build(2816)
                        elif line=='SCENE_ACK':scene_pending=False
                        elif line=='PING':peer.sendall(b'PONG\n')
                        elif line.startswith('PAUSE|'):
                            from fleet_pause import parse as parse_pause
                            parse_pause(line);self.on_pause(line)
                        elif line.startswith('JUMP|'):
                            from jump_vote import parse as parse_jump
                            parse_jump(line);self.on_jump(line)
                        elif line.startswith('COMBAT|'):
                            from combat import parse
                            parse(line);self.on_combat(line)
                        elif line.startswith('SCENE|'):
                            from scene import parse
                            self.on_scene(parse(line));peer.sendall(b"SCENE_ACK\n")
                        elif line.startswith('VIEW|'):
                            from view_frame import parse_frame
                            self.on_frame(parse_frame(line))
                        elif line.startswith('SHIP|'):
                            report=parse_ship(line)
                            if report is None:raise ValueError('invalid local ship report')
                            now=time.monotonic()
                            if now-last_report>=.05:self.on_ship(report['ship']);last_report=now
                        else:raise ValueError('unsupported local message')
                        self.last_seen=time.monotonic()
                    now=time.monotonic()
                    if hello:
                        commands=[]
                        # Only a bounded batch; new control precedes unsent snapshots.
                        for _ in range(32):
                            try:commands.append(self.commands.get_nowait())
                            except queue.Empty:break
                        for command in commands:peer.sendall(command)
                    if hello and now-last_send>=.02 and not select.select([],[peer],[],0)[1]:
                        # The game is not draining its socket (hitch, loading, dragged
                        # window). Snapshots are replaceable: skip this round, keep them.
                        last_send=now
                    elif hello and now-last_send>=.02:
                        with self.lock:
                            latest=self.latest;frame=self.frame;self.frame=None;scene=None if scene_pending else self.scene
                            if scene is not None:self.scene=None
                        if scene and now-scene[0]<1:
                            peer.sendall(scene[1]);scene_pending=True
                        last_send=now
                        if frame and now-frame[0]<1:peer.sendall(frame[1])
                        if latest and now-latest[0]<1:
                            peer.sendall(latest[1]);last_send=now
            except (OSError,ValueError,UnicodeError) as exc:
                self.error=str(exc);diag.exception('Local game transport failed')
            finally:
                self.last_seen=0;peer.close();self.peer=None
        self.last_seen=0
