"""Fleet Co-op companion: connection, live status and diagnostics."""
from __future__ import annotations

import diagnostics as diag
from async_sender import AsyncSender
from priority_updates import UpdateQueue,ui_key
import json
import secrets
from travel import Travel
from bridge_room import Bridge
from event_vote import EventVote, validate_event
from input_bridge import send_ship, send_cursor, send_status, send_packet, send_choice_digit, WindowsInput, target_status
from shared_map import integer, parse_line, validate_snapshot, fingerprint, compare, SIMPLE, SHARED_SEED
import os
import queue
import re
import socket
import socketserver
import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

PORT = 38473
MAX_LINE = 524288
ACCEPTED = SIMPLE | {"V0_5_MOD_LOADED"}
MARKER = re.compile(r"\[FleetCoop\]\s+(V0_5_MOD_LOADED|RUN_NEW|RUN_LOADED|JUMP_LEAVE|JUMP_ARRIVE)\b")


def parse_event(line: str) -> str | None:
    if "[FleetCoop7]" in line:
        return parse_line(line)
    match = MARKER.search(line)
    return match.group(1) if match else None


def log_guesses() -> list[Path]:
    root = [Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)')),
            Path(os.environ.get('PROGRAMFILES',r'C:\Program Files'))]
    roots = [x/'Steam'/'steamapps'/'common'/'FTL Faster Than Light'/'FTL_HS.log' for x in root]
    return [x for x in roots if x.exists()]


def decode_message(raw):
    msg=json.loads(raw)
    if isinstance(msg,dict) and msg.get('type')=='view_frame_z':
        from view_frame import unpack_frame
        return dict(type='view_frame',frame=unpack_frame(msg.get('frame')))
    if isinstance(msg,dict) and msg.get("type")=="scene_z":
        from scene import unpack
        return dict(type="scene",scene=unpack(msg.get("scene")))
    return msg

