"""Opt-in shared-enemy alpha. The relay orders shots; FTL on the host rolls damage.
No client-provided hull delta is ever accepted. Not a complete three-ship engine.
"""
import re,time,secrets
from collections import deque
TOKEN=re.compile(r'^[A-Za-z0-9_.-]{1,100}$')

def number(s,lo,hi):
    if not re.fullmatch(r'-?\d+(?:\.\d+)?',s):raise ValueError('number')
    n=float(s)
    if not lo<=n<=hi:raise ValueError('range')
    return n

def parse(line):
    if not isinstance(line,str) or len(line)>(60000 if line.startswith(('COMBAT|EFFECT|','COMBAT|FINISH|')) else 6000) or '\n' in line or '\r' in line:raise ValueError('line')
    p=line.split('|')
    if p[0]!='COMBAT':raise ValueError('prefix')
    kind=p[1]
    if kind=='ARM' and len(p)==6:
        number(p[2],0,4294967295)
        if not TOKEN.fullmatch(p[3]) or not TOKEN.fullmatch(p[4]):raise ValueError('signature')
        loadout=p[5].split(',') if p[5] else []
        if any(not TOKEN.fullmatch(x) for x in loadout) or len(loadout)>16:raise ValueError('loadout')
    elif kind in ('SHOT','SPAWN') and len(p) in (11,20):
        if not TOKEN.fullmatch(p[2]) or not TOKEN.fullmatch(p[4]):raise ValueError('identity')
        number(p[3],1,2147483647)
        for x in p[5:9]:number(x,-2048,4096)
        number(p[9],-720,720);number(p[10],0,1)
        if p[10] not in ('0','1'):raise ValueError('owner')
        if len(p)==20:
            if p[11] not in ('0','1') or p[12] not in ('0','1','2','3','4') or p[17] not in ('0','1') or p[19] not in ('0','1'):raise ValueError('weapon flags')
            number(p[13],-2048,4096);number(p[14],-2048,4096)
            length=number(p[15],0,2000)
            if int(length)!=length or (p[12]=='2' and length<1):raise ValueError('beam length')
            if not TOKEN.fullmatch(p[16]):raise ValueError('image')
            damage=p[18].split(',')
            if len(damage)!=13:raise ValueError('damage')
            for v in damage[:9]:
                n=number(v,-100,100)
                if n!=int(n):raise ValueError('damage integer')
            if any(v not in ('0','1') for v in damage[9:]):raise ValueError('damage flags')
            if p[17]=='1' and (p[12]!='4' or any(float(v)!=0 for v in damage[:9]) or damage[9:12]!=['0','0','0']):raise ValueError('fake damage')

    elif kind in ('SNAP','FINISH') and len(p) in (9,10,11,13):
        if not TOKEN.fullmatch(p[2]):raise ValueError('epoch')
        number(p[3],1,2147483647);hp=number(p[4],0,255);maximum=number(p[5],1,255)
        if hp>maximum or (kind=='FINISH' and hp!=0 and not (len(p)==13 and p[11]=='crew')):raise ValueError('hull')
        number(p[6],0,16);number(p[7],0,16)
        if len(p)>=10:
            ss=number(p[9],0,255)
            if ss!=int(ss):raise ValueError('super shield integer')
        if len(p)>=11:
            sm=number(p[10],0,255)
            if sm!=int(sm) or sm<ss:raise ValueError('super shield maximum')
        if len(p)==13:
            if kind!='FINISH' or p[11] not in ('hull','crew'):raise ValueError('boarding finish')
            from enemy_effects import validate
            validate(p[12])
            if not p[12].startswith('E28 '):raise ValueError('boarding roster header')
        rows=p[8].split(';') if p[8] else []
        if len(rows)>20:raise ValueError('systems')
        ids=set()
        for row in rows:
            fields=row.split(',')
            if len(fields)!=5:raise ValueError('system')
            typ=number(fields[0],0,20)
            if typ in ids:raise ValueError('duplicate system')
            ids.add(typ)
            hp=number(fields[1],0,16);maximum=number(fields[2],1,16)
            if hp>maximum:raise ValueError('health')
            number(fields[3],0,16);number(fields[4],0,100)
    elif kind=='EFFECT' and len(p)==5:
        if not TOKEN.fullmatch(p[2]):raise ValueError('epoch')
        number(p[3],1,2147483647)
        from enemy_effects import validate
        validate(p[4])
    elif kind in ('ACK','FINISH_ACK','POST_READY') and len(p)==4:
        if not TOKEN.fullmatch(p[2]):raise ValueError('epoch')
        number(p[3],1,2147483647)
    elif kind=='STOP' and len(p)==3:
        if not TOKEN.fullmatch(p[2]):raise ValueError('reason')
    else:raise ValueError('kind')
    return p

