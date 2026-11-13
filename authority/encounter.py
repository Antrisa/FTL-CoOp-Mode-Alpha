"""Shared encounter ownership and command bookkeeping, NOT an FTL combat simulator.

The trusted native host adapter must supply all ship states and execute intents.
No client may report hits/damage. Logical IDs deliberately differ from FTL's
hard-coded player/enemy indices; mapping them is a separate, unfinished adapter.
"""
from copy import deepcopy
from collections import OrderedDict
import math
import secrets

class Rejected(ValueError):pass

def integer(v,lo,hi):
    if type(v)is not int or not lo<=v<=hi:raise Rejected('integer outside bounds')
    return v

def number(v,lo,hi):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise Rejected('number outside bounds')
    return v

def fields(obj,required):
    if type(obj)is not dict or set(obj)!=set(required):raise Rejected('invalid fields')

def ship_state(s):
    fields(s,('hull','maximum','rooms','crew','weapons','shields'))
    maximum=integer(s['maximum'],1,1000);integer(s['hull'],0,maximum);integer(s['shields'],0,32)
    rooms=s['rooms'];crew=s['crew'];weapons=s['weapons']
    if type(rooms)is not list or not 1<=len(rooms)<=64:raise Rejected('rooms')
    for room in rooms:integer(room,0,255)
    if len(set(rooms))!=len(rooms):raise Rejected('duplicate rooms')
    if type(crew)is not list or len(crew)>64 or type(weapons)is not list or len(weapons)>32:raise Rejected('entity count')
    ids=set()
    for c in crew:
        fields(c,('id','room','x','y','health','maximum'))
        ident=integer(c['id'],0,65535)
        integer(c['room'],0,255)
        if ident in ids or c['room'] not in rooms:raise Rejected('crew identity/room')
        ids.add(ident);number(c['x'],-10000,10000);number(c['y'],-10000,10000)
        number(c['health'],0,number(c['maximum'],1,10000))
    ids=set()
    for w in weapons:
        fields(w,('id','charge','required','enabled'))
        ident=integer(w['id'],0,255)
        if ident in ids or type(w['enabled'])is not bool:raise Rejected('weapon')
        ids.add(ident);number(w['charge'],0,number(w['required'],0.001,10000))
    return deepcopy(s)