def wire(message: dict) -> bytes:
    if message.get("type")=="scene":
        from scene import pack
        message=dict(type="scene_z",scene=pack(message["scene"]))
    if message.get('type')=='view_frame':
        from view_frame import pack_frame
        message=dict(type='view_frame_z',frame=pack_frame(message['frame']))
    return (json.dumps(message, separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8')


class Room:
    """Two-captain telemetry room. Seed enforcement lives in the installed mod."""
    def __init__(self):
        self.lock = threading.RLock()
        self.members: dict[int, tuple] = {}
        self.events = deque(maxlen=100)
        self.next_id = 1
        self.snapshots = {}
        self.seen = {}
        self.host_id = None
        self.travel = Travel()
        self.bridge = Bridge()
        self.ships={}
        self.mod_builds={}
        self.frame_seen={}
        self.scene_seen={}
        self.cursors={}
        self.event_states={}
        self.event_seen={}
        self.event_vote=EventVote()
        from combat import CombatRoom
        self.combat=CombatRoom()
        from jump_vote import JumpRoom
        self.jump=JumpRoom()
        from fleet_pause import PauseRoom
        self.pause=PauseRoom()

    def state(self):
        return {'type': 'state', 'server_time': time.time(),
                'players': [{'id': k, 'name': v[1], 'snapshot': self.snapshots.get(k), 'seen': self.seen.get(k, 0), 'mod_build':self.mod_builds.get(k,(0,0))[0], 'ship_view':self.ships.get(k), 'cursor':self.cursors.get(k), 'event':self.event_states.get(k),'event_seen':self.event_seen.get(k,0)} for k,v in self.members.items()],
                'events': list(self.events), 'host_id':self.host_id, 'travel':self.travel.public(), 'bridge':self.bridge.public(), 'event_vote':self.event_vote.public()}

    def broadcast(self):
        with self.lock:
            self.event_vote.sync(self.state()['players'],time.time())
            self.bridge.tick(self.members,time.time())
            self.pause.update(self.members,self.bridge.enabled,self.mod_builds,self.pause_send)
            self.combat.tick(self.members,self.combat_guards(),self.combat_send)
            self.travel.tick(self.state()['players'],time.time())
            self.jump.tick(self.state()['players'],self.jump_send)
            msg = wire(self.state())
            targets = [v[0] for v in self.members.values()]
            for target in targets:
                try:
                    target.send(msg)
                except (OSError, ValueError):
                    pass

    def join(self, handler, name, is_host=False):
        with self.lock:
            if len(self.members) >= 2:
                return None
            client_id = self.next_id
            self.next_id += 1
            self.members[client_id] = (handler, name[:24] or 'Captain')
            if is_host:
                self.host_id = client_id
            handler.send(wire({'type':'welcome','id':client_id}))
        self.broadcast()
        return client_id

    def panel_action(self, client_id, event):
        # Resolve the local screen token against a fresh shared ballot, never the UI's cached round.
        with self.lock:
            if client_id not in self.members:return
            try:
                _, token, action, index = event.split('|')
                if action not in {'vote','apply','tie'}:raise ValueError('Unknown panel action.')
                token=integer(token,1,4294967295);index=integer(index,0,9)
                self.event_vote.sync(self.state()['players'],time.time())
                b=self.event_vote.ballot
                if not b or b['guards'].get(str(client_id))!=token:
                    raise ValueError('Panel request rejected: both games must have the same current event.')
                self.event_action(client_id,dict(action=action,round=b['round'],index=index))
            except (ValueError,TypeError):
                self.members[client_id][0].send(wire({'type':'error','message':'Panel request rejected. Check matching events and both connections.'}))

    def pause_send(self,cid,line):
        if cid in self.members:
            try:self.members[cid][0].send(wire({'type':'pause','line':line}))
            except (OSError,ValueError):pass
    def pause_line(self,cid,line):
        with self.lock:
            try:self.pause.receive(cid,line,self.members,self.bridge.enabled,self.mod_builds,self.pause_send)
            except (ValueError,TypeError,KeyError):
                self.pause.hold('invalid_pause_message')
                self.pause.update(self.members,self.bridge.enabled,self.mod_builds,self.pause_send,force=True)

    def combat_send(self,cid,line):
        if cid in self.members:
            try:self.members[cid][0].send(wire({'type':'combat','line':line}))
            except (OSError,ValueError):pass

    def jump_send(self,cid,line):
        if cid in self.members:
            try:self.members[cid][0].send(wire({'type':'jump','line':line}))
            except OSError:pass
    def jump_line(self,cid,line):
        with self.lock:
            if len(self.members)!=2 or any(self.mod_builds.get(x,(0,0))[0]!=2816 or time.monotonic()-self.mod_builds.get(x,(0,0))[1]>5 for x in self.members):
                self.jump_send(cid,'JUMP|CANCEL|both_games_need_v0.28.16');return
            try:self.jump.receive(cid,line,self.state()['players'],self.jump_send)
            except (ValueError,TypeError,KeyError) as exc:
                self.jump.cancel(self.jump_send,list(self.members),'not_ready_'+str(exc).replace('|','_')[:90])

    def combat_guards(self):
        from ship_view import guard
        result={}
        for cid in self.members:
            report=self.pause.reports.get(cid)
            if report is not None:
                if time.monotonic()-report['seen']<1.5 and report['guard']>=0:result[cid]=report['guard']
            else:
                ship=self.ships.get(cid)
                if ship and time.time()-ship.get('seen',0)<2:result[cid]=guard(ship)
        return result

    def game_build(self,cid,version):
        if type(version)is int and version==2816:
            with self.lock:
                if cid in self.members:self.mod_builds[cid]=(version,time.monotonic())

    def combat_line(self,cid,line):
        with self.lock:
            if line=='COMBAT|STOP|game_reconnected':
                self.pause.game_reconnected(cid)
                self.mod_builds.pop(cid,None)
                self.jump.cancel(self.jump_send,list(self.members),'game_reconnected')
            if isinstance(line,str) and line.startswith('COMBAT|ARM|') and (len(self.members)!=2 or any(self.mod_builds.get(x,(0,0))[0]!=2816 or time.monotonic()-self.mod_builds.get(x,(0,0))[1]>5 for x in self.members)):
                self.combat_send(cid,'COMBAT|WAIT|both_need_mod_v0.28.16');return
            try:self.combat.receive(cid,line,self.host_id,self.members,self.combat_guards(),self.combat_send)
            except (ValueError,TypeError,KeyError):self.combat_send(cid,'COMBAT|STOP|invalid_message')

    def view_frame(self,client_id,data):
        from view_frame import validate_frame
        from ship_view import guard,context
        try:frame=validate_frame(data)
        except (ValueError,TypeError,KeyError):return
        with self.lock:
            if time.monotonic()-self.frame_seen.get(client_id,0)<.2:return
            own=self.ships.get(client_id)
            if not own or time.time()-own.get('seen',0)>2 or frame['guard']!=guard(own):return
            self.frame_seen[client_id]=time.monotonic()
            for peer,(handler,name) in self.members.items():
                other=self.ships.get(peer)
                if peer!=client_id and other and time.time()-other.get('seen',0)<=2 and context(own)==context(other):
                    handler.send(wire({'type':'view_frame','frame':frame}))

    def scene(self,client_id,data):
        from scene import validate
        from ship_view import guard,context
        try:frame=validate(data)
        except (ValueError,TypeError,KeyError):return
        with self.lock:
            now=time.monotonic()
            if now-self.scene_seen.get(client_id,0)<.025:return
            own=self.ships.get(client_id)
            if not own or time.time()-own.get('seen',0)>2 or frame['guard']!=guard(own):return
            self.scene_seen[client_id]=now
            for peer,(handler,name) in self.members.items():
                other=self.ships.get(peer)
                if peer!=client_id and other and time.time()-other.get('seen',0)<=2 and context(own)==context(other):
                    handler.send(wire({'type':'scene','scene':frame}))

    def ship_view(self,client_id,data):
        from ship_view import validate_ship
        try:clean=validate_ship(data)
        except (ValueError,TypeError,KeyError):return
        with self.lock:
            if client_id not in self.members:return
            now=time.time()
            if client_id in self.ships and now-self.ships[client_id]['seen']<.09:return
            clean['seen']=now;self.ships[client_id]=clean
            self.broadcast()

    def cursor(self,client_id,data):
        from cursor_sync import validate_cursor
        try:clean=validate_cursor(data)
        except (ValueError,TypeError,KeyError):return
        with self.lock:
            if client_id not in self.members:return
            old=self.cursors.get(client_id)
            now=time.time()
            if old and now-old['seen']<.2:return
            clean['seen']=now;self.cursors[client_id]=clean
            self.broadcast()

    def report(self, client_id, event):
        if isinstance(event,str) and event.startswith('NATIVE_VOTE|'):
            try:
                _,token,index=event.split('|')
                self.panel_action(client_id,'PANEL_ACTION|'+token+'|vote|'+index)
                with self.lock:
                    b=self.event_vote.ballot
                    if b and not b['applied'] and b['guards'].get(str(client_id))==integer(token,1,4294967295) and b['votes'].get(str(client_id))==integer(index,1,9):
                        b.setdefault('native',[]).append(str(client_id))
                self.auto_native()
            except (ValueError,TypeError):pass
            return
        if isinstance(event,str) and event.startswith('PANEL_ACTION|') and len(event)<100:
            self.panel_action(client_id,event)
            return
        with self.lock:
            if client_id in self.members and isinstance(event,str):
                if event in {'BRIDGE10_READY','V0_10_BRIDGE_LOADED'}: self.bridge.loaded[client_id]=time.time()
                if event.startswith('BRIDGE_ACK|'): self.bridge.ack(client_id,event)
                if event in {'RUN_NEW','RUN_LOADED','MAIN_MENU','V0_9_BRIDGE_LOADED','V0_10_BRIDGE_LOADED'}: self.bridge.cancel()
                if event=='BRIDGE10_READY':
                    self.broadcast()
                    return
            if client_id not in self.members or not isinstance(event, str) or len(event) > 500 or not (event in ACCEPTED or event in {'V0_9_BRIDGE_LOADED','V0_10_BRIDGE_LOADED'} or event.startswith(('ERROR|', 'SEED_FORCED|','BRIDGE_ACK|'))):
                return
            if event in {'RUN_NEW', 'RUN_LOADED', 'MAIN_MENU', 'V0_7_MOD_LOADED'} or event.startswith('ERROR|'):
                self.event_states.pop(client_id,None)
                self.event_seen.pop(client_id,None)
                self.snapshots.pop(client_id, None)
                self.seen.pop(client_id, None)
            self.events.append({'captain': self.members[client_id][1], 'event': event,
                                'time': time.strftime('%H:%M:%S', time.localtime())})
        self.broadcast()

    def snapshot(self, client_id, data):
        try:
            clean = validate_snapshot(data)
        except (ValueError, KeyError, TypeError):
            return
        with self.lock:
            if client_id not in self.members:
                return
            self.snapshots[client_id] = clean
            self.seen[client_id] = time.time()
        self.broadcast()

    def action(self, client_id, msg):
        with self.lock:
            if client_id not in self.members:
                return
            players=self.state()['players']
            try:
                action=msg.get('action')
                if action=='propose':
                    self.travel.propose(client_id,self.host_id,players,msg.get('target'),time.time())
                elif action=='ready':
                    self.travel.ready(client_id,msg.get('plan_id'),players,time.time())
                elif action=='cancel':
                    if self.travel.plan and msg.get('plan_id')==self.travel.plan['id']:
                        self.travel.cancel('Travel cancelled by '+self.members[client_id][1]+'.')
                else:
                    raise ValueError('Unknown travel action.')
            except ValueError as exc:
                self.members[client_id][0].send(wire({'type':'error','message':str(exc)}))
            self.broadcast()

    def event_state(self,client_id,data):
        try:clean=validate_event(data)
        except (ValueError,TypeError,KeyError):return
        with self.lock:
            if client_id not in self.members:return
            self.event_states[client_id]=clean;self.event_seen[client_id]=time.time()
            self.broadcast()

    def event_action(self,client_id,msg):
        with self.lock:
            if client_id not in self.members:return
            self.event_vote.sync(self.state()['players'],time.time())
            try:
                action=msg.get('action');round_id=msg.get('round')
                if action=='vote':self.event_vote.vote(client_id,round_id,msg.get('index'))
                elif action=='tie':self.event_vote.break_tie(client_id,self.host_id,round_id)
                elif action=='apply':
                    op,guards=self.event_vote.prepare(client_id,self.host_id,round_id)
                    self.bridge.command(client_id,self.host_id,self.members,op,time.time())
                    self.bridge.pending['guards']=guards
                    self.event_vote.ballot['applied']=True
                    self.event_vote.message='Choice dispatched. Both return to FTL; wait for game acknowledgments.'
                else:raise ValueError('Unknown event action.')
            except ValueError as exc:self.members[client_id][0].send(wire({'type':'error','message':str(exc)}))
            self.broadcast()

    def auto_native(self):
        with self.lock:
            self.event_vote.sync(self.state()['players'],time.time())
            b=self.event_vote.ballot
            if not b or b['applied'] or len(b['votes'])!=2:return
            if set(b.get('native',[]))!=set(b['guards']):return
            if (self.bridge.pending or {}).get('status')=='waiting':return
            if b['agreed'] is None:
                b['agreed']=secrets.choice(list(b['votes'].values()))
                self.events.append({'captain':'Fleet','event':'TIE_BREAK|choice='+str(b['agreed']), 'time':time.strftime('%H:%M:%S')})
            try:
                op,guards=self.event_vote.prepare(self.host_id,self.host_id,b['round'])
                self.bridge.command(self.host_id,self.host_id,self.members,op,time.time())
            except ValueError:return
            self.bridge.pending['guards']=guards;b['applied']=True
            self.event_vote.message='Both native votes received. Applying choice '+str(b['agreed'])+'.'
            self.broadcast()

    def bridge_action(self,client_id,msg):
        with self.lock:
            if client_id not in self.members:return
            try:
                if msg.get('action')=='enable':
                    if msg.get('enabled') is True:self.bridge.enabled.add(client_id)
                    else:self.bridge.enabled.discard(client_id)
                elif msg.get('action')=='delivery_failed':
                    self.bridge.delivery_failed(client_id,msg.get('nonce'),msg.get('op'))
                elif msg.get('action')=='command':
                    if msg.get('op') in {'PAUSE','RESUME'}:
                        self.pause_send(client_id,'PAUSE|LOCAL_'+('HOLD' if msg.get('op')=='PAUSE' else 'READY'))
                        return
                    if msg.get('op') not in {'PING'}:raise ValueError('Use the event ballot for choices.')
                    self.bridge.command(client_id,self.host_id,self.members,msg.get('op'),time.time())
                else:raise ValueError('Unknown bridge action.')
            except ValueError as exc:
                self.members[client_id][0].send(wire({'type':'error','message':str(exc)}))
            self.broadcast()

    def tick(self):
        self.auto_native()
        with self.lock:
            before=json.dumps([self.travel.public(),self.bridge.public(),self.event_vote.public()],sort_keys=True)
            self.event_vote.sync(self.state()['players'],time.time())
            self.bridge.tick(self.members,time.time())
            self.pause.update(self.members,self.bridge.enabled,self.mod_builds,self.pause_send)
            self.combat.tick(self.members,self.combat_guards(),self.combat_send)
            self.travel.tick(self.state()['players'],time.time())
            self.jump.tick(self.state()['players'],self.jump_send)
            if before!=json.dumps([self.travel.public(),self.bridge.public(),self.event_vote.public()],sort_keys=True):
                self.broadcast()

    def leave(self, client_id):
        with self.lock:
            self.combat.stop(self.combat_send,"peer_left")
            self.pause.disconnected(client_id)
            self.members.pop(client_id, None)
            self.event_states.pop(client_id,None)
            self.event_seen.pop(client_id,None)
            self.bridge.enabled.discard(client_id)
            self.bridge.loaded.pop(client_id,None)
            self.snapshots.pop(client_id, None)
            self.seen.pop(client_id, None)
            if self.host_id==client_id: self.host_id=None
        self.broadcast()


class Request(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.writer = AsyncSender(self.request,label="relay server")
        self.request.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)

    def send(self, data: bytes):
        self.writer.send(data)

    def finish(self):
        self.writer.finish()
        super().finish()

    def handle(self):
        member_id = None
        try:
            self.request.settimeout(30)
            raw = self.rfile.readline(MAX_LINE)
            if not raw.endswith(b'\n'):
                return
            hello = json.loads(raw)
            if not isinstance(hello, dict) or hello.get('type') != 'join':
                return
            if hello.get('version') != 2816:
                self.send(wire({'type':'error', 'message':'Both players must use a protocol 2816 utility (v0.28.16).'}))
                return
            name = str(hello.get('name', 'Captain')).strip()
            member_id = self.server.room.join(self, name, secrets.compare_digest(str(hello.get('host_token','')),self.server.host_token))
            if member_id is None:
                self.send(wire({'type': 'error', 'message': 'Room full: two captains maximum.'}))
                return
            self.request.settimeout(None)
            while True:
                raw = self.rfile.readline(MAX_LINE)
                if not raw or not raw.endswith(b'\n'):
                    diag.record('Relay server EOF or incomplete line; bytes='+str(len(raw)))
                    break
                try:
                    msg = decode_message(raw)
                except (ValueError, UnicodeError):
                    diag.exception('Relay server rejected message')
                    continue
                if isinstance(msg, dict) and msg.get('type') == 'event':
                    self.server.room.report(member_id, msg.get('event'))
                elif isinstance(msg, dict) and msg.get('type') == 'snapshot':
                    self.server.room.snapshot(member_id, msg.get('snapshot'))
                elif isinstance(msg,dict) and msg.get('type')=='pause':
                    self.server.room.pause_line(member_id,msg.get('line'))
                elif isinstance(msg,dict) and msg.get('type')=='game_build':
                    self.server.room.game_build(member_id,msg.get('version'))
                elif isinstance(msg,dict) and msg.get('type')=='jump':
                    self.server.room.jump_line(member_id,msg.get('line'))
                elif isinstance(msg,dict) and msg.get('type')=='combat':
                    self.server.room.combat_line(member_id,msg.get('line'))
                elif isinstance(msg,dict) and msg.get('type')=='scene':
                    self.server.room.scene(member_id,msg.get('scene'))
                elif isinstance(msg,dict) and msg.get('type')=='view_frame':
                    self.server.room.view_frame(member_id,msg.get('frame'))
                elif isinstance(msg,dict) and msg.get('type')=='ship_view':
                    self.server.room.ship_view(member_id,msg.get('ship'))
                elif isinstance(msg,dict) and msg.get('type')=='cursor':
                    self.server.room.cursor(member_id,msg.get('cursor'))
                elif isinstance(msg,dict) and msg.get('type')=='travel':
                    self.server.room.action(member_id,msg)
                elif isinstance(msg,dict) and msg.get('type')=='bridge':
                    self.server.room.bridge_action(member_id,msg)
                elif isinstance(msg,dict) and msg.get('type')=='event_state':
                    self.server.room.event_state(member_id,msg.get('event'))
                elif isinstance(msg,dict) and msg.get('type')=='event_vote':
                    self.server.room.event_action(member_id,msg)
        except (ValueError, UnicodeError, OSError):
            diag.exception('Relay server request failed')
        finally:
            diag.record('Relay server leaving member '+str(member_id))
            if member_id is not None:
                self.server.room.leave(member_id)


class RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    def __init__(self, host_ip: str, port=PORT):
        self.room = Room()
        self.host_token = secrets.token_hex(24)
        super().__init__((host_ip, port), Request)

    def handle_error(self, request, client_address):
        diag.exception('Relay request thread failed')
        super().handle_error(request,client_address)

    def service_actions(self):
        self.room.tick()


class RelayClient:
    def __init__(self, server_ip: str, name: str, outbox: queue.Queue, port=PORT, host_token="", on_realtime=None):
        self.on_realtime=on_realtime
        self.sock = socket.create_connection((server_ip, port), timeout=8)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        self.writer = AsyncSender(self.sock,label="relay client")
        self.outbox = outbox
        self.running = True
        self.send({'type': 'join', 'name': name, 'version': 2816, 'host_token':host_token})
        threading.Thread(target=self.listen, daemon=True).start()

    def send(self, msg):
        if self.running:
            self.writer.send(wire(msg))

    def listen(self):
        try:
            with self.sock.makefile('rb') as fp:
                while self.running:
                    line = fp.readline(MAX_LINE)
                    if not line or not line.endswith(b'\n'):
                        diag.record('Relay client EOF or incomplete line; bytes='+str(len(line)))
                        break
                    try:
                        msg = decode_message(line)
                    except (ValueError, UnicodeError):
                        diag.exception('Relay client rejected message')
                        continue
                    if isinstance(msg, dict):
                        if self.on_realtime and self.on_realtime(msg):continue
                        self.outbox.put(('network', msg))
        except OSError:
            diag.exception('Relay client receive failed')
        finally:
            diag.record('Relay client listener ended')
            self.running = False
            self.outbox.put(('closed', None))

    def close(self):
        self.writer.close()
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class LogTail:
    def __init__(self, path: Path, on_event):
        self.path = path
        self.on_event = on_event
        self.stop_signal = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_signal.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)

    def run(self):
        # Ignore events from prior game sessions; start the link first, then launch FTL.
        position = None
        identity = None
        fragment = b''
        while not self.stop_signal.is_set():
            try:
                st = self.path.stat()
                current_id = (st.st_dev, st.st_ino)
                if identity != current_id:
                    identity = current_id
                    position = None
                if position is None:
                    # The log already exists: tail from end, not ancient events.
                    position = st.st_size
                if st.st_size < position:
                    position = 0
                    fragment = b''
                with self.path.open('rb') as f:
                    f.seek(position)
                    new = f.read(256*1024)
                    position = f.tell()
                if new:
                    chunks = (fragment+new).split(b'\n')
                    fragment = chunks.pop()
                    for chunk in chunks:
                        event = parse_event(chunk.decode('utf-8',errors='replace'))
                        if event:
                            self.on_event(event)
                    if len(fragment)>65536:
                        fragment = b''
            except (FileNotFoundError, PermissionError, OSError):
                pass
            self.stop_signal.wait(.35)


class Window:
    def __init__(self, root):
        self.root = root
        self.queue = UpdateQueue(key=ui_key)
        self.server = None
        self.client = None
        self.watcher = None
        self.active = False
        root.title('FTL Fleet Co-op v0.28.16 — Companion')
        root.geometry('1020x880')
        root.minsize(980, 880)
        self.style=ttk.Style(root);self.style.theme_use('clam')
        root.configure(background='#101923')
        self.style.configure('.',background='#101923',foreground='#dce7ee',font=('Segoe UI',10))
        self.style.configure('TEntry',fieldbackground='#1c2b39',foreground='#edf5fa',insertcolor='#edf5fa',padding=6)
        self.style.configure('TCombobox',fieldbackground='#1c2b39',foreground='#edf5fa',padding=5)
        self.style.map('TCombobox',fieldbackground=[('readonly','#1c2b39')],foreground=[('readonly','#edf5fa')])
        self.style.configure('TButton',background='#23394c',padding=(12,7),borderwidth=0)
        self.style.map('TButton',background=[('active','#33546c')],foreground=[('disabled','#6f8493')])
        self.style.configure('Accent.TButton',background='#247b96',foreground='white')
        self.style.configure('TNotebook',borderwidth=0)
        self.style.configure('TNotebook.Tab',padding=(16,9),background='#1c2b39')
        self.style.map('TNotebook.Tab',background=[('selected','#29465a')],foreground=[('selected','#6edfff')])
        self.style.configure('Muted.TLabel',foreground='#9eb2c0')
        self.style.configure('TCheckbutton',padding=3)
        self.style.configure('TRadiobutton',padding=3)
        self.role = tk.StringVar(value='host')
        self.name = tk.StringVar(value='Captain 1')
        self.ip = tk.StringVar(value='')
        guessed = log_guesses()
        self.path = tk.StringVar(value=str(guessed[0]) if guessed else '')
        self.status = tk.StringVar(value='Install ONLY the v0.28.16 .ftl on both PCs, connect the utilities, then launch FTL.')
        self.people = tk.StringVar(value='Nobody connected yet.')
        frame = ttk.Frame(root, padding=15)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='FLEET CO-OP   /   0.28.16', font=('Segoe UI',16,'bold')).pack(anchor='w')
        ttk.Label(frame, text='Two captains. Separate ships. Shared encounters.  |  Vanilla / custom Hyperspace 1.20.0').pack(anchor='w', pady=(2,12))
        roles = ttk.Frame(frame)
        roles.pack(fill='x')
        ttk.Radiobutton(roles,text='Host',variable=self.role,value='host').pack(side='left',padx=(0,25))
        ttk.Radiobutton(roles,text='Join',variable=self.role,value='join').pack(side='left')
        fields = ttk.Frame(frame)
        fields.pack(fill='x',pady=8)
        fields.columnconfigure(0,weight=1)
        fields.columnconfigure(1,weight=1)
        ttk.Label(fields,text='Your captain name').grid(row=0,column=0,sticky='w')
        ttk.Label(fields,text="Host IP address (both players enter the host's)").grid(row=0,column=1,sticky='w')
        ttk.Entry(fields,textvariable=self.name).grid(row=1,column=0,sticky='ew',padx=(0,7))
        ttk.Entry(fields,textvariable=self.ip).grid(row=1,column=1,sticky='ew')
        ttk.Label(frame,text='FTL_HS.log (use Browse if FTL is on another drive)').pack(anchor='w',pady=(9,0))
        pathrow=ttk.Frame(frame)
        pathrow.pack(fill='x')
        ttk.Entry(pathrow,textvariable=self.path).pack(side='left',fill='x',expand=True)
        ttk.Button(pathrow,text='Browse...',command=self.browse).pack(side='left',padx=(6,0))
        controls=ttk.Frame(frame)
        controls.pack(fill='x',pady=(10,6))
        self.connectbtn=ttk.Button(controls,text='Connect fleet',style='Accent.TButton',command=self.connect)
        self.connectbtn.pack(side='left')
        # Network ping is in Diagnostics below.
        ttk.Label(frame,textvariable=self.status,wraplength=730).pack(anchor='w',pady=6)
        ttk.Separator(frame).pack(fill='x',pady=8)
        ttk.Label(frame,text='CONNECTED CAPTAINS',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(frame,textvariable=self.people).pack(anchor='w',pady=(4,10))
        self.tabs=ttk.Notebook(frame)
        self.tabs.pack(fill='both',expand=True)
        travel_frame=ttk.Frame(self.tabs,padding=5)
        events_frame=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(travel_frame,text='Fleet overview')
        self.tabs.add(events_frame,text='Event details')
        help_frame=ttk.Frame(self.tabs,padding=16);diag_frame=ttk.Frame(self.tabs,padding=16)
        self.tabs.add(help_frame,text='Controls & help');self.tabs.add(diag_frame,text='Diagnostics')
        frame=travel_frame
        self.map_status = tk.StringVar(value='WAITING — no map telemetry yet.')
        ttk.Label(frame, textvariable=self.map_status, font=('Segoe UI', 11, 'bold'), wraplength=850).pack(anchor='w')
        self.canvas = tk.Canvas(frame, height=245, background='#101b2a', highlightthickness=0)
        self.canvas.pack(fill='x', pady=8)
        self.players = []
        self.my_id = None
        self.host_id = None
        self.travel = {'plan':None,'message':'Waiting for connection.'}
        self.last_phase = None
        self.game_exe=tk.StringVar(value='')
        self.last_ship_send=0
        self.ship_busy=False
        self.interior_busy=False
        self.last_interior_send=0
        self.interior_seq=0
        self.last_cursor_send=0
        self.cursor_busy=False
        self.last_panel_status=0
        self.panel_status_busy=False
        self.network_received=0
        self.diagnostic_path=Path(__file__).resolve().with_name('bridge_debug.txt')
        self.write_debug('START v0.28.16 — no bridge activity yet.')
        from fast_local import LocalCompanion
        self.fast_local=LocalCompanion(lambda ship:self.queue.put(('fast_ship',ship)),on_frame=lambda frame:self.queue.put(('fast_frame',frame)),on_combat=lambda line:self.realtime_send('combat',line),on_build=lambda version:self.queue.put(('game_build',version)),on_jump=lambda line:self.realtime_send('jump',line),on_scene=lambda scene:self.realtime_send('scene',scene),on_pause=lambda line:self.realtime_send('pause',line))
        try:self.fast_local.start()
        except OSError as exc:
            self.write_debug('Native companion unavailable: '+str(exc))
            messagebox.showerror('Fleet Link already running or port unavailable','Close all other Fleet Link windows, then reopen this version.\n\n'+str(exc))
            raise SystemExit(1)
        self.bridge_enabled=tk.BooleanVar(value=False)
        self.bridge_allowed=threading.Event()
        self.bridge_status=tk.StringVar(value='Enable game link on both PCs. Connection test is in Diagnostics.')
        self.bridge_data={}
        self.sent_nonces=set()
        self.committed_nonces=set()
        self.event_data={}
        self.displayed_round=None
        self.bridge_stop=threading.Event()
        self.choices = {}
        self.destination = tk.StringVar()
        self.travel_status = tk.StringVar(value='Waiting for both maps.')
        self.canvas.bind('<Configure>', lambda e: self.draw_maps())
        ttk.Label(diag_frame,text='ADVANCED CONNECTION TOOLS',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,8))
        self.testbtn=ttk.Button(diag_frame,text='Send network test ping',command=self.test,state='disabled');self.testbtn.pack(anchor='w',pady=5)
        targetrow=ttk.Frame(diag_frame)
        targetrow.pack(fill='x',pady=3)
        ttk.Label(targetrow,text='FTL executable (optional):').pack(side='left')
        ttk.Entry(targetrow,textvariable=self.game_exe).pack(side='left',fill='x',expand=True,padx=5)
        ttk.Button(targetrow,text='Open debug log',command=self.open_debug).pack(side='left')
        ttk.Button(targetrow,text='Choose .exe',command=self.choose_exe).pack(side='left')
        ttk.Button(targetrow,text='Inspect focus (5s)',command=self.inspect_focus).pack(side='left',padx=5)
        inbound=ttk.Frame(frame)
        inbound.pack(fill='x',pady=4)
        ttk.Checkbutton(inbound,text='Enable game link',variable=self.bridge_enabled,command=self.enable_bridge).pack(side='left')
        for label,op in [('Pause fleet','PAUSE'),('Ready to resume','RESUME')]:
            ttk.Button(inbound,text=label,command=lambda op=op:self.bridge_command(op)).pack(side='left',padx=4)
        ttk.Label(frame,textvariable=self.bridge_status,wraplength=920).pack(anchor='w',pady=4)
        ttk.Label(frame,text='PLAY IN FTL',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(14,6))
        ttk.Label(frame,text='Click event options to vote. Click the same beacon on both maps to jump.',wraplength=900).pack(anchor='w',pady=3)
        ttk.Label(frame,text='Missile-station trades are personal. Finish both event screens, then ready together.',wraplength=900).pack(anchor='w',pady=3)
        ttk.Label(frame,text='Keep this companion running. F8 shows co-op status in the game.',style='Muted.TLabel').pack(anchor='w',pady=8)
        ttk.Button(diag_frame,text='Test in-game bridge',command=lambda:self.bridge_command('PING')).pack(anchor='w',pady=5)
        ttk.Label(diag_frame,textvariable=self.bridge_status,wraplength=850).pack(anchor='w',pady=8)
        ttk.Label(diag_frame,text='RECENT ACTIVITY' ,font=('Segoe UI',11,'bold')).pack(anchor='w')
        box=ttk.Frame(diag_frame)
        box.pack(fill='both',expand=True,pady=(4,0))
        self.listbox=tk.Listbox(box,font=('Consolas',10),height=8,background='#152330',foreground='#cbdce8',borderwidth=0,highlightthickness=0)
        self.listbox.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(box,command=self.listbox.yview)
        scroll.pack(side='right',fill='y')
        self.listbox.configure(yscrollcommand=scroll.set)
        self.event_status=tk.StringVar(value='Waiting for matching open events.')
        ttk.Label(events_frame,text='EVENT DETAILS & MANUAL FALLBACK',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(events_frame,text='Normally choose in FTL: two native votes apply automatically; a tie selects one of the voted choices. These manual controls are a fallback.',wraplength=880).pack(anchor='w',pady=6)
        self.event_text=tk.Text(events_frame,height=16,wrap='word',font=('Segoe UI',11),state='disabled',background='#152330',foreground='#dce7ee',borderwidth=0,padx=12,pady=10)
        self.event_text.pack(fill='both',expand=True)
        self.vote_choice=tk.StringVar()
        self.vote_combo=ttk.Combobox(events_frame,textvariable=self.vote_choice,state='readonly')
        self.vote_combo.pack(fill='x',pady=8)
        buttons=ttk.Frame(events_frame);buttons.pack(fill='x')
        ttk.Button(buttons,text='Cast / change my vote',command=lambda:self.send_vote('vote')).pack(side='left')
        self.host_tie_button=ttk.Button(buttons,text='Host: use my vote for tie',command=lambda:self.send_vote('tie'))
        self.host_apply_button=ttk.Button(buttons,text='Host: apply agreed choice',command=lambda:self.send_vote('apply'))
        ttk.Label(events_frame,textvariable=self.event_status,wraplength=880,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=10)
        ttk.Label(events_frame,textvariable=self.bridge_status,wraplength=880).pack(anchor='w')
        ttk.Label(events_frame,text='Personal missile sales do not use this ballot. Choose separately in FTL. A blocked shared event needs investigation; do not force-dismiss it.',wraplength=880).pack(anchor='w',pady=8)
        ttk.Label(help_frame,text='IN-GAME CONTROLS',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=(0,12))
        for key,description in [('SPACE','Pause / mark yourself ready. Both captains must be ready to resume.'),('F6','With an event open: split this beacon so each captain plays it separately. Otherwise: manual combat setup.'),('F7','Partner inspector. Opens paused; F7 or Escape closes it.'),('F8','Co-op status and manual event-voting panel.'),('F9','Balanced / your-ship detail / partner detail. Does not enable solo play.'),('F10','Crisp / smooth friendly-ship texture sampling.'),('F13-F15','Reserved for the input bridge; do not press manually.')]:
            row=ttk.Frame(help_frame);row.pack(fill='x',pady=7)
            ttk.Label(row,text=key,width=11,foreground='#6edfff',font=('Segoe UI',11,'bold')).pack(side='left',anchor='n')
            ttk.Label(row,text=description,wraplength=710).pack(side='left',anchor='n')
        ttk.Separator(help_frame).pack(fill='x',pady=15)
        ttk.Label(help_frame,text='Start here: apply this mod on both PCs, connect both companions, enable both game links, then use Start_FTL_Coop.bat. Keep the companions open.',wraplength=850).pack(anchor='w')
        ttk.Label(help_frame,text='Experimental build. If stuck, preserve both FTL_HS.log, bridge_debug.txt and fleet_diagnostics.txt. Host / Join still happens here, not inside FTL.',wraplength=850,style='Muted.TLabel').pack(anchor='w',pady=12)
        self.last_events=None
        root.after(100,self.poll)
        root.protocol('WM_DELETE_WINDOW',self.close)

    def write_debug(self,message):
        try:
            with self.diagnostic_path.open('a',encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+str(message)+'\n')
        except OSError as exc:
            self.status.set('Cannot write debug log: '+str(exc))

    def open_debug(self):
        self.write_debug('Diagnostic log opened.')
        try:os.startfile(str(self.diagnostic_path))
        except (OSError,AttributeError) as exc:
            self.status.set('Debug log: '+str(self.diagnostic_path)+' | '+str(exc))

    def browse(self):
        fn=filedialog.askopenfilename(title='Select FTL_HS.log',filetypes=[('Hyperspace log','FTL_HS.log'),('Log files','*.log'),('All files','*.*')])
        if fn:
            self.path.set(fn)

    def connect(self):
        log=Path(self.path.get().strip())
        if not log.is_file():
            messagebox.showwarning('FTL log missing','Launch FTL once and select FTL_HS.log in its installation folder.')
            return
        if log.name.lower()!='ftl_hs.log':
            messagebox.showwarning('Wrong file','Select FTL_HS.log, not an exported log or a different file.')
            return
        address=self.ip.get().strip()
        try:
            socket.inet_aton(address)
            if address.count('.')!=3:
                raise OSError('invalid format')
        except OSError:
            messagebox.showwarning('Invalid IP','Enter the host PC\'s Hamachi IPv4 address.')
            return
        self.connectbtn.configure(state='disabled')
        self.status.set('Connecting…')
        threading.Thread(target=self.connect_worker,args=(self.role.get(),address,self.name.get().strip(),log),daemon=True).start()

    def connect_worker(self,role,ip,name,log):
        try:
            if role=='host':
                self.server=RelayServer(ip) # bind ONLY to Hamachi, not public/normal LAN adapters
                threading.Thread(target=self.server.serve_forever,daemon=True).start()
                dial='127.0.0.1' if ip=='127.0.0.1' else ip
            else:
                dial=ip
            self.client=RelayClient(dial,name or 'Captain',self.queue,host_token=self.server.host_token if self.server else '',on_realtime=self.realtime_receive)
            self.watcher=LogTail(log,lambda evt:self.queue.put(('local',evt)))
            self.watcher.start()
            self.queue.put(('ok',f'Connected. Watching {log}. Resume your shared run. The game mod must be v0.28.16.'))
        except Exception as exc:
            self.queue.put(('problem',str(exc)))

    def test(self):
        if self.client and self.client.running:
            try:
                self.client.send({'type':'event','event':'LINK_TEST'})
            except OSError as exc:
                self.status.set(f'Could not send: {exc}')

    def realtime_send(self,kind,payload):
        client=getattr(self,'client',None)
        if not client or not client.running or not self.bridge_allowed.is_set():return
        try:client.send({'type':kind,'scene' if kind=='scene' else 'line':payload})
        except OSError:diag.exception('Realtime output failed')

    def realtime_receive(self,msg):
        from realtime_bridge import forward
        return forward(msg,self.fast_local,self.bridge_allowed.is_set(),
                       lambda message:self.queue.put(('bridge_result',message)))

    def poll(self):
        diag.mark('UI poll')
        now=time.monotonic()
        if now-getattr(self,'last_queue_diag',0)>=5:
            self.last_queue_diag=now
            diag.record('QUEUE ui='+str(self.queue.qsize())+' replaced='+str(self.queue.replaced)+' local='+str(self.fast_local.commands.qsize()))
        deadline=time.monotonic()+.008
        try:
            for _ in range(32):
                if time.monotonic()>=deadline:break
                kind, payload=self.queue.get_nowait()
                diag.mark('UI message '+str(kind))
                if kind=='bridge_result':
                    self.status.set(payload)
                    self.write_debug(payload)
                elif kind=='delivery_failed':
                    self.write_debug('DELIVERY FAILED: '+str(payload))
                    if self.client and self.client.running:
                        try:self.client.send(dict(type='bridge',action='delivery_failed',nonce=payload['nonce'],op=payload['op']))
                        except OSError:pass
                elif kind=='ok':
                    self.active=True
                    self.status.set(payload)
                    self.testbtn.configure(state='normal')
                elif kind=='problem':
                    self.status.set('Connection failed: '+payload+'  Check Hamachi, both PCs, and TCP port 38473.')
                    self.connectbtn.configure(state='normal')
                elif kind=='local':
                    if isinstance(payload,str) and payload.startswith(('COMBAT22|','PAUSE27|','SHIP_DIAG|','NATIVE_','CURSOR_DIAG|','PANEL_','BRIDGE_ACK|','ERROR|')):
                        self.write_debug('GAME: '+payload)
                    if self.client and self.client.running:
                        try:
                            self.client.send({'type':'ship_view','ship':payload['ship']} if isinstance(payload,dict) and payload.get('kind')=='ship_view' else {'type':'cursor','cursor':payload['cursor']} if isinstance(payload,dict) and payload.get('kind')=='cursor' else {'type':'event_state','event':payload['event']} if isinstance(payload,dict) and payload.get('kind')=='event_state' else {'type':'snapshot','snapshot':payload} if isinstance(payload, dict) else {'type':'event','event':payload})
                        except OSError:
                            pass
                elif kind=='closed':
                    diag.record('UI received relay disconnect')
                    self.status.set('Disconnected. Close and reopen the link utility to reconnect.')
                    self.testbtn.configure(state='disabled')
                    self.bridge_stop.set()
                    self.bridge_allowed.clear()
                    self.bridge_enabled.set(False)
                    self.players=[]
                    self.travel={'plan':None,'message':'Disconnected — travel cancelled.'}
                    self.my_id=None
                    self.refresh_event()
                    self.draw_maps()
                elif kind=='game_build':
                    if self.client and self.client.running:self.client.send({'type':'game_build','version':payload})
                elif kind=='fast_pause':
                    if self.client and self.client.running:self.client.send({'type':'pause','line':payload})
                elif kind=='fast_jump':
                    if self.client and self.bridge_allowed.is_set():self.client.send({'type':'jump','line':payload})
                elif kind=='fast_combat':
                    if self.client and self.bridge_allowed.is_set():self.client.send({'type':'combat','line':payload})
                elif kind=='fast_scene':
                    if self.client and self.client.running and self.bridge_allowed.is_set():self.client.send({'type':'scene','scene':payload})
                elif kind=='fast_frame':
                    if self.client and self.client.running and self.bridge_allowed.is_set():
                        self.client.send({'type':'view_frame','frame':payload})
                elif kind=='fast_ship':
                    if self.client and self.client.running and self.bridge_allowed.is_set():
                        self.client.send({'type':'ship_view','ship':payload})
                elif kind=='network':
                    if payload.get('type')=='welcome':
                        self.my_id=payload['id']
                    elif payload.get('type')=='error':
                        self.status.set(payload.get('message','Server error'))
                        self.write_debug('SERVER: '+payload.get('message','Server error'))
                    elif payload.get('type')=='pause':
                        self.fast_local.send_combat(payload.get('line',''))
                    elif payload.get('type')=='jump':
                        self.write_debug('JUMP: '+payload.get('line',''))
                        self.fast_local.send_combat(payload.get('line',''))
                    elif payload.get('type')=='combat':
                        if self.bridge_allowed.is_set():
                            self.fast_local.send_combat(payload.get('line',''))
                            if '|SNAP|' not in payload.get('line','') and '|EFFECT|' not in payload.get('line',''):self.write_debug('COMBAT: '+payload.get('line',''))
                    elif payload.get('type')=='scene':
                        if self.bridge_allowed.is_set():
                            try:self.fast_local.set_scene(payload['scene'])
                            except (ValueError,TypeError,KeyError):pass
                    elif payload.get('type')=='view_frame':
                        if self.bridge_allowed.is_set():
                            try:self.fast_local.set_frame(payload['frame'])
                            except (ValueError,TypeError,KeyError):pass
                    elif payload.get('type')=='state':
                        players=payload.get('players',[])
                        received=time.time()
                        self.network_received=time.monotonic()
                        server_now=payload.get('server_time', received)
                        for player in players:
                            player['event_seen']=received-max(0,server_now-player.get('event_seen',0))
                            if player.get('ship_view'):
                                player['ship_view']['seen']=received-max(0,server_now-player['ship_view']['seen'])
                            if player.get('cursor'):
                                player['cursor']['seen']=received-max(0,server_now-player['cursor']['seen'])
                            player['seen']=received-max(0,server_now-player.get('seen',0))
                        self.players=players
                        self.host_id=payload.get('host_id')
                        self.travel=payload.get('travel',{'plan':None,'message':''})
                        self.event_data=payload.get('event_vote',{})
                        self.refresh_event()
                        self.bridge_data=payload.get('bridge',{})
                        self.process_bridge()
                        phase=(self.travel['plan']['id'],self.travel['plan']['phase']) if self.travel.get('plan') else None
                        if phase and phase!=self.last_phase and phase[1] in ('go','done'): self.root.bell()
                        self.last_phase=phase
                        self.draw_maps()
                        self.people.set('  |  '.join(str(x.get('name','Captain'))+(' [mod 0.28.16]' if x.get('mod_build')==2816 else ' [game mod unconfirmed]') for x in players) if players else 'Nobody connected yet.')
                        events=payload.get('events',[])
                        if events != self.last_events:
                            self.last_events=events
                            self.listbox.delete(0,'end')
                            for e in events:
                                self.listbox.insert('end',f"{e.get('time','--:--:--')}  {e.get('captain','?')}: {e.get('event','?')}")
                            self.listbox.yview_moveto(1.0)
        except queue.Empty:
            pass
        except OSError as exc:
            self.status.set('Connection output stopped: '+str(exc))
            self.write_debug('NETWORK OUTPUT: '+str(exc))
        diag.mark('UI refresh')
        self.map_status.set(compare(self.players))
        self.refresh_travel()
        self.send_panel_status()
        self.update_fast_snapshot()
        if not self.bridge_allowed.is_set():self.fast_local.send_combat("COMBAT|STOP|bridge_disabled")
        self.send_partner_ship()
        self.send_partner_cursor()
        self.send_partner_interior()
        diag.mark('UI idle')
        self.root.after(33,self.poll)

    def refresh_event(self):
        for button in (self.host_tie_button,self.host_apply_button):
            if self.my_id is not None and self.my_id==self.host_id:button.pack(side='left',padx=4)
            else:button.pack_forget()
        b=self.event_data.get('ballot')
        round_id=b['round'] if b else None
        if round_id!=self.displayed_round:
            self.displayed_round=round_id
            self.event_text.configure(state='normal');self.event_text.delete('1.0','end')
            if b:
                self.event_text.insert('end',b['text']+'\n\n'+'\n\n'.join(f"{i+1}. {c['text']}"+(" [unavailable to one or both ships]" if c['type']==1 else "") for i,c in enumerate(b['choices'])))
                self.vote_combo.configure(values=[f"{i+1}. {c['text'][:100]}"+(" [unavailable]" if c['type']==1 else "") for i,c in enumerate(b['choices'])])
                self.vote_combo.current(0)
            else:self.vote_combo.configure(values=[]);self.vote_choice.set('')
            self.event_text.configure(state='disabled')
        message=self.event_data.get('message','Waiting for event telemetry.')
        if b:
            names={str(p['id']):p['name'] for p in self.players}
            votes=', '.join(f"{names.get(i,'Captain')}: option {v}" for i,v in b['votes'].items()) or 'No votes yet'
            message=votes+' | Agreed: '+str(b['agreed'] or 'none')+'\n'+message
        self.event_status.set(message)

    def send_vote(self,action):
        b=self.event_data.get('ballot')
        if not b or not self.client or not self.client.running:return
        try:self.client.send({'type':'event_vote','action':action,'round':b['round'],'index':self.vote_combo.current()+1})
        except OSError as exc:self.status.set(str(exc))

    def choose_exe(self):
        fn=filedialog.askopenfilename(title='Select the actual FTL game executable (not FTL Manager)',initialdir=str(Path(self.path.get()).parent),filetypes=[('Windows executable','*.exe')])
        if fn:self.game_exe.set(fn)

    def inspect_focus(self):
        expected=self.game_exe.get().strip()
        self.status.set('Inspecting in 5 seconds: click your FTL game window. This sends NO keys.')
        def worker():
            time.sleep(5)
            try:
                state=WindowsInput().inspect()
                reason=target_status(state,expected)
                self.queue.put(('bridge_result',f"FOCUS CHECK: {state.get('exe','unknown')} | PID {state.get('pid','?')} | {reason or 'FTL target accepted; modifiers released.'}"))
            except Exception as exc:self.queue.put(('bridge_result',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def enable_bridge(self):
        if not self.client or not self.client.running:
            self.bridge_enabled.set(False)
            return
        if self.bridge_enabled.get():self.bridge_allowed.set()
        else:self.bridge_allowed.clear()
        try:self.client.send({'type':'bridge','action':'enable','enabled':self.bridge_enabled.get()})
        except OSError as exc:self.status.set(str(exc))

    def bridge_command(self,op):
        if self.client and self.client.running:
            try:self.client.send({'type':'bridge','action':'command','op':op})
            except OSError as exc:self.status.set(str(exc))

    def update_fast_snapshot(self):
        from ship_view import partner_ship
        if not self.bridge_allowed.is_set() or time.monotonic()-self.network_received>5:
            self.fast_local.set_snapshot(None,0);return
        target=partner_ship(self.players,self.my_id,time.time())
        peer=next((p.get('ship_view') for p in self.players if p['id']!=self.my_id),None)
        self.fast_local.set_snapshot(peer if target else None,target[3] if target else 0)

    def send_partner_ship(self):
        if self.fast_local.ready:return
        from ship_view import partner_ship
        now=time.monotonic()
        if self.ship_busy or now-self.last_ship_send<3:return
        if not self.client or not self.client.running or not self.bridge_allowed.is_set():return
        if now-self.network_received>5 or (self.bridge_data.get('pending') or {}).get('status')=='waiting':return
        target=partner_ship(self.players,self.my_id,time.time())
        if target is None:return
        self.last_ship_send=now;self.ship_busy=True
        expected=self.game_exe.get().strip()
        def allowed():
            return self.bridge_allowed.is_set() and self.client.running and time.monotonic()-self.network_received<5 and (self.bridge_data.get('pending') or {}).get('status')!='waiting'
        def worker():
            try:send_ship(*target,allowed=allowed,expected_exe=expected)
            except Exception as exc:self.queue.put(('bridge_result','Ship view update skipped: '+str(exc)))
            finally:self.ship_busy=False
        threading.Thread(target=worker,daemon=True).start()

    def send_partner_interior(self):
        if self.fast_local.ready:return
        from ship_view import partner_ship, context
        from interior import send_interior
        now=time.monotonic()
        if self.interior_busy or now-self.last_interior_send<1.5:return
        if not self.client or not self.client.running or not self.bridge_allowed.is_set():return
        if now-self.network_received>5 or (self.bridge_data.get('pending') or {}).get('status')=='waiting':return
        target=partner_ship(self.players,self.my_id,time.time())
        peer=next((p.get('ship_view') for p in self.players if p['id']!=self.my_id),None)
        if target is None or not peer or not peer.get('interior'):return
        value=peer['interior'];ctx=context(peer);guard=target[3]
        self.interior_seq=self.interior_seq%16777215+1
        seq=self.interior_seq;self.interior_busy=True
        expected=self.game_exe.get().strip()
        def allowed():
            if not self.bridge_allowed.is_set() or not self.client.running or time.monotonic()-self.network_received>5:return False
            if (self.bridge_data.get('pending') or {}).get('status')=='waiting':return False
            current=next((p.get('ship_view') for p in self.players if p['id']!=self.my_id),None)
            return current is not None and context(current)==ctx and time.time()-current.get('seen',0)<=5
        def worker():
            try:
                if send_interior(value,seq,guard,allowed,expected):
                    self.last_interior_send=time.monotonic()
                    self.queue.put(('bridge_result',f'Interior snapshot {seq} sent; check game APPLIED log for confirmation.'))
            except Exception as exc:
                self.last_interior_send=time.monotonic()
                self.queue.put(('bridge_result','Interior update skipped: '+str(exc)))
            finally:self.interior_busy=False
        threading.Thread(target=worker,daemon=True).start()

    def send_partner_cursor(self):
        from cursor_sync import partner_cursor
        now=time.monotonic()
        if self.cursor_busy or now-self.last_cursor_send<1.25:return
        if not self.client or not self.client.running or not self.bridge_allowed.is_set():return
        if now-self.network_received>3 or (self.bridge_data.get('pending') or {}).get('status')=='waiting':return
        target=partner_cursor(self.players,self.my_id,time.time())
        if target is None:return
        self.last_cursor_send=now;self.cursor_busy=True
        expected=self.game_exe.get().strip()
        def allowed():
            return self.bridge_allowed.is_set() and self.client.running and time.monotonic()-self.network_received<3 and (self.bridge_data.get('pending') or {}).get('status')!='waiting'
        def worker():
            try:send_cursor(*target,allowed=allowed,expected_exe=expected)
            except Exception:pass
            finally:self.cursor_busy=False
        threading.Thread(target=worker,daemon=True).start()

    def send_panel_status(self):
        from panel_status import encode_status
        now=time.monotonic()
        if self.panel_status_busy or now-self.last_panel_status<5:return
        if not self.bridge_allowed.is_set() or not self.client or not self.client.running:return
        if now-self.network_received>10:return
        payload,token=encode_status(self.my_id,self.host_id,self.players,self.bridge_data,self.event_data)
        expected=self.game_exe.get().strip()
        self.last_panel_status=now;self.panel_status_busy=True
        def allowed():
            return self.bridge_allowed.is_set() and self.client.running and time.monotonic()-self.network_received<10
        def worker():
            try:send_status(payload,token,allowed,expected)
            except Exception:pass # optional display update; stale badge replaces old data
            finally:self.panel_status_busy=False
        threading.Thread(target=worker,daemon=True).start()

    def process_bridge(self):
        p=self.bridge_data.get('pending')
        if not p:
            self.bridge_status.set('Bridge enabled: '+str(len(self.bridge_data.get('enabled',[])))+'/2. Host: Test bridge, then BOTH return to FTL.')
            return
        self.bridge_status.set(f"{p['op']}: {p['status'].upper()} | In-game acknowledgments: {len(p['acks'])}/2. Return to FTL for delivery.")
        if p['status']!='waiting':
            self.bridge_stop.set()
            return
        if not self.bridge_allowed.is_set() or self.my_id not in p['members']:return
        if p['op'].startswith('CHOICE_') and self.my_id in p.get('armed',[]) and p['nonce'] not in self.committed_nonces:
            self.committed_nonces.add(p['nonce'])
            expected=self.game_exe.get().strip();stop=self.bridge_stop
            def commit():
                try:
                    send_choice_digit(int(p['op'].split('_')[1]),lambda:self.bridge_allowed.is_set() and not stop.is_set(),expected,lambda m:self.queue.put(('bridge_result',m)))
                    self.queue.put(('bridge_result','Guarded choice key sent; waiting for the event screen to advance.'))
                except Exception as exc:
                    self.queue.put(('bridge_result',str(exc)))
                    self.queue.put(('delivery_failed',dict(nonce=p['nonce'],op=p['op'])))
            threading.Thread(target=commit,daemon=True).start()
        if p['nonce'] in self.sent_nonces:return
        self.sent_nonces.add(p['nonce'])
        self.bridge_stop=threading.Event()
        stop=self.bridge_stop
        expected=self.game_exe.get().strip()
        def worker():
            try:
                send_packet(p['op'],p['nonce'],lambda:self.bridge_allowed.is_set() and not stop.is_set(),expected_exe=expected,report=lambda message:self.queue.put(('bridge_result',message)),guard=p.get('guards',{}).get(str(self.my_id),0))
                self.queue.put(('bridge_result','Input sent. Waiting for acknowledgment from FTL; input alone is not confirmation.'))
            except Exception as exc:
                self.queue.put(('bridge_result',str(exc)))
                self.queue.put(('delivery_failed',dict(nonce=p['nonce'],op=p['op'])))
        threading.Thread(target=worker,daemon=True).start()

    def send_action(self,action,target=None):
        if not self.client or not self.client.running: return
        plan=self.travel.get('plan')
        try:
            self.client.send({'type':'travel','action':action,'target':target,'plan_id':plan['id'] if plan else None})
        except OSError as exc:
            self.status.set(str(exc))

    def propose(self):
        target=self.choices.get(self.destination.get())
        if target: self.send_action('propose',target)

    def refresh_travel(self):
        # Legacy planning protocol retained for compatibility; gameplay uses native map voting.
        pass

    def draw_maps(self):
        canvas = self.canvas
        canvas.delete('all')
        width = max(canvas.winfo_width(), 760)
        if not self.players:
            canvas.create_text(width/2,110,text='YOUR SHIP                         PARTNER SHIP',fill='#6edfff',font=('Segoe UI',13,'bold'))
            canvas.create_text(width/2,145,text='Connect both captains, then start your shared run.',fill='#9eb2c0',font=('Segoe UI',11))
        colors = ['#54d7ff', '#ffcb6b']
        for slot, player in enumerate(self.players[:2]):
            left = slot * width / 2
            color = colors[slot]
            canvas.create_text(left+14, 16, text=player.get('name', 'Captain'), anchor='w', fill=color, font=('Segoe UI', 11, 'bold'))
            s = player.get('snapshot')
            if not s:
                canvas.create_text(left+14, 50, text='Waiting for current game data…', anchor='w', fill='#aaaaaa')
                continue
            nodes = s['nodes']
            minx, maxx = min(n[0] for n in nodes), max(n[0] for n in nodes)
            miny, maxy = min(n[1] for n in nodes), max(n[1] for n in nodes)
            def point(n):
                return (left+25+(n[0]-minx)/max(1,maxx-minx)*(width/2-50), 55+(n[1]-miny)/max(1,maxy-miny)*140)
            for node in nodes:
                x,y=point(node)
                for edge in node[3]:
                    tx,ty=point(nodes[edge])
                    canvas.create_line(x,y,tx,ty,fill='#344860')
            for node in nodes:
                x,y=point(node)
                canvas.create_oval(x-3,y-3,x+3,y+3,fill='#b591ed' if node[2] else '#ced7e4',outline='')
                plan=self.travel.get('plan')
                if plan and node[:2]==plan['target'] and fingerprint(s)==plan['layout']:
                    canvas.create_rectangle(x-10,y-10,x+10,y+10,outline='#ff7272',width=2)
                if node[:2] == s['position']:
                    canvas.create_oval(x-8,y-8,x+8,y+8,outline=color,width=3)
            caption = f"Seed {s['seed']} | Sector {s['level']+1} | Beacon {s['position'][0]},{s['position'][1]}"
            canvas.create_text(left+14,218,text=caption,anchor='w',fill=color,font=('Segoe UI',9))
            canvas.create_text(left+14,235,text='Layout '+fingerprint(s)[:12]+' • includes unexplored paths',anchor='w',fill='#aaaaaa',font=('Segoe UI',9))

    def close(self):
        self.fast_local.stop()
        self.bridge_stop.set()
        self.bridge_allowed.clear()
        if self.watcher:
            self.watcher.stop()
        if self.client:
            self.client.close()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.root.destroy()


if __name__=='__main__':
    diag.start(Path(__file__).resolve().parent)
    window=tk.Tk()
    window.report_callback_exception=diag.tk_error
    Window(window)
    window.mainloop()
