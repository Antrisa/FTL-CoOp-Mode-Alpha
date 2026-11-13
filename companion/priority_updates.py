"""Reliable FIFO control, replaceable snapshots. Never drop input/shot/ACK messages."""
from collections import deque, OrderedDict
import json
import queue
import threading
import time

def line_key(line):
    p=line.split('|',4)
    if len(p)>=4 and p[0]=='COMBAT' and p[1] in ('SNAP','EFFECT'):
        return ('combat',p[1],p[2])
    return None

def message_key(msg):
    if not isinstance(msg,dict):return None
    kind=msg.get('type')
    if kind in ('scene','scene_z','view_frame','ship_view','state','cursor'):
        return (kind,)
    if kind=='combat':return line_key(msg.get('line',''))
    return None

def wire_key(data):
    if data is None:return None
    try:return message_key(json.loads(data))
    except (ValueError,TypeError,UnicodeError):return None

def ui_key(item):
    kind,payload=item
    if kind in ('fast_scene','fast_frame','fast_ship'):return (kind,)
    if kind=='fast_combat':
        k=line_key(payload);return (kind,k) if k else None
    if kind=='network':
        k=message_key(payload);return (kind,k) if k else None
    return None

class UpdateQueue:
    def __init__(self,maxsize=0,key=lambda item:None):
        self.maxsize=maxsize;self.key=key;self.control=deque();self.latest=OrderedDict()
        self.cv=threading.Condition();self.replaced=0
    def put_nowait(self,item):
        key=self.key(item)
        with self.cv:
            if key is None:
                if self.maxsize and len(self.control)>=self.maxsize:raise queue.Full
                self.control.append(item)
            else:
                if key in self.latest:self.replaced+=1
                elif len(self.latest)>=32:
                    self.latest.popitem(last=False);self.replaced+=1
                self.latest[key]=item
            self.cv.notify()
    def put(self,item,block=True,timeout=None):self.put_nowait(item)
    def get(self,block=True,timeout=None):
        end=None if timeout is None else time.monotonic()+timeout
        with self.cv:
            while not self.control and not self.latest:
                if not block:raise queue.Empty
                remaining=None if end is None else end-time.monotonic()
                if remaining is not None and remaining<=0:raise queue.Empty
                self.cv.wait(remaining)
            if self.control:return self.control.popleft()
            return self.latest.popitem(last=False)[1]
    def get_nowait(self):return self.get(False)
    def qsize(self):
        with self.cv:return len(self.control)+len(self.latest)
    def clear(self):
        with self.cv:self.control.clear();self.latest.clear()
