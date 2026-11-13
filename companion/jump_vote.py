"""Two matching native-map votes, prepare acknowledgments, then one commit.
A disconnected client cannot be made to jump atomically; partial commit stops
further votes and reports failure instead of retrying an already executed jump.
"""
import time
from travel import Travel
from ship_view import guard

def parse(line):
    if not isinstance(line,str) or len(line)>250:raise ValueError('jump line')
    p=line.split('|')
    sizes={'VOTE':6,'CLEAR':2,'READY':3,'ACK':3}
    if len(p)<2 or p[0]!='JUMP' or len(p)!=sizes.get(p[1]):raise ValueError('jump kind')
    for x in p[2:]:
        if not x.lstrip('-').isdigit() or abs(int(x))>4294967295:raise ValueError('jump integer')
    return p
class JumpRoom:
    def __init__(self):self.votes={};self.pending=None;self.serial=0
    def cancel(self,send,members,why):
        for cid in members:send(cid,'JUMP|CANCEL|'+why)
        self.votes={};self.pending=None
    def receive(self,cid,line,players,send,now=None):
        now=time.time() if now is None else now;p=parse(line);members=[v['id'] for v in players]
        if cid not in members:return
        if p[1]=='CLEAR':
            if self.pending and self.pending['phase']=='commit':return
            self.cancel(send,members,'map_closed_or_vote_cancelled');return
        if p[1]=='VOTE':
            if self.pending and self.pending['phase']=='commit':return
            s=Travel().eligible(players,now);g=guard(dict(seed=s['seed'],level=s['level'],x=s['position'][0],y=s['position'][1]))
            if int(p[2])!=g:raise ValueError('jump context')
            target=[int(p[4]),int(p[5])];t=Travel();t.propose(cid,cid,players,target,now)
            if self.pending:self.cancel(send,members,'vote_changed')
            self.votes[cid]=(int(p[3]),target,now,g)
            for peer in members:
                own=self.votes.get(peer);other=next((v for k,v in self.votes.items() if k!=peer),None)
                fmt=lambda v:','.join(map(str,v[1])) if v else 'waiting'
                send(peer,'JUMP|STATUS|You '+fmt(own)+' / Partner '+fmt(other))
            if len(self.votes)==2 and all(now-v[2]<15 and v[3]==g and v[1]==target for v in self.votes.values()):
                self.serial+=1;self.pending=dict(id=self.serial,phase='prepare',ready=set(),acks=set(),expires=now+3,guard=g,target=target,origin=s['position'],members=members)
                for peer in members:send(peer,f'JUMP|PREPARE|{self.serial}|{g}|{self.votes[peer][0]}')
        elif self.pending and int(p[2])==self.pending['id']:
            q=self.pending
            if now>q['expires']:self.cancel(send,members,'jump_confirmation_timeout');return
            if p[1]=='READY' and q['phase']=='prepare':
                Travel().eligible(players,now);q['ready'].add(cid)
                if q['ready']==set(members):
                    q['phase']='commit';q['expires']=now+20
                    for peer in members:send(peer,f'JUMP|COMMIT|{q["id"]}|{q["guard"]}|{self.votes[peer][0]}')
            elif p[1]=='ACK' and q['phase']=='commit':q['acks'].add(cid)
    def tick(self,players,send,now=None):
        now=time.time() if now is None else now;members=[p['id'] for p in players];q=self.pending
        if q:
            if members!=q['members'] or now>q['expires']:self.cancel(send,members,'jump_connection_or_timeout_check_both_positions');return
            if q['phase']=='commit':
                positions=[p.get('snapshot',{}).get('position') for p in players]
                if all(x==q['target'] for x in positions):self.cancel(send,members,'both_arrived');return
                if any(x not in [q['origin'],q['target']] for x in positions):self.cancel(send,members,'unexpected_destination');return
            else:
                try:Travel().eligible(players,now)
                except ValueError:self.cancel(send,members,'map_state_changed')
        elif self.votes and (len(members)!=2 or any(now-v[2]>15 for v in self.votes.values())):self.cancel(send,members,'vote_expired')