class CombatRoom:
    def __init__(self):
        self.post=None;self.completed=None;self.arms={};self.active=None;self.serial=0;self.last={};self.shots={};self.rate={};self.stale_since=None;self.hold_sent=-10
    def stop(self,send,reason):
        if self.active:
            for cid in self.active['members']:send(cid,'COMBAT|STOP|'+reason)
        self.active=None;self.arms={};self.last={};self.shots={};self.rate={};self.stale_since=None;self.hold_sent=-10
    def receive(self,cid,line,host,members,guards,send,now=None):
        now=time.monotonic() if now is None else now
        p=parse(line);kind=p[1]
        if cid not in members:return
        if kind=='STOP':
            # Setup can fail before an active epoch exists. Inform the other
            # captain immediately instead of leaving them to hit setup_timeout.
            if not self.active:
                for other in members:
                    if other!=cid:send(other,'COMBAT|STOP|'+p[2])
            self.post=None;self.completed=None;self.stop(send,p[2]);return
        if kind=='POST_READY':
            post=self.post
            if not post or p[2]!=post['epoch'] or p[3]!=post['seq'] or cid not in post['members']:return
            if set(members)!=set(post['members']) or any(guards.get(x)!=post['guard'] for x in post['members']):return
            post['ready'].add(cid)
            if post['ready']==set(post['members']):
                post['released']=True
                for x in post['members']:send(x,'COMBAT|POST_RELEASE|'+p[2]+'|'+p[3])
            return
        if kind=='FINISH' and self.completed and cid==self.completed[0] and line==self.completed[1]:
            send(cid,'COMBAT|FINISH_ACK|'+p[2]+'|'+p[3]);return
        if kind=='ARM':
            if int(p[2])!=guards.get(cid):return
            if self.post and not self.post['released']:
                # v0.28.16: an unreleased reward barrier only holds at its own
                # beacon. Once a captain arms at another beacon it is stale.
                if int(p[2])==self.post['guard']:return
                self.post=None
            self.arms[cid]=(now,p)
            a=self.active
            if a:
                if set(members)!=set(a['members']) or int(p[2])!=a['guard'] or p[3]!=a['enemy_signature'] or p[4]!=a['player_signatures'].get(cid):
                    self.stop(send,'encounter_changed');return
                send(cid,f"COMBAT|START|{a['epoch']}|{a['guard']}|{'H' if cid==host else 'G'}")
                return
            if len(members)!=2 or host not in members or any(x not in self.arms for x in members):return
            values=[self.arms[x] for x in members]
            if any(now-t>2 for t,_ in values):return
            if values[0][1][2:4]!=values[1][1][2:4]:
                for x in members:send(x,'COMBAT|WAIT|enemy_layout_mismatch')
                return
            self.serial+=1
            self.active=dict(epoch=secrets.token_hex(8),members=tuple(members),host=host,guard=int(p[2]),enemy_signature=p[3],player_signatures={x:self.arms[x][1][4] for x in members})
            for x in members:send(x,f"COMBAT|START|{self.active['epoch']}|{p[2]}|{'H' if x==host else 'G'}")
            return
        a=self.active
        if not a or p[2]!=a['epoch'] or any(guards.get(x)!=a['guard'] for x in a['members']):return
        if kind=='FINISH' and cid==a['host']:
            terminal=a.get('finish')
            if terminal and terminal!=line:self.stop(send,'completion_changed');return
            a['finish']=line
            for x in a['members']:
                if x!=cid:send(x,line)
            return
        if kind=='FINISH_ACK' and cid!=a['host'] and a.get('finish'):
            terminal=a['finish'];parts=terminal.split('|')
            if p[3]!=parts[3]:return
            self.completed=(a['host'],terminal)
            self.post=dict(epoch=p[2],seq=p[3],members=a['members'],guard=a['guard'],ready=set(),released=False)
            send(a['host'],line)
            # Normal completion is not a combat STOP/failure.
            self.active=None;self.arms={};self.last={};self.shots={};self.rate={};self.stale_since=None
            return
        if a.get('finish'):return
        if any(now-self.arms.get(x,(0,None))[0]>3 for x in a['members']):
            return
        if self.stale_since is not None:return
        if kind=='SHOT':
            if cid==host or p[10]!='0':return
            if len(p)==20 and p[11]!='1':return # self-targeting stays local
            if p[4] not in self.arms[cid][1][5].split(','):return
            seq=int(p[3])
            if seq in self.shots:
                if self.shots[seq]['line']!=line:self.stop(send,'shot_identity_changed');return
                if self.shots[seq]['ack']:send(cid,f'COMBAT|ACK|{a["epoch"]}|{seq}')
                elif now-self.shots[seq]['sent']>=.2:
                    send(host,line);self.shots[seq]['sent']=now
                return
            # bounded, in-order session IDs; never evict and replay an old projectile
            if seq<=self.last.get('shot',0):return
            if len(self.shots)>=4096:self.stop(send,'shot_limit');return
            q=self.rate.setdefault(cid,deque())
            while q and now-q[0]>1:q.popleft()
            if len(q)>=128:self.stop(send,'shot_rate');return
            q.append(now);self.last['shot']=seq;self.shots[seq]=dict(line=line,ack=False,sent=now)
            send(host,line)
        elif kind=='ACK' and cid==host:
            seq=int(p[3])
            if seq in self.shots:
                self.shots[seq]['ack']=True
                for x in members:
                    if x!=host:send(x,line)
        elif kind in ('SPAWN','SNAP','EFFECT') and cid==host:
            seq=int(p[3])
            if seq<=self.last.get(kind,0):return
            self.last[kind]=seq
            for x in members:
                if x!=host:send(x,line)
    def tick(self,members,guards,send,now=None):
        now=time.monotonic() if now is None else now
        a=self.active
        if not a:return
        if set(members)!=set(a['members']):self.stop(send,'peer_disconnected');return
        missing=[]
        for cid in a['members']:
            if cid in guards and guards[cid]!=a['guard']:self.stop(send,'beacon_changed_'+str(cid));return
            if cid not in guards or now-self.arms.get(cid,(0,None))[0]>3:missing.append(cid)
        if missing:
            if self.stale_since is None:self.stale_since=now
            if now-self.stale_since>10:self.stop(send,'peer_unavailable_after_hold');return
            if now-self.hold_sent>=.2:
                self.hold_sent=now
                for cid in a['members']:send(cid,'COMBAT|HOLD|'+a['epoch']+'|waiting_for_peer')
            return
        if self.stale_since is not None:
            self.stale_since=None
            for cid in a['members']:send(cid,'COMBAT|SYNC|'+a['epoch'])