class Encounter:
    def __init__(self,host,guest,context,initial):
        if not isinstance(host,str) or not isinstance(guest,str) or host==guest or not host or not guest:raise Rejected('two distinct captains required')
        if type(context)is not tuple or len(context)!=4:raise Rejected('run context')
        for v in context:integer(v,-2**32,2**32)
        self.host=host;self.guest=guest;self.context=context
        self.id=secrets.token_hex(16)
        self.owners={'ally_a':host,'ally_b':guest}
        self.tick=0;self.state=self._state(initial);self.pending=OrderedDict();self.receipts=OrderedDict()
        self.last_seq={host:0,guest:0};self.closed=False;self.paused=False
        self.events=[];self.last_event=0

    def _state(self,state):
        fields(state,('ally_a','ally_b','enemy'))
        return {k:ship_state(v) for k,v in state.items()}

    def submit(self,actor,message):
        fields(message,('encounter','seq','ship','kind','args'))
        if self.closed or message['encounter']!=self.id:raise Rejected('encounter ended or mismatched')
        if actor not in self.last_seq:raise Rejected('not a participant')
        seq=integer(message['seq'],1,2**53-1);key=(actor,seq)
        if key in self.receipts:
            old=self.receipts[key]
            if old['message']!=message:raise Rejected('sequence reused with different command')
            return deepcopy(old['receipt'])
        if seq<=self.last_seq[actor]:raise Rejected('old sequence')
        if len(self.pending)>=128:raise Rejected('command queue full')
        ship=message['ship']
        if type(ship)is not str or self.owners.get(ship)!=actor:raise Rejected('not your ship')
        kind=message['kind'];args=message['args'];current=self.state[ship]
        if current['hull']==0:raise Rejected('ship destroyed')
        if kind in ('aim','fire'):
            fields(args,('weapon','target','room'))
            integer(args['weapon'],0,255);integer(args['room'],0,255)
            if args['target']!='enemy' or args['room'] not in self.state['enemy']['rooms']:raise Rejected('invalid enemy target')
            if self.state['enemy']['hull']==0:raise Rejected('enemy destroyed')
            weapon=next((w for w in current['weapons'] if w['id']==args['weapon']),None)
            if weapon is None:raise Rejected('unknown weapon')
            if kind=='fire':
                if self.paused:raise Rejected('encounter paused')
                if not weapon['enabled'] or weapon['charge']<weapon['required']:raise Rejected('weapon not ready')
                if any(c['ship']==ship and c['kind']=='fire' and c['args']['weapon']==args['weapon'] for c in self.pending.values()):raise Rejected('weapon command already pending')
        elif kind=='move':
            fields(args,('crew','room'))
            integer(args['crew'],0,65535);integer(args['room'],0,255)
            if args['room'] not in current['rooms'] or not any(c['id']==args['crew'] and c['health']>0 for c in current['crew']):raise Rejected('invalid crew move')
        elif kind=='power':
            fields(args,('system','level'))
            integer(args['system'],0,20);integer(args['level'],0,16)
            # Reactor capacity/system existence must be checked by native adapter.
        else:raise Rejected('unsupported intent; clients cannot submit damage')
        command=deepcopy(message);command['actor']=actor;command['accepted_tick']=self.tick
        self.pending[key]=command;self.last_seq[actor]=seq
        receipt={'status':'queued','seq':seq,'encounter':self.id}
        self.receipts[key]={'message':deepcopy(message),'receipt':receipt}
        self._trim();return deepcopy(receipt)

    def _trim(self):
        while len(self.receipts)>512:
            candidate=next((k for k in self.receipts if k not in self.pending),None)
            if candidate is None:break
            del self.receipts[candidate]

    def commands(self,actor):
        if actor!=self.host:raise Rejected('only native host adapter may drain commands')
        return deepcopy(list(self.pending.values()))

    def publish(self,actor,encounter,tick,state,completed=(),events=()):
        if actor!=self.host or encounter!=self.id or self.closed:raise Rejected('not authoritative host/current encounter')
        integer(tick,self.tick+1,2**53-1)
        clean=self._state(state)
        if type(completed) not in (tuple,list) or len(completed)>128 or type(events) not in (tuple,list) or len(events)>256:raise Rejected('batch bounds')
        result=[];keys=set()
        for c in completed:
            fields(c,('actor','seq','status'))
            if type(c['actor'])is not str:raise Rejected('completion actor')
            integer(c['seq'],1,2**53-1)
            key=(c['actor'],c['seq'])
            if key not in self.pending or key in keys or c['status'] not in ('executed','rejected'):raise Rejected('invalid completion')
            keys.add(key);result.append((key,c['status']))
        clean_events=[];last=self.last_event
        for e in events:
            fields(e,('id','kind','source','target'))
            integer(e['id'],last+1,2**53-1);last=e['id']
            if any(type(e[k])is not str for k in ('kind','source','target')):raise Rejected('event fields')
            if e['kind'] not in ('projectile','impact','miss','destroyed','escaped') or e['source'] not in clean or e['target'] not in clean:raise Rejected('invalid engine event')
            clean_events.append(deepcopy(e))
        # Commit only after the ENTIRE batch validates. This ledger never applies damage.
        self.state=clean;self.tick=tick;self.last_event=last
        self.events=(self.events+clean_events)[-256:]
        for key,status in result:
            del self.pending[key];self.receipts[key]['receipt']['status']=status
            self.receipts[key]['receipt']['tick']=tick
        self._trim()
        return self.snapshot()

    def pause(self,actor,paused):
        if actor!=self.host or type(paused)is not bool or self.closed:raise Rejected('invalid pause authority')
        self.paused=paused

    def end(self,actor):
        if actor!=self.host:raise Rejected('invalid end authority')
        self.closed=True
        for key in self.pending:self.receipts[key]['receipt']['status']='cancelled'
        self.pending.clear()

    def snapshot(self):
        return deepcopy(dict(encounter=self.id,context=self.context,tick=self.tick,ships=self.state,paused=self.paused,closed=self.closed,events=self.events))
