"""Two-captain pause barrier. No game clock is advanced by this relay."""
import secrets,time,re
TOKEN=re.compile(r'[a-zA-Z0-9_-]{1,40}\Z')
REASONS={'clear','event','map','menu','setup','combat','inspector','lobby','link'}
def integer(s,lo,hi):
    if not isinstance(s,str) or not re.fullmatch(r'-?\d+',s):raise ValueError('pause integer')
    n=int(s)
    if not lo<=n<=hi:raise ValueError('pause range')
    return n

def parse(line):
    if not isinstance(line,str) or len(line)>200 or '\n' in line or '\r' in line:raise ValueError('pause line')
    p=line.split('|')
    if len(p)<2 or p[0]!='PAUSE':raise ValueError('pause prefix')
    if p[1]=='REPORT' and len(p)==6:
        integer(p[2],-1,4294967295)
        if p[3] not in REASONS or not TOKEN.fullmatch(p[4]):raise ValueError('pause report')
        integer(p[5],0,2147483647)
    elif p[1] in ('HOLD','READY') and len(p)==5:
        if not TOKEN.fullmatch(p[2]):raise ValueError('pause token')
        integer(p[3],1,2147483647);integer(p[4],1,2147483647)
    else:raise ValueError('pause kind')
    return p

class PauseRoom:
    def __init__(self):
        self.token=secrets.token_hex(8);self.rev=1;self.running=False
        self.ready=set();self.reports={};self.seq={};self.members=();self.condition=None;self.reason='waiting_for_both';self.last_send=-10
    def hold(self,reason):
        self.rev+=1;self.running=False;self.ready.clear();self.reason=reason
    def condition_for(self,members,enabled,builds,now):
        ids=tuple(sorted(members))
        if len(ids)!=2:return ('waiting_for_both',ids)
        for cid in ids:
            if cid not in enabled:return ('bridge_disabled',cid)
            v=builds.get(cid,(0,0))
            if v[0]!=2816 or now-v[1]>5:return ('game_version_or_link',cid)
            r=self.reports.get(cid)
            if not r or now-r['seen']>1.5:return ('game_heartbeat_lost',cid)
            if r['guard']<0 or r['blocked']!='clear':return ('blocked_'+r['blocked'],cid)
        guards=tuple(self.reports[c]['guard'] for c in ids)
        if guards[0]!=guards[1]:return ('different_beacons',guards)
        return ('clear',guards[0])
    def update(self,members,enabled,builds,send,now=None,force=False):
        now=time.monotonic() if now is None else now
        ids=tuple(sorted(members));condition=self.condition_for(members,enabled,builds,now)
        # Every transition invalidates readiness, including block -> clear.
        if ids!=self.members or condition!=self.condition:
            self.members=ids;self.condition=condition;self.hold(condition[0] if condition[0]!='clear' else 'both_press_space');force=True
        if condition[0]=='clear' and not self.running and set(ids)==self.ready:
            if all(self.reports[c]['token']==self.token and self.reports[c]['rev']==self.rev for c in ids):
                self.running=True;self.reason='running';force=True
        if force or now-self.last_send>=.2:
            self.last_send=now
            for cid in ids:
                send(cid,f'PAUSE|STATE|{self.token}|{self.rev}|{"RUN" if self.running else "HOLD"}|{self.reason}|{len(self.ready)}|{int(cid in self.ready)}|{self.seq.get(cid,0)}')
    def receive(self,cid,line,members,enabled,builds,send,now=None):
        now=time.monotonic() if now is None else now;p=parse(line)
        if cid not in members:return
        if p[1]=='REPORT':
            self.reports[cid]=dict(guard=int(p[2]),blocked=p[3],token=p[4],rev=int(p[5]),seen=now)
        else:
            self.update(members,enabled,builds,send,now)
            if p[2]!=self.token:return
            seq=int(p[4])
            if seq<=self.seq.get(cid,0):return
            self.seq[cid]=seq
            if p[1]=='HOLD':
                if self.running or self.ready:self.hold('captain_paused')
            elif int(p[3])==self.rev and self.condition[0]=='clear' and not self.running:
                r=self.reports.get(cid)
                if r and r['token']==self.token and r['rev']==self.rev:self.ready.add(cid)
        # Heartbeats must not echo immediately: a rejected RUN can otherwise
        # generate REPORT -> RUN -> REPORT indefinitely. Requests get an ACK.
        self.update(members,enabled,builds,send,now,p[1]!='REPORT')
    def disconnected(self,cid):
        self.reports.pop(cid,None);self.seq.pop(cid,None);self.hold('peer_disconnected')
    def game_reconnected(self,cid):
        self.disconnected(cid)
